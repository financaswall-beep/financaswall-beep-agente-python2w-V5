"""JSON Schema estrito para Structured Outputs do EnvelopeIA.

Garante que o modelo nunca devolva tipos errados (ex.: string em
bloqueios_identificados). Todos os campos ficam em "required" — opcionais
usam ["type", "null"] para compatibilidade com strict mode do OpenAI.

Schema dinâmico (build_envelope_schema):
  Gera schema com enum restrito por etapa para etapa_atual e acoes_sugeridas.
  Impede na geração que o mini retorne etapa ou ação inválida para o contexto
  atual — elimina retries desnecessários com flagship.
"""

# Transições válidas por etapa (espelho de maquina_estados.py — mantido aqui
# para não importar engine em ia/, evitando dependência circular)
_TRANSICOES: dict[str, list[str]] = {
    "identificacao":    ["identificacao", "busca"],
    "busca":            ["busca", "oferta", "identificacao"],
    "oferta":           ["oferta", "confirmacao_item", "entrega_pagamento", "busca"],
    "confirmacao_item": ["confirmacao_item", "entrega_pagamento", "oferta", "busca"],
    "entrega_pagamento": ["entrega_pagamento", "fechamento", "confirmacao_item", "busca"],
    "fechamento":       ["fechamento", "oferta", "busca"],
}

# Ações válidas por etapa (espelho de pendencias.py)
_ACOES: dict[str, list[str]] = {
    "identificacao": [
        "pedir_clarificacao_moto", "pedir_clarificacao_medida", "pedir_clarificacao_posicao",
        "buscar_por_moto", "buscar_por_medida", "registrar_fato_observado",
        "registrar_opcoes_encontradas", "responder_incerteza_segura",
    ],
    "busca": [
        "buscar_por_moto", "buscar_por_medida", "buscar_medida_proxima",
        "pedir_clarificacao_moto", "pedir_clarificacao_medida",
        "registrar_fato_observado", "registrar_opcoes_encontradas", "responder_incerteza_segura",
    ],
    "oferta": [
        "apresentar_opcoes", "explicar_falta", "pedir_escolha_cliente",
        "confirmar_item", "finalizar_itens", "perguntar_tipo_entrega",
        "perguntar_forma_pagamento", "registrar_entrega", "registrar_pagamento",
        "registrar_fato_observado", "responder_incerteza_segura",
    ],
    "confirmacao_item": [
        "confirmar_item", "registrar_quantidade", "registrar_posicao",
        "rejeitar_item", "adicionar_outro_item", "finalizar_itens",
        "registrar_fato_observado", "responder_incerteza_segura",
    ],
    "entrega_pagamento": [
        "perguntar_tipo_entrega", "perguntar_endereco", "perguntar_forma_pagamento",
        "registrar_entrega", "registrar_pagamento", "adicionar_outro_item",
        "registrar_fato_observado", "responder_incerteza_segura",
    ],
    "fechamento": [
        "revisar_pedido", "converter_em_pedido", "cancelar_pedido",
        "buscar_por_moto", "buscar_por_medida", "explicar_falta",
        "rejeitar_item", "registrar_fato_observado", "responder_incerteza_segura",
    ],
}

# Cache: 6 etapas × 1 schema cada
_SCHEMAS_POR_ETAPA: dict[str, dict] = {}


def _build_schema_base() -> dict:
    """Retorna a parte do schema que não muda por etapa."""
    return {
        "type": "object",
        "properties": {
            "mensagem_cliente": {"type": "string"},
            # etapa_atual e acoes_sugeridas são injetados por build_envelope_schema
            "intencao_atual": {"type": "string"},
            "pendencias":     {"type": "array", "items": {"type": "string"}},
            "confianca":      {"type": "string", "enum": ["alta", "media", "baixa"]},
            "fatos_observados": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "chave":            {"type": "string"},
                        "valor":            {"type": "string"},
                        "mensagem_chat_id": {"type": ["string", "null"]},
                    },
                    "required": ["chave", "valor", "mensagem_chat_id"],
                    "additionalProperties": False,
                },
            },
            "fatos_inferidos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "chave":         {"type": "string"},
                        "valor":         {"type": "string"},
                        "justificativa": {"type": "string"},
                    },
                    "required": ["chave", "valor", "justificativa"],
                    "additionalProperties": False,
                },
            },
            "mudancas_contexto": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "chave":      {"type": "string"},
                        "valor_novo": {"type": "string"},
                        "motivo":     {"type": "string"},
                    },
                    "required": ["chave", "valor_novo", "motivo"],
                    "additionalProperties": False,
                },
            },
            "mudancas_itens": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item_provisorio_id": {"type": ["string", "null"]},
                        "acao": {
                            "type": "string",
                            "enum": ["criar", "confirmar", "atualizar", "cancelar", "rejeitar"],
                        },
                        "dados": {
                            "anyOf": [
                                {
                                    "type": "object",
                                    "properties": {
                                        "status_item":    {"type": ["string", "null"]},
                                        "pneu_id":        {"type": ["string", "null"]},
                                        "quantidade":     {"type": ["integer", "null"]},
                                        "preco_unitario": {"type": ["number", "null"]},
                                        "posicao":        {"type": ["string", "null"]},
                                        "observacao":     {"type": ["string", "null"]},
                                    },
                                    "required": [
                                        "status_item", "pneu_id", "quantidade",
                                        "preco_unitario", "posicao", "observacao",
                                    ],
                                    "additionalProperties": False,
                                },
                                {"type": "null"},
                            ]
                        },
                    },
                    "required": ["item_provisorio_id", "acao", "dados"],
                    "additionalProperties": False,
                },
            },
            "bloqueios_identificados": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "codigo_motivo":     {"type": "string"},
                        "mensagem_motivo":   {"type": "string"},
                        "campo_relacionado": {"type": ["string", "null"]},
                    },
                    "required": ["codigo_motivo", "mensagem_motivo", "campo_relacionado"],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "mensagem_cliente", "etapa_atual", "intencao_atual",
            "acoes_sugeridas", "pendencias", "confianca",
            "fatos_observados", "fatos_inferidos", "mudancas_contexto",
            "mudancas_itens", "bloqueios_identificados",
        ],
        "additionalProperties": False,
    }


