-- ============================================================
-- 003_liberar_reservas_orfas.sql
-- Job de limpeza: libera estoque reservado de pedidos
-- que ficaram em "confirmado" por mais de 7 dias sem avançar.
-- Previne leak de reservas que travavam disponível_real.
-- ============================================================

-- 1. Adicionar status 'expirado' ao enum (se usar check constraint)
--    Se a coluna status_pedido for TEXT livre, isso nao e necessario.
--    Caso use enum nativo do Postgres, descomente:
-- ALTER TYPE status_pedido ADD VALUE IF NOT EXISTS 'expirado';

-- 2. Funcao principal: libera reservas orfas e marca pedidos como expirados
CREATE OR REPLACE FUNCTION liberar_reservas_orfas(p_dias_limite integer DEFAULT 7)
RETURNS jsonb AS $$
DECLARE
    v_pedidos_expirados integer := 0;
    v_itens_liberados   integer := 0;
    v_item              RECORD;
BEGIN
    -- Para cada item de pedido confirmado ha mais de p_dias_limite dias,
    -- decrementar o reservado no estoque
    FOR v_item IN
        SELECT ip.pneu_id, ip.quantidade
        FROM item_pedido ip
        JOIN pedido p ON p.id = ip.pedido_id
        WHERE p.status_pedido = 'confirmado'
          AND p.criado_em < NOW() - (p_dias_limite || ' days')::interval
    LOOP
        UPDATE estoque
        SET reservado = GREATEST(0, reservado - v_item.quantidade)
        WHERE pneu_id = v_item.pneu_id
          AND reservado > 0;

        v_itens_liberados := v_itens_liberados + 1;
    END LOOP;

    -- Marcar os pedidos como expirados para nao processar novamente
    UPDATE pedido
    SET status_pedido = 'expirado',
        atualizado_em = NOW()
    WHERE status_pedido = 'confirmado'
      AND criado_em < NOW() - (p_dias_limite || ' days')::interval;

    GET DIAGNOSTICS v_pedidos_expirados = ROW_COUNT;

    RETURN jsonb_build_object(
        'pedidos_expirados', v_pedidos_expirados,
        'itens_liberados', v_itens_liberados,
        'executado_em', NOW()
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 3. Agendar execucao diaria as 03:00 UTC via pg_cron
-- IMPORTANTE: pg_cron precisa estar habilitado no Supabase (Dashboard > Extensions > pg_cron)
-- Descomente apos habilitar:
-- SELECT cron.schedule(
--     'limpar-reservas-orfas',
--     '0 3 * * *',
--     $$SELECT liberar_reservas_orfas(7)$$
-- );

-- 4. Para executar manualmente (ex: primeira limpeza):
-- SELECT liberar_reservas_orfas(7);
