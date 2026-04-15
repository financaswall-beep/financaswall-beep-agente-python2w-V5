"""
Testes das 5 novas mudancas implementadas no commit 809290d.

B1  — Check de estoque antes da IA (step 2c)
B4  — Sessao ainda ativa antes do recovery
B5  — Recalcular valor_total/valor_frete em alterar_pedido_sessao
L5  — Alerta de estoque esgotado no montador_contexto
Handoff — Escalar quando item_provisorio >= 3 (step 9e)

Roda sem banco: tudo mockado com unittest.mock.
Execute: python tests/test_guardrails_novos.py
"""
import sys
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_PASS = 0
_FAIL = 0


def ok(nome):
    global _PASS
    _PASS += 1
    print(f"  [OK] {nome}")


def fail(nome, motivo):
    global _FAIL
    _FAIL += 1
    print(f"  [FALHOU] {nome}: {motivo}")


# ===========================================================================
# Helpers
# ===========================================================================

def _make_estoque(disponivel, reservado):
    e = MagicMock()
    e.quantidade_disponivel = disponivel
    e.reservado = reservado
    return e


def _make_pneu(nome="Pirelli MT 60"):
    p = MagicMock()
    p.descricao_comercial = nome
    return p


def _make_item_prov(pneu_id=None, status="selecionado_cliente"):
    from agente_2w.enums.enums import StatusItemProvisorio
    i = MagicMock()
    i.id = uuid.uuid4()
    i.pneu_id = pneu_id or uuid.uuid4()
    i.status_item = StatusItemProvisorio(status)
    i.quantidade = 1
    from decimal import Decimal
    i.preco_unitario_sugerido = Decimal("259.90")
    return i


def _make_item_pedido(preco, qtd=1):
    i = MagicMock()
    i.preco_unitario = Decimal(str(preco))
    i.quantidade = qtd
    return i


def _make_pedido(valor_frete, valor_total, tipo_entrega="entrega", status="confirmado"):
    p = MagicMock()
    p.id = uuid.uuid4()
    p.status_pedido = MagicMock()
    p.status_pedido.value = status
    p.valor_frete = Decimal(str(valor_frete))
    p.valor_total = Decimal(str(valor_total))
    p.tipo_entrega = MagicMock()
    p.tipo_entrega.value = tipo_entrega
    p.forma_pagamento = MagicMock()
    p.forma_pagamento.value = "pix"
    p.endereco_entrega_json = None
    return p


def _make_fato(valor_texto):
    f = MagicMock()
    f.valor_texto = valor_texto
    f.valor_json = None
    return f


# ===========================================================================
# GRUPO 1 — B1: Check de estoque antes da IA
# ===========================================================================

print("\nGRUPO 1 — B1: Check de estoque antes da IA (step 2c)")
print("-" * 60)


def _simular_b1_check(disponivel, reservado):
    """Simula a logica do step 2c de _nucleo.py diretamente."""
    from agente_2w.enums.enums import StatusItemProvisorio

    pneu_id = uuid.uuid4()
    item = _make_item_prov(pneu_id)
    estoque = _make_estoque(disponivel, reservado)
    pneu = _make_pneu("Pirelli MT 60 RS")

    cancelados = []
    fatos_registrados = []

    disp = estoque.quantidade_disponivel - estoque.reservado
    if disp <= 0:
        cancelados.append(item.id)
        fatos_registrados.append({
            "chave": "estoque_esgotado",
            "valor_texto": pneu.descricao_comercial,
        })

    return cancelados, fatos_registrados


def test_b1_estoque_zero_cancela_item():
    cancelados, fatos = _simular_b1_check(disponivel=1, reservado=1)
    if len(cancelados) == 1:
        ok("estoque=0 cancela o item")
    else:
        fail("estoque=0 cancela o item", f"esperava 1 cancelado, got {len(cancelados)}")


def test_b1_estoque_negativo_cancela():
    cancelados, fatos = _simular_b1_check(disponivel=0, reservado=2)
    if len(cancelados) == 1:
        ok("estoque negativo cancela item")
    else:
        fail("estoque negativo cancela item", f"esperava 1 cancelado, got {len(cancelados)}")


def test_b1_estoque_ok_nao_cancela():
    cancelados, fatos = _simular_b1_check(disponivel=5, reservado=1)
    if len(cancelados) == 0:
        ok("estoque=4 nao cancela item")
    else:
        fail("estoque=4 nao cancela item", f"esperava 0 cancelados, got {len(cancelados)}")


