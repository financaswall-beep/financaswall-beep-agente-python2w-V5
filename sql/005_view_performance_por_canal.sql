-- View: performance por canal de atendimento (WhatsApp / Instagram / Facebook)
-- Criada em: 2026-04-17
-- Como usar: SELECT * FROM vw_performance_por_canal;

CREATE OR REPLACE VIEW vw_performance_por_canal AS
SELECT
    s.canal,
    COUNT(DISTINCT s.id)                                                                        AS total_conversas,
    COUNT(DISTINCT CASE WHEN p.status_pedido <> 'cancelado' THEN p.id END)                      AS total_pedidos,
    ROUND(
        COUNT(DISTINCT CASE WHEN p.status_pedido <> 'cancelado' THEN p.id END)::numeric
        / NULLIF(COUNT(DISTINCT s.id), 0) * 100, 1
    )                                                                                           AS taxa_conversao_pct,
    ROUND(AVG(p.valor_total) FILTER (WHERE p.status_pedido <> 'cancelado')::numeric, 2)         AS ticket_medio,
    ROUND(SUM(p.valor_total) FILTER (WHERE p.status_pedido <> 'cancelado')::numeric, 2)         AS faturamento_total,
    COUNT(DISTINCT CASE WHEN p.status_pedido = 'confirmado' THEN p.id END)                      AS pedidos_confirmados,
    COUNT(DISTINCT CASE WHEN p.status_pedido = 'cancelado'  THEN p.id END)                      AS pedidos_cancelados,
    MIN(s.criado_em)                                                                            AS primeira_conversa,
    MAX(s.criado_em)                                                                            AS ultima_conversa
FROM sessao_chat s
LEFT JOIN pedido p ON p.sessao_chat_id = s.id
GROUP BY s.canal
ORDER BY total_pedidos DESC;
