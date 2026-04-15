import os
from dotenv import load_dotenv

load_dotenv(override=True)

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]

OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

# ─── Roteamento de modelos (2 tiers) ──────────────────────────────────────────
# MINI  : ~70% dos turnos (turnos normais). Barato e rapido.
# FLAGSHIP: retries e mensagens com imagem. Mais inteligente.
# Rollback : sete OPENAI_MODEL_MINI=gpt-4o para desligar roteamento sem tocar codigo.
OPENAI_MODEL_MINI: str = os.getenv("OPENAI_MODEL_MINI", OPENAI_MODEL)
OPENAI_MODEL_FLAGSHIP: str = os.getenv("OPENAI_MODEL_FLAGSHIP", OPENAI_MODEL)

# ─── Limites de execucao ──────────────────────────────────────────────────────
# Quantos retries a IA ganha quando o envelope vem invalido
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))

# Quantos rounds de tool calls a IA pode fazer em um unico turno
MAX_TOOL_ROUNDS: int = int(os.getenv("MAX_TOOL_ROUNDS", "5"))

# --- Chatwoot (opcional -- agente funciona sem) ---
CHATWOOT_BASE_URL: str = os.getenv("CHATWOOT_BASE_URL", "").rstrip("/")
CHATWOOT_API_TOKEN: str = os.getenv("CHATWOOT_API_TOKEN", "")
CHATWOOT_ACCOUNT_ID: str = os.getenv("CHATWOOT_ACCOUNT_ID", "1")
CHATWOOT_TEAM_VENDAS_ID: int = int(os.getenv("CHATWOOT_TEAM_VENDAS_ID", "0"))
