"""Teste da Fase 4 — Tools."""
import sys
sys.path.insert(0, ".")

resultados = []

def teste(nome, fn):
    try:
        r = fn()
        resultados.append(("PASS", nome))
        return r
    except Exception as e:
        resultados.append(("FAIL", nome, str(e)))
        return None

print("=" * 60)
print("TESTE FASE 4: TOOLS")
print("=" * 60)

# --- TOOL 1: busca_catalogo ---
print("\n--- busca_catalogo ---")

from agente_2w.tools.busca_catalogo import buscar_pneus, buscar_pneus_por_moto, buscar_detalhes_pneu

r1 = teste("buscar_pneus(aro=17)", lambda: buscar_pneus(aro=17))
if r1:
    print(f"  -> {r1['quantidade']} pneus encontrados")

r2 = teste("buscar_pneus(medida_texto='100/80')", lambda: buscar_pneus(medida_texto="100/80"))
if r2:
    print(f"  -> {r2['quantidade']} pneus encontrados")

r3 = teste("buscar_pneus_por_moto('CG 160')", lambda: buscar_pneus_por_moto("CG 160"))
if r3:
    print(f"  -> {r3['quantidade']} compatibilidades")

# Pegar um pneu_id real
pneu_id_real = None
if r1 and r1["pneus"]:
    pneu_id_real = r1["pneus"][0].get("pneu_id") or r1["pneus"][0].get("id")
    print(f"  pneu_id para detalhe: {pneu_id_real}")

if pneu_id_real:
    r4 = teste("buscar_detalhes_pneu(real)", lambda: buscar_detalhes_pneu(str(pneu_id_real)))
    if r4:
        tem_estoque = "sim" if r4.get("estoque") else "nao"
        print(f"  -> encontrado={r4['encontrado']}, estoque={tem_estoque}")

r5 = teste("buscar_detalhes_pneu(fake)", lambda: buscar_detalhes_pneu("00000000-0000-0000-0000-000000000000"))
if r5:
    print(f"  -> encontrado={r5['encontrado']}")

# --- TOOL 2: consulta_estoque ---
print("\n--- consulta_estoque ---")

from agente_2w.tools.consulta_estoque import consultar_estoque

if pneu_id_real:
    r6 = teste("consultar_estoque(real)", lambda: consultar_estoque(str(pneu_id_real)))
    if r6:
        print(f"  -> disponivel={r6['disponivel']}, preco={r6.get('preco_venda','N/A')}, disp_real={r6.get('disponivel_real','N/A')}")

r7 = teste("consultar_estoque(fake)", lambda: consultar_estoque("00000000-0000-0000-0000-000000000000"))
if r7:
    print(f"  -> disponivel={r7['disponivel']}")

# --- TOOL 3: resolve_cliente ---
print("\n--- resolve_cliente ---")

from agente_2w.tools.resolve_cliente import resolver_cliente

r8 = teste("resolver_cliente(inexistente)", lambda: resolver_cliente("0000000000"))
if r8:
    print(f"  -> ja_existia={r8['ja_existia']}, id={r8['cliente']['id'][:8]}...")

# Buscar de novo (deve retornar ja_existia=True)
tel_criado = r8["cliente"]["telefone"] if r8 else None
if tel_criado:
    r9 = teste("resolver_cliente(mesmo tel)", lambda: resolver_cliente(tel_criado))
    if r9:
        print(f"  -> ja_existia={r9['ja_existia']}")

# Limpar cliente de teste
if r8:
    from agente_2w.db.client import supabase
    supabase.table("cliente").delete().eq("id", r8["cliente"]["id"]).execute()
    print("  -> cliente de teste removido")

# --- RELATORIO ---
print("\n" + "=" * 60)
print("RELATORIO FASE 4")
print("=" * 60)
total = len(resultados)
passed = sum(1 for r in resultados if r[0] == "PASS")
failed = sum(1 for r in resultados if r[0] == "FAIL")
for r in resultados:
    mark = "V" if r[0] == "PASS" else "X"
    print(f"  {mark} {r[1]}")
    if r[0] == "FAIL":
        print(f"    ERRO: {r[2]}")
print(f"\nTotal: {total} | PASS: {passed} | FAIL: {failed}")
if failed == 0:
    print("TODOS OS TESTES PASSARAM")
else:
    print(f"{failed} FALHA(S)")