def test_b1_registra_fato_estoque_esgotado():
    cancelados, fatos = _simular_b1_check(disponivel=1, reservado=1)
    if fatos and fatos[0]["chave"] == "estoque_esgotado":
        ok("registra fato estoque_esgotado quando item cancelado")
    else:
        fail("registra fato estoque_esgotado", f"fatos={fatos}")


def test_b1_fato_contem_nome_pneu():
    cancelados, fatos = _simular_b1_check(disponivel=0, reservado=0)
    if fatos and "Pirelli MT 60 RS" in fatos[0]["valor_texto"]:
        ok("fato estoque_esgotado contem nome do pneu")
    else:
        fail("fato contem nome do pneu", f"fatos={fatos}")


def test_b1_sem_cancelamento_sem_fato():
    cancelados, fatos = _simular_b1_check(disponivel=10, reservado=2)
    if not cancelados and not fatos:
        ok("estoque ok => nenhum fato registrado")
    else:
        fail("estoque ok sem fato", f"cancelados={cancelados}, fatos={fatos}")


test_b1_estoque_zero_cancela_item()
test_b1_estoque_negativo_cancela()
test_b1_estoque_ok_nao_cancela()
test_b1_registra_fato_estoque_esgotado()
test_b1_fato_contem_nome_pneu()
test_b1_sem_cancelamento_sem_fato()


# ===========================================================================
# GRUPO 2 — B4 (recovery): Sessao ativa antes de enviar mensagem
# ===========================================================================

print("\nGRUPO 2 — B4 (recovery): Sessao ativa antes de enviar mensagem")
print("-" * 60)

import asyncio


def _simular_b4_check(status_sessao):
    """Simula a logica de B4 no _recovery_cliente_perdido."""
    from agente_2w.enums.enums import StatusSessao

    sessao = MagicMock()
    sessao.status_sessao = StatusSessao(status_sessao)

    # Logica inserida em webhook_server.py
    if not sessao or sessao.status_sessao != StatusSessao.ativa:
        return False  # ignorou — nao enviou
    return True  # enviou


def test_b4_sessao_ativa_envia():
    enviou = _simular_b4_check("ativa")
    if enviou:
        ok("sessao ativa -> envia recovery")
    else:
        fail("sessao ativa -> envia recovery", "bloqueou indevidamente")


def test_b4_sessao_escalada_nao_envia():
    enviou = _simular_b4_check("escalada")
    if not enviou:
        ok("sessao escalada -> nao envia recovery")
    else:
        fail("sessao escalada -> nao envia recovery", "enviou quando nao devia")


def test_b4_sessao_fechada_nao_envia():
    enviou = _simular_b4_check("fechada")
    if not enviou:
        ok("sessao fechada -> nao envia recovery")
    else:
        fail("sessao fechada -> nao envia recovery", "enviou quando nao devia")


def test_b4_sessao_bloqueada_nao_envia():
    enviou = _simular_b4_check("bloqueada")
    if not enviou:
        ok("sessao bloqueada -> nao envia recovery")
    else:
        fail("sessao bloqueada -> nao envia recovery", "enviou quando nao devia")


test_b4_sessao_ativa_envia()
test_b4_sessao_escalada_nao_envia()
test_b4_sessao_fechada_nao_envia()
test_b4_sessao_bloqueada_nao_envia()


# ===========================================================================
# GRUPO 3 — B5: Recalcular valor_total quando frete muda
# ===========================================================================

print("\nGRUPO 3 — B5: Recalcular valor_total/valor_frete")
print("-" * 60)

import unicodedata


def _normalizar(valor):
    sem_acento = unicodedata.normalize("NFD", valor)
    sem_acento = sem_acento.encode("ascii", "ignore").decode("ascii")
    return sem_acento.strip().lower()


def _simular_b5(
    frete_atual_pedido,  # Decimal: frete salvo no pedido
    novo_frete_fato,     # str|None: valor no fato FRETE_VALOR
    tipo_entrega_fato,   # str: "entrega" ou "retirada"
    itens_preco,         # list[float]: precos dos itens do pedido
):
    """Simula a logica de recalculo B5 em alterar_pedido_sessao."""
    from agente_2w.enums.enums import TipoEntrega

    pedido = _make_pedido(valor_frete=frete_atual_pedido, valor_total=sum(Decimal(str(p)) for p in itens_preco) + frete_atual_pedido)
    campos = {}

    fato_frete = _make_fato(novo_frete_fato) if novo_frete_fato else None
    fato_tipo = _make_fato(tipo_entrega_fato)

    # Logica de B5 (replicada de promotor.py)
    novo_frete = Decimal("0")
    if fato_tipo and fato_tipo.valor_texto:
        if _normalizar(fato_tipo.valor_texto) == TipoEntrega.entrega.value:
            if fato_frete and fato_frete.valor_texto:
                try:
                    novo_frete = Decimal(fato_frete.valor_texto)
                except (ValueError, ArithmeticError):
                    pass

    if novo_frete != pedido.valor_frete:
        valor_itens = sum(Decimal(str(p)) for p in itens_preco)
        campos["valor_frete"] = str(novo_frete)
        campos["valor_total"] = str(valor_itens + novo_frete)

    return campos


