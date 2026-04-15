from agente_2w.db.client import supabase

# Pedido 1157
p = supabase.table('pedido').select('*').eq('numero_pedido', 1157).execute()
if not p.data:
    print('Pedido 1157 nao encontrado')
    exit()

ped = p.data[0]
print('=== PEDIDO ===')
for k, v in ped.items():
    print(f'  {k}: {v}')

# Itens do pedido
itens = supabase.table('item_pedido').select('*').eq('pedido_id', ped['id']).execute()
print(f'\n=== ITENS ({len(itens.data)}) ===')
for it in itens.data:
    pneu_id = it['pneu_id']
    qty = it['quantidade']
    preco = it['preco_unitario']
    posicao = it.get('posicao', '-')
    print(f'  pneu_id={pneu_id}  qty={qty}  preco={preco}  posicao={posicao}')

    # Buscar nome do pneu
    pneu = supabase.table('pneu').select('descricao_comercial, medida').eq('id', pneu_id).execute()
    if pneu.data:
        print(f'    -> {pneu.data[0]["descricao_comercial"]}  {pneu.data[0]["medida"]}')

# Item provisorio restante (deveria estar vazio)
itp = supabase.table('item_provisorio').select('*').eq('sessao_chat_id', ped['sessao_chat_id']).execute()
print(f'\n=== ITEM_PROVISORIO restante: {len(itp.data)} ===')
for it in itp.data:
    print(f'  {it}')

# Contexto chave
ctx = supabase.table('contexto_conversa').select('chave,valor_texto,valor_json').eq('sessao_chat_id', ped['sessao_chat_id']).eq('ativo', True).execute()
print(f'\n=== CONTEXTO ATIVO ({len(ctx.data)} fatos) ===')
for c in ctx.data:
    val = c['valor_texto'] or c['valor_json']
    print(f'  {c["chave"]}: {val}')
