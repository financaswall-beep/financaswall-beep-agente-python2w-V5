"""Parser da resposta da IA — converte texto bruto em EnvelopeIA validado."""

import json
import re

from agente_2w.schemas.envelope_ia import EnvelopeIA
from agente_2w.schemas.contexto_executavel import ContextoExecutavel
from agente_2w.engine.validador_envelope import validar_envelope


class ParseError(Exception):
    """Erro ao fazer parse da resposta da IA."""

    def __init__(self, mensagem: str, resposta_bruta: str):
        self.mensagem = mensagem
        self.resposta_bruta = resposta_bruta
        super().__init__(mensagem)


def _extrair_json(texto: str) -> str:
    """Extrai o primeiro bloco JSON do texto, mesmo com markdown ao redor.

    Usa bracket counting (balanceamento de chaves) com rastreio de strings —
    `{` ou `}` dentro de string nao contam. Sem isso, JSON truncado no meio
    de uma string (ex: ...: "olha o } no texto ) era considerado fechado.
    """
    inicio = texto.find("{")
    if inicio == -1:
        return texto

    nivel = 0
    em_string = False
    escape = False
    for i in range(inicio, len(texto)):
        c = texto[i]
        if escape:
            escape = False
            continue
        if c == "\\" and em_string:
            escape = True
            continue
        if c == '"':
            em_string = not em_string
            continue
        if em_string:
            continue
        if c == "{":
            nivel += 1
        elif c == "}":
            nivel -= 1
            if nivel == 0:
                return texto[inicio : i + 1]

    # Se nao fechou (JSON truncado), retorna do inicio ate o fim
    return texto[inicio:]


def parse_resposta(
    resposta_bruta: str,
    contexto: ContextoExecutavel,
) -> tuple[EnvelopeIA, list[str]]:
    """Faz parse e validação da resposta da IA.

    Args:
        resposta_bruta: texto retornado pelo modelo (deve ser JSON do EnvelopeIA)
        contexto: contexto executável da sessão (para validação)

    Returns:
        Tupla (envelope, erros) onde erros é lista de strings com problemas.
        Se erros estiver vazio, o envelope é válido.

    Raises:
        ParseError: se não for possível parsear o JSON ou validar com Pydantic.
    """
    json_str = _extrair_json(resposta_bruta)

    try:
        dados = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ParseError(
            f"Resposta da IA não é JSON válido: {e}",
            resposta_bruta,
        )

    try:
        envelope = EnvelopeIA(**dados)
    except Exception as e:
        raise ParseError(
            f"JSON não corresponde ao schema EnvelopeIA: {e}",
            resposta_bruta,
        )

    # Guardrail: mensagem_cliente não pode ser JSON bruto (alucinação do modelo).
    # Quando acontece, o modelo colocou o envelope inteiro como valor do campo.
    # Tenta extrair o mensagem_cliente interno; se não conseguir, força retry.
    msg = envelope.mensagem_cliente or ""
    if msg.strip().startswith("{"):
        try:
            interno = json.loads(msg)
            texto_limpo = interno.get("mensagem_cliente", "")
            if texto_limpo and not texto_limpo.strip().startswith("{"):
                envelope.mensagem_cliente = texto_limpo
            else:
                raise ValueError("mensagem_cliente interna também é JSON")
        except Exception:
            raise ParseError(
                "mensagem_cliente contém JSON bruto em vez de texto ao cliente",
                resposta_bruta,
            )

    erros = validar_envelope(envelope, contexto)

    return envelope, erros
