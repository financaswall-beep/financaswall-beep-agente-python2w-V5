import sys
from agente_2w.db.client import supabase

sid = sys.argv[1] if len(sys.argv) > 1 else 'b03e5d59-e6d7-4db7-93d1-752d403732bd'

msgs = supabase.table('mensagem_chat').select('direcao,conteudo_texto,criado_em').eq('sessao_chat_id', sid).order('criado_em').execute()
print(f'=== MENSAGENS ({len(msgs.data)}) ===')
for m in msgs.data:
    d = 'CLIENTE' if m['direcao'] == 'entrada' else 'AGENTE '
    texto = (m['conteudo_texto'] or '')[:100]
    print(f'  [{d}] {texto}')

fatos = supabase.table('contexto_conversa').select('chave,valor_texto,coletado_em').eq('sessao_chat_id', sid).order('coletado_em').execute()
print(f'\n=== FATOS ({len(fatos.data)}) ===')
for f in fatos.data:
    chave = f['chave']
    val = (f['valor_texto'] or '')[:80]
    print(f'  {chave} = {val}')

itens = supabase.table('item_provisorio').select('pneu_id,status_item,quantidade,preco_unitario_sugerido').eq('sessao_chat_id', sid).execute()
print(f'\n=== ITENS PROVISORIOS ({len(itens.data)}) ===')
for i in itens.data:
    print(f'  {i}')
