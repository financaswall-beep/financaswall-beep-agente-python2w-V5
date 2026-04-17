"""Script para inspecionar e configurar o segundo Chatwoot."""
import httpx
import json

BASE = "https://chatwoot.smarttecsolutions.com.br/api/v1/accounts/2"
HEADERS = {"api_access_token": "11JFDQAfQasYWiHK3V2E7pBQ", "Content-Type": "application/json"}
client = httpx.Client(timeout=15, verify=False)

def get(path):
    r = client.get(f"{BASE}{path}", headers=HEADERS)
    print(f"\n=== GET {path} -> {r.status_code} ===")
    return r

def pp(data):
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))

# 1. Labels
print("\n" + "="*60)
print("LABELS")
print("="*60)
r = get("/labels")
if r.status_code == 200:
    data = r.json()
    labels = data.get("payload", data) if isinstance(data, dict) else data
    for l in labels:
        print(f"  id={l.get('id')}  title=\"{l.get('title')}\"  show_on_sidebar={l.get('show_on_sidebar')}")
else:
    print(r.text[:500])

# 2. Custom Attributes
print("\n" + "="*60)
print("CUSTOM ATTRIBUTES")
print("="*60)
r = get("/custom_attribute_definitions")
if r.status_code == 200:
    data = r.json()
    attrs = data.get("data", data) if isinstance(data, dict) else data
    for a in attrs:
        print(f"  id={a.get('id')}  key=\"{a.get('attribute_key')}\"  model={a.get('attribute_model')}  type={a.get('attribute_display_type')}")
else:
    print(r.text[:500])

# 3. Teams
print("\n" + "="*60)
print("TEAMS")
print("="*60)
r = get("/teams")
if r.status_code == 200:
    data = r.json()
    teams = data if isinstance(data, list) else data.get("data", data.get("payload", []))
    if isinstance(teams, list):
        for t in teams:
            print(f"  id={t.get('id')}  name=\"{t.get('name')}\"")
    else:
        pp(data)
else:
    print(r.text[:500])

# 4. Inboxes
print("\n" + "="*60)
print("INBOXES")
print("="*60)
r = get("/inboxes")
if r.status_code == 200:
    data = r.json()
    inboxes = data.get("payload", data) if isinstance(data, dict) else data
    for i in inboxes:
        print(f"  id={i.get('id')}  name=\"{i.get('name')}\"  channel_type={i.get('channel_type')}")
else:
    print(r.text[:500])

# 5. Conversations (pra ver se tem Kanban/SLA)
print("\n" + "="*60)
print("CONVERSATIONS (sample)")
print("="*60)
r = get("/conversations?page=1")
if r.status_code == 200:
    data = r.json()
    meta = data.get("data", {}).get("meta", {})
    print(f"  Total: {meta}")
    convs = data.get("data", {}).get("payload", [])
    for c in convs[:3]:
        print(f"  id={c.get('id')}  status={c.get('status')}  priority={c.get('priority')}  labels={c.get('labels')}")
else:
    print(r.text[:500])

# 6. Automations
print("\n" + "="*60)
print("AUTOMATIONS")
print("="*60)
r = get("/automation_rules")
if r.status_code == 200:
    data = r.json()
    rules = data.get("payload", data) if isinstance(data, dict) else data
    if isinstance(rules, list):
        for ru in rules:
            print(f"  id={ru.get('id')}  name=\"{ru.get('name')}\"  active={ru.get('active')}")
    else:
        pp(data)
else:
    print(r.text[:500])

# 7. Agents
print("\n" + "="*60)
print("AGENTS")
print("="*60)
r = get("/agents")
if r.status_code == 200:
    data = r.json()
    agents = data if isinstance(data, list) else data.get("payload", data.get("data", []))
    if isinstance(agents, list):
        for ag in agents:
            print(f"  id={ag.get('id')}  name=\"{ag.get('name')}\"  role={ag.get('role')}  availability={ag.get('availability_status')}")
    else:
        pp(data)
else:
    print(r.text[:500])

print("\n\nFIM DA INSPEÇÃO")
