"""Detector de loop: identifica quando o agente repete o mesmo comportamento.

Verifica se a sessao esta presa na mesma etapa com o cliente enviando
confirmacoes que nao surtem efeito. Quando detecta loop, forca transicao
ou escala para humano.
"""
import logging
import re
from uuid import UUID

from agente_2w.enums.enums import EtapaFluxo, Direcao
from agente_2w.db import mensagem_repo

logger = logging.getLogger(__name__)

# Turnos (pares entrada+saida) consecutivos na mesma etapa pra considerar loop
_LIMITE_TURNOS_LOOP = 3

# Keywords que indicam que o cliente esta tentando confirmar/avancar
_RE_CONFIRMACAO = re.compile(
    r"\b(?:sim|s|quero|pode ser|pode|ok|isso|esse|essa|bora|fecha|"
    r"manda|quero esse|pode mandar|vamos|beleza|blz|bom|boa|certo|"
    r"fechado|combinado|perfeito|tá|ta)\b",
    re.IGNORECASE,
)


def _contar_saidas_recentes(sessao_id: UUID, limite: int = 10) -> list[str]:
    """Retorna textos das ultimas mensagens de SAIDA (agente) da sessao."""
    try:
        msgs = mensagem_repo.listar_mensagens_por_sessao(sessao_id, limite=limite * 2)
        saidas = [
            m.conteudo_texto
            for m in msgs
            if m.direcao == Direcao.saida and m.conteudo_texto
        ]
        return saidas[-limite:]  # ultimas N
    except Exception:
        logger.exception("Falha ao buscar mensagens para detector de loop")
        return []


def _normalizar_para_comparacao(texto: str) -> str:
    """Remove numeros, UUIDs, precos para comparar conteudo semantico."""
    # Remove precos (R$xxx,xx ou R$ xxx)
    t = re.sub(r"R\$\s*[\d.,]+", "PRECO", texto)
    # Remove UUIDs
    t = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "UUID", t, flags=re.I)
    # Remove numeros soltos
    t = re.sub(r"\d+", "N", t)
    # Lowercase e strip
    return t.lower().strip()


def detectar_loop(
    sessao_id: UUID,
    etapa_atual: EtapaFluxo,
    etapa_pos_turno: EtapaFluxo,
    mensagem_cliente: str,
) -> str | None:
    """Detecta loop e retorna acao sugerida ou None.

    Retornos possiveis:
    - None: sem loop
    - "forcar_transicao": backend deve forcar avanco de etapa
    - "escalar": escalar para humano

    So roda quando etapa NAO mudou neste turno (possivel loop).
    """
    # Se a etapa mudou, nao e loop
    if etapa_pos_turno != etapa_atual:
        return None

    # Se o cliente nao esta tentando confirmar, nao e loop (pode ser conversa normal)
    if not _RE_CONFIRMACAO.search(mensagem_cliente):
        return None

    # Buscar ultimas saidas
    saidas = _contar_saidas_recentes(sessao_id, limite=_LIMITE_TURNOS_LOOP + 1)
    if len(saidas) < _LIMITE_TURNOS_LOOP:
        return None  # Poucas mensagens — ainda nao e loop

    # Comparar as ultimas N saidas normalizadas
    ultimas = [_normalizar_para_comparacao(s) for s in saidas[-_LIMITE_TURNOS_LOOP:]]
    # Se todas sao iguais (mesma estrutura), e loop
    if len(set(ultimas)) == 1:
        logger.warning(
            "Loop detectado: %d saidas identicas na etapa %s. "
            "Mensagem repetida: '%s'",
            _LIMITE_TURNOS_LOOP, etapa_atual.value, saidas[-1][:100],
        )
        return "escalar"

    # Se 2+ das ultimas N sao iguais E cliente confirmou, possivel loop
    from collections import Counter
    contagem = Counter(ultimas)
    mais_comum, freq = contagem.most_common(1)[0]
    if freq >= _LIMITE_TURNOS_LOOP - 1:
        logger.warning(
            "Loop provavel: %d/%d saidas similares na etapa %s",
            freq, _LIMITE_TURNOS_LOOP, etapa_atual.value,
        )
        # Se em busca/oferta com confirmacao → forcar transicao
        if etapa_atual in (EtapaFluxo.busca, EtapaFluxo.oferta):
            return "forcar_transicao"
        return "escalar"

    return None
