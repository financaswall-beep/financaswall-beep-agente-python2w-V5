# Migração das Tabelas de Frete — 12/04/2026

## Contexto

Preparação para o redesign do sistema de frete (eliminar web_search, simplificar fluxo).
As tabelas `area_entrega` e `bairro_municipio_cache` receberam otimizações de schema
sem alteração nos dados existentes.

---

## Migration 1: `area_entrega_add_atualizado_em_e_indices`

### Alterações

| # | Tipo | Detalhe |
|---|------|---------|
| 1 | ADD COLUMN | `atualizado_em TIMESTAMPTZ DEFAULT NOW()` |
| 2 | UNIQUE INDEX | `uq_area_entrega_municipio_bairro` em `(lower(municipio), COALESCE(lower(bairro), ''))` WHERE ativo=true |
| 3 | INDEX | `idx_area_entrega_municipio` em `(lower(municipio))` WHERE ativo=true |

### SQL executado

```sql
ALTER TABLE area_entrega 
  ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMPTZ DEFAULT NOW();

CREATE UNIQUE INDEX IF NOT EXISTS uq_area_entrega_municipio_bairro 
  ON area_entrega (lower(municipio), COALESCE(lower(bairro), '')) 
  WHERE ativo = true;

CREATE INDEX IF NOT EXISTS idx_area_entrega_municipio 
  ON area_entrega (lower(municipio)) 
  WHERE ativo = true;
```

### Schema final

| Coluna | Tipo | Default | Nota |
|--------|------|---------|------|
| `id` | UUID PK | gen_random_uuid() | |
| `municipio` | TEXT NOT NULL | | |
| `bairro` | TEXT | NULL | NULL = cobre município inteiro |
| `valor_frete` | NUMERIC(10,2) NOT NULL | | CHECK >= 0 |
| `ativo` | BOOLEAN NOT NULL | true | |
| `criado_em` | TIMESTAMPTZ NOT NULL | NOW() | |
| `atualizado_em` | TIMESTAMPTZ | NOW() | **NOVO** |

### Índices finais

| Nome | Colunas | Tipo | Filtro |
|------|---------|------|--------|
| `area_entrega_pkey` | `id` | UNIQUE (PK) | — |
| `area_entrega_municipio_bairro_idx` | `municipio, COALESCE(bairro, '')` | UNIQUE | — (pré-existente) |
| `uq_area_entrega_municipio_bairro` | `lower(municipio), COALESCE(lower(bairro), '')` | UNIQUE | ativo=true |
| `idx_area_entrega_municipio` | `lower(municipio)` | INDEX | ativo=true |

### Dados: 17 registros — zero alteração

---

## Migration 2: `bairro_municipio_cache_redesign_pk_e_bi`

### Problema resolvido

PK anterior era `termo_normalizado` — isso impedia que o mesmo bairro existisse em
múltiplos municípios. Exemplo: "Centro" só podia mapear para UMA cidade, quando na
realidade existe em Rio de Janeiro, Niterói, São Gonçalo, etc.

### Alterações

| # | Tipo | Detalhe |
|---|------|---------|
| 1 | ADD COLUMN | `id UUID DEFAULT gen_random_uuid()` |
| 2 | ADD COLUMN | `sessao_id UUID` (BI — rastrear qual conversa gerou o registro) |
| 3 | ADD COLUMN | `cliente_id UUID` (BI — cruzar bairro × perfil de cliente) |
| 4 | CHANGE PK | `termo_normalizado` → `id` |
| 5 | UNIQUE INDEX | `uq_cache_termo_municipio` em `(termo_normalizado, COALESCE(municipio, ''))` |
| 6 | INDEX | `idx_cache_termo` em `(termo_normalizado)` |
| 7 | INDEX | `idx_cache_sessao` em `(sessao_id)` WHERE NOT NULL |

### SQL executado

