"""Cadastro assistido de motos, pneus e estoque.

Menu principal:
  1 - Listar motos cadastradas
  2 - Adicionar nova moto
  3 - Listar pneus e estoque
  4 - Adicionar novo pneu + estoque
  5 - Atualizar preco/quantidade de pneu existente
  6 - Ver o que cada moto aceita (compatibilidade)
  7 - Associar medida a uma moto

Uso: python cadastro.py
"""

import os
import sys
import re

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from agente_2w.db.client import supabase


# ---------------------------------------------------------------------------
# Helpers de input
# ---------------------------------------------------------------------------

def ask(prompt, obrigatorio=True, padrao=None):
    sufixo = f" [{padrao}]" if padrao is not None else ""
    while True:
        val = input(f"  {prompt}{sufixo}: ").strip()
        if not val and padrao is not None:
            return padrao
        if not val and obrigatorio:
            print("  [!] Campo obrigatorio, tente novamente.")
            continue
        return val or None


def ask_int(prompt, obrigatorio=True, padrao=None):
    while True:
        val = ask(prompt, obrigatorio=obrigatorio, padrao=padrao)
        if val is None:
            return None
        try:
            return int(val)
        except ValueError:
            print("  [!] Digite um numero inteiro.")


def ask_float(prompt, obrigatorio=True, padrao=None):
    while True:
        val = ask(prompt, obrigatorio=obrigatorio, padrao=padrao)
        if val is None:
            return None
        try:
            return float(str(val).replace(",", "."))
        except ValueError:
            print("  [!] Digite um numero. Ex: 239.90 ou 239,90")


def escolher(lista, campo_display):
    """Exibe lista numerada e retorna o item escolhido."""
    for i, item in enumerate(lista, 1):
        print(f"  {i:>3}. {item[campo_display]}")
    while True:
        n = ask_int(f"Numero (1-{len(lista)})")
        if 1 <= n <= len(lista):
            return lista[n - 1]
        print(f"  [!] Digite entre 1 e {len(lista)}")


def confirmar(prompt):
    resp = input(f"  {prompt} (s/n): ").strip().lower()
    return resp in ("s", "sim", "y", "yes")


def titulo(texto):
    print()
    print("=" * 55)
    print(f"  {texto}")
    print("=" * 55)


# ---------------------------------------------------------------------------
# 1. Listar motos
# ---------------------------------------------------------------------------

def listar_motos():
    titulo("MOTOS CADASTRADAS")
    res = supabase.table("moto").select("id, marca, modelo, versao, ano_inicio, ano_fim, descricao_resolvida").order("marca").order("modelo").execute()
    motos = res.data or []
    if not motos:
        print("  Nenhuma moto cadastrada.")
        return
    print(f"  {'#':<4} {'Descricao':<40} {'Ano':<12} {'ID'}")
    print("  " + "-" * 100)
    for i, m in enumerate(motos, 1):
        ano = ""
        if m.get("ano_inicio"):
            ano = str(m["ano_inicio"])
            if m.get("ano_fim"):
                ano += f"-{m['ano_fim']}"
        desc = m.get("descricao_resolvida") or f"{m['marca']} {m['modelo']}"
        print(f"  {i:<4} {desc:<40} {ano:<12} {m['id']}")
    print(f"\n  Total: {len(motos)} motos")


# ---------------------------------------------------------------------------
# 2. Adicionar moto
# ---------------------------------------------------------------------------