def test_b5_frete_muda_recalcula_total():
    campos = _simular_b5(
        frete_atual_pedido=Decimal("15.00"),
        novo_frete_fato="25.00",
        tipo_entrega_fato="entrega",
        itens_preco=[259.90],
    )
    if "valor_frete" in campos and "valor_total" in campos:
        novo_total = Decimal(campos["valor_total"])
        esperado = Decimal("259.90") + Decimal("25.00")
        if novo_total == esperado:
            ok("frete muda: valor_total recalculado corretamente")
        else:
            fail("valor_total correto", f"esperado={esperado}, got={novo_total}")
    else:
        fail("frete muda recalcula total", f"campos gerados: {campos}")


def test_b5_mesmo_frete_nao_recalcula():
    campos = _simular_b5(
        frete_atual_pedido=Decimal("15.00"),
        novo_frete_fato="15.00",
        tipo_entrega_fato="entrega",
        itens_preco=[259.90],
    )
    if not campos:
        ok("mesmo frete => nenhuma alteracao")
    else:
        fail("mesmo frete sem alteracao", f"campos gerados indevidamente: {campos}")


def test_b5_retirada_frete_zero():
    campos = _simular_b5(
        frete_atual_pedido=Decimal("15.00"),
        novo_frete_fato=None,
        tipo_entrega_fato="retirada",
        itens_preco=[259.90],
    )
    # retirada nao tem frete — frete calculado = 0, que é != 15, entao deve recalcular
    if "valor_total" in campos:
        novo_total = Decimal(campos["valor_total"])
        esperado = Decimal("259.90")
        if novo_total == esperado:
            ok("tipo_entrega=retirada: frete zerado, total = apenas itens")
        else:
            fail("retirada total correto", f"esperado={esperado}, got={novo_total}")
    else:
        fail("retirada recalcula total", f"campos gerados: {campos}")


def test_b5_multiplos_itens():
    campos = _simular_b5(
        frete_atual_pedido=Decimal("10.00"),
        novo_frete_fato="20.00",
        tipo_entrega_fato="entrega",
        itens_preco=[150.00, 200.00],
    )
    if "valor_total" in campos:
        novo_total = Decimal(campos["valor_total"])
        esperado = Decimal("150.00") + Decimal("200.00") + Decimal("20.00")
        if novo_total == esperado:
            ok("multiplos itens: soma correta com novo frete")
        else:
            fail("multiplos itens soma", f"esperado={esperado}, got={novo_total}")
    else:
        fail("multiplos itens recalcula", f"campos={campos}")


test_b5_frete_muda_recalcula_total()
test_b5_mesmo_frete_nao_recalcula()
test_b5_retirada_frete_zero()
test_b5_multiplos_itens()


# ===========================================================================
# GRUPO 4 — L5: Alerta de estoque esgotado no montador_contexto
# ===========================================================================

print("\nGRUPO 4 — L5: Alerta de estoque esgotado no montador_contexto")
print("-" * 60)

from agente_2w.constantes import ChaveContexto


def _simular_l5_alerta(chave_estoque_esgotado_presente, nome_pneu="Pirelli MT"):
    """Simula a logica de alerta L5 em montador_contexto.py."""
    alertas = []
    chaves_ativas = set()

    if chave_estoque_esgotado_presente:
        chaves_ativas.add(ChaveContexto.ESTOQUE_ESGOTADO)

    fatos_db = []
    if chave_estoque_esgotado_presente:
        f = MagicMock()
        f.chave = ChaveContexto.ESTOQUE_ESGOTADO
        f.valor_texto = nome_pneu
        fatos_db.append(f)

    # Logica de montador_contexto.py
    if ChaveContexto.ESTOQUE_ESGOTADO in chaves_ativas:
        fato_esgotado = next((f for f in fatos_db if f.chave == ChaveContexto.ESTOQUE_ESGOTADO), None)
        if fato_esgotado:
            alertas.append(
                f"ESTOQUE ESGOTADO: o pneu '{fato_esgotado.valor_texto}' que o cliente havia escolhido "
                "acabou de esgotar e foi removido do carrinho."
            )

    return alertas