```sql
ALTER TABLE bairro_municipio_cache 
  ADD COLUMN IF NOT EXISTS id UUID DEFAULT gen_random_uuid(),
  ADD COLUMN IF NOT EXISTS sessao_id UUID,
  ADD COLUMN IF NOT EXISTS cliente_id UUID;

UPDATE bairro_municipio_cache SET id = gen_random_uuid() WHERE id IS NULL;

ALTER TABLE bairro_municipio_cache 
  DROP CONSTRAINT bairro_municipio_cache_pkey;

ALTER TABLE bairro_municipio_cache 
  ADD PRIMARY KEY (id);

CREATE UNIQUE INDEX uq_cache_termo_municipio 
  ON bairro_municipio_cache (termo_normalizado, COALESCE(municipio, ''));

CREATE INDEX idx_cache_termo 
  ON bairro_municipio_cache (termo_normalizado);

CREATE INDEX idx_cache_sessao 
  ON bairro_municipio_cache (sessao_id) 
  WHERE sessao_id IS NOT NULL;
```

### Schema final

| Coluna | Tipo | Default | Nota |
|--------|------|---------|------|
| `id` | UUID PK | gen_random_uuid() | **NOVO** — era termo_normalizado |
| `termo_normalizado` | TEXT NOT NULL | | Chave de busca (normalizada sem acentos, lowercase) |
| `termo_original` | TEXT | | Texto original digitado pelo cliente |
| `bairro` | TEXT | | Nome oficial do bairro |
| `municipio` | TEXT | | NULL = fora de cobertura (cache negativo) |
| `fonte` | TEXT | 'web_search' | Origem: inserido_manual, web_search, confirmado_frete, informado_cliente |
| `acessos` | INTEGER | 1 | Contador de hits (incrementa cada consulta) |
| `criado_em` | TIMESTAMPTZ | NOW() | |
| `atualizado_em` | TIMESTAMPTZ | NOW() | |
| `sessao_id` | UUID | NULL | **NOVO** — qual conversa gerou o registro |
| `cliente_id` | UUID | NULL | **NOVO** — qual cliente gerou o registro |

### Índices finais

| Nome | Colunas | Tipo | Filtro |
|------|---------|------|--------|
| `bairro_municipio_cache_pkey` | `id` | UNIQUE (PK) | — |
| `uq_cache_termo_municipio` | `termo_normalizado, COALESCE(municipio, '')` | UNIQUE | — |
| `bairro_municipio_cache_municipio_idx` | `municipio` | INDEX | municipio IS NOT NULL (pré-existente) |
| `idx_cache_termo` | `termo_normalizado` | INDEX | — |
| `idx_cache_sessao` | `sessao_id` | INDEX | sessao_id IS NOT NULL |

### Dados: 625 registros — zero alteração

- Todos receberam `id` UUID auto-gerado
- `sessao_id` e `cliente_id` = NULL nos registros existentes (será preenchido nos novos)
- Acessos preservados, fontes preservadas

### Teste de validação realizado

Inserido "Centro" em 2 municípios diferentes → PK nova aceitou (antes falharia com PK duplicada).
Registros de teste removidos após validação. Total final: 625.

---

## Resumo de impacto

| Tabela | Registros | Dados alterados | Schema alterado |
|--------|-----------|-----------------|-----------------|
| `area_entrega` | 17 | Nenhum | +1 coluna, +2 índices |
| `bairro_municipio_cache` | 625 | +id UUID populado | +3 colunas, PK trocada, +3 índices |

### O que a nova PK habilita

| Cenário | Antes | Depois |
|---------|-------|--------|
| buscar("centro") | 1 resultado (forçado pela PK) | N resultados (1 por município) |
| buscar("bangu") | 1 resultado | 1 resultado (só existe em RJ) |
| buscar("vila nova") | 1 resultado (errado se existir em 2+ cidades) | N resultados → sistema detecta ambiguidade |

### Próximos passos

1. Reescrever `area_entrega_repo.py` — query SQL filtrada em vez de SELECT *
2. Reescrever `bairro_municipio_cache_repo.py` — buscar() retorna lista, salvar() usa nova PK
3. Reescrever `localidade_frete.py` — fluxo sem web_search
4. Integrar ViaCEP como camada 3 de resolução
5. Atualizar prompt da IA — regra "pedir CEP ou município"