def adicionar_moto():
    titulo("NOVA MOTO")
    print("  Dica: use descricao_resolvida para o agente identificar.")
    print("  Exemplo: Honda CG 160 / Yamaha Fazer 250")
    print()

    marca = ask("Marca (ex: Honda)")
    modelo = ask("Modelo (ex: CG 160)")
    versao = ask("Versao (ex: Titan, Fan) - opcional", obrigatorio=False)
    ano_inicio = ask_int("Ano inicio (ex: 2015) - opcional", obrigatorio=False)
    ano_fim = ask_int("Ano fim (ex: 2023) - opcional", obrigatorio=False)

    # Monta descricao automatica
    desc_auto = f"{marca} {modelo}"
    if versao:
        desc_auto += f" {versao}"
    if ano_inicio:
        desc_auto += f" ({ano_inicio}"
        if ano_fim:
            desc_auto += f"-{ano_fim}"
        desc_auto += ")"

    descricao = ask("Descricao resolvida", padrao=desc_auto)

    print()
    print(f"  Resumo: {descricao}")
    if not confirmar("Confirma cadastro?"):
        print("  Cancelado.")
        return

    payload = {
        "marca": marca,
        "modelo": modelo,
        "descricao_resolvida": descricao,
    }
    if versao:
        payload["versao"] = versao
    if ano_inicio:
        payload["ano_inicio"] = ano_inicio
    if ano_fim:
        payload["ano_fim"] = ano_fim

    res = supabase.table("moto").insert(payload).execute()
    moto_id = res.data[0]["id"]
    print(f"\n  Moto cadastrada! ID: {moto_id}")

    # Oferecer cadastro de medida logo em seguida
    if confirmar("Deseja cadastrar as medidas de pneu desta moto agora?"):
        _cadastrar_medida_moto(moto_id, descricao)


# ---------------------------------------------------------------------------
# 3. Listar pneus e estoque
# ---------------------------------------------------------------------------

def listar_pneus():
    titulo("PNEUS E ESTOQUE")
    res = supabase.table("catalogo_agente").select("*").order("pneu_marca").order("pneu_modelo").execute()
    pneus = res.data or []
    if not pneus:
        print("  Nenhum pneu cadastrado.")
        return

    print(f"  {'#':<4} {'Pneu':<38} {'Medida':<14} {'Tipo':<12} {'Qtd':>5} {'Preco':>10}")
    print("  " + "-" * 95)
    for i, p in enumerate(pneus, 1):
        nome = f"{p.get('pneu_marca','')} {p.get('pneu_modelo','')}".strip()
        medida = p.get("medida", "")
        tipo = p.get("pneu_tipo", "universal") or "universal"
        qtd = p.get("disponivel_real", 0) or 0
        preco = p.get("preco_venda")
        preco_fmt = f"R${float(preco):.2f}" if preco else "sem preco"
        print(f"  {i:<4} {nome:<38} {medida:<14} {tipo:<12} {qtd:>5} {preco_fmt:>10}")
    print(f"\n  Total: {len(pneus)} pneus")


# ---------------------------------------------------------------------------
# 4. Adicionar pneu + estoque
# ---------------------------------------------------------------------------

def _parsear_medida(medida_str):
    """Extrai largura/perfil/aro de '110/70-17' ou '90/90-18'."""
    m = re.match(r"(\d+)[/\-\s](\d+)[/\-\s](\d+)", medida_str.strip())
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None, None, None


