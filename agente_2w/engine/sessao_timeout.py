"""Logica de timeout de sessao.

Regras de negocio:
- Sessao bloqueada por erro tecnico ha mais de TIMEOUT_BLOQUEADA_HORAS → desbloquear
- Sessao pos-pedido inativa ha mais de TIMEOUT_POS_PEDIDO_HORAS → expirada_pos_pedido
- Sessao inativa ha mais de TIMEOUT_SESSAO_DIAS com contexto valioso → expirada_com_contexto
- Sessao inativa ha mais de TIMEOUT_SESSAO_DIAS sem contexto → expirada_sem_contexto

Etapas com contexto valioso: oferta, confirmacao_item, entrega_pagamento, fechamento.
Cliente estava no meio de uma escolha — vale preservar o historico no cadastro.

Etapas sem contexto relevante: identificacao, busca.
Pouco contexto acumulado — pode recomecar silenciosamente.
"""

from datetime import datetime, timezone, timedelta
from enum import Enum

from agente_2w.schemas.sessao_chat import SessaoChat
from agente_2w.enums.enums import EtapaFluxo, StatusSessao

# --- Configuracao de timeouts ---

# Dias sem interacao para considerar sessao expirada
TIMEOUT_SESSAO_DIAS: int = 7

# Horas para desbloquear sessao travada por erro tecnico
TIMEOUT_BLOQUEADA_HORAS: int = 2

# Horas para manter sessao aberta apos pedido criado.
# Permite o cliente consultar status, alterar endereco etc.
TIMEOUT_POS_PEDIDO_HORAS: int = 24

# Etapas com contexto acumulado suficiente para valer registrar a situacao
_ETAPAS_COM_CONTEXTO: frozenset[EtapaFluxo] = frozenset({
    EtapaFluxo.oferta,
    EtapaFluxo.confirmacao_item,
    EtapaFluxo.entrega_pagamento,
    EtapaFluxo.fechamento,
})


class SituacaoSessao(str, Enum):
    ok = "ok"
    # Sessao bloqueada ha mais de TIMEOUT_BLOQUEADA_HORAS — desbloquear
    bloqueada_antiga = "bloqueada_antiga"
    # Inativa ha mais de TIMEOUT_SESSAO_DIAS com etapa com contexto
    expirada_com_contexto = "expirada_com_contexto"
    # Inativa ha mais de TIMEOUT_SESSAO_DIAS em etapa inicial (identificacao/busca)
    expirada_sem_contexto = "expirada_sem_contexto"
    # Inativa ha mais de TIMEOUT_POS_PEDIDO_HORAS apos pedido criado (fechamento)
    expirada_pos_pedido = "expirada_pos_pedido"


def avaliar_sessao(sessao: SessaoChat, tem_pedido: bool = False) -> SituacaoSessao:
    """Avalia se a sessao esta em estado normal ou precisa de tratamento.

    Nao faz nenhuma escrita no banco — apenas classifica.
    Toda a logica de correcao fica no orquestrador (_resolver_timeout).

    Args:
        sessao: sessao a avaliar.
        tem_pedido: True se a sessao ja possui um pedido criado.
    """
    # Sessao ja fechada nao deve chegar aqui, mas por seguranca retorna ok
    if sessao.status_sessao == StatusSessao.fechada:
        return SituacaoSessao.ok

    agora = datetime.now(timezone.utc)
    ultima = sessao.ultima_interacao_em

    # Garantir que ultima_interacao_em e timezone-aware
    if ultima.tzinfo is None:
        ultima = ultima.replace(tzinfo=timezone.utc)

    tempo_inativo = agora - ultima

    # Sessao bloqueada: verificar se e bloqueio tecnico antigo
    if sessao.status_sessao == StatusSessao.bloqueada:
        if tempo_inativo > timedelta(hours=TIMEOUT_BLOQUEADA_HORAS):
            return SituacaoSessao.bloqueada_antiga
        # Bloqueio recente — respeitar, nao interferir
        return SituacaoSessao.ok

    # Pos-pedido: sessao em fechamento com pedido criado — timeout curto de 48h
    if tem_pedido and sessao.etapa_atual == EtapaFluxo.fechamento:
        if tempo_inativo > timedelta(hours=TIMEOUT_POS_PEDIDO_HORAS):
            return SituacaoSessao.expirada_pos_pedido
        return SituacaoSessao.ok

    # Sessao ativa ou aguardando_cliente: verificar inatividade
    if tempo_inativo > timedelta(days=TIMEOUT_SESSAO_DIAS):
        if sessao.etapa_atual in _ETAPAS_COM_CONTEXTO:
            return SituacaoSessao.expirada_com_contexto
        return SituacaoSessao.expirada_sem_contexto

    return SituacaoSessao.ok
