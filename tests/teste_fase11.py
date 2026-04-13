"""
Teste Fase 11 — Historico de Pedido, Reserva de Estoque e Alteracao de Pedido.

Cobertura:
  BLOCO 1 — Sem IA (rapido)
    T01  incrementar_reservado grava no banco
    T02  decrementar_reservado grava no banco (nao vai negativo)
    T03  alterar_pedido_sessao sem pedido retorna False
    T04  montador_contexto popula ultimo_pedido de cliente com historico

  BLOCO 2 — Com IA (E2E)
    T05  Conversa completa: pedido criado, reservado incrementado
    T06  Mesmo cliente nova sessao: contexto tem ultimo_pedido
    T07  Alteracao pos-fechamento: cliente muda forma de pagamento
    T08  Cancelamento: reservado decrementado, stats revertidos
"""

import sys
import time
import logging
from uuid import UUID

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from agente_2w.db import sessao_repo, pedido_repo, cliente_repo, catalogo_repo
from agente_2w.db.pedido_repo import listar_itens_pedido
from agente_2w.engine.montador_contexto import montar_contexto
from agente_2w.engine.promotor import alterar_pedido_sessao, cancelar_pedido_sessao
from agente_2w.engine.orquestrador import processar_turno
from agente_2w.enums.enums import EtapaFluxo, StatusSessao
from agente_2w.schemas.sessao_chat import SessaoChatCreate

SEP = "-" * 65
PAUSA = 8  # segundos entre turnos com IA

# Contato unico por execucao para nao colidir com testes anteriores
import random
CONTATO_TESTE = f"5521{random.randint(800000000, 899999999)}"

resultados: list[tuple[str, bool, str]] = []


def check(nome: str, condicao: bool, detalhe: str = ""):
    ok = "[OK]  " if condicao else "[FAIL]"
    resultados.append((nome, condicao, detalhe))
    print(f"  {ok} {nome}" + (f" — {detalhe}" if detalhe else ""))
    return condicao


def nova_sessao(contato: str = CONTATO_TESTE):
    sessao = sessao_repo.criar_sessao(SessaoChatCreate(
        canal="teste",
        contato_externo=contato,
        etapa_atual=EtapaFluxo.identificacao,
        status_sessao=StatusSessao.ativa,
    ))
    return sessao


def turno(sessao_id, msg, pausa=True):
    resposta = processar_turno(sessao_id, msg)
    s = sessao_repo.buscar_sessao_por_id(sessao_id)
    etapa = s.etapa_atual.value if s else "?"
    print(f"    Cliente : {msg}")
    print(f"    Agente  : {resposta}")
    print(f"    Etapa   : {etapa}")
    print()
    if pausa:
        time.sleep(PAUSA)
    return resposta, etapa


# ─────────────────────────────────────────────────────────────────────────────
# BLOCO 1 — SEM IA
# ─────────────────────────────────────────────────────────────────────────────

