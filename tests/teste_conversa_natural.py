"""
Teste de conversa natural com o agente 2W Pneus.
Simula um cliente comprando pneu traseiro para CG 160, entrega com dinheiro.
"""

import sys
import time
from agente_2w.db import sessao_repo, pedido_repo, cliente_repo
from agente_2w.db.pedido_repo import listar_itens_pedido
from agente_2w.enums.enums import EtapaFluxo, StatusSessao
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.engine.orquestrador import processar_turno

# ────────────────────────────────────────────────────────────────
# SCRIPT DE MENSAGENS — conversa simulada
# ────────────────────────────────────────────────────────────────
CONVERSA = [
    "fala meu amigo, tem pneu pra cg 160?",              # identificacao → busca
    "quero o traseiro",                                    # complemento de posicao
    "pode ser esse",                                       # aceita a opcao (oferta → confirmacao)
    "1 unidade, confirma",                                 # quantidade + confirmacao
    "quero entrega, pago no dinheiro",                    # entrega_pagamento
    "João Silva, Rua das Flores, 123, Bangu, Rio de Janeiro",  # nome + endereco
    "pode fechar",                                         # fechamento
]

CONTATO = "5554988887777"
PAUSA_ENTRE_TURNOS = 8  # segundos — evita estourar rate limit 30k TPM

SEP = "-" * 60


def run():
    print()
    print(SEP)
    print("  TESTE DE CONVERSA NATURAL - 2W Pneus")
    print(SEP)

    sessao = sessao_repo.criar_sessao(SessaoChatCreate(
        canal="cli",
        contato_externo=CONTATO,
        etapa_atual=EtapaFluxo.identificacao,
        status_sessao=StatusSessao.ativa,
    ))
    sessao_id = sessao.id
    print(f"  Sessao: {sessao_id}")
    print(f"  Contato: {CONTATO}")
    print()

    erros = []
    etapas = []

    for i, msg in enumerate(CONVERSA, 1):
        print(f"[Turno {i}/{len(CONVERSA)}]")
        print(f"  Cliente : {msg}")

        try:
            resposta = processar_turno(sessao_id, msg)
            print(f"  Agente  : {resposta}")
        except Exception as e:
            erro = f"Turno {i} EXCECAO: {e}"
            print(f"  [ERRO]  : {e}")
            erros.append(erro)

        sessao_atual = sessao_repo.buscar_sessao_por_id(sessao_id)
        if sessao_atual:
            etapa = sessao_atual.etapa_atual.value
            etapas.append(etapa)
            print(f"  Etapa   : {etapa}")

        print()

        if i < len(CONVERSA):
            time.sleep(PAUSA_ENTRE_TURNOS)

    # ────────────────────────────────────────────────────────────
    # VERIFICACAO DO BANCO
    # ────────────────────────────────────────────────────────────
    print(SEP)
    print("  VERIFICACAO DO BANCO DE DADOS")
    print(SEP)

    pedido = pedido_repo.buscar_pedido_por_sessao(sessao_id)
    if pedido:
        print(f"  [OK] Pedido criado: {pedido.id}")
        print(f"       Valor     : R${pedido.valor_total:.2f}")
        print(f"       Entrega   : {pedido.tipo_entrega}")
        print(f"       Pagamento : {pedido.forma_pagamento}")
        print(f"       Criado em : {pedido.criado_em}")

        itens = listar_itens_pedido(pedido.id)
        print(f"       Itens     : {len(itens)}")
        for it in itens:
            print(f"         - pneu_id={it.pneu_id}  qtd={it.quantidade}  posicao={it.posicao}  preco=R${it.preco_unitario:.2f}")
    else:
        erros.append("Nenhum pedido encontrado no banco apos conversa completa")
        print("  [FAIL] Nenhum pedido encontrado!")

    # Inteligencia de negocio do cliente
    print()
    print("  VERIFICACAO - INTELIGENCIA DE NEGOCIO DO CLIENTE")
    sessao_final = sessao_repo.buscar_sessao_por_id(sessao_id)
    if sessao_final and sessao_final.cliente_id:
        cliente = cliente_repo.buscar_cliente_por_id(sessao_final.cliente_id)
        if cliente:
            print(f"  segmento        : {cliente.segmento}")
            print(f"  total_pedidos   : {cliente.total_pedidos}")
            print(f"  valor_total_gasto: R${cliente.valor_total_gasto:.2f}")
            print(f"  ultima_compra_em: {cliente.ultima_compra_em}")
            print(f"  municipio       : {cliente.municipio}")
            print(f"  bairro          : {cliente.bairro}")

            if not cliente.nome:
                erros.append("nome do cliente nao foi salvo no banco")
                print("  [FAIL] nome = None — nao coletado")
            else:
                print(f"  [OK] nome coletado: {cliente.nome}")

            if cliente.total_pedidos == 0:
                erros.append("total_pedidos nao foi incrementado apos pedido")
                print("  [FAIL] total_pedidos = 0 — stats nao atualizados")
            else:
                print("  [OK] stats do cliente atualizados")

            if cliente.segmento not in ("novo", "recorrente", "vip"):
                erros.append(f"segmento invalido: {cliente.segmento}")
                print(f"  [FAIL] segmento invalido: {cliente.segmento}")
            else:
                print(f"  [OK] segmento valido: {cliente.segmento}")
        else:
            erros.append("Cliente nao encontrado no banco")
            print("  [FAIL] Cliente nao encontrado")
    else:
        erros.append("Sessao sem cliente_id apos conversa")
        print("  [FAIL] Sessao sem cliente_id")

    # ────────────────────────────────────────────────────────────
    # RELATORIO FINAL
    # ────────────────────────────────────────────────────────────
    print()
    print(SEP)
    print("  RELATORIO FINAL")
    print(SEP)
    print(f"  Sessao  : {sessao_id}")
    print(f"  Turnos  : {len(CONVERSA)}")
    print(f"  Etapas  : {' -> '.join(etapas)}")
    print()

    if erros:
        print(f"  RESULTADO: FAIL ({len(erros)} erro(s))")
        for e in erros:
            print(f"    - {e}")
        sys.exit(1)
    else:
        print("  RESULTADO: PASS - Conversa completa, pedido gravado no banco!")
        sys.exit(0)


if __name__ == "__main__":
    run()
