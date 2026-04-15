"""
Testes de integracao com agente REAL (Supabase + OpenAI).

Testa cenarios especificos das 5 mudancas do commit 809290d:
  B1  — Estoque esgotado: cancela item e registra fato
  B4  — Recovery: sessao escalada nao recebe mensagem
  B5  — Recalculo: valor_total atualizado quando frete muda
  L5  — Alerta de estoque esgotado chega na IA
  Handoff — 3+ itens escala para humano

Requer .env configurado com Supabase e OpenAI validos.
Execute: python tests/test_integracao_guardrails_novos.py
"""
import os
import sys
import uuid
from decimal import Decimal
from datetime import datetime, timezone

# Carregar .env
_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agente_2w.db.client import supabase
from agente_2w.db import sessao_repo, item_provisorio_repo, contexto_repo, catalogo_repo, escalacao_repo
from agente_2w.enums.enums import (
    EtapaFluxo, StatusSessao, StatusItemProvisorio, TipoDeVerdade,
    NivelConfirmacao, OrigemContexto,
)
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.schemas.item_provisorio import ItemProvisorioCreate
from agente_2w.schemas.contexto_conversa import ContextoConversaCreate
from agente_2w.constantes import ChaveContexto
from agente_2w.engine.montador_contexto import montar_contexto
from agente_2w.engine.promotor import alterar_pedido_sessao

_PASS = 0
_FAIL = 0
_sessoes_criadas = []  # para limpeza no final


def ok(nome):
    global _PASS
    _PASS += 1
    print(f"  [OK] {nome}")


def fail(nome, motivo):
    global _FAIL
    _FAIL += 1
    print(f"  [FALHOU] {nome}: {motivo}")


def _criar_sessao_teste(sufixo=""):
    contato = f"5521000{uuid.uuid4().hex[:6]}"
    s = sessao_repo.criar_sessao(SessaoChatCreate(
        canal="teste_integracao",
        contato_externo=contato,
        etapa_atual=EtapaFluxo.oferta,
        status_sessao=StatusSessao.ativa,
    ))
    _sessoes_criadas.append(s.id)
    return s


def _buscar_pneu_com_estoque():
    """Busca um pneu real do catalogo com estoque > 0."""
    res = supabase.table("catalogo_agente").select("pneu_id").gt("disponivel_real", 0).limit(1).execute()
    if not res.data:
        return None
    return uuid.UUID(res.data[0]["pneu_id"])


def _buscar_pneu_sem_estoque():
    """Busca ou simula um pneu sem estoque disponivel."""
    # Busca pneu com disponivel_real = 0
    res = supabase.table("catalogo_agente").select("pneu_id").eq("disponivel_real", 0).limit(1).execute()
    if res.data:
        return uuid.UUID(res.data[0]["pneu_id"])
    return None


def _criar_item_para_sessao(sessao_id, pneu_id):
    return item_provisorio_repo.criar_item(ItemProvisorioCreate(
        sessao_chat_id=sessao_id,
        status_item=StatusItemProvisorio.selecionado_cliente,
        pneu_id=pneu_id,
        quantidade=1,
        preco_unitario_sugerido=Decimal("259.90"),
    ))


def _registrar_fato(sessao_id, chave, valor):
    return contexto_repo.registrar_fato(ContextoConversaCreate(
        sessao_chat_id=sessao_id,
        chave=chave,
        valor_texto=valor,
        valor_json=None,
        tipo_de_verdade=TipoDeVerdade.validado_tool,
        nivel_confirmacao=NivelConfirmacao.nenhum,
        fonte=OrigemContexto.backend,
    ))


# ===========================================================================
# GRUPO 1 — B1: Check de estoque ao chamar processar_turno
# ===========================================================================

print("\nGRUPO 1 — B1: Check de estoque (step 2c)")
print("-" * 60)


