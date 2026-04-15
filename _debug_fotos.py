"""Debug de fotos — roda sequência automática e mostra tudo."""
import logging
import sys
from uuid import UUID

# Ativar logs DEBUG para ver o que acontece
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
# Silenciar logs de libs externas
for lib in ("httpx", "httpcore", "openai", "supabase", "postgrest"):
    logging.getLogger(lib).setLevel(logging.WARNING)

from agente_2w.db import sessao_repo
from agente_2w.db.client import supabase
from agente_2w.enums.enums import EtapaFluxo, StatusSessao
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.engine.orquestrador._nucleo import processar_turno

CONTATO = "5521_debug_foto_01"

# Limpar sessão anterior se existir
_anterior = (
    supabase.table("sessao_chat")
    .select("id")
    .eq("contato_externo", CONTATO)
    .eq("status_sessao", "ativa")
    .execute()
)
if _anterior.data:
    for s in _anterior.data:
        supabase.table("sessao_chat").update({"status_sessao": "fechada"}).eq("id", s["id"]).execute()
    print(f"[DEBUG] {len(_anterior.data)} sessão(ões) anterior(es) encerrada(s)")

# Criar nova sessão
nova = sessao_repo.criar_sessao(SessaoChatCreate(
    canal="debug_cli",
    contato_externo=CONTATO,
    etapa_atual=EtapaFluxo.identificacao,
    status_sessao=StatusSessao.ativa,
))
SESSAO_ID = nova.id
print(f"\n[DEBUG] Sessão criada: {SESSAO_ID}")
print("=" * 70)


def turno(msg: str):
    print(f"\n>>> Cliente: {msg}")
    print("-" * 50)
    resposta = processar_turno(SESSAO_ID, msg)
    print(f"\n<<< Agente: {resposta.texto}")
    print(f"\n    [FOTOS]: {resposta.fotos}")
    print(f"    [VIDEOS]: {resposta.videos}")
    print("=" * 70)
    return resposta


# --- Sequência de debug ---

print("\n[TURNO 1] Identificação")
turno("oi, meu nome é João, quero pneu")

print("\n[TURNO 2] Busca por dimensão com foto")
turno("preciso de um 110/70-14")

print("\n[TURNO 3] Pede foto explicitamente")
turno("manda foto")

print("\n[TURNO 4] Pede foto de outra forma")
turno("tem foto desse pneu?")

print("\n\n[FIM DO DEBUG]")
