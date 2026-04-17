"""Apaga labels antigas e cria labels + custom attrs do agente 2W."""
import httpx, json, sys

BASE = "https://chatwoot.smarttecsolutions.com.br/api/v1/accounts/2"
HEADERS = {"api_access_token": "11JFDQAfQasYWiHK3V2E7pBQ", "Content-Type": "application/json"}
client = httpx.Client(timeout=15, verify=False)

# ── 1. APAGAR TODAS AS LABELS EXISTENTES ──────────────────────────────────
print("=== APAGANDO LABELS ANTIGAS ===")
r = client.get(f"{BASE}/labels", headers=HEADERS)
r.raise_for_status()
labels = r.json().get("payload", r.json()) if isinstance(r.json(), dict) else r.json()
for l in labels:
    lid = l["id"]
    title = l["title"]
    dr = client.delete(f"{BASE}/labels/{lid}", headers=HEADERS)
    status = "OK" if dr.status_code in (200, 204) else f"ERRO {dr.status_code}"
    print(f"  Apagada: {title} (id={lid}) -> {status}")

# ── 2. CRIAR LABELS DO NOSSO AGENTE (funil Kanban) ────────────────────────
print("\n=== CRIANDO LABELS DO AGENTE ===")
LABELS_AGENTE = [
    {"title": "identificacao",    "description": "Cliente em fase de identificação",      "color": "#1B83D6", "show_on_sidebar": True},
    {"title": "buscando",         "description": "Buscando pneus no catálogo",            "color": "#F59E0B", "show_on_sidebar": True},
    {"title": "oferta_enviada",   "description": "Oferta de preço enviada ao cliente",     "color": "#8B5CF6", "show_on_sidebar": True},
    {"title": "confirmando_item", "description": "Cliente confirmando itens do pedido",    "color": "#EC4899", "show_on_sidebar": True},
    {"title": "dados_entrega",    "description": "Coletando dados de entrega/pagamento",   "color": "#F97316", "show_on_sidebar": True},
    {"title": "em_fechamento",    "description": "Pedido em fase de fechamento",           "color": "#10B981", "show_on_sidebar": True},
    {"title": "pedido_criado",    "description": "Pedido criado com sucesso",              "color": "#22C55E", "show_on_sidebar": True},
    {"title": "pedido_cancelado", "description": "Pedido cancelado pelo cliente",          "color": "#EF4444", "show_on_sidebar": True},
]

for lb in LABELS_AGENTE:
    r = client.post(f"{BASE}/labels", json=lb, headers=HEADERS)
    status = "OK" if r.status_code in (200, 201) else f"ERRO {r.status_code}: {r.text[:200]}"
    print(f"  Criada: {lb['title']} -> {status}")

# ── 3. APAGAR CUSTOM ATTRS ANTIGOS QUE NÃO SERVEM ────────────────────────
print("\n=== LIMPANDO CUSTOM ATTRIBUTES ANTIGOS ===")
r = client.get(f"{BASE}/custom_attribute_definitions", headers=HEADERS)
r.raise_for_status()
data = r.json()
attrs_existentes = data.get("data", data) if isinstance(data, dict) else data

# Manter 'ultima_compra' (id=8), apagar os outros
MANTER = {"ultima_compra"}
for a in attrs_existentes:
    key = a.get("attribute_key", "")
    aid = a["id"]
    if key in MANTER:
        print(f"  Mantido: {key} (id={aid})")
        continue
    dr = client.delete(f"{BASE}/custom_attribute_definitions/{aid}", headers=HEADERS)
    status = "OK" if dr.status_code in (200, 204) else f"ERRO {dr.status_code}"
    print(f"  Apagado: {key} (id={aid}) -> {status}")

# ── 4. CRIAR CUSTOM ATTRIBUTES DO AGENTE ──────────────────────────────────
print("\n=== CRIANDO CUSTOM ATTRIBUTES DO AGENTE ===")
CUSTOM_ATTRS = [
    # Contato
    {"attribute_display_name": "Segmento",          "attribute_display_type": 0, "attribute_description": "Segmento do cliente",      "attribute_model": 0, "attribute_key": "segmento"},
    {"attribute_display_name": "Total Pedidos",      "attribute_display_type": 1, "attribute_description": "Quantidade total de pedidos", "attribute_model": 0, "attribute_key": "total_pedidos"},
    {"attribute_display_name": "Valor Total Gasto",  "attribute_display_type": 0, "attribute_description": "Valor total gasto pelo cliente", "attribute_model": 0, "attribute_key": "valor_total_gasto"},
    # Conversa
    {"attribute_display_name": "Número Pedido",      "attribute_display_type": 1, "attribute_description": "Número do pedido",         "attribute_model": 1, "attribute_key": "numero_pedido"},
    {"attribute_display_name": "Valor Total",         "attribute_display_type": 0, "attribute_description": "Valor total do pedido",     "attribute_model": 1, "attribute_key": "valor_total"},
    {"attribute_display_name": "Forma Pagamento",     "attribute_display_type": 0, "attribute_description": "Forma de pagamento",        "attribute_model": 1, "attribute_key": "forma_pagamento"},
    {"attribute_display_name": "Tipo Entrega",        "attribute_display_type": 0, "attribute_description": "Tipo de entrega",           "attribute_model": 1, "attribute_key": "tipo_entrega"},
    {"attribute_display_name": "Município",           "attribute_display_type": 0, "attribute_description": "Município de entrega",      "attribute_model": 1, "attribute_key": "municipio"},
]

for ca in CUSTOM_ATTRS:
    r = client.post(f"{BASE}/custom_attribute_definitions", json=ca, headers=HEADERS)
    status = "OK" if r.status_code in (200, 201) else f"ERRO {r.status_code}: {r.text[:200]}"
    print(f"  Criado: {ca['attribute_key']} ({['contato','conversa'][ca['attribute_model']]}) -> {status}")

# ── 5. VALIDAÇÃO FINAL ────────────────────────────────────────────────────
print("\n=== VALIDAÇÃO FINAL ===")
r = client.get(f"{BASE}/labels", headers=HEADERS)
labels_final = r.json().get("payload", r.json()) if isinstance(r.json(), dict) else r.json()
print(f"\nLabels ({len(labels_final)}):")
for l in labels_final:
    print(f"  ✓ {l['title']}")

r = client.get(f"{BASE}/custom_attribute_definitions", headers=HEADERS)
attrs_final = r.json().get("data", r.json()) if isinstance(r.json(), dict) else r.json()
print(f"\nCustom Attributes ({len(attrs_final)}):")
for a in attrs_final:
    print(f"  ✓ {a['attribute_key']} ({a['attribute_model']})")

print("\nCONCLUÍDO!")
