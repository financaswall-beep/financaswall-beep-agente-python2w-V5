from agente_2w.db.client import supabase

sessao_id = '8f3d26e4-e7e6-48aa-abe0-057799e429a8'

# Todos os fatos de municipio (ativos e inativos) em ordem
fatos = (
    supabase.table('contexto_conversa')
    .select('chave, valor_texto, ativo, coletado_em')
    .eq('sessao_chat_id', sessao_id)
    .in_('chave', ['municipio', 'bairro', 'municipio_entrega', 'localidade_nao_resolvida', 'frete_valor', 'frete_nao_coberto', 'municipio_ambiguo'])
    .order('coletado_em')
    .execute()
)
print('=== FATOS LOCALIDADE (ordem cronologica) ===')
for f in fatos.data:
    print(f"  {f['coletado_em'][11:19]}  {f['chave']:30} ativo={str(f['ativo']):5}  valor={f['valor_texto']}")

# Mensagens em ordem
msgs = (
    supabase.table('mensagem_chat')
    .select('criado_em, direcao, conteudo_texto')
    .eq('sessao_chat_id', sessao_id)
    .order('criado_em')
    .execute()
)
print('\n=== MENSAGENS ===')
for m in msgs.data:
    quem = 'CLIENTE' if m['direcao'] == 'entrada' else 'AGENTE '
    print(f"  {m['criado_em'][11:19]}  {quem}: {m['conteudo_texto'][:80]}")
