import httpx, json

client = httpx.Client(timeout=10, verify=False)
BASE = "https://chatwoot.smarttecsolutions.com.br/api/v1/accounts/2"
HEADERS = {"api_access_token": "11JFDQAfQasYWiHK3V2E7pBQ", "Content-Type": "application/json"}

# Tentar vários endpoints de webhook do Chatwoot
print("=== BUSCANDO WEBHOOK DO AGENTE ===")
endpoints = [
    "/integrations/webhooks",
    "/webhooks",
    "/settings/integrations/webhook",
    "/integrations",
]
for ep in endpoints:
    r = client.get(f"{BASE}{ep}", headers=HEADERS)
    print(f"{ep} -> {r.status_code} | {r.text[:200]}")
    print()

# Verificar conversa mais recente para ver de onde veio
print("=== ULTIMA CONVERSA ===")
r = client.get(f"{BASE}/conversations?page=1&assignee_type=all", headers=HEADERS)
data = r.json().get("data", {}).get("payload", [])
for conv in data[:2]:
    cid = conv["id"]
    print(f"Conv {cid}: inbox_id={conv.get('inbox_id')} channel={conv.get('channel')}")
    # Pegar mensagens
    rm = client.get(f"{BASE}/conversations/{cid}/messages", headers=HEADERS)
    msgs = rm.json().get("payload", {})
    if isinstance(msgs, dict):
        msgs = msgs.get("messages", [])
    for m in msgs[-5:]:
        content = m.get("content", "")[:80]
        mtype = m.get("message_type")
        sender = m.get("sender", {}).get("name", "?") if m.get("sender") else "?"
        print(f"  [{mtype}] {sender}: {content}")
