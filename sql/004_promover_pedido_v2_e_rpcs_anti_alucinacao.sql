-- ============================================================
-- 004_promover_pedido_v2_e_rpcs_anti_alucinacao.sql
--
-- 1. promover_para_pedido v2: check atomico de estoque + preco
--    + reserva DENTRO da transacao (elimina race condition)
-- 2. catalogo_resumo: marcas/medidas/aros com estoque
-- 3. motos_atendidas: motos com pneu disponivel
-- 4. historico_cliente: ultimos pedidos de um cliente
-- ============================================================

-- =================================================================
-- promover_para_pedido v2 — com FOR UPDATE + reserva atomica + check preco
-- =================================================================
CREATE OR REPLACE FUNCTION promover_para_pedido(
    p_sessao_id uuid,
    p_cliente_id uuid,
    p_tipo_entrega tipo_entrega_enum,
    p_forma_pagamento forma_pagamento_enum,
    p_valor_total numeric,
    p_endereco_json jsonb DEFAULT NULL,
    p_itens jsonb DEFAULT '[]'::jsonb,
    p_valor_frete numeric DEFAULT 0
)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    v_pedido_id uuid;
    v_item jsonb;
    v_item_pedido_id uuid;
    v_resultado jsonb;
    v_disponivel integer;
    v_preco_atual numeric;
BEGIN
    -- 1. Verificar estoque e preco ATOMICAMENTE para cada item
    FOR v_item IN SELECT * FROM jsonb_array_elements(p_itens)
    LOOP
        SELECT (e.quantidade_disponivel - e.reservado), e.preco_venda
        INTO v_disponivel, v_preco_atual
        FROM estoque e
        WHERE e.pneu_id = (v_item->>'pneu_id')::uuid
        FOR UPDATE;  -- lock da linha para evitar race condition

        IF v_disponivel IS NULL THEN
            RAISE EXCEPTION 'estoque_nao_encontrado:pneu_id=%', (v_item->>'pneu_id');
        END IF;

        IF v_disponivel < (v_item->>'quantidade')::integer THEN
            RAISE EXCEPTION 'estoque_insuficiente:pneu_id=%,disponivel=%,necessario=%',
                (v_item->>'pneu_id'), v_disponivel, (v_item->>'quantidade');
        END IF;

        -- Verificar se preco mudou (tolerancia de 1 centavo)
        IF ABS(v_preco_atual - (v_item->>'preco_unitario')::numeric) > 0.01 THEN
            RAISE EXCEPTION 'preco_divergente:pneu_id=%,preco_pedido=%,preco_atual=%',
                (v_item->>'pneu_id'), (v_item->>'preco_unitario'), v_preco_atual;
        END IF;
    END LOOP;

    -- 2. Criar pedido
    INSERT INTO pedido (
        sessao_chat_id, cliente_id, tipo_entrega, forma_pagamento,
        valor_total, valor_frete, status_pedido, endereco_entrega_json
    ) VALUES (
        p_sessao_id, p_cliente_id, p_tipo_entrega, p_forma_pagamento,
        p_valor_total, p_valor_frete, 'confirmado', p_endereco_json
    )
    RETURNING id INTO v_pedido_id;

    -- 3. Criar itens do pedido, promover provisorios E reservar estoque
    FOR v_item IN SELECT * FROM jsonb_array_elements(p_itens)
    LOOP
        INSERT INTO item_pedido (
            pedido_id, pneu_id, quantidade, preco_unitario,
            subtotal, item_provisorio_id, posicao
        ) VALUES (
            v_pedido_id,
            (v_item->>'pneu_id')::uuid,
            (v_item->>'quantidade')::integer,
            (v_item->>'preco_unitario')::numeric,
            (v_item->>'subtotal')::numeric,
            (v_item->>'item_provisorio_id')::uuid,
            v_item->>'posicao'
        )
        RETURNING id INTO v_item_pedido_id;

        -- Marcar item provisorio como promovido
        UPDATE item_provisorio
        SET status_item = 'promovido', atualizado_em = now()
        WHERE id = (v_item->>'item_provisorio_id')::uuid;

        -- Reservar estoque DENTRO da transacao (atomico)
        UPDATE estoque
        SET reservado = reservado + (v_item->>'quantidade')::integer,
            atualizado_em = now()
        WHERE pneu_id = (v_item->>'pneu_id')::uuid;
    END LOOP;

    -- 4. Sessao permanece ativa (timeout fecha automaticamente)
    UPDATE sessao_chat
    SET ultima_interacao_em = now(), atualizado_em = now()
    WHERE id = p_sessao_id;

    -- 5. Retornar resultado
    SELECT jsonb_build_object(
        'pedido_id', v_pedido_id,
        'valor_total', p_valor_total,
        'valor_frete', p_valor_frete,
        'itens_criados', jsonb_array_length(p_itens)
    ) INTO v_resultado;

    RETURN v_resultado;
