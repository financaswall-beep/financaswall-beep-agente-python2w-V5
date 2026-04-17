import httpx, json

client = httpx.Client(timeout=10, verify=False)

# Webhook configurado no Chatwoot: n8n-coolify.smarttecsolutions.com.br
# O agente Python deve estar em alguma URL no mesmo servidor (Coolify)

print("=== TESTANDO URLs PROVÁVEIS DO AGENTE ===")
urls_candidatas = [
    "https://agente-2w.smarttecsolutions.com.br/health",
    "https://agente.smarttecsolutions.com.br/health",
    "https://2w.smarttecsolutions.com.br/health",
    "https://bot.smarttecsolutions.com.br/health",
    "https://api.smarttecsolutions.com.br/health",
    "https://webhook.smarttecsolutions.com.br/health",
    "https://pneus.smarttecsolutions.com.br/health",
    "https://agente-pneus.smarttecsolutions.com.br/health",
]
for url in urls_candidatas:
    try:
        r = client.get(url, timeout=5)
        print(f"OK  {url} -> {r.status_code} | {r.text[:150]}")
    except Exception as e:
        print(f"ERR {url} -> {type(e).__name__}: {str(e)[:60]}")

print("\n=== DETALHES DO WEBHOOK N8N ===")
BASE = "https://chatwoot.smarttecsolutions.com.br/api/v1/accounts/2"
HEADERS = {"api_access_token": "11JFDQAfQasYWiHK3V2E7pBQ", "Content-Type": "application/json"}
r = client.get(f"{BASE}/webhooks", headers=HEADERS)
data = r.json().get("payload", {}).get("webhooks", [])
for w in data:
    print(json.dumps(w, indent=2))
