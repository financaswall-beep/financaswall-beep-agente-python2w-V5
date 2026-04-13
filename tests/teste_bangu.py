"""
Teste de conversa simulando cliente que diz "entrega em bangu"
sem digitar CEP — valida que o agente resolve o município
automaticamente via web_search e calcula o frete corretamente.
"""

import sys
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from agente_2w.db import sessao_repo, pedido_repo, cliente_repo, contexto_repo
from agente_2w.enums.enums import EtapaFluxo, StatusSessao
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.engine.orquestrador import processar_turno
from agente_2w.constantes import ChaveContexto

CONVERSA = [
    "oi, tem pneu pra cg 160?",
    "quero o traseiro",
    "pode ser esse",
    "1 unidade confirma",
    "quero entrega, pago no dinheiro",
    "Carlos, Rua das Acácias 45, Bangu",   # <- bairro sem CEP, sem "Rio de Janeiro"
    "pode fechar",
]

CONTATO = "5521988880001"
PAUSA = 8

SEP = "-" * 60


def run():
    print()
    print(SEP)
    print("  TESTE BANGU — resolução automática de bairro")
    print(SEP)
    print()

    sessao = sessao_repo.criar_sessao(SessaoChatCreate(
        canal="cli",
        contato_externo=CONTATO,
        etapa_atual=EtapaFluxo.identificacao,
        status_sessao=StatusSessao.ativa,
    ))
    sessao_id = sessao.id
    print(f"  Sessao: {sessao_id}")
    print()

    erros = []

    for i, msg in enumerate(CONVERSA, 1):
        print(f"[Turno {i}/{len(CONVERSA)}]")
        print(f"  Cliente : {msg}")
        try:
            resposta = processar_turno(sessao_id, msg)
            print(f"  Agente  : {resposta}")
        except Exception as e:
            print(f"  [ERRO]  : {e}")
            erros.append(f"Turno {i}: {e}")

        s = sessao_repo.buscar_sessao_por_id(sessao_id)
        if s:
            print(f"  Etapa   : {s.etapa_atual.value}")
        print()

        if i < len(CONVERSA):
            time.sleep(PAUSA)

    # ── Verificações ─────────────────────────────────────────────
    print(SEP)
    print("  VERIFICAÇÕES")
    print(SEP)

    # 1. Frete foi calculado (não deve ter frete_nao_coberto)
    fato_frete = contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.FRETE_VALOR)
    fato_nc = contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.FRETE_NAO_COBERTO)

    if fato_frete:
        print(f"  [OK] Frete calculado: R${fato_frete.valor_texto}")
    else:
        msg = "frete_valor não registrado — resolver pode ter falhado"
        print(f"  [FAIL] {msg}")
        erros.append(msg)

    if fato_nc:
        msg = f"frete_nao_coberto registrado indevidamente: '{fato_nc.valor_texto}'"
        print(f"  [FAIL] {msg}")
        erros.append(msg)
    else:
        print("  [OK] frete_nao_coberto não registrado (correto)")

    # 2. Pedido criado
    pedido = pedido_repo.buscar_pedido_por_sessao(sessao_id)
    if pedido:
        print(f"  [OK] Pedido criado: {pedido.id} — R${pedido.valor_total:.2f}")
    else:
        msg = "Pedido não encontrado no banco"
        print(f"  [FAIL] {msg}")
        erros.append(msg)

    # 3. Cliente com municipio=Rio de Janeiro
    s_final = sessao_repo.buscar_sessao_por_id(sessao_id)
    if s_final and s_final.cliente_id:
        cliente = cliente_repo.buscar_cliente_por_id(s_final.cliente_id)
        if cliente:
            print(f"  municipio cliente: {cliente.municipio}")
            print(f"  bairro    cliente: {cliente.bairro}")
            if cliente.municipio and "rio de janeiro" in cliente.municipio.lower():
                print("  [OK] municipio resolvido para Rio de Janeiro")
            else:
                msg = f"municipio esperado 'Rio de Janeiro', got '{cliente.municipio}'"
                print(f"  [FAIL] {msg}")
                erros.append(msg)

    print()
    print(SEP)
    if erros:
        print(f"  RESULTADO: FAIL ({len(erros)} erro(s))")
        for e in erros:
            print(f"    - {e}")
        sys.exit(1)
    else:
        print("  RESULTADO: PASS — Bangu resolvido, frete calculado, pedido criado! 🎉")
        sys.exit(0)


if __name__ == "__main__":
    run()
