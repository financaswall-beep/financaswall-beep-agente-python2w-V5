"""Sincronizacao com Chatwoot — atualiza contato, labels e notas em tempo real.

Todas as funcoes sao fail-safe: se o Chatwoot estiver fora do ar, com token
invalido ou nao configurado, retornam silenciosamente sem lancar excecao.
O agente nunca quebra por causa do Chatwoot.

Uso:
    from agente_2w import chatwoot_sync

    chatwoot_sync.sincronizar_etapa(conv_id, "oferta")
    chatwoot_sync.sincronizar_custom_attributes(contact_id, cliente)
    chatwoot_sync.sincronizar_pedido_criado(conv_id, 42, Decimal("950.00"))
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx

from agente_2w.config import CHATWOOT_API_TOKEN, CHATWOOT_ACCOUNT_ID, CHATWOOT_BASE_URL, CHATWOOT_KANBAN_BOARD_ID

if TYPE_CHECKING:
    from agente_2w.schemas.cliente import Cliente

logger = logging.getLogger(__name__)

# Mapeamento etapa do agente -> label no Chatwoot
_LABEL_POR_ETAPA: dict[str, str] = {
    "identificacao": "identificacao",
    "busca": "buscando",
    "oferta": "oferta_enviada",
    "confirmacao_item": "confirmando_item",
    "entrega_pagamento": "dados_entrega",
    "fechamento": "em_fechamento",
}

# Mapeamento etapa -> board_step_id do Kanban (Pipeline de Vendas, board_id=3)
# IDs das colunas: 21=Novo Lead, 22=Qualificando, 23=Proposta Enviada,
#                  24=Negociação, 25=Oportunidade Perdida, 26=Oportunidade Ganha
_KANBAN_STEP_POR_ETAPA: dict[str, int] = {
    "identificacao": 21,   # Novo Lead
    "busca": 22,           # Qualificando
    "oferta": 23,          # Proposta Enviada
    "confirmacao_item": 24,    # Negociação
    "entrega_pagamento": 24,   # Negociação
    "fechamento": 24,          # Negociação
}
_KANBAN_STEP_PEDIDO_CRIADO = 26  # Oportunidade Ganha
_KANBAN_STEP_CANCELADO = 25      # Oportunidade Perdida

# Descricao legivel para cada etapa (preenche description da task Kanban)
_DESCRICAO_ETAPA: dict[str, str] = {
    "identificacao": "Identificação",
    "busca": "Qualificando",
    "oferta": "Proposta Enviada",
    "confirmacao_item": "Negociação",
    "entrega_pagamento": "Negociação — dados de entrega",
    "fechamento": "Fechamento",
}

# Cliente HTTP reutilizavel (singleton lazy)
_http: httpx.Client | None = None


def _habilitado() -> bool:
    """Retorna True apenas se BASE_URL e TOKEN estao configurados."""
    return bool(CHATWOOT_BASE_URL and CHATWOOT_API_TOKEN)


def _client() -> httpx.Client:
    global _http
    if _http is None:
        _http = httpx.Client(timeout=8.0)
    return _http


def _headers() -> dict[str, str]:
    return {"api_access_token": CHATWOOT_API_TOKEN, "Content-Type": "application/json"}


def _base() -> str:
    return f"{CHATWOOT_BASE_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}"


# ---------------------------------------------------------------------------
# Funcoes publicas
# ---------------------------------------------------------------------------

def atualizar_contato(contact_id: int, dados: dict) -> None:
    """Atualiza campos do contato no Chatwoot (nome, custom_attributes, etc.)."""
    if not _habilitado() or not contact_id:
        return
    try:
        url = f"{_base()}/contacts/{contact_id}"
        resp = _client().patch(url, json=dados, headers=_headers())
        resp.raise_for_status()
        logger.debug("Contato %s atualizado no Chatwoot", contact_id)
    except Exception:
        logger.warning("Falha ao atualizar contato %s no Chatwoot", contact_id, exc_info=True)


def adicionar_label(conv_id: int, label: str) -> None:
    """Adiciona uma label a conversa sem remover as existentes."""
    if not _habilitado() or not conv_id:
        return
    try:
        url = f"{_base()}/conversations/{conv_id}/labels"
        # GET labels atuais para nao sobrescrever
        resp = _client().get(url, headers=_headers())
        resp.raise_for_status()
        labels_atuais: list[str] = resp.json().get("payload", [])
        if label in labels_atuais:
            return  # ja existe, nada a fazer
        labels_atuais.append(label)
        _client().post(url, json={"labels": labels_atuais}, headers=_headers()).raise_for_status()
        logger.info("Label '%s' adicionada na conv %d", label, conv_id)
    except Exception:
        logger.warning("Falha ao adicionar label '%s' na conv %d", label, conv_id, exc_info=True)


def nota_privada(conv_id: int, texto: str) -> None:
    """Cria uma nota privada (nao visivel ao cliente) na conversa."""
    if not _habilitado() or not conv_id:
        return
    try:
        url = f"{_base()}/conversations/{conv_id}/messages"
        payload = {"content": texto, "message_type": "outgoing", "private": True}
        resp = _client().post(url, json=payload, headers=_headers())
        resp.raise_for_status()
        logger.debug("Nota privada criada na conv %d", conv_id)
    except Exception:
        logger.warning("Falha ao criar nota privada na conv %d", conv_id, exc_info=True)


def resolver_conversa(conv_id: int) -> None:
    """Marca a conversa como resolvida no Chatwoot."""
    if not _habilitado() or not conv_id:
        return
    try:
        url = f"{_base()}/conversations/{conv_id}/toggle_status"
        resp = _client().post(url, json={"status": "resolved"}, headers=_headers())
        resp.raise_for_status()
        logger.info("Conversa %d marcada como resolvida", conv_id)
    except Exception:
        logger.warning("Falha ao resolver conversa %d", conv_id, exc_info=True)


def ativar_typing(conv_id: int) -> None:
    """Ativa indicador 'digitando...' na conversa."""
    if not _habilitado() or not conv_id:
        return
    try:
        url = f"{_base()}/conversations/{conv_id}/toggle_typing_status"
        _client().post(url, json={"typing_status": "on"}, headers=_headers())
    except Exception:
        pass  # silencioso — UX only, nao pode travar o fluxo


def _buscar_contact_id_da_conversa(conv_id: int) -> int | None:
    """Retorna o contact_id do Chatwoot para uma conversa."""
    try:
        resp = _client().get(f"{_base()}/conversations/{conv_id}", headers=_headers())
        resp.raise_for_status()
        meta = resp.json().get("meta", {})
        sender = meta.get("sender", {})
        return sender.get("id")
    except Exception:
        logger.warning("Falha ao buscar contact_id para conv %d", conv_id, exc_info=True)
    return None


def _buscar_task_por_conversa(conv_id: int) -> int | None:
    """Busca o task_id no Kanban pela conversa ou pelo contato da conversa."""
    if not CHATWOOT_KANBAN_BOARD_ID:
        return None
    try:
        url = f"{_base()}/kanban/tasks?board_id={CHATWOOT_KANBAN_BOARD_ID}"
        resp = _client().get(url, headers=_headers())
        resp.raise_for_status()
        tasks = resp.json().get("tasks", [])

        # 1) busca direta por conversation_ids
        for task in tasks:
            if conv_id in task.get("conversation_ids", []):
                return task["id"]

        # 2) fallback: busca pelo contact_id da conversa
        #    pega a task mais recente (maior id) do contato
        contact_id = _buscar_contact_id_da_conversa(conv_id)
        if contact_id:
            candidatas = [
                t for t in tasks
                if contact_id in t.get("contact_ids", [])
            ]
            if candidatas:
                melhor = max(candidatas, key=lambda t: t["id"])
                # vincula a conversa à task para próximas buscas
                try:
                    existing = list(melhor.get("conversation_ids", []))
                    existing.append(conv_id)
                    _client().patch(
                        f"{_base()}/kanban/tasks/{melhor['id']}",
                        json={"conversation_ids": existing},
                        headers=_headers(),
                    )
                except Exception:
                    pass
                return melhor["id"]
    except Exception:
        logger.warning("Falha ao buscar task Kanban para conv %d", conv_id, exc_info=True)
    return None


def _atualizar_task_kanban(conv_id: int, dados: dict) -> None:
    """Atualiza campos da task Kanban vinculada à conversa (fail-safe)."""
    if not CHATWOOT_KANBAN_BOARD_ID or not conv_id:
        return
    try:
        task_id = _buscar_task_por_conversa(conv_id)
        if not task_id:
            return
        _client().patch(
            f"{_base()}/kanban/tasks/{task_id}",
            json=dados,
            headers=_headers(),
        ).raise_for_status()
        logger.debug("Kanban task %d atualizada: %s", task_id, list(dados.keys()))
    except Exception:
        logger.warning("Falha ao atualizar task Kanban para conv %d", conv_id, exc_info=True)


def _criar_task_kanban(conv_id: int, board_step_id: int) -> int | None:
    """Cria uma nova task no Kanban vinculada à conversa."""
    try:
        payload = {
            "board_id": CHATWOOT_KANBAN_BOARD_ID,
            "board_step_id": board_step_id,
            "title": f"Lead — conv #{conv_id}",
            "conversation_ids": [conv_id],
        }
        resp = _client().post(f"{_base()}/kanban/tasks", json=payload, headers=_headers())
        resp.raise_for_status()
        task_id = resp.json()["id"]
        logger.info("Kanban: task %d criada para conv %d (step %d)", task_id, conv_id, board_step_id)
        return task_id
    except Exception:
        logger.warning("Falha ao criar task Kanban para conv %d", conv_id, exc_info=True)
    return None


def mover_kanban(conv_id: int, board_step_id: int) -> None:
    """Move a task do Kanban para a coluna especificada; cria se não existir (fail-safe)."""
    if not _habilitado() or not CHATWOOT_KANBAN_BOARD_ID or not conv_id:
        return
    try:
        task_id = _buscar_task_por_conversa(conv_id)
        if not task_id:
            task_id = _criar_task_kanban(conv_id, board_step_id)
            return  # já criou na coluna certa
        url = f"{_base()}/kanban/tasks/{task_id}"
        resp = _client().patch(url, json={"board_step_id": board_step_id}, headers=_headers())
        resp.raise_for_status()
        logger.info("Kanban: task %d → step %d (conv %d)", task_id, board_step_id, conv_id)
    except Exception:
        logger.warning("Falha ao mover Kanban para conv %d", conv_id, exc_info=True)


def sincronizar_etapa(
    conv_id: int,
    etapa: str,
    nome_cliente: str | None = None,
    moto: str | None = None,
    medida: str | None = None,
) -> None:
    """Adiciona a label e move o lead no Kanban conforme a etapa atual."""
    label = _LABEL_POR_ETAPA.get(etapa)
    if not label:
        logger.debug("Etapa '%s' sem label mapeada — ignorando sync", etapa)
        return
    adicionar_label(conv_id, label)
    step_id = _KANBAN_STEP_POR_ETAPA.get(etapa)
    if step_id:
        mover_kanban(conv_id, step_id)
    etapa_legivel = _DESCRICAO_ETAPA.get(etapa, etapa)
    partes: list[str] = [etapa_legivel]
    if nome_cliente:
        partes.append(nome_cliente)
    if moto:
        partes.append(moto)
    if medida:
        partes.append(medida)
    if _habilitado():
        _atualizar_task_kanban(conv_id, {"description": " | ".join(partes)})


def sincronizar_nome_cliente(contact_id: int, nome: str) -> None:
    """Atualiza o nome do contato no Chatwoot."""
    if not nome:
        return
    atualizar_contato(contact_id, {"name": nome})


def atualizar_task_nome_cliente(conv_id: int, nome: str) -> None:
    """Atualiza o titulo da task Kanban com o nome do cliente (fail-safe)."""
    if not _habilitado() or not nome or not conv_id:
        return
    _atualizar_task_kanban(conv_id, {"title": nome})


def sincronizar_custom_attributes(contact_id: int, cliente: Cliente) -> None:
    """Envia segmento, historico de compras e ultima compra pro perfil do contato."""
    if not _habilitado() or not contact_id:
        return
    try:
        attrs: dict = {
            "segmento": cliente.segmento,
            "total_pedidos": cliente.total_pedidos,
            "valor_total_gasto": f"R$ {cliente.valor_total_gasto:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        }
        if cliente.ultima_compra_em:
            attrs["ultima_compra"] = cliente.ultima_compra_em.strftime("%d/%m/%Y")
        atualizar_contato(contact_id, {"custom_attributes": attrs})
        logger.debug("Custom attributes sincronizados pro contato %s", contact_id)
    except Exception:
        logger.warning("Falha ao sincronizar custom attributes do contato %s", contact_id, exc_info=True)


def atualizar_conversa_attrs(conv_id: int, attrs: dict) -> None:
    """Atualiza custom attributes da conversa (visíveis na lateral do Chatwoot)."""
    if not _habilitado() or not conv_id or not attrs:
        return
    try:
        url = f"{_base()}/conversations/{conv_id}/custom_attributes"
        resp = _client().post(url, json={"custom_attributes": attrs}, headers=_headers())
        resp.raise_for_status()
        logger.debug("Conversa %d attrs atualizados: %s", conv_id, list(attrs.keys()))
    except Exception:
        logger.warning("Falha ao atualizar attrs da conv %d", conv_id, exc_info=True)


def sincronizar_pedido_criado(
    conv_id: int,
    numero_pedido: int | str,
    valor_total: Decimal | float,
    forma_pagamento: str | None = None,
    tipo_entrega: str | None = None,
    municipio: str | None = None,
    nome_cliente: str | None = None,
    moto: str | None = None,
    medida: str | None = None,
) -> None:
    """Adiciona label pedido_criado, nota privada e custom attributes na conversa."""
    adicionar_label(conv_id, "pedido_criado")
    mover_kanban(conv_id, _KANBAN_STEP_PEDIDO_CRIADO)
    valor_fmt = f"R$ {float(valor_total):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    nota_privada(conv_id, f"Pedido #{numero_pedido} criado — {valor_fmt}")
    # Preencher task Kanban com resumo legivel para o funcionario
    _titulo = f"Pedido #{numero_pedido}"
    if nome_cliente:
        _titulo += f" — {nome_cliente}"
    _desc_partes: list[str] = [f"Pedido #{numero_pedido} — {valor_fmt}"]
    if nome_cliente:
        _desc_partes.append(nome_cliente)
    if moto:
        _desc_partes.append(moto)
    if medida:
        _desc_partes.append(medida)
    if forma_pagamento:
        _desc_partes.append(forma_pagamento)
    if tipo_entrega:
        _desc_partes.append(tipo_entrega)
    if municipio:
        _desc_partes.append(municipio)
    _atualizar_task_kanban(conv_id, {
        "title": _titulo,
        "description": " | ".join(_desc_partes),
        "deal_value": float(valor_total),
    })

    # Custom attributes na conversa (barra lateral)
    attrs: dict = {
        "numero_pedido": int(numero_pedido) if numero_pedido else None,
        "valor_total": valor_fmt,
    }
    if forma_pagamento:
        attrs["forma_pagamento"] = forma_pagamento
    if tipo_entrega:
        attrs["tipo_entrega"] = tipo_entrega
    if municipio:
        attrs["municipio"] = municipio
    atualizar_conversa_attrs(conv_id, attrs)


def sincronizar_cancelamento(
    conv_id: int,
    numero_pedido: int | str | None = None,
    nome_cliente: str | None = None,
    moto: str | None = None,
    medida: str | None = None,
) -> None:
    """Adiciona label pedido_cancelado, move para Oportunidade Perdida e cria nota."""
    adicionar_label(conv_id, "pedido_cancelado")
    mover_kanban(conv_id, _KANBAN_STEP_CANCELADO)
    texto_base = f"Pedido #{numero_pedido} cancelado pelo cliente" if numero_pedido else "Cancelado pelo cliente"
    nota_privada(conv_id, texto_base)
    _partes_cancel: list[str] = [texto_base]
    if nome_cliente:
        _partes_cancel.append(nome_cliente)
    if moto:
        _partes_cancel.append(moto)
    if medida:
        _partes_cancel.append(medida)
    _atualizar_task_kanban(conv_id, {"description": " | ".join(_partes_cancel)})


def definir_prioridade(conv_id: int, prioridade: str) -> None:
    """Define a prioridade da conversa no Chatwoot (urgent, high, medium, low)."""
    if not _habilitado() or not conv_id:
        return
    try:
        url = f"{_base()}/conversations/{conv_id}"
        resp = _client().patch(url, json={"priority": prioridade}, headers=_headers())
        resp.raise_for_status()
        logger.info("Prioridade '%s' definida na conv %d", prioridade, conv_id)
    except Exception:
        logger.warning("Falha ao definir prioridade na conv %d", conv_id, exc_info=True)


def assignar_time(conv_id: int, team_id: int) -> None:
    """Atribui a conversa a um time no Chatwoot."""
    if not _habilitado() or not conv_id or not team_id:
        return
    try:
        url = f"{_base()}/conversations/{conv_id}/assignments"
        resp = _client().post(url, json={"team_id": team_id}, headers=_headers())
        resp.raise_for_status()
        logger.info("Time %d assignado na conv %d", team_id, conv_id)
    except Exception:
        logger.warning("Falha ao assignar time na conv %d", conv_id, exc_info=True)


# Mapeamento motivo -> labels extras (lista)
_LABELS_POR_MOTIVO: dict[str, list[str]] = {
    "cliente_atacado": ["atacado", "emergencia"],
    "emergencia_pneu": ["emergencia"],
    "frete_nao_coberto": ["fora_de_area"],
}


def escalar_para_humano(
    conv_id: int,
    team_id: int | None,
    motivo: str,
    prioridade: str,
) -> None:
    """Escala conversa para atendimento humano — composta, cada etapa fail-safe."""
    adicionar_label(conv_id, "escalado_vendas")
    for label_extra in _LABELS_POR_MOTIVO.get(motivo, []):
        adicionar_label(conv_id, label_extra)
    definir_prioridade(conv_id, prioridade)
    if team_id:
        assignar_time(conv_id, team_id)
    nota_privada(conv_id, f"[ESCALACAO] {motivo}. Prioridade: {prioridade}")