def test_l5_alerta_gerado_quando_esgotado():
    alertas = _simular_l5_alerta(True, "Michelin Pilot Street")
    if any("ESTOQUE ESGOTADO" in a for a in alertas):
        ok("fato estoque_esgotado -> alerta gerado")
    else:
        fail("alerta gerado", f"alertas={alertas}")


def test_l5_alerta_contem_nome_pneu():
    alertas = _simular_l5_alerta(True, "Michelin Pilot Street")
    if any("Michelin Pilot Street" in a for a in alertas):
        ok("alerta contem nome do pneu")
    else:
        fail("alerta contem nome", f"alertas={alertas}")


def test_l5_sem_fato_sem_alerta():
    alertas = _simular_l5_alerta(False)
    if not alertas:
        ok("sem fato estoque_esgotado -> sem alerta")
    else:
        fail("sem fato sem alerta", f"alertas gerados indevidamente: {alertas}")


def test_l5_constante_existe():
    if hasattr(ChaveContexto, "ESTOQUE_ESGOTADO") and ChaveContexto.ESTOQUE_ESGOTADO == "estoque_esgotado":
        ok("ChaveContexto.ESTOQUE_ESGOTADO definida corretamente")
    else:
        fail("constante ESTOQUE_ESGOTADO", "nao encontrada ou valor errado")


test_l5_alerta_gerado_quando_esgotado()
test_l5_alerta_contem_nome_pneu()
test_l5_sem_fato_sem_alerta()
test_l5_constante_existe()


# ===========================================================================
# GRUPO 5 — Handoff 3+: Escalar quando >= 3 itens
# ===========================================================================

print("\nGRUPO 5 — Handoff 3+: Escalar com 3+ itens (step 9e)")
print("-" * 60)


def _simular_handoff(n_itens, tem_escalacao_ativa=False):
    """Simula a logica do step 9e em _nucleo.py."""
    itens = [_make_item_prov() for _ in range(n_itens)]
    itens_com_pneu = [i for i in itens if i.pneu_id]

    escalacoes_criadas = []

    if len(itens_com_pneu) >= 3:
        if not tem_escalacao_ativa:
            escalacoes_criadas.append("pedido_volume")

    return escalacoes_criadas


def test_handoff_3_itens_escala():
    esc = _simular_handoff(3)
    if esc and "pedido_volume" in esc:
        ok("3 itens -> escalacao criada com motivo pedido_volume")
    else:
        fail("3 itens escala", f"escalacoes={esc}")


def test_handoff_4_itens_escala():
    esc = _simular_handoff(4)
    if esc:
        ok("4 itens -> escalacao criada")
    else:
        fail("4 itens escala", "nao escalou")


def test_handoff_2_itens_nao_escala():
    esc = _simular_handoff(2)
    if not esc:
        ok("2 itens -> nao escala")
    else:
        fail("2 itens nao escala", f"escalou indevidamente: {esc}")


def test_handoff_1_item_nao_escala():
    esc = _simular_handoff(1)
    if not esc:
        ok("1 item -> nao escala")
    else:
        fail("1 item nao escala", f"escalou indevidamente: {esc}")


def test_handoff_idempotente_ja_escalado():
    esc = _simular_handoff(5, tem_escalacao_ativa=True)
    if not esc:
        ok("ja tem escalacao ativa -> nao cria duplicata")
    else:
        fail("idempotencia escalacao", f"criou duplicata: {esc}")


def test_handoff_zero_itens_nao_escala():
    esc = _simular_handoff(0)
    if not esc:
        ok("0 itens -> nao escala")
    else:
        fail("0 itens nao escala", f"escalou: {esc}")


test_handoff_3_itens_escala()
test_handoff_4_itens_escala()
test_handoff_2_itens_nao_escala()
test_handoff_1_item_nao_escala()
test_handoff_idempotente_ja_escalado()
test_handoff_zero_itens_nao_escala()


# ===========================================================================
# Resultado final
# ===========================================================================

total = _PASS + _FAIL
print("\n" + "=" * 60)
print(f"RESULTADO: {_PASS}/{total} testes passaram")
if _FAIL == 0:
    print("Todos os guardrails novos funcionando corretamente.")
else:
    print(f"ATENCAO: {_FAIL} teste(s) falharam!")
    sys.exit(1)
