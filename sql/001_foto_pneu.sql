-- Migration: Criar tabela foto_pneu e atualizar view catalogo_agente
-- Projeto: Envio de fotos de pneus pelo agente
-- Data: 2026-04-06

-- 1. Criar tabela foto_pneu
CREATE TABLE IF NOT EXISTS foto_pneu (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pneu_id     uuid NOT NULL REFERENCES pneu(id) ON DELETE CASCADE,
    url         text NOT NULL,
    tipo        text NOT NULL DEFAULT 'principal'
                CHECK (tipo IN ('principal', 'detalhe', 'sulco', 'lateral')),
    ordem       smallint NOT NULL DEFAULT 1,
    descricao   text,
    ativo       boolean NOT NULL DEFAULT true,
    criado_em   timestamptz NOT NULL DEFAULT now(),

    UNIQUE (pneu_id, tipo, ordem)
);

-- Indice para busca rapida por pneu (apenas fotos ativas)
CREATE INDEX IF NOT EXISTS idx_foto_pneu_pneu_id
    ON foto_pneu(pneu_id) WHERE ativo = true;

COMMENT ON TABLE foto_pneu IS
  'Fotos de pneus armazenadas no Supabase Storage. Cada pneu pode ter multiplas fotos (principal, detalhe, sulco, lateral). A URL aponta para o bucket publico "fotos".';

-- 2. Atualizar view catalogo_agente com foto_url
-- IMPORTANTE: Ajuste os campos existentes conforme a view atual do seu banco.
-- O SELECT abaixo assume a estrutura documentada. Verifique antes de executar.
CREATE OR REPLACE VIEW catalogo_agente AS
SELECT
    p.id          AS pneu_id,
    p.marca       AS pneu_marca,
    p.modelo      AS pneu_modelo,
    p.medida,
    p.largura,
    p.perfil,
    p.aro,
    p.tipo        AS pneu_tipo,
    p.descricao_comercial,
    e.preco_venda,
    e.quantidade_disponivel,
    e.reservado,
    (e.quantidade_disponivel - e.reservado) AS disponivel_real,
    p.ativo,
    fp.url        AS foto_url
FROM pneu p
JOIN estoque e ON e.pneu_id = p.id
LEFT JOIN foto_pneu fp
    ON fp.pneu_id = p.id
    AND fp.tipo = 'principal'
    AND fp.ordem = 1
    AND fp.ativo = true
WHERE p.ativo = true;

-- 3. Consultas uteis pos-implementacao

-- Pneus sem foto cadastrada (acao necessaria)
-- SELECT p.marca, p.modelo, p.medida
-- FROM pneu p
-- LEFT JOIN foto_pneu fp ON fp.pneu_id = p.id AND fp.ativo = true
-- WHERE p.ativo = true AND fp.id IS NULL;

-- Verificar que a view nao duplica linhas
-- SELECT COUNT(*) FROM catalogo_agente;
-- vs
-- SELECT COUNT(*) FROM pneu p JOIN estoque e ON e.pneu_id = p.id WHERE p.ativo = true;
