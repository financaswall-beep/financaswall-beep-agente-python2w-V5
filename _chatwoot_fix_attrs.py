"""Corrige custom attributes que ficaram com model invertido."""
import httpx

BASE = "https://chatwoot.smarttecsolutions.com.br/api/v1/accounts/2"
HEADERS = {"api_access_token": "11JFDQAfQasYWiHK3V2E7pBQ", "Content-Type": "application/json"}
client = httpx.Client(timeout=15, verify=False)

# 1. Apagar todos os custom attrs errados (manter ultima_compra que já estava certo)
print("=== APAGANDO ATTRS COM MODEL INVERTIDO ===")
r = client.get(f"{BASE}/custom_attribute_definitions", headers=HEADERS)
r.raise_for_status()
attrs = r.json().get("data", r.json()) if isinstance(r.json(), dict) else r.json()

MANTER = {"ultima_compra"}
for a in attrs:
    key = a.get("attribute_key", "")
    aid = a["id"]
    if key in MANTER:
        print(f"  Mantido: {key} (id={aid}) model={a['attribute_model']}")
        continue
    dr = client.delete(f"{BASE}/custom_attribute_definitions/{aid}", headers=HEADERS)
    status = "OK" if dr.status_code in (200, 204) else f"ERRO {dr.status_code}"
    print(f"  Apagado: {key} (id={aid}) -> {status}")

# 2. Recriar com model correto: 1=contact, 0=conversation
print("\n=== RECRIANDO COM MODEL CORRETO ===")
CUSTOM_ATTRS = [
    # Contato (model=1)
    {"attribute_display_name": "Segmento",          "attribute_display_type": 0, "attribute_description": "Segmento do cliente",          "attribute_model": 1, "attribute_key": "segmento"},
    {"attribute_display_name": "Total Pedidos",      "attribute_display_type": 1, "attribute_description": "Quantidade total de pedidos",   "attribute_model": 1, "attribute_key": "total_pedidos"},
    {"attribute_display_name": "Valor Total Gasto",  "attribute_display_type": 0, "attribute_description": "Valor total gasto pelo cliente","attribute_model": 1, "attribute_key": "valor_total_gasto"},
    # Conversa (model=0)
    {"attribute_display_name": "Número Pedido",      "attribute_display_type": 1, "attribute_description": "Número do pedido",             "attribute_model": 0, "attribute_key": "numero_pedido"},
    {"attribute_display_name": "Valor Total",         "attribute_display_type": 0, "attribute_description": "Valor total do pedido",        "attribute_model": 0, "attribute_key": "valor_total"},
    {"attribute_display_name": "Forma Pagamento",     "attribute_display_type": 0, "attribute_description": "Forma de pagamento",           "attribute_model": 0, "attribute_key": "forma_pagamento"},
    {"attribute_display_name": "Tipo Entrega",        "attribute_display_type": 0, "attribute_description": "Tipo de entrega",              "attribute_model": 0, "attribute_key": "tipo_entrega"},
    {"attribute_display_name": "Município",           "attribute_display_type": 0, "attribute_description": "Município de entrega",         "attribute_model": 0, "attribute_key": "municipio"},
]

for ca in CUSTOM_ATTRS:
    model_label = "contato" if ca["attribute_model"] == 1 else "conversa"
    r = client.post(f"{BASE}/custom_attribute_definitions", json=ca, headers=HEADERS)
    status = "OK" if r.status_code in (200, 201) else f"ERRO {r.status_code}: {r.text[:200]}"
    print(f"  Criado: {ca['attribute_key']} ({model_label}) -> {status}")

# 3. Validação
print("\n=== VALIDAÇÃO FINAL ===")
r = client.get(f"{BASE}/custom_attribute_definitions", headers=HEADERS)
attrs_final = r.json().get("data", r.json()) if isinstance(r.json(), dict) else r.json()
print(f"\nCustom Attributes ({len(attrs_final)}):")
for a in attrs_final:
    print(f"  {a['attribute_key']} -> {a['attribute_model']}")

print("\nOK!")
