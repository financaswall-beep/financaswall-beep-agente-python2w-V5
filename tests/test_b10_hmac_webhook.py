"""
Teste B10 — HMAC webhook Chatwoot obrigatorio quando secret nao configurada.

Verifica:
1. Secret configurada + assinatura correta → 200
2. Secret configurada + assinatura errada → 401
3. Secret configurada + sem headers HMAC → 401
4. Secret ausente (vazia) → 401 (antes: passava como valid)
"""
import sys
import os
import hmac
import hashlib
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carrega .env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)

SECRET = "secret-de-teste-b10"

# Variaveis obrigatorias para import do app
os.environ["CHATWOOT_WEBHOOK_SECRET"] = SECRET
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "fake-key")
os.environ.setdefault("OPENAI_API_KEY", "fake-key")
os.environ.setdefault("OPENAI_MODEL", "gpt-4o")
os.environ.setdefault("CHATWOOT_BASE_URL", "http://fake-chatwoot.local")
os.environ.setdefault("CHATWOOT_API_TOKEN", "fake-token")
os.environ.setdefault("CHATWOOT_ACCOUNT_ID", "1")
os.environ.setdefault("CHATWOOT_INBOX_ID", "1")
os.environ.setdefault("INTERNAL_API_TOKEN", "fake-internal-token")

from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

with patch("agente_2w.db.client.supabase"), \
     patch("agente_2w.db.sessao_repo.buscar_sessao_por_id"), \
     patch("agente_2w.config.SUPABASE_URL", "https://fake.supabase.co"):
    from webhook_server import app, _verificar_assinatura, CHATWOOT_WEBHOOK_SECRET


def _assinar(body: bytes, secret: str, ts: str | None = None) -> tuple[str, str]:
    """Gera assinatura HMAC valida no formato Chatwoot (timestamp.body)."""
    ts = ts or str(int(time.time()))
    message = f"{ts}.".encode() + body
    sig = "sha256=" + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return ts, sig


def _assinar_body_only(body: bytes, secret: str) -> str:
    """Fallback defensivo para ambientes que assinem apenas o body."""
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------- testes de _verificar_assinatura diretamente ----------

def test_assinatura_correta_passa():
    import webhook_server as ws
    original = ws.CHATWOOT_WEBHOOK_SECRET
    ws.CHATWOOT_WEBHOOK_SECRET = SECRET
    try:
        body = b'{"event": "test"}'
        ts, sig = _assinar(body, SECRET)
        assert ws._verificar_assinatura(body, sig, ts) is True
        print("  [OK] Assinatura correta \u2192 True")
    finally:
        ws.CHATWOOT_WEBHOOK_SECRET = original


def test_assinatura_body_only_fallback_passa():
    import webhook_server as ws
    original = ws.CHATWOOT_WEBHOOK_SECRET
    ws.CHATWOOT_WEBHOOK_SECRET = SECRET
    try:
        body = b'{"event": "test"}'
        sig = _assinar_body_only(body, SECRET)
        assert _verificar_assinatura(body, sig) is True
        print("  [OK] Assinatura body-only fallback \u2192 True")
    finally:
        ws.CHATWOOT_WEBHOOK_SECRET = original


def test_assinatura_errada_falha():
    body = b'{"event": "test"}'
    assert _verificar_assinatura(body, "sha256=assinatura-invalida", "12345") is False
    print("  [OK] Assinatura errada → False")


def test_sem_headers_falha():
    body = b'{"event": "test"}'
    assert _verificar_assinatura(body, "", "") is False
    print("  [OK] Sem signature header → False")


def test_secret_ausente_bloqueia():
    """Sem secret configurada, _verificar_assinatura deve retornar False (B10)."""
    import webhook_server as ws
    original = ws.CHATWOOT_WEBHOOK_SECRET
    ws.CHATWOOT_WEBHOOK_SECRET = ""
    try:
        body = b'{"event": "test"}'
        result = ws._verificar_assinatura(body, "sha256=qualquer", "12345")
        assert result is False, f"Esperava False, got {result}"
        print("  [OK] Secret ausente → False (bloqueado)")
    finally:
        ws.CHATWOOT_WEBHOOK_SECRET = original


# ---------- teste via endpoint HTTP ----------

def _payload_valido() -> bytes:
    return json.dumps({
        "event": "message_created",
        "message_type": "incoming",
        "sender": {"phone_number": "+5521999999999", "name": "Teste"},
        "content": "oi",
        "conversation": {"id": 1},
        "account": {"id": 1},
        "inbox": {"id": 1},
    }).encode()


def test_endpoint_sem_assinatura_retorna_401():
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post("/webhook/chatwoot", content=_payload_valido())
        assert resp.status_code == 401, f"Esperava 401, got {resp.status_code}"
        print("  [OK] Endpoint sem assinatura → 401")


def test_endpoint_com_assinatura_valida_passa():
    body = _payload_valido()
    ts, sig = _assinar(body, SECRET)
    import webhook_server as ws
    original = ws.CHATWOOT_WEBHOOK_SECRET
    ws.CHATWOOT_WEBHOOK_SECRET = SECRET
    try:
        with patch("webhook_server.processar_turno", return_value=MagicMock(texto="ok", fotos=[])), \
             patch("webhook_server._enviar_mensagem_chatwoot", return_value=None), \
             patch("webhook_server._obter_ou_criar_sessao", return_value=MagicMock(id="s1", chatwoot_conv_id=1)), \
             patch("webhook_server._get_turno_lock"), \
             TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post(
                "/webhook/chatwoot",
                content=body,
                headers={
                    "x-chatwoot-signature": sig,
                    "x-chatwoot-timestamp": ts,
                    "Content-Type": "application/json",
                },
            )
        # 200 (processamento em background) ou qualquer 2xx
        assert resp.status_code == 200, f"Esperava 200, got {resp.status_code}"
        print("  [OK] Endpoint com assinatura valida \u2192 200")
    finally:
        ws.CHATWOOT_WEBHOOK_SECRET = original


if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    sys.exit(result.returncode)
