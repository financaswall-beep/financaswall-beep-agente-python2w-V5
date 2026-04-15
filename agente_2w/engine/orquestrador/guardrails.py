"""Guardrails aplicados ao envelope antes do processamento backend.

Um guardrail ajusta o envelope retornado pela IA quando ele contem combinacoes
contraditorias ou transicoes invalidas. A logica e conservadora: preserva a
acao mais forte (ex.: confirmar_item) e descarta a conflitante.
"""
import logging

from agente_2w.enums.enums import EtapaFluxo

logger = logging.getLogger(__name__)


def _aplicar_guardrail(envelope, etapa_atual, pedido_sessao_atual=None):
    """Guardrail: corrige acoes conflitantes no envelope antes do processamento.

    Regras:
    1. confirmar_item + adicionar_outro_item = contradicao → manter confirmar_item
    2. converter_em_pedido + cancelar_pedido = contradicao → manter cancelar_pedido
    3. finalizar_itens + adicionar_outro_item = contradicao → manter finalizar_itens
    4. rejeitar_item + confirmar_item = contradicao → manter rejeitar_item
    5. converter_em_pedido quando pedido ja existe = erro → remover
    """
    acoes = list(envelope.acoes_sugeridas)
    etapa = envelope.etapa_atual

    # Regra 1: confirmar vs adicionar
    if "confirmar_item" in acoes and "adicionar_outro_item" in acoes:
        acoes.remove("adicionar_outro_item")
        logger.info("Guardrail: adicionar_outro_item removido — conflito com confirmar_item")
        if etapa == EtapaFluxo.busca:
            etapa = etapa_atual
            logger.info(
                "Guardrail: etapa_atual revertida de busca para %s", etapa_atual.value
            )

    # Regra 2: converter vs cancelar
    if "converter_em_pedido" in acoes and "cancelar_pedido" in acoes:
        acoes.remove("converter_em_pedido")
        logger.info("Guardrail: converter_em_pedido removido — conflito com cancelar_pedido")

    # Regra 3: finalizar vs adicionar
    if "finalizar_itens" in acoes and "adicionar_outro_item" in acoes:
        acoes.remove("adicionar_outro_item")
        logger.info("Guardrail: adicionar_outro_item removido — conflito com finalizar_itens")
        if etapa == EtapaFluxo.busca:
            etapa = etapa_atual

    # Nota: rejeitar_item + confirmar_item no mesmo turno NAO e contradicao —
    # o cliente pode rejeitar um item e confirmar outro (itens diferentes).
    # Nao remover nenhum dos dois.

    # Regra 5: finalizar_itens sem nenhum mudancas_itens:criar neste turno
    # e mensagem contendo "anotado"/"registrado" → warning (a rede de seguranca
    # em _despachar_acoes cria os itens ausentes, mas o log ajuda a diagnosticar).
    if "finalizar_itens" in acoes:
        tem_criar = any(
            getattr(m, "acao", None) == "criar"
            for m in getattr(envelope, "mudancas_itens", [])
        )
        msg = getattr(envelope, "mensagem_cliente", "") or ""
        _palavras_confirmacao = ("anotado", "registrado", "confirmado", "os dois", "os três")
        menciona_confirmacao = any(p in msg.lower() for p in _palavras_confirmacao)
        if not tem_criar and menciona_confirmacao:
            logger.warning(
                "Guardrail alerta: finalizar_itens com mensagem de confirmacao "
                "mas sem mudancas_itens:criar — safety net vai compensar"
            )

    # Regra 5: converter_em_pedido quando pedido ja existe nesta sessao
    if pedido_sessao_atual and "converter_em_pedido" in acoes:
        acoes.remove("converter_em_pedido")
        logger.warning(
            "Guardrail: converter_em_pedido removido — pedido #%s ja existe nesta sessao",
            getattr(pedido_sessao_atual, "numero_pedido", "?"),
        )

    envelope.acoes_sugeridas = acoes
    envelope.etapa_atual = etapa
    return envelope


# --- C9: detectar "nao temos" quando tools retornaram resultados ---

import re

_RE_NEGACAO = re.compile(
    r"(?:n[aã]o temos|n[aã]o encontrei|n[aã]o achei|infelizmente n[aã]o|"
    r"n[aã]o temos dispon[ií]vel|n[aã]o tem em estoque|"
    r"n[aã]o tive resultado|sem resultado|nenhum pneu encontrado)",
    re.IGNORECASE,
)


def detectar_falso_negativo(envelope, pneus_encontrados: list[dict]) -> bool:
    """Retorna True se a IA disse 'nao temos' mas tools retornaram pneus.

    Nao corrige (mensagem ja foi gerada). Loga WARNING para diagnostico
    e marca no envelope para que o retry corrija na proxima tentativa.
    """
    if not pneus_encontrados:
        return False

    msg = getattr(envelope, "mensagem_cliente", "") or ""
    if not _RE_NEGACAO.search(msg):
        return False

    # Contar pneus unicos com estoque
    pneus_unicos = {str(p["pneu_id"]) for p in pneus_encontrados if p.get("pneu_id")}
    if not pneus_unicos:
        return False

    logger.warning(
        "C9 FALSO NEGATIVO: IA disse '%s' mas tools retornaram %d pneu(s). "
        "IDs: %s. Mensagem completa: '%s'",
        _RE_NEGACAO.search(msg).group(),
        len(pneus_unicos),
        list(pneus_unicos)[:3],
        msg[:200],
    )
    return True


def tentar_busca_fallback_dimensoes(medida_hint: str | None) -> list[dict]:
    """C9 fallback: busca server-side por largura/perfil/aro.

    Chamada quando a IA disse "não temos" e pneus_encontrados está vazio.
    Se houver uma medida parseável, tenta busca exata por dimensões como
    última rede de segurança.

    Retorna lista de dicts de pneus (pode ser vazia).
    """
    if not medida_hint:
        return []

    # Imports lazy para evitar circular
    from agente_2w.tools.busca_catalogo import _parsear_medida
    from agente_2w.db import catalogo_repo

    dim = _parsear_medida(str(medida_hint))
    if not dim:
        return []

    resultados = catalogo_repo.buscar_pneus_por_dimensoes(**dim)
    if resultados:
        logger.warning(
            "C9 FALLBACK DIMENSOES: busca por %s encontrou %d pneu(s) para '%s'",
            dim, len(resultados), medida_hint,
        )
    return resultados


def _montar_mensagem_fallback(pneus: list[dict]) -> str:
    """Monta mensagem de apresentação dos pneus encontrados pelo C9 fallback."""
    if len(pneus) == 1:
        p = pneus[0]
        marca = p.get("marca", "")
        modelo = p.get("modelo", "")
        preco = p.get("preco_venda")
        nome = f"{marca} {modelo}".strip()
        if preco:
            return f"Temos o {nome} por R${preco:.2f}!"
        return f"Temos o {nome}!"

    linhas = ["Temos essas opções:"]
    for p in pneus:
        marca = p.get("marca", "")
        modelo = p.get("modelo", "")
        preco = p.get("preco_venda")
        nome = f"{marca} {modelo}".strip()
        if preco:
            linhas.append(f"- {nome} por R${preco:.2f}")
        else:
            linhas.append(f"- {nome}")
    return "\n".join(linhas)
