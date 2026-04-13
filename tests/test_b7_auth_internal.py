"""
Teste B7 — middleware de autenticacao para endpoints /internal/*.

Usa TestClient do FastAPI (sem precisar subir servidor de verdade).
Verifica:
1. Sem token → 401
2. Token errado → 401
3. Token correto → passa (endpoint responde normalmente)
4. Endpoint /webhook (nao-interno) → nao exige token
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Token deve ser lido do .env real (load_dotenv(override=True) sobrescreve os.environ)
# Carrega o .env antes de importar o app para pegar o valor real
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)
TOKEN = os.environ.get("INTERNAL_API_TOKEN", "token-de-teste-b7-fallback")

# Garante que as variaveis obrigatorias existam para o import nao explodir
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "fake-key")
os.environ.setdefault("OPENAI_API_KEY", "fake-key")
os.environ.setdefault("OPENAI_MODEL", "gpt-4o")
os.environ.setdefault("CHATWOOT_BASE_URL", "http://fake-chatwoot.local")
os.environ.setdefault("CHATWOOT_API_TOKEN", "fake-token")
os.environ.setdefault("CHATWOOT_ACCOUNT_ID", "1")
os.environ.setdefault("CHATWOOT_INBOX_ID", "1")
os.environ.setdefault("CHATWOOT_WEBHOOK_SECRET", "")

from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

# Mock das dependencias de banco/IA antes de importar o app
with patch("agente_2w.db.client.supabase"), \
     patch("agente_2w.db.sessao_repo.buscar_sessao_por_id"), \
     patch("agente_2w.config.SUPABASE_URL", "https://fake.supabase.co"):
    from webhook_server import app


def _client():
    return TestClient(app, raise_server_exceptions=False)


def test_sem_token_retorna_401():
    with _client() as c:
        resp = c.post("/internal/sync-etapa", json={})
        assert resp.status_code == 401, f"Esperava 401, got {resp.status_code}"
        print("  [OK] Sem token → 401")


def test_token_errado_retorna_401():
    with _client() as c:
        resp = c.post(
            "/internal/sync-etapa",
            json={},
            headers={"Authorization": "Bearer token-errado-completamente"},
        )
        assert resp.status_code == 401, f"Esperava 401, got {resp.status_code}"
        print("  [OK] Token errado → 401")


def test_token_correto_passa_middleware():
    with _client() as c:
        resp = c.post(
            "/internal/sync-etapa",
            json={},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        # O endpoint em si pode retornar qualquer coisa (200, 422, 500)
        # O que importa e que NAO seja 401 (middleware deixou passar)
        assert resp.status_code != 401, f"Middleware bloqueou token correto! status={resp.status_code}"
        print(f"  [OK] Token correto → middleware passou (status={resp.status_code})")


def test_endpoint_nao_interno_nao_exige_token():
    with _client() as c:
        resp = c.get("/health")
        # /health nao exige token — pode retornar 200 ou 503 (banco fake), mas nao 401
        assert resp.status_code != 401, f"Middleware bloqueou /health sem motivo! status={resp.status_code}"
        print(f"  [OK] /health sem token → nao bloqueado (status={resp.status_code})")


def main():
    print("\n=== Teste B7: middleware autenticacao /internal/* ===\n")
    try:
        print("1. Chamada sem token...")
        test_sem_token_retorna_401()

        print("2. Chamada com token errado...")
        test_token_errado_retorna_401()

        print("3. Chamada com token correto...")
        test_token_correto_passa_middleware()

        print("4. Endpoint publico /health sem token...")
        test_endpoint_nao_interno_nao_exige_token()

        print("\n✓ Todos os testes B7 passaram.\n")
    except AssertionError as e:
        print(f"\n✗ FALHOU: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