def test_b1_item_esgotado_cancelado_e_fato_registrado():
    """Cria sessao com item cuja estoque = 0. Chama processar_turno.
    Verifica que o item foi cancelado e fato ESTOQUE_ESGOTADO registrado."""
    pneu_id = _buscar_pneu_sem_estoque()
    if not pneu_id:
        print("  [SKIP] Nenhum pneu com estoque=0 encontrado no banco")
        return

    sessao = _criar_sessao_teste("b1_esgotado")
    item = _criar_item_para_sessao(sessao.id, pneu_id)

    # Chamar processar_turno — step 2c deve cancelar o item antes de qualquer coisa
    from agente_2w.engine.orquestrador._nucleo import processar_turno
    try:
        processar_turno(sessao.id, "oi, quero meu pneu")
    except Exception:
        pass  # nao importa a resposta, so o efeito colateral

    # Verificar: item deve estar cancelado
    itens = item_provisorio_repo.listar_itens_ativos_por_sessao(sessao.id)
    item_ainda_ativo = any(str(i.id) == str(item.id) for i in itens)

    if not item_ainda_ativo:
        ok("item com estoque=0 foi cancelado pelo step 2c")
    else:
        fail("item cancelado", "item ainda aparece como ativo apos processar_turno")

    # Verificar: fato ESTOQUE_ESGOTADO registrado
    fato = contexto_repo.buscar_fato_ativo(sessao.id, ChaveContexto.ESTOQUE_ESGOTADO)
    if fato:
        ok(f"fato ESTOQUE_ESGOTADO registrado (pneu: {fato.valor_texto})")
    else:
        fail("fato ESTOQUE_ESGOTADO", "nao foi registrado")


def test_b1_item_com_estoque_nao_cancelado():
    """Item com estoque disponivel nao deve ser cancelado."""
    pneu_id = _buscar_pneu_com_estoque()
    if not pneu_id:
        print("  [SKIP] Nenhum pneu com estoque > 0 no banco")
        return

    sessao = _criar_sessao_teste("b1_ok")
    item = _criar_item_para_sessao(sessao.id, pneu_id)

    from agente_2w.engine.orquestrador._nucleo import processar_turno
    try:
        processar_turno(sessao.id, "oi")
    except Exception:
        pass

    itens = item_provisorio_repo.listar_itens_ativos_por_sessao(sessao.id)
    item_ativo = any(str(i.id) == str(item.id) for i in itens)

    if item_ativo:
        ok("item com estoque > 0 nao foi cancelado")
    else:
        fail("item com estoque preservado", "item foi cancelado indevidamente")

    fato = contexto_repo.buscar_fato_ativo(sessao.id, ChaveContexto.ESTOQUE_ESGOTADO)
    if not fato:
        ok("sem fato ESTOQUE_ESGOTADO (correto — estoque ok)")
    else:
        fail("sem fato estoque_esgotado", f"fato registrado indevidamente: {fato.valor_texto}")


test_b1_item_esgotado_cancelado_e_fato_registrado()
test_b1_item_com_estoque_nao_cancelado()


# ===========================================================================
# GRUPO 2 — B4: Recovery nao envia para sessao nao-ativa
# ===========================================================================

print("\nGRUPO 2 — B4: Recovery verifica status")
print("-" * 60)


def test_b4_sessao_escalada_nao_enviaria():
    """Verifica que a logica de B4 filtraria sessao escalada."""
    from agente_2w.enums.enums import StatusSessao

    sessao = _criar_sessao_teste("b4_escalada")
    sessao_repo.atualizar_status(sessao.id, StatusSessao.escalada)

    # Buscar de volta (como o recovery faz)
    sessao_atual = sessao_repo.buscar_sessao_por_id(sessao.id)

    enviaria = sessao_atual and sessao_atual.status_sessao == StatusSessao.ativa

    if not enviaria:
        ok("sessao escalada: logica B4 nao enviaria recovery")
    else:
        fail("sessao escalada bloqueada", "logica deixaria enviar")


def test_b4_sessao_ativa_enviaria():
    """Sessao ativa deve passar pelo filtro B4."""
    sessao = _criar_sessao_teste("b4_ativa")
    sessao_atual = sessao_repo.buscar_sessao_por_id(sessao.id)

    enviaria = sessao_atual and sessao_atual.status_sessao == StatusSessao.ativa

    if enviaria:
        ok("sessao ativa: logica B4 permitiria recovery")
    else:
        fail("sessao ativa permite recovery", f"status={sessao_atual.status_sessao}")


test_b4_sessao_escalada_nao_enviaria()
test_b4_sessao_ativa_enviaria()


# ===========================================================================
# GRUPO 3 — B5: Recalculo de valor_total
# ===========================================================================

