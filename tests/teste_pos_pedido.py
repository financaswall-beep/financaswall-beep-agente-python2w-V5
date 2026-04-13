"""Teste: comportamento pós-pedido no fechamento.

Fluxo: cumprimento → fazer dianteiro+traseiro → confirma → entrega+pix → 
       pedido criado → pede resumo (bug anterior: pedia confirmacao de novo)
       → agradece (bug anterior: "Valeu!" sem contexto)
"""

import logging
import sys
from uuid import UUID
from agente_2w.db import sessao_repo
from agente_2w.enums.enums import EtapaFluxo, StatusSessao
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.engine.orquestrador import processar_turno

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

CONTATO = "5521988887777"

def turno(sessao_id: UUID, msg: str) -> str:
    print(f"\n>>> Cliente: {msg}")
    resposta = processar_turno(sessao_id, msg)
    print(f"<<< Agente:  {resposta}")
    sessao = sessao_repo.buscar_sessao_por_id(sessao_id)
    print(f"    [etapa={sessao.etapa_atual.value}]")
    return resposta

def main():
    sessao = sessao_repo.criar_sessao(SessaoChatCreate(
        canal="cli_teste",
        contato_externo=CONTATO,
        etapa_atual=EtapaFluxo.identificacao,
        status_sessao=StatusSessao.ativa,
    ))
    sid = sessao.id
    print(f"\n=== SESSÃO: {sid} ===")
    print("Testando fluxo completo até fechamento + comportamento pós-pedido\n")

    turno(sid, "oi")
    turno(sid, "quero dianteiro e traseiro pra fazer")
    turno(sid, "fazer")
    turno(sid, "sim")
    turno(sid, "não")
    turno(sid, "entrega em niterói, pix")
    turno(sid, "rua das flores 100 centro niterói")
    turno(sid, "sim")  # confirmação do pedido

    print("\n" + "="*60)
    print("PEDIDO DEVE ESTAR CRIADO AGORA. Testando pós-pedido:")
    print("="*60)

    turno(sid, "pode resumir meu pedido")
    turno(sid, "valeu")

if __name__ == "__main__":
    main()