def bloco1_sem_ia():
    print()
    print(SEP)
    print("  BLOCO 1 — Testes sem IA")
    print(SEP)

    # T01 — incrementar_reservado
    print()
    print("  T01: incrementar_reservado")
    try:
        # Pega qualquer pneu com estoque no banco
        resultado = catalogo_repo.supabase_query_estoque_qualquer()
        if resultado:
            pneu_id = UUID(resultado["pneu_id"])
            reservado_antes = resultado["reservado"]
            catalogo_repo.incrementar_reservado(pneu_id, 2)
            estoque_depois = catalogo_repo.buscar_estoque_por_pneu(pneu_id)
            check("T01 reservado incrementado",
                  estoque_depois.reservado == reservado_antes + 2,
                  f"antes={reservado_antes} depois={estoque_depois.reservado}")
            # Limpar
            catalogo_repo.decrementar_reservado(pneu_id, 2)
        else:
            check("T01 reservado incrementado", False, "nenhum pneu em estoque encontrado")
    except Exception as e:
        check("T01 reservado incrementado", False, str(e))

    # T02 — decrementar_reservado nao vai negativo
    print()
    print("  T02: decrementar_reservado nao vai negativo")
    try:
        resultado = catalogo_repo.supabase_query_estoque_qualquer()
        if resultado:
            pneu_id = UUID(resultado["pneu_id"])
            # Zera reservado tentando subtrair muito
            catalogo_repo.decrementar_reservado(pneu_id, 9999)
            estoque = catalogo_repo.buscar_estoque_por_pneu(pneu_id)
            check("T02 reservado >= 0 apos decrementar excessivo",
                  estoque.reservado >= 0,
                  f"reservado={estoque.reservado}")
        else:
            check("T02 reservado >= 0", False, "nenhum pneu em estoque encontrado")
    except Exception as e:
        check("T02 reservado >= 0", False, str(e))

    # T03 — alterar_pedido_sessao sem pedido
    print()
    print("  T03: alterar_pedido_sessao sem pedido")
    try:
        sessao = nova_sessao()
        resultado = alterar_pedido_sessao(sessao.id)
        check("T03 retorna False quando nao ha pedido", resultado is False)
        # Limpar sessao
        sessao_repo.atualizar_status(sessao.id, StatusSessao.fechada)
    except Exception as e:
        check("T03 retorna False quando nao ha pedido", False, str(e))

    # T04 — montador_contexto com cliente sem historico
    print()
    print("  T04: montador_contexto ultimo_pedido=None para cliente novo")
    try:
        sessao = nova_sessao(f"5521{random.randint(700000000, 799999999)}")
        # Resolver cliente
        from agente_2w.db import cliente_repo as cr
        cliente = cr.resolver_ou_criar_cliente(sessao.contato_externo)
        sessao_repo.vincular_cliente(sessao.id, cliente.id)
        ctx = montar_contexto(sessao.id)
        check("T04 ultimo_pedido=None para cliente sem historico",
              ctx.cliente.ultimo_pedido is None,
              f"resolvido={ctx.cliente.resolvido}")
        sessao_repo.atualizar_status(sessao.id, StatusSessao.fechada)
    except Exception as e:
        check("T04 ultimo_pedido=None para cliente sem historico", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# BLOCO 2 — COM IA (E2E)
# ─────────────────────────────────────────────────────────────────────────────

# Conversa 1: pedido completo para o cliente de teste
CONVERSA_PEDIDO1 = [
    "oi, preciso de pneu traseiro pra minha CG 160",
    "qualquer marca ta bom",
    "quero esse",
    "1 unidade, confirma",
    "vou retirar na loja, pix",
    "Carlos Teste",
    "pode fechar",
]

# Conversa 2 (mesmo cliente): mudanca de pagamento no fechamento
CONVERSA_ALTERACAO = [
    "oi, quero pneu traseiro pra CG 160 de novo",
    "qualquer marca",
    "pode ser",
    "1 unidade",
    "retiro, pix",
    "Carlos Teste",
    "na verdade muda pra dinheiro",  # alteracao de pagamento pos-fechamento
    "pode fechar com dinheiro mesmo",
]

# Conversa 3 (mesmo cliente): cancelamento
CONVERSA_CANCELAMENTO = [
    "quero pneu traseiro CG 160",
    "qualquer um",
    "esse mesmo",
    "1 unidade",
    "retiro, pix",
    "Carlos Teste",
    "pode fechar",
    "na verdade cancela o pedido",
]


def bloco2_com_ia():
    print()
    print(SEP)
    print("  BLOCO 2 — Testes com IA (E2E)")
    print(SEP)

    # ── T05: Pedido completo + reservado incrementado ──────────────
    print()
    print("  T05: Pedido completo — reservado deve ser incrementado")
    sessao1 = nova_sessao()
    sessao_id1 = sessao1.id
    print(f"    Sessao: {sessao_id1}  Contato: {CONTATO_TESTE}")
    print()

    for i, msg in enumerate(CONVERSA_PEDIDO1, 1):
        print(f"    [Turno {i}/{len(CONVERSA_PEDIDO1)}]")
        try:
            turno(sessao_id1, msg, pausa=(i < len(CONVERSA_PEDIDO1)))
        except Exception as e:
            print(f"    [ERRO turno {i}]: {e}")
            break

    pedido1 = pedido_repo.buscar_pedido_por_sessao(sessao_id1)
    check("T05a pedido criado no banco", pedido1 is not None,
          str(pedido1.id) if pedido1 else "nenhum pedido")

    if pedido1:
        itens1 = listar_itens_pedido(pedido1.id)
        check("T05b itens do pedido existem", len(itens1) > 0, f"{len(itens1)} item(s)")

        if itens1:
            pneu_id_t5 = itens1[0].pneu_id
            estoque_t5 = catalogo_repo.buscar_estoque_por_pneu(pneu_id_t5)
            check("T05c reservado > 0 apos promocao",
                  estoque_t5 is not None and estoque_t5.reservado > 0,
                  f"reservado={estoque_t5.reservado if estoque_t5 else '?'}")

        check("T05d status_pedido=confirmado",
              pedido1.status_pedido.value == "confirmado")
        check("T05e tipo_entrega=retirada",
              pedido1.tipo_entrega.value == "retirada")

    # Verificar cliente
    sessao1_final = sessao_repo.buscar_sessao_por_id(sessao_id1)
    cliente1 = None
    if sessao1_final and sessao1_final.cliente_id:
        cliente1 = cliente_repo.buscar_cliente_por_id(sessao1_final.cliente_id)
        check("T05f total_pedidos >= 1", cliente1 and cliente1.total_pedidos >= 1,
              f"total={cliente1.total_pedidos if cliente1 else '?'}")
        check("T05g valor_total_gasto > 0", cliente1 and cliente1.valor_total_gasto > 0)

    # ── T06: Novo sessao mesmo cliente — ultimo_pedido no contexto ──
    print()
    print("  T06: Nova sessao mesmo cliente — ultimo_pedido no contexto")
    if cliente1:
        try:
            sessao_t6 = nova_sessao(CONTATO_TESTE)
            cliente_t6 = cliente_repo.resolver_ou_criar_cliente(CONTATO_TESTE)
            sessao_repo.vincular_cliente(sessao_t6.id, cliente_t6.id)
            ctx_t6 = montar_contexto(sessao_t6.id)
            check("T06a ultimo_pedido populado no contexto",
                  ctx_t6.cliente.ultimo_pedido is not None)
            if ctx_t6.cliente.ultimo_pedido:
                up = ctx_t6.cliente.ultimo_pedido
                check("T06b ultimo_pedido.itens nao vazio", len(up.itens) > 0,
                      f"{len(up.itens)} item(s)")
                check("T06c ultimo_pedido.valor_total > 0", up.valor_total > 0,
                      f"R${up.valor_total:.2f}")
                import re as _re
                nome_pneu = up.itens[0].pneu_nome if up.itens else ""
                _e_uuid = bool(_re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-', nome_pneu, _re.IGNORECASE))
                check("T06d pneu_nome e nome real (nao UUID)",
                      bool(nome_pneu) and not _e_uuid,
                      nome_pneu)
            sessao_repo.atualizar_status(sessao_t6.id, StatusSessao.fechada)
        except Exception as e:
            check("T06 ultimo_pedido no contexto", False, str(e))
    else:
        check("T06 ultimo_pedido no contexto", False, "cliente nao resolvido no T05")

    time.sleep(PAUSA)

    # ── T07: Alteracao de pedido pos-fechamento ─────────────────────
    print()
    print("  T07: Alteracao de pedido (mudanca de pagamento apos fechamento)")
    sessao2 = nova_sessao()
    sessao_id2 = sessao2.id
    print(f"    Sessao: {sessao_id2}")
    print()

    for i, msg in enumerate(CONVERSA_ALTERACAO, 1):
        print(f"    [Turno {i}/{len(CONVERSA_ALTERACAO)}]")
        try:
            turno(sessao_id2, msg, pausa=(i < len(CONVERSA_ALTERACAO)))
        except Exception as e:
            print(f"    [ERRO turno {i}]: {e}")
            break

    pedido2 = pedido_repo.buscar_pedido_por_sessao(sessao_id2)
    check("T07a pedido criado", pedido2 is not None)
    if pedido2:
        check("T07b forma_pagamento alterada para dinheiro",
              pedido2.forma_pagamento.value == "dinheiro",
              f"forma_pagamento={pedido2.forma_pagamento.value}")

    time.sleep(PAUSA)

    # ── T08: Cancelamento — reservado decrementado ──────────────────
    print()
    print("  T08: Cancelamento — reservado deve ser decrementado")
    sessao3 = nova_sessao()
    sessao_id3 = sessao3.id
    print(f"    Sessao: {sessao_id3}")
    print()

    reservado_antes_t8 = None
    pneu_id_t8 = None

    for i, msg in enumerate(CONVERSA_CANCELAMENTO, 1):
        print(f"    [Turno {i}/{len(CONVERSA_CANCELAMENTO)}]")
        try:
            turno(sessao_id3, msg, pausa=(i < len(CONVERSA_CANCELAMENTO)))
        except Exception as e:
            print(f"    [ERRO turno {i}]: {e}")
            break

        # Capturar reservado logo apos a promocao (apos turno 7 = fechamento)
        if i == 7:
            pedido_temp = pedido_repo.buscar_pedido_por_sessao(sessao_id3)
            if pedido_temp:
                itens_temp = listar_itens_pedido(pedido_temp.id)
                if itens_temp:
                    pneu_id_t8 = itens_temp[0].pneu_id
                    est = catalogo_repo.buscar_estoque_por_pneu(pneu_id_t8)
                    reservado_antes_t8 = est.reservado if est else None

    pedido3 = pedido_repo.buscar_pedido_por_sessao(sessao_id3)
    if pedido3:
        check("T08a pedido cancelado",
              pedido3.status_pedido.value == "cancelado",
              f"status={pedido3.status_pedido.value}")

        if pneu_id_t8 and reservado_antes_t8 is not None:
            est_depois = catalogo_repo.buscar_estoque_por_pneu(pneu_id_t8)
            check("T08b reservado decrementado apos cancelamento",
                  est_depois.reservado < reservado_antes_t8,
                  f"antes={reservado_antes_t8} depois={est_depois.reservado}")
        else:
            check("T08b reservado decrementado", False, "nao foi possivel capturar reservado pre-cancelamento")

        sessao3_final = sessao_repo.buscar_sessao_por_id(sessao_id3)
        if sessao3_final and sessao3_final.cliente_id:
            cliente3 = cliente_repo.buscar_cliente_por_id(sessao3_final.cliente_id)
            if cliente3 and cliente1:
                check("T08c stats revertidos apos cancelamento",
                      cliente3.total_pedidos < (cliente1.total_pedidos + 2),
                      f"total_pedidos={cliente3.total_pedidos}")
    else:
        check("T08a pedido cancelado", False, "pedido nao encontrado")
        check("T08b reservado decrementado", False, "pedido nao encontrado")
        check("T08c stats revertidos", False, "pedido nao encontrado")


# ─────────────────────────────────────────────────────────────────────────────
# RELATORIO
# ─────────────────────────────────────────────────────────────────────────────

def relatorio():
    print()
    print(SEP)
    print("  RELATORIO FINAL")
    print(SEP)
    total = len(resultados)
    passou = sum(1 for _, ok, _ in resultados if ok)
    falhou = total - passou

    for nome, ok, detalhe in resultados:
        marca = "[OK]  " if ok else "[FAIL]"
        linha = f"  {marca} {nome}"
        if detalhe:
            linha += f" — {detalhe}"
        print(linha)

    print()
    print(f"  Total : {total}")
    print(f"  Pass  : {passou}")
    print(f"  Fail  : {falhou}")
    print()

    if falhou == 0:
        print("  RESULTADO: PASS — todos os testes passaram!")
    else:
        print(f"  RESULTADO: FAIL — {falhou} teste(s) falharam")
    print(SEP)

    return falhou == 0


# ─────────────────────────────────────────────────────────────────────────────
# PATCH para T01/T02 — funcao auxiliar que nao existe no catalogo_repo
# ─────────────────────────────────────────────────────────────────────────────

def _patch_catalogo_repo():
    """Adiciona supabase_query_estoque_qualquer ao catalogo_repo em tempo de execucao."""
    from agente_2w.db.client import supabase
    import agente_2w.db.catalogo_repo as cr

    def _buscar_qualquer():
        try:
            resultado = supabase.table("estoque").select("pneu_id, reservado").limit(1).execute()
            if resultado.data:
                return resultado.data[0]
            return None
        except Exception:
            return None

    cr.supabase_query_estoque_qualquer = _buscar_qualquer


if __name__ == "__main__":
    _patch_catalogo_repo()

    bloco1_sem_ia()
    bloco2_com_ia()
    passou = relatorio()
    sys.exit(0 if passou else 1)