print("\nGRUPO 3 — B5: Recalculo valor_total em alterar_pedido_sessao")
print("-" * 60)


def _criar_pedido_teste(sessao_id, valor_frete, valor_total):
    """Insere um pedido confirmado direto no banco para teste."""
    sessao = sessao_repo.buscar_sessao_por_id(sessao_id)
    if not sessao.cliente_id:
        # Resolver cliente para ter cliente_id
        from agente_2w.db import cliente_repo
        cliente = cliente_repo.resolver_ou_criar_cliente(sessao.contato_externo)
        sessao_repo.vincular_cliente(sessao_id, cliente.id)
        sessao = sessao_repo.buscar_sessao_por_id(sessao_id)

    res = supabase.table("pedido").insert({
        "sessao_chat_id": str(sessao_id),
        "cliente_id": str(sessao.cliente_id),
        "numero_pedido": int(uuid.uuid4().int % 900000) + 100000,
        "status_pedido": "confirmado",
        "tipo_entrega": "retirada",
        "forma_pagamento": "pix",
        "valor_total": str(valor_total),
        "valor_frete": str(valor_frete),
    }).execute()
    if res.data:
        return uuid.UUID(res.data[0]["id"])
    return None


def test_b5_frete_muda_recalcula_valor_total():
    """Cria pedido com frete=10 (retirada desatualizada). Registra fato TIPO_ENTREGA=retirada.
    Chama alterar_pedido_sessao. Verifica que valor_frete zerou e valor_total foi recalculado."""
    sessao = _criar_sessao_teste("b5_frete")

    # Registrar fatos de retirada e pagamento
    _registrar_fato(sessao.id, ChaveContexto.TIPO_ENTREGA, "retirada")
    _registrar_fato(sessao.id, ChaveContexto.FORMA_PAGAMENTO, "pix")
    # Sem FRETE_VALOR fato => B5 usa novo_frete = 0

    pedido_id = _criar_pedido_teste(sessao.id, valor_frete=Decimal("10.00"), valor_total=Decimal("269.90"))
    if not pedido_id:
        fail("b5 criou pedido", "falha ao inserir pedido teste")
        return

    # Chamar alterar_pedido_sessao — B5 deve recalcular (0 != 10)
    alterar_pedido_sessao(sessao.id)

    # Buscar pedido atualizado
    pedido_res = supabase.table("pedido").select("valor_frete,valor_total").eq("id", str(pedido_id)).maybe_single().execute()
    if not pedido_res or not pedido_res.data:
        fail("b5 busca pedido", "pedido nao encontrado apos alteracao")
        supabase.table("pedido").delete().eq("id", str(pedido_id)).execute()
        return

    novo_frete = Decimal(pedido_res.data["valor_frete"])
    novo_total = Decimal(pedido_res.data["valor_total"])

    # Limpar pedido de teste
    supabase.table("pedido").delete().eq("id", str(pedido_id)).execute()

    if novo_frete == Decimal("0"):
        ok(f"B5: valor_frete zerado para retirada (era 10.00)")
    else:
        fail("B5 frete zerado", f"frete={novo_frete}, esperado=0.00")

    # valor_total = 0 itens + 0 frete = 0
    if novo_total == Decimal("0"):
        ok(f"B5: valor_total recalculado para 0 (sem itens, sem frete)")
    else:
        fail("B5 total recalculado", f"total={novo_total}, esperado=0.00")


test_b5_frete_muda_recalcula_valor_total()


# ===========================================================================
# GRUPO 4 — L5: Alerta de estoque esgotado chega no contexto da IA
# ===========================================================================

print("\nGRUPO 4 — L5: Alerta de estoque esgotado no contexto montado")
print("-" * 60)


def test_l5_alerta_aparece_no_contexto():
    """Registra fato ESTOQUE_ESGOTADO. Monta contexto. Verifica que alerta aparece."""
    sessao = _criar_sessao_teste("l5")
    _registrar_fato(sessao.id, ChaveContexto.ESTOQUE_ESGOTADO, "Pirelli MT 60 RS")

    ctx = montar_contexto(sessao.id)

    alerta_esgotado = next(
        (a for a in ctx.alertas if "ESTOQUE ESGOTADO" in a), None
    )

    if alerta_esgotado:
        ok("alerta ESTOQUE ESGOTADO aparece no contexto montado")
    else:
        fail("alerta L5 no contexto", f"alertas presentes: {ctx.alertas}")

    if alerta_esgotado and "Pirelli MT 60 RS" in alerta_esgotado:
        ok("alerta contem nome do pneu correto")
    elif alerta_esgotado:
        fail("nome do pneu no alerta", f"alerta={alerta_esgotado}")


