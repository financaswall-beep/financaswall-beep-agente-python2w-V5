import httpx, json

client = httpx.Client(timeout=10, verify=False)
BASE = "https://chatwoot.smarttecsolutions.com.br/api/v1/accounts/2"
HEADERS = {"api_access_token": "11JFDQAfQasYWiHK3V2E7pBQ", "Content-Type": "application/json"}

# Inboxes e webhook URLs
r = client.get(f"{BASE}/inboxes", headers=HEADERS)
inboxes = r.json().get("payload", [])
print("=== INBOXES ===")
for inbox in inboxes:
    print(f"id={inbox['id']} name={inbox['name']}")
    print(f"  webhook_url: {inbox.get('webhook_url', 'NAO CONFIGURADO')}")
    print(f"  channel_type: {inbox.get('channel_type')}")
    print()

# Testar URL do agente - tentar pegar health do servidor
print("=== TESTANDO HEALTH DO SERVIDOR AGENTE ===")
# URL provável com base no nosso Coolify
urls_candidatas = [
    "https://agente.smarttecsolutions.com.br/health",
    "https://agente-2w.smarttecsolutions.com.br/health",
    "https://api.smarttecsolutions.com.br/health",
]
for url in urls_candidatas:
    try:
        r2 = client.get(url, timeout=5)
        print(f"{url} -> {r2.status_code} | {r2.text[:100]}")
    except Exception as e:
        print(f"{url} -> ERRO: {e}")