def build_envelope_schema(etapa_atual: str) -> dict:
    """Retorna schema com etapa_atual e acoes_sugeridas restritos à etapa.

    Ex: etapa_atual="identificacao" →
      etapa_atual.enum = ["identificacao", "busca"]
      acoes_sugeridas.items.enum = [ações de identificacao + busca]

    O modelo não consegue retornar valor fora do enum mesmo que queira.
    Cache por etapa — gerado uma vez por processo.
    """
    if etapa_atual in _SCHEMAS_POR_ETAPA:
        return _SCHEMAS_POR_ETAPA[etapa_atual]

    etapas_validas = _TRANSICOES.get(etapa_atual, [etapa_atual])

    # Ações: union das ações de todas as etapas alcançáveis neste turno
    acoes_set: list[str] = []
    seen: set[str] = set()
    for etapa in etapas_validas:
        for acao in _ACOES.get(etapa, []):
            if acao not in seen:
                acoes_set.append(acao)
                seen.add(acao)

    schema = _build_schema_base()
    schema["properties"]["etapa_atual"] = {
        "type": "string",
        "enum": etapas_validas,
    }
    schema["properties"]["acoes_sugeridas"] = {
        "type": "array",
        "items": {"type": "string", "enum": acoes_set},
    }

    _SCHEMAS_POR_ETAPA[etapa_atual] = schema
    return schema


ENVELOPE_IA_SCHEMA = {
    "type": "object",
    "properties": {
        "mensagem_cliente": {"type": "string"},
        "etapa_atual": {
            "type": "string",
            "enum": [
                "identificacao", "busca", "oferta", "confirmacao_item",
                "entrega_pagamento", "fechamento",
            ],
        },
        "intencao_atual": {"type": "string"},
        "acoes_sugeridas": {"type": "array", "items": {"type": "string"}},
        "pendencias":      {"type": "array", "items": {"type": "string"}},
        "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
        "fatos_observados": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chave":           {"type": "string"},
                    "valor":           {"type": "string"},
                    "mensagem_chat_id": {"type": ["string", "null"]},
                },
                "required": ["chave", "valor", "mensagem_chat_id"],
                "additionalProperties": False,
            },
        },
        "fatos_inferidos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chave":        {"type": "string"},
                    "valor":        {"type": "string"},
                    "justificativa": {"type": "string"},
                },
                "required": ["chave", "valor", "justificativa"],
                "additionalProperties": False,
            },
        },
        "mudancas_contexto": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chave":     {"type": "string"},
                    "valor_novo": {"type": "string"},
                    "motivo":    {"type": "string"},
                },
                "required": ["chave", "valor_novo", "motivo"],
                "additionalProperties": False,
            },
        },
        "mudancas_itens": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_provisorio_id": {"type": ["string", "null"]},
                    "acao":              {"type": "string", "enum": ["criar", "confirmar", "atualizar", "cancelar", "rejeitar"]},
                    "dados": {
                        "anyOf": [
                            {
                                "type": "object",
                                "properties": {
                                    "status_item":    {"type": ["string", "null"]},
                                    "pneu_id":        {"type": ["string", "null"]},
                                    "quantidade":     {"type": ["integer", "null"]},
                                    "preco_unitario": {"type": ["number", "null"]},
                                    "posicao":        {"type": ["string", "null"]},
                                    "observacao":     {"type": ["string", "null"]},
                                },
                                "required": [
                                    "status_item", "pneu_id", "quantidade",
                                    "preco_unitario", "posicao", "observacao",
                                ],
                                "additionalProperties": False,
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["item_provisorio_id", "acao", "dados"],
                "additionalProperties": False,
            },
        },
        "bloqueios_identificados": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "codigo_motivo":    {"type": "string"},
                    "mensagem_motivo":  {"type": "string"},
                    "campo_relacionado": {"type": ["string", "null"]},
                },
                "required": ["codigo_motivo", "mensagem_motivo", "campo_relacionado"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "mensagem_cliente", "etapa_atual", "intencao_atual",
        "acoes_sugeridas", "pendencias", "confianca",
        "fatos_observados", "fatos_inferidos", "mudancas_contexto",
        "mudancas_itens", "bloqueios_identificados",
    ],
    "additionalProperties": False,
}