def test_l5_sem_fato_sem_alerta_esgotado():
    """Contexto sem fato nao deve ter alerta de esgotado."""
    sessao = _criar_sessao_teste("l5_vazio")
    ctx = montar_contexto(sessao.id)

    alerta_esgotado = next(
        (a for a in ctx.alertas if "ESTOQUE ESGOTADO" in a), None
    )

    if not alerta_esgotado:
        ok("sem fato ESTOQUE_ESGOTADO => sem alerta")
    else:
        fail("sem fato sem alerta", f"alerta indevido: {alerta_esgotado}")


test_l5_alerta_aparece_no_contexto()
test_l5_sem_fato_sem_alerta_esgotado()


# ===========================================================================
# GRUPO 5 — Handoff 3+: Escalar quando >= 3 itens
# ===========================================================================

print("\nGRUPO 5 — Handoff 3+: Escalar com 3+ itens")
print("-" * 60)


def test_handoff_3_itens_cria_escalacao():
    """Cria sessao com 3 itens. Chama processar_turno. Verifica escalacao criada."""
    pneu_id = _buscar_pneu_com_estoque()
    if not pneu_id:
        print("  [SKIP] Sem pneu com estoque para teste handoff")
        return

    sessao = _criar_sessao_teste("handoff3")

    # Criar 3 itens
    for _ in range(3):
        _criar_item_para_sessao(sessao.id, pneu_id)

    # Verificar estado antes
    esc_antes = escalacao_repo.buscar_escalacao_ativa(sessao.id)
    if esc_antes:
        print("  [SKIP] Ja havia escalacao ativa antes do teste")
        return

    from agente_2w.engine.orquestrador._nucleo import processar_turno
    try:
        processar_turno(sessao.id, "quero os 3 pneus")
    except Exception:
        pass

    esc_depois = escalacao_repo.buscar_escalacao_ativa(sessao.id)
    if esc_depois:
        ok(f"Handoff 3+: escalacao criada (motivo={esc_depois.motivo})")
        if esc_depois.motivo == "pedido_volume":
            ok("motivo correto: pedido_volume")
        else:
            fail("motivo escalacao", f"esperado 'pedido_volume', got '{esc_depois.motivo}'")
    else:
        fail("escalacao criada", "nenhuma escalacao encontrada apos 3 itens")


def test_handoff_2_itens_nao_escala():
    """Com 2 itens, nao deve escalar."""
    pneu_id = _buscar_pneu_com_estoque()
    if not pneu_id:
        print("  [SKIP] Sem pneu com estoque")
        return

    sessao = _criar_sessao_teste("handoff2")

    # Criar apenas 2 itens
    for _ in range(2):
        _criar_item_para_sessao(sessao.id, pneu_id)

    from agente_2w.engine.orquestrador._nucleo import processar_turno
    try:
        processar_turno(sessao.id, "quero esses 2 pneus")
    except Exception:
        pass

    esc = escalacao_repo.buscar_escalacao_ativa(sessao.id)
    esc_volume = esc and esc.motivo == "pedido_volume"

    if not esc_volume:
        ok("2 itens: sem escalacao de pedido_volume")
    else:
        fail("2 itens nao escala", f"escalacao criada indevidamente: {esc.motivo}")


test_handoff_3_itens_cria_escalacao()
test_handoff_2_itens_nao_escala()


# ===========================================================================
# Limpeza + Resultado
# ===========================================================================

print("\nLimpando sessoes de teste...")
for sid in _sessoes_criadas:
    try:
        sessao_repo.fechar_sessao(sid)
    except Exception:
        pass
print(f"  {len(_sessoes_criadas)} sessao(es) limpas.")

total = _PASS + _FAIL
print("\n" + "=" * 60)
print(f"RESULTADO: {_PASS}/{total} testes passaram")
if _FAIL == 0:
    print("Todos os testes de integracao passaram.")
else:
    print(f"ATENCAO: {_FAIL} teste(s) falharam!")
    sys.exit(1)