def adicionar_pneu():
    titulo("NOVO PNEU + ESTOQUE")
    print("  Preencha os dados do pneu que voce tem em estoque.")
    print()

    marca = ask("Marca do pneu (ex: Pirelli, Michelin, Metzeler)")
    modelo_pneu = ask("Modelo do pneu (ex: Street Rider, City Dragon)")

    # Medida com parse automatico
    while True:
        medida_str = ask("Medida (ex: 100/80-17 ou 90/90-18)")
        largura, perfil, aro = _parsear_medida(medida_str)
        if largura:
            print(f"    -> Largura: {largura}  Perfil: {perfil}  Aro: {aro}")
            break
        print("  [!] Formato invalido. Use: 110/70-17")

    tipo = ask("Tipo (dianteiro / traseiro / universal)", padrao="universal")
    if tipo not in ("dianteiro", "traseiro", "universal"):
        print("  [!] Tipo invalido, usando 'universal'")
        tipo = "universal"

    descricao_comercial = ask(
        "Descricao comercial (como aparece pro cliente)",
        padrao=f"{marca} {modelo_pneu} {medida_str}"
    )
    sku = ask("SKU/codigo interno - opcional", obrigatorio=False)

    print()
    quantidade = ask_int("Quantidade em estoque", padrao=1)
    preco = ask_float("Preco de venda (ex: 239.90)")

    print()
    print(f"  Resumo:")
    print(f"    Pneu:      {marca} {modelo_pneu}")
    print(f"    Medida:    {medida_str} ({largura}/{perfil}-{aro})")
    print(f"    Tipo:      {tipo}")
    print(f"    Descricao: {descricao_comercial}")
    print(f"    Estoque:   {quantidade} unidades a R${preco:.2f}")

    if not confirmar("Confirma cadastro?"):
        print("  Cancelado.")
        return

    # Inserir pneu
    payload_pneu = {
        "marca": marca,
        "modelo": modelo_pneu,
        "medida": medida_str,
        "largura": largura,
        "perfil": perfil,
        "aro": aro,
        "tipo": tipo,
        "descricao_comercial": descricao_comercial,
        "ativo": True,
    }
    if sku:
        payload_pneu["sku"] = sku

    res_pneu = supabase.table("pneu").insert(payload_pneu).execute()
    pneu_id = res_pneu.data[0]["id"]
    print(f"\n  Pneu cadastrado! ID: {pneu_id}")

    # Inserir estoque
    supabase.table("estoque").insert({
        "pneu_id": pneu_id,
        "quantidade_disponivel": quantidade,
        "preco_venda": str(preco),
        "reservado": 0,
        "atualizado_por": "cadastro_manual",
    }).execute()
    print(f"  Estoque registrado: {quantidade} un. a R${preco:.2f}")

    # Oferecer associacao com motos
    if confirmar("Deseja associar este pneu a alguma moto agora?"):
        _associar_pneu_a_motos(medida_str, largura, perfil, aro, tipo)


# ---------------------------------------------------------------------------
# 5. Atualizar preco/quantidade
# ---------------------------------------------------------------------------

def atualizar_estoque():
    titulo("ATUALIZAR PRECO / QUANTIDADE")

    # Buscar pneus com estoque
    res = supabase.table("catalogo_agente").select("pneu_id, pneu_marca, pneu_modelo, medida, pneu_tipo, disponivel_real, preco_venda").order("pneu_marca").order("pneu_modelo").execute()
    pneus = res.data or []
    if not pneus:
        print("  Nenhum pneu encontrado.")
        return

    for i, p in enumerate(pneus, 1):
        nome = f"{p.get('pneu_marca','')} {p.get('pneu_modelo','')} {p.get('medida','')}"
        qtd = p.get("disponivel_real", 0)
        preco = p.get("preco_venda")
        preco_fmt = f"R${float(preco):.2f}" if preco else "sem preco"
        print(f"  {i:>3}. {nome:<45} {qtd:>3} un.  {preco_fmt}")

    print()
    n = ask_int(f"Qual pneu atualizar? (1-{len(pneus)})")
    if not 1 <= n <= len(pneus):
        print("  Numero invalido.")
        return

    pneu = pneus[n - 1]
    pneu_id = pneu["pneu_id"]
    nome = f"{pneu.get('marca','')} {pneu.get('modelo','')} {pneu.get('medida','')}"
    print(f"\n  Editando: {nome}")
    print(f"  Atual: {pneu.get('disponivel_real',0)} un. | R${float(pneu['preco_venda']):.2f}" if pneu.get("preco_venda") else "")

    nova_qtd = ask_int("Nova quantidade (Enter pra nao alterar)", obrigatorio=False)
    novo_preco = ask_float("Novo preco (Enter pra nao alterar)", obrigatorio=False)

    if nova_qtd is None and novo_preco is None:
        print("  Nada alterado.")
        return

    payload = {"atualizado_por": "cadastro_manual"}
    if nova_qtd is not None:
        payload["quantidade_disponivel"] = nova_qtd
    if novo_preco is not None:
        payload["preco_venda"] = str(novo_preco)

    supabase.table("estoque").update(payload).eq("pneu_id", pneu_id).execute()
    print("  Atualizado com sucesso!")


