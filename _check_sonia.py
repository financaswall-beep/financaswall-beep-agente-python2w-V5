from agente_2w.db.client import supabase

# Sessoes recentes
sessoes = supabase.table('sessao_chat').select('id, contato_externo, cliente_id, criado_em').order('criado_em', desc=True).limit(5).execute()
for s in sessoes.data:
    print(f"sessao={s['id']}  contato={s['contato_externo']}  cliente={s['cliente_id']}  em={s['criado_em'][:16]}")

# Buscar o cliente da sessao mais recente
if sessoes.data:
    cliente_id = sessoes.data[0]['cliente_id']
    sessao_id = sessoes.data[0]['id']
    if cliente_id:
        c = supabase.table('cliente').select('*').eq('id', cliente_id).execute()
        print('\n=== CLIENTE ===')
        for k, v in c.data[0].items():
            print(f'  {k}: {v}')

        # Ver fatos ativos de municipio/bairro
        fatos = supabase.table('contexto_conversa').select('chave, valor_texto, ativo').eq('sessao_chat_id', sessao_id).in_('chave', ['municipio', 'bairro', 'municipio_entrega', 'endereco_entrega']).execute()
        print('\n=== FATOS LOCALIDADE ===')
        for f in fatos.data:
            print(f"  {f['chave']} (ativo={f['ativo']}): {f['valor_texto']}")
