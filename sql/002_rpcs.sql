-- ============================================================================
-- 002_rpcs.sql — RPCs (stored functions) existentes no Supabase
-- Reference only — already applied in production. DO NOT re-run.
-- ============================================================================

-- 1. buscar_pneu_por_texto(p_termo text, p_threshold float default 0.15)
--    Busca trigram em catalogo_agente com unaccent. Usado por catalogo_repo.
--    Retorna pneus com similaridade >= threshold, ordenados por score desc.

-- 2. buscar_moto_por_texto(p_termo text, p_threshold float default 0.15)
--    Busca trigram em compatibilidade_moto_pneu com unaccent.
--    Retorna motos + pneus compatíveis, ordenados por similaridade desc.

-- 3. atualizar_reservado_estoque(p_pneu_id uuid, p_delta integer)
--    Incrementa/decrementa campo `reservado` na tabela estoque.
--    Chamada ao criar/cancelar item_provisorio.

-- 4. baixar_estoque_fisico(p_pneu_id uuid, p_quantidade integer)
--    Reduz `quantidade_disponivel` na tabela estoque. Chamada ao confirmar pedido.

-- 5. registrar_fato_atomico(...)
--    Desativa fato anterior com mesma chave+sessao e insere novo fato em
--    uma única transação. Evita race condition em fatos duplicados.

-- 6. resolver_ou_criar_cliente_atomico(p_telefone text, p_nome text)
--    Busca cliente por telefone. Se não existe, cria. Retorna o registro.
--    Operação atômica (upsert) para evitar duplicatas em concorrência.