END;
$$;

-- =================================================================
-- catalogo_resumo: marcas, medidas e aros com estoque disponivel
-- =================================================================
CREATE OR REPLACE FUNCTION catalogo_resumo()
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    SELECT jsonb_build_object(
        'marcas', (
            SELECT COALESCE(jsonb_agg(DISTINCT pneu_marca ORDER BY pneu_marca), '[]'::jsonb)
            FROM catalogo_agente
            WHERE disponivel_real > 0
        ),
        'medidas', (
            SELECT COALESCE(jsonb_agg(DISTINCT medida ORDER BY medida), '[]'::jsonb)
            FROM catalogo_agente
            WHERE disponivel_real > 0
        ),
        'aros', (
            SELECT COALESCE(jsonb_agg(DISTINCT aro ORDER BY aro), '[]'::jsonb)
            FROM catalogo_agente
            WHERE disponivel_real > 0
        )
    );
$$;

-- =================================================================
-- motos_atendidas: motos distintas com pneu em estoque
-- =================================================================
CREATE OR REPLACE FUNCTION motos_atendidas()
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
        jsonb_agg(
            jsonb_build_object(
                'moto', sub.moto,
                'moto_marca', sub.moto_marca,
                'posicoes', sub.posicoes
            )
            ORDER BY sub.moto_marca, sub.moto
        ),
        '[]'::jsonb
    )
    FROM (
        SELECT
            c.moto,
            c.moto_marca,
            array_agg(DISTINCT c.posicao ORDER BY c.posicao) AS posicoes
        FROM compatibilidade_moto_pneu c
        WHERE c.disponivel_real > 0
        GROUP BY c.moto, c.moto_marca
    ) sub;
$$;

-- =================================================================
-- historico_cliente: ultimos pedidos de um cliente
-- =================================================================
CREATE OR REPLACE FUNCTION historico_cliente(p_cliente_id uuid, p_limite integer DEFAULT 5)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
        jsonb_agg(
            jsonb_build_object(
                'pedido_id', p.id,
                'numero_pedido', p.numero_pedido,
                'status', p.status_pedido,
                'valor_total', p.valor_total,
                'criado_em', p.criado_em,
                'itens', (
                    SELECT COALESCE(jsonb_agg(
                        jsonb_build_object(
                            'pneu_modelo', pn.modelo,
                            'pneu_marca', pn.marca,
                            'medida', pn.medida,
                            'quantidade', ip.quantidade,
                            'preco_unitario', ip.preco_unitario,
                            'posicao', ip.posicao
                        )
                    ), '[]'::jsonb)
                    FROM item_pedido ip
                    JOIN pneu pn ON pn.id = ip.pneu_id
                    WHERE ip.pedido_id = p.id
                )
            )
            ORDER BY p.criado_em DESC
        ),
        '[]'::jsonb
    )
    FROM (
        SELECT * FROM pedido
        WHERE cliente_id = p_cliente_id
          AND status_pedido != 'cancelado'
        ORDER BY criado_em DESC
        LIMIT p_limite
    ) p;
$$;
