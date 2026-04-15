"""CLI interativo para testar o agente localmente."""
import sys
from agente_2w.db import sessao_repo
from agente_2w.enums.enums import EtapaFluxo, StatusSessao
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.engine.orquestrador._nucleo import processar_turno

CONTATO = sys.argv[1] if len(sys.argv) > 1 else "5521999000099"

# Buscar sessao ativa existente ou criar nova
_sessoes = (
    __import__("agente_2w.db.client", fromlist=["supabase"]).supabase
    .table("sessao_chat")
    .select("id")
    .eq("contato_externo", CONTATO)
    .eq("status_sessao", "ativa")
    .order("criado_em", desc=True)
    .limit(1)
    .execute()
)
if _sessoes.data:
    from uuid import UUID
    SESSAO_ID = UUID(_sessoes.data[0]["id"])
else:
    _nova = sessao_repo.criar_sessao(SessaoChatCreate(
        canal="teste_cli",
        contato_externo=CONTATO,
        etapa_atual=EtapaFluxo.identificacao,
        status_sessao=StatusSessao.ativa,
    ))
    SESSAO_ID = _nova.id

print("=" * 60)
print("AGENTE 2W PNEUS — teste interativo")
print(f"sessao: {SESSAO_ID}  |  contato: {CONTATO}")
print("Digite sua mensagem. 'sair' para encerrar.")
print("=" * 60)

while True:
    try:
        msg = input("\nVocê: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nEncerrando.")
        break
    if msg.lower() in ("sair", "exit", "quit"):
        break
    if not msg:
        continue
    resposta = processar_turno(SESSAO_ID, msg)
    print(f"\nAgente: {resposta.texto}")