# ---------------------------------------------------------------------------
# 6. Ver compatibilidade de uma moto
# ---------------------------------------------------------------------------

def ver_compatibilidade():
    titulo("COMPATIBILIDADE DE MOTO")

    termo = ask("Digite nome da moto (ex: CG 160, Fazer 250)")
    res = supabase.rpc("buscar_moto_por_texto", {"termo_busca": termo}).execute()
    motos = res.data or []

    if not motos:
        print("  Nenhuma moto encontrada com esse nome.")
        return

    print()
    moto = escolher(motos, "descricao_resolvida")
    moto_id = moto["id"]

    # Buscar medidas cadastradas
    medidas = supabase.table("medida_moto").select("*").eq("moto_id", moto_id).execute().data or []
    # Buscar pneus compativeis
    compat = supabase.table("compatibilidade_moto_pneu").select("*").eq("moto_id", moto_id).execute().data or []

    print(f"\n  Moto: {moto['descricao_resolvida']} (ID: {moto_id})")

    if medidas:
        print("\n  Medidas registradas:")
        for med in medidas:
            print(f"    {med['posicao']:>10}: {med['largura']}/{med['perfil']}-{med['aro']}  (fonte: {med.get('fonte','?')})")
    else:
        print("\n  [!] Nenhuma medida cadastrada para esta moto.")
        print("      Use opcao 7 para associar medida.")

    if compat:
        print("\n  Pneus disponiveis em estoque:")
        for c in compat:
            nome = c.get("pneu") or f"{c.get('pneu_marca','')}".strip()
            qtd = c.get("disponivel_real", 0)
            preco = c.get("preco_venda")
            preco_fmt = f"R${float(preco):.2f}" if preco else "sem preco"
            print(f"    {c.get('posicao','-'):>10}: {nome:<40} {qtd:>3} un.  {preco_fmt}")
    else:
        print("  Nenhum pneu compativel em estoque (verifique medidas e catalogo de pneus).")


# ---------------------------------------------------------------------------
# 7. Associar medida a uma moto
# ---------------------------------------------------------------------------

def _cadastrar_medida_moto(moto_id, descricao_moto):
    print(f"\n  Moto: {descricao_moto}")
    print("  Informe as medidas (dianteiro e/ou traseiro).")

    for posicao in ("dianteiro", "traseiro"):
        print(f"\n  --- {posicao.upper()} ---")
        if not confirmar(f"Cadastrar medida {posicao}?"):
            continue

        while True:
            medida_str = ask(f"Medida {posicao} (ex: 100/80-17)")
            largura, perfil, aro = _parsear_medida(medida_str)
            if largura:
                print(f"    -> {largura}/{perfil}-{aro}")
                break
            print("  [!] Formato invalido. Use: 110/70-17")

        # Verificar se ja existe
        existe = supabase.table("medida_moto").select("id").eq("moto_id", moto_id).eq("posicao", posicao).execute().data
        if existe:
            print(f"  [!] Ja existe medida {posicao} para esta moto. Substituindo...")
            supabase.table("medida_moto").update({
                "largura": largura, "perfil": perfil, "aro": aro,
                "fonte": "cadastro_manual"
            }).eq("moto_id", moto_id).eq("posicao", posicao).execute()
        else:
            supabase.table("medida_moto").insert({
                "moto_id": moto_id,
                "posicao": posicao,
                "largura": largura,
                "perfil": perfil,
                "aro": aro,
                "fonte": "cadastro_manual",
            }).execute()
        print(f"  Medida {posicao} salva: {largura}/{perfil}-{aro}")


