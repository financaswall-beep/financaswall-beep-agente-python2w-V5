"""Teste rapido: injeta buscas no log_demanda_pneu e verifica views."""
from uuid import UUID
from agente_2w.tools.busca_catalogo import buscar_pneus_por_moto, buscar_pneus

# Usar sessao real para evitar FK violation
fake_sessao = UUID("d5729c77-8542-475a-b721-a6721cb0fa57")
print(f"Sessao fake: {fake_sessao}")

# 1. Busca por moto
r1 = buscar_pneus_por_moto("CG 160", posicao="traseiro", sessao_id=fake_sessao)
qtd1 = r1.get("quantidade", 0)
print(f"[1] buscar_pneus_por_moto CG 160 traseiro: {qtd1} resultados")

# 2. Busca por medida (fix de hoje)
r2 = buscar_pneus(medida_texto="130/70-13", sessao_id=fake_sessao)
print(f"[2] buscar_pneus 130/70-13: {r2['quantidade']} resultados")

# 3. Busca por marca
r3 = buscar_pneus(marca_modelo="Pirelli", sessao_id=fake_sessao)
print(f"[3] buscar_pneus Pirelli: {r3['quantidade']} resultados")

# 4. Busca por dimensoes
r4 = buscar_pneus(largura=110, perfil=80, aro=14, sessao_id=fake_sessao)
print(f"[4] buscar_pneus 110/80-14: {r4['quantidade']} resultados")

print(f"\n4 buscas injetadas. Verificando log_demanda_pneu...")

# Verificar registros
from agente_2w.db.client import supabase
rows = (
    supabase.table("log_demanda_pneu")
    .select("moto,posicao,largura,perfil,aro,sessao_id,tinha_estoque,fonte_resolucao")
    .eq("sessao_id", str(fake_sessao))
    .execute()
)
print(f"\nRegistros com sessao_id={fake_sessao}: {len(rows.data)}")
for r in rows.data:
    print(f"  moto={r['moto']!r:15} pos={r['posicao']!r:12} medida={r['largura']}/{r['perfil']}-{r['aro']}  estoque={r['tinha_estoque']}  fonte={r['fonte_resolucao']}")

# Verificar views
print("\n--- v_demanda_semanal ---")
v1 = supabase.table("v_demanda_semanal").select("*").execute()
for r in v1.data:
    print(f"  {r}")

print("\n--- v_demanda_mensal ---")
v2 = supabase.table("v_demanda_mensal").select("*").execute()
for r in v2.data:
    print(f"  {r}")

print("\n--- v_conversao_por_pneu ---")
v3 = supabase.table("v_conversao_por_pneu").select("*").execute()
for r in v3.data:
    print(f"  {r}")

# Registros mantidos para visualização no sistema
print(f"\nRegistros mantidos (nao removidos).")
