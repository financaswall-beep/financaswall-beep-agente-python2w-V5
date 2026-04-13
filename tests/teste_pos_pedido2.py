"""Teste direto: sessao com pedido ja criado.
Usa a sessao 622a00e3 que ja tem pedido #1119 em fechamento.
Testa exatamente o bug: pedir resumo e agradecer apos pedido criado.
"""
import logging
from uuid import UUID
from agente_2w.db import sessao_repo, pedido_repo
from agente_2w.engine.orquestrador import processar_turno

logging.basicConfig(level=logging.WARNING)

SESSAO_ID = UUID("622a00e3-dae9-4888-b633-841fa1af20f7")

def turno(sid, msg):
    print(f"\n>>> Cliente: {msg}")
    resp = processar_turno(sid, msg)
    print(f"<<< Agente:  {resp}")
    sessao = sessao_repo.buscar_sessao_por_id(sid)
    pedido = pedido_repo.buscar_pedido_por_sessao(sid)
    print(f"    [etapa={sessao.etapa_atual.value} | pedido={'#'+str(pedido.numero_pedido) if pedido else 'none'}]")
    return resp

def main():
    sessao = sessao_repo.buscar_sessao_por_id(SESSAO_ID)
    pedido = pedido_repo.buscar_pedido_por_sessao(SESSAO_ID)
    print(f"=== Sessao: {SESSAO_ID} ===")
    print(f"    Etapa: {sessao.etapa_atual.value} | Status: {sessao.status_sessao.value}")
    print(f"    Pedido: {'#'+str(pedido.numero_pedido)+' ('+pedido.status_pedido.value+')' if pedido else 'nenhum'}")
    print("\nCenario 1: cliente pede resumo do pedido (antes: pedia confirmacao de novo)")
    r1 = turno(SESSAO_ID, "pode me resumir o pedido?")

    print("\nCenario 2: cliente agradece (antes: resposta vaga)")
    r2 = turno(SESSAO_ID, "valeu demais!")

    print("\nCenario 3: cliente pergunta sobre entrega")
    r3 = turno(SESSAO_ID, "quando chega?")

    print("\n" + "="*60)
    print("RESULTADO:")
    print(f"  Resumo: {'OK - nao pediu confirmacao' if 'confirma' not in r1.lower() else 'FALHOU - pediu confirmacao de novo'}")
    print(f"  Agradecimento: {'OK' if 'valeu' in r2.lower() or 'obrigad' in r2.lower() or '#1119' in r2 else 'VERIFICAR: ' + r2[:80]}")

if __name__ == "__main__":
    main()
