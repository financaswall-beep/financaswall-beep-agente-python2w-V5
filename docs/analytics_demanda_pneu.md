# Analytics de Demanda de Pneus

**Data:** 2026-04-06
**Projeto Supabase:** betaAgente (`vyxdquwxmgibpkoswxut`)

## Objetivo

Registrar **toda intenção de busca de pneu por clientes**, independente de:
- Ter estoque ou não
- Ter vindo do catálogo local, cache ou busca web
- Ter resultado em compra ou não

Permite relatórios de **sazonalidade**, **falta de estoque** e **taxa de conversão** por período.

---

## Tabela: `log_demanda_pneu`

Tabela de eventos (append-only). Cada busca de pneu = 1 registro.

| Coluna | Tipo | Nullable | Descrição |
|--------|------|----------|-----------|
| `id` | uuid (PK) | NO | Auto-gerado |
| `sessao_id` | uuid (FK → sessao_chat) | YES | Sessão de chat do cliente |
| `cliente_id` | uuid (FK → cliente) | YES | Cliente (quando disponível) |
| `moto` | text | NO | Moto buscada (termo original) |
| `marca_moto` | text | YES | Marca extraída (Yamaha, Honda...) |
| `ano_moto` | integer | YES | Ano extraído (2024, 2025...) |
| `posicao` | text | NO | dianteiro / traseiro |
| `largura` | integer | YES | Largura do pneu (ex: 120) |
| `perfil` | integer | YES | Perfil do pneu (ex: 70) |
| `aro` | integer | YES | Aro do pneu (ex: 15) |
| `tinha_estoque` | boolean | NO | Encontrou pneu disponível no catálogo? |
| `fonte_resolucao` | text | NO | `catalogo` / `cache` / `web` / `nenhuma` |
| `canal` | text | YES | whatsapp / web / cli |
| `converteu_pedido` | boolean | NO | Busca resultou em pedido confirmado? |
| `pedido_id` | uuid (FK → pedido) | YES | ID do pedido (quando converteu) |
| `preco_encontrado` | numeric(10,2) | YES | Preço do primeiro pneu retornado |
| `criado_em` | timestamptz | NO | Timestamp da busca |

### Índices

- `idx_log_demanda_criado_em` — ordenação por data (relatórios por período)
- `idx_log_demanda_moto` — filtro por moto
- `idx_log_demanda_medida` — filtro por medida (largura, perfil, aro)
- `idx_log_demanda_converteu` — filtro por conversão
- `idx_log_demanda_cliente` — filtro por cliente

---

## Views de Relatório

Todas as views leem `log_demanda_pneu` em tempo real (não duplicam dados).

### `v_demanda_semanal`

Pneus mais buscados agrupados por semana.

| Coluna | Descrição |
|--------|-----------|
| `semana` | Início da semana |
| `moto`, `posicao`, `largura`, `perfil`, `aro` | Identificação do pneu |
| `total_buscas` | Total de buscas na semana |
| `buscas_com_estoque` | Quantas tinham estoque |
| `buscas_sem_estoque` | Quantas NÃO tinham estoque |
| `conversoes` | Quantas viraram pedido |
| `taxa_conversao_pct` | % de conversão |

### `v_demanda_mensal`

Mesma estrutura, agrupado por mês. Ideal para sazonalidade.

### `v_falta_estoque`

Pneus buscados que NÃO tinham no catálogo, ordenados por demanda.

| Coluna | Descrição |
|--------|-----------|
| `moto`, `posicao`, `largura`, `perfil`, `aro` | Identificação |
| `vezes_sem_estoque` | Quantas vezes pediram e não tinha |
| `ultima_vez` | Última vez que foi procurado |
| `clientes_distintos` | Quantos clientes diferentes pediram |

### `v_conversao_por_pneu`

Taxa de conversão por medida (busca → pedido).

| Coluna | Descrição |
|--------|-----------|
| `total_buscas` | Total de buscas para essa medida |
| `total_vendas` | Quantas resultaram em pedido |
| `taxa_conversao_pct` | % de conversão |
| `preco_medio` | Preço médio apresentado |

---

## Integração no Código

### Onde é registrada a busca

**Arquivo:** `agente_2w/tools/busca_catalogo.py`
**Função:** `buscar_pneus_por_moto()`

O log acontece em **todos os pontos terminais** (onde tem `return`):

| Caminho | `fonte_resolucao` | `tinha_estoque` |
|---------|-------------------|-----------------|
| Catálogo local com estoque | `catalogo` | `true` |
| Catálogo local, posição indisponível | `catalogo` | `false` |
| Cache web com estoque | `cache` | `true` |
| Busca web com estoque | `web` | `true` |
| Busca web sem estoque | `web` | `false` |
| Nada encontrado | `nenhuma` | `false` |

**Regra importante:** só loga nos pontos terminais (`return`), nunca em passagens intermediárias (ex: cache sem estoque que cai pro web search). Isso evita duplicatas.

### Onde é marcada a conversão

**Arquivo:** `agente_2w/engine/promotor.py`
**Função:** `promover_para_pedido()`

Após pedido criado com sucesso:
```python
log_demanda_pneu_repo.marcar_converteu_pedido(sessao_id, pedido.id)
```

Atualiza todos os registros da sessão: `converteu_pedido = true`, `pedido_id = <id>`.

### Repositório

**Arquivo:** `agente_2w/db/log_demanda_pneu_repo.py`

Duas funções, ambas **fail-safe** (nunca levantam exceção):
- `registrar_busca(...)` — INSERT no log
- `marcar_converteu_pedido(sessao_id, pedido_id)` — UPDATE para conversão

---

## Custo

**Zero tokens de IA.** O backend Python faz o INSERT diretamente no Supabase com dados que já estão em memória. Nenhuma chamada extra à API de IA.

---

## Consultas Úteis

```sql
-- Mais buscados na semana passada
SELECT * FROM v_demanda_semanal
WHERE semana = date_trunc('week', now()) - interval '7 days';

-- Mais buscados no mês passado
SELECT * FROM v_demanda_mensal
WHERE mes = date_trunc('month', now()) - interval '1 month';

-- Pneus mais pedidos que NÃO temos em estoque
SELECT * FROM v_falta_estoque LIMIT 20;

-- Taxa de conversão por pneu
SELECT * FROM v_conversao_por_pneu WHERE total_buscas >= 5;

-- Sazonalidade de uma medida específica
SELECT mes, total_buscas, conversoes
FROM v_demanda_mensal
WHERE largura = 120 AND perfil = 70 AND aro = 17
ORDER BY mes;
```
