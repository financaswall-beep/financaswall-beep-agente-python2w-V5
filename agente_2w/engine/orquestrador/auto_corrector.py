"""Auto-corrector determinístico para envelopes da IA.

Roda ANTES do validador. Corrige etapa_atual e ações quando a intenção
é clara mas o LLM errou a estrutura. Evita retries desnecessários.

Princípio: só corrige quando tem CERTEZA (sinais determinísticos).
Se não tem certeza, deixa passar pro validador normalmente.
"""
import logging

from agente_2w.enums.enums import EtapaFluxo
from agente_2w.engine.maquina_estados import transicao_permitida
from agente_2w.engine.pendencias import acoes_permitidas

logger = logging.getLogger(__name__)

# Ações que SÓ existem em oferta (nunca em busca/identificacao)
_ACOES_EXCLUSIVAS_OFERTA = frozenset({
    "apresentar_opcoes",
    "pedir_escolha_cliente",
    "confirmar_item",
    "finalizar_itens",
    "perguntar_tipo_entrega",
    "perguntar_forma_pagamento",
    "registrar_entrega",
    "registrar_pagamento",
})

# Ações que SÓ existem em confirmacao_item
_ACOES_EXCLUSIVAS_CONFIRMACAO = frozenset({
    "registrar_quantidade",
    "registrar_posicao",
    "adicionar_outro_item",
})


def auto_corrigir_envelope(envelope, etapa_atual_db: EtapaFluxo) -> bool:
    """Corrige envelope in-place se possível. Retorna True se houve correção."""
    corrigido = False

    corrigido |= _corrigir_salto_busca_confirmacao(envelope, etapa_atual_db)
    corrigido |= _corrigir_acao_etapa_errada(envelope, etapa_atual_db)
    corrigido |= _corrigir_salto_busca_entrega(envelope, etapa_atual_db)

    return corrigido


def _corrigir_salto_busca_confirmacao(envelope, etapa_atual_db: EtapaFluxo) -> bool:
    """C1: busca → confirmacao_item quando tem mudancas_itens:criar → corrige pra oferta."""
    if etapa_atual_db != EtapaFluxo.busca:
        return False
    if envelope.etapa_atual != EtapaFluxo.confirmacao_item:
        return False

    # Só corrige se tem intenção clara de criar item
    tem_criar = any(
        getattr(m, "acao", None) == "criar"
        for m in getattr(envelope, "mudancas_itens", [])
    )

    if not tem_criar:
        # Mesmo sem mudancas_itens, se tem ação de oferta → corrige
        acoes_set = set(envelope.acoes_sugeridas)
        if not acoes_set & _ACOES_EXCLUSIVAS_OFERTA:
            return False

    envelope.etapa_atual = EtapaFluxo.oferta
    logger.info(
        "Auto-corrector C1: busca -> confirmacao_item corrigido para busca -> oferta"
    )
    return True


def _corrigir_acao_etapa_errada(envelope, etapa_atual_db: EtapaFluxo) -> bool:
    """C2/C5: IA usa ação de outra etapa sem transicionar.

    Se a etapa proposta == etapa_atual_db (não transicionou) mas as ações
    pertencem a outra etapa acessível, corrige a etapa.
    """
    # Só atua se a IA NÃO tentou transicionar (ficou na mesma etapa)
    # OU se propôs etapa inválida
    acoes_set = set(envelope.acoes_sugeridas)
    if not acoes_set:
        return False

    permitidas_atual = set(acoes_permitidas(etapa_atual_db))
    permitidas_proposta = set(acoes_permitidas(envelope.etapa_atual))

    # Se todas as ações já são válidas na etapa proposta, nada a corrigir
    if acoes_set <= (permitidas_atual | permitidas_proposta):
        return False

    # Ações inválidas na etapa atual/proposta
    invalidas = acoes_set - permitidas_atual - permitidas_proposta

    if not invalidas:
        return False

    # Tentar inferir etapa correta a partir das ações inválidas
    # Prioridade: oferta (caso mais comum)
    if invalidas & _ACOES_EXCLUSIVAS_OFERTA:
        destino = EtapaFluxo.oferta
    elif invalidas & _ACOES_EXCLUSIVAS_CONFIRMACAO:
        destino = EtapaFluxo.confirmacao_item
    else:
        return False  # Não consegue inferir → deixa pro validador

    # Só corrige se a transição seria válida
    if not transicao_permitida(etapa_atual_db, destino):
        return False

    etapa_anterior = envelope.etapa_atual.value
    envelope.etapa_atual = destino
    logger.info(
        "Auto-corrector C2/C5: etapa corrigida de %s para %s "
        "(ações %s só válidas em %s)",
        etapa_anterior, destino.value, invalidas, destino.value,
    )
    return True


def _corrigir_salto_busca_entrega(envelope, etapa_atual_db: EtapaFluxo) -> bool:
    """C4: busca → entrega_pagamento (inválido) com mudancas_itens:criar → força oferta."""
    if etapa_atual_db != EtapaFluxo.busca:
        return False
    if envelope.etapa_atual != EtapaFluxo.entrega_pagamento:
        return False

    # Só corrige se tem item sendo criado (intenção clara de confirmar)
    tem_criar = any(
        getattr(m, "acao", None) == "criar"
        for m in getattr(envelope, "mudancas_itens", [])
    )
    if not tem_criar:
        return False

    envelope.etapa_atual = EtapaFluxo.oferta
    logger.info(
        "Auto-corrector C4: busca -> entrega_pagamento corrigido para busca -> oferta "
        "(tem mudancas_itens:criar)"
    )
    return True
