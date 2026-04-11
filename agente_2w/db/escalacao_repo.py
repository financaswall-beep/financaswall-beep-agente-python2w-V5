"""CRUD para tabela escalacao + classificador de prioridade."""

import logging
from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from agente_2w.db.client import supabase
from agente_2w.schemas.escalacao import Escalacao, EscalacaoCreate

logger = logging.getLogger(__name__)

_TABELA = "escalacao"


def criar_escalacao(dados: EscalacaoCreate) -> Escalacao:
    resultado = (
        supabase.table(_TABELA)
        .insert(dados.model_dump(mode="json"))
        .execute()
    )
    logger.info("Escalacao criada: %s (motivo=%s)", resultado.data[0]["id"], dados.motivo)
    return Escalacao(**resultado.data[0])


def buscar_escalacao_ativa(sessao_chat_id: UUID) -> Optional[Escalacao]:
    resultado = (
        supabase.table(_TABELA)
        .select("*")
        .eq("sessao_chat_id", str(sessao_chat_id))
        .not_.in_("status", ["resolvida", "devolvida_bot"])
        .order("criado_em", desc=True)
        .limit(1)
        .maybe_single()
        .execute()
    )
    if resultado is None or resultado.data is None:
        return None
    return Escalacao(**resultado.data)


def buscar_escalacao_ativa_por_conv(chatwoot_conv_id: int) -> Optional[Escalacao]:
    resultado = (
        supabase.table(_TABELA)
        .select("*")
        .eq("chatwoot_conv_id", chatwoot_conv_id)
        .not_.in_("status", ["resolvida", "devolvida_bot"])
        .order("criado_em", desc=True)
        .limit(1)
        .maybe_single()
        .execute()
    )
    if resultado is None or resultado.data is None:
        return None
    return Escalacao(**resultado.data)


def resolver_escalacao(
    escalacao_id: UUID,
    status: str,
    notas: Optional[str] = None,
) -> Escalacao:
    payload = {
        "status": status,
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
    }
    if notas:
        payload["notas"] = notas
    resultado = (
        supabase.table(_TABELA)
        .update(payload)
        .eq("id", str(escalacao_id))
        .execute()
    )
    logger.info("Escalacao %s -> %s", escalacao_id, status)
    return Escalacao(**resultado.data[0])


def classificar_prioridade(
    motivo: str,
    cliente_segmento: Optional[str] = None,
    cliente_total_pedidos: int = 0,
    valor_pedido: Optional[Decimal | float] = None,
) -> str:
    """Classifica prioridade da escalacao. Codigo puro, sem IA."""
    URGENT = {"cliente_atacado", "emergencia_pneu"}
    if motivo in URGENT or cliente_segmento == "vip" or (valor_pedido and float(valor_pedido) > 800):
        return "urgent"
    HIGH = {"frete_nao_coberto", "cliente_pediu_humano", "estoque_zerado"}
    if motivo in HIGH or cliente_total_pedidos >= 2:
        return "high"
    return "medium"