def _associar_pneu_a_motos(medida_str, largura, perfil, aro, tipo_pneu):
    print(f"\n  Pneu {medida_str} - associar a motos compatíveis")
    print("  (Busca motos que usam essa medida no banco)")

    # Motos que ja tem essa medida cadastrada
    posicoes_buscar = []
    if tipo_pneu == "dianteiro":
        posicoes_buscar = ["dianteiro"]
    elif tipo_pneu == "traseiro":
        posicoes_buscar = ["traseiro"]
    else:
        posicoes_buscar = ["dianteiro", "traseiro"]

    existentes = supabase.table("medida_moto").select("moto_id, posicao").eq("largura", largura).eq("perfil", perfil).eq("aro", aro).execute().data or []

    if existentes:
        print(f"\n  Motos que ja usam essa medida ({len(existentes)} registros):")
        for e in existentes[:10]:
            moto = supabase.table("moto").select("descricao_resolvida").eq("id", e["moto_id"]).maybe_single().execute()
            if moto and moto.data:
                print(f"    {e['posicao']:>10}: {moto.data['descricao_resolvida']}")

    print()
    if not confirmar("Associar a outra moto manualmente?"):
        return

    while True:
        termo = ask("Nome da moto (ou Enter para sair)", obrigatorio=False)
        if not termo:
            break

        res = supabase.rpc("buscar_moto_por_texto", {"termo_busca": termo}).execute()
        motos = res.data or []
        if not motos:
            print("  Moto nao encontrada.")
            continue

        moto = escolher(motos, "descricao_resolvida")

        for posicao in posicoes_buscar:
            existe = supabase.table("medida_moto").select("id").eq("moto_id", moto["id"]).eq("posicao", posicao).execute().data
            if existe:
                print(f"  Ja existe medida {posicao} para {moto['descricao_resolvida']}. Pulando.")
                continue
            supabase.table("medida_moto").insert({
                "moto_id": moto["id"],
                "posicao": posicao,
                "largura": largura,
                "perfil": perfil,
                "aro": aro,
                "fonte": "cadastro_manual",
            }).execute()
            print(f"  Associado: {moto['descricao_resolvida']} {posicao} = {medida_str}")


def associar_medida_moto():
    titulo("ASSOCIAR MEDIDA A MOTO")

    termo = ask("Nome da moto (ex: CG 160, Hornet)")
    res = supabase.rpc("buscar_moto_por_texto", {"termo_busca": termo}).execute()
    motos = res.data or []

    if not motos:
        print("  Moto nao encontrada. Use opcao 2 para cadastrar primeiro.")
        return

    moto = escolher(motos, "descricao_resolvida")
    _cadastrar_medida_moto(moto["id"], moto["descricao_resolvida"])


# ---------------------------------------------------------------------------
# Menu principal
# ---------------------------------------------------------------------------

MENU = [
    ("Listar motos cadastradas",              listar_motos),
    ("Adicionar nova moto",                   adicionar_moto),
    ("Listar pneus e estoque",                listar_pneus),
    ("Adicionar novo pneu + estoque",         adicionar_pneu),
    ("Atualizar preco/quantidade de pneu",    atualizar_estoque),
    ("Ver compatibilidade de uma moto",       ver_compatibilidade),
    ("Associar medida de pneu a uma moto",    associar_medida_moto),
]


def main():
    print()
    print("=" * 55)
    print("  2W PNEUS - CADASTRO ASSISTIDO")
    print("=" * 55)

    while True:
        print()
        for i, (nome, _) in enumerate(MENU, 1):
            print(f"  {i}. {nome}")
        print("  0. Sair")
        print()

        escolha = input("  Opcao: ").strip()
        if escolha == "0":
            print("\n  Ate logo!")
            break

        try:
            n = int(escolha)
            if 1 <= n <= len(MENU):
                MENU[n - 1][1]()
            else:
                print("  [!] Opcao invalida.")
        except ValueError:
            print("  [!] Digite um numero.")
        except KeyboardInterrupt:
            print("\n  Voltando ao menu...")
        except Exception as e:
            print(f"\n  [ERRO] {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
