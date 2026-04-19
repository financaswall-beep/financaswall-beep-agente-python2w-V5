# Relatório — Próxima Sessão de Correções
## Agente 2W Pneus — Pendências após sessão de 19/04/2026

---

## CONTEXTO GERAL

O agente foi auditado e 10 bugs foram corrigidos na sessão anterior.
Restam 4 pendências concretas (2 em código Python, 2 em SQL no Supabase).
O código está em: `agente_2w/engine/orquestrador/_nucleo.py`

---

## PENDÊNCIA 1 — A1 (CRÍTICA): Redes de segurança 9b/9c/9d criam itens duplicados

### O arquivo e as linhas exatas
- Arquivo: `agente_2w/engine/orquestrador/_nucleo.py`
- Rede 9b: linhas ~1358–1387
- Rede 9c: linhas ~1389–1441
- Rede 9d: linhas ~1443–1493

### O problema
As redes 9b, 9c e 9d chamam diretamente `item_provisorio_repo.criar_item(...)`.
O módulo `enriquecimento_itens.py` tem uma guarda anti-duplicata robusta
(linhas 152–162) que checa se já existe item com o mesmo `pneu_id` antes de criar.
Mas as redes 9b/9c/9d **pulam esse módulo** e chamam o repo diretamente.
Resultado: duplicatas entram quando duas redes disparam no mesmo turno.

### A guarda que existe em enriquecimento_itens.py (linhas 152–162)
```python
itens_existentes = item_provisorio_repo.listar_itens_ativos_por_sessao(sessao_id)
duplicata = next(
    (i for i in itens_existentes if i.pneu_id and str(i.pneu_id) == str(pneu_uuid)),
    None,
)
if duplicata:
    logger.info("Item duplicado ignorado: pneu_id=%s ja existe como item %s", ...)
    continue
```

### A correção a aplicar
Em cada uma das 3 redes (9b, 9c, 9d), ANTES de chamar `item_provisorio_repo.criar_item(...)`,
adicionar a mesma checagem anti-duplicata:

```python
# Guarda anti-duplicata (mesma logica de enriquecimento_itens.py:152)
_itens_check = item_provisorio_repo.listar_itens_ativos_por_sessao(sessao_id)
if any(i.pneu_id and str(i.pneu_id) == str(pneu_uuid) for i in _itens_check):
    logger.info("Rede 9X: item pneu_id=%s ja existe — skip", pneu_uuid)
    continue  # ou: pass + não criar
```

Isso precisa ser adicionado em 3 lugares (9b ~linha 1371, 9c ~linha 1424, 9d ~linha 1475),
sempre logo antes da chamada `item_provisorio_repo.criar_item(...)`.

---

## PENDÊNCIA 2 — 1.4 (ALTA): Safety net de finalização cobre posição errada

### O arquivo e as linhas exatas
- Arquivo: `agente_2w/engine/orquestrador/_nucleo.py`
- Função: `_salvar_itens_orfaos_pre_finalizacao`
- Linhas problemáticas: ~476–479

### O problema
A função decide quais posições (dianteiro/traseiro) já estão cobertas para não criar duplicata.
O código atual marca uma posição como "coberta" baseado em `pneu_id in pneu_ids_ja_salvos`.
O problema: `pneu_ids_ja_salvos` inclui itens com qualquer status (inclusive `sugerido` — apenas sugerido pela IA, não confirmado pelo cliente).
Isso bloqueia a criação de itens de posições que o cliente confirmou mas cujo item
ainda estava com status `sugerido`.

### Código atual (linhas ~476–479)
```python
posicoes_ja_cobertas: set[str] = set()
for item in itens_ativos:
    if item.posicao and item.pneu_id and str(item.pneu_id) in pneu_ids_ja_salvos:
        posicoes_ja_cobertas.add(item.posicao.lower().strip())
```

### A correção
Trocar para filtrar apenas itens com status `selecionado_cliente` ou `validado`:
```python
posicoes_ja_cobertas: set[str] = set()
for item in itens_ativos:
    if item.posicao and item.status_item in (
        StatusItemProvisorio.selecionado_cliente,
        StatusItemProvisorio.validado,
    ):
        posicoes_ja_cobertas.add(item.posicao.lower().strip())
```

`StatusItemProvisorio` já está importado no topo do arquivo.

---

## PENDÊNCIA 3 — SQL (URGENTE): UNIQUE constraint em item_provisorio

### O que é
Uma linha de SQL para rodar direto no Supabase (Dashboard → SQL Editor).
Isso cria uma trava no banco de dados que impede físicamente itens duplicados,
mesmo que algum caminho no código Python escape das guardas.

### O SQL a executar
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_item_prov_sessao_pneu_ativo
  ON item_provisorio(sessao_chat_id, pneu_id)
  WHERE status_item IN ('sugerido','selecionado_cliente','validado');
```

### Como executar
1. Acessar Supabase Dashboard do projeto `vyxdquwxmgibpkoswxut`
2. Ir em: Database → SQL Editor
3. Colar e executar o SQL acima
4. Confirmar que não retornou erro

---

## PENDÊNCIA 4 — SQL (URGENTE): Habilitar pg_cron para limpar estoque fantasma

### O que é
O banco tem uma função `liberar_reservas_orfas` que limpa estoque preso por sessões que expiraram.
Ela existe mas **nunca roda** porque o agendador (pg_cron) está desligado.
Enquanto isso, estoque some lentamente: pneus com 5 unidades aparecem como 0 para o agente.

### Passo 1 — Limpar estoque fantasma acumulado (AGORA)
```sql
SELECT liberar_reservas_orfas(7);
```
Isso libera reservas de pedidos com mais de 7 dias sem atividade.
Executar uma vez para limpar o débito atual.

### Passo 2 — Habilitar pg_cron
No Supabase Dashboard:
1. Ir em: Database → Extensions
2. Ativar extensão **pg_cron**

### Passo 3 — Agendar execução diária
```sql
SELECT cron.schedule(
  'liberar-orfas-diario',
  '0 3 * * *',
  $$SELECT liberar_reservas_orfas(7)$$
);
```
Isso roda todos os dias às 3h da manhã.

---

## OUTRAS PENDÊNCIAS (menor prioridade)

### B10 — Código duplicado em area_entrega_repo.py
- Arquivo: `agente_2w/db/area_entrega_repo.py`
- Linhas 114–199 são cópia das linhas 1–113 (merge errado)
- Correção: deletar as linhas 114–199

### B7/B11 — Contexto sem limite de tamanho
- Arquivos: `agente_2w/db/contexto_repo.py` (função `listar_fatos_ativos`)
              `agente_2w/engine/montador_contexto.py`
- Problema: em sessões longas, o contexto fica enorme e cara
- Correção: adicionar `.limit(30).order("coletado_em", desc=True)` nas queries

### Stats do cliente fora da transação (2.4)
- Arquivo: `agente_2w/engine/promotor.py` linha ~465
- Problema: `_atualizar_stats_cliente` roda fora da RPC transacional.
  Se o servidor cair entre a criação do pedido e o update de stats,
  os números do cliente ficam errados.
- Correção: criar trigger AFTER INSERT ON pedido no Supabase,
  ou mover a lógica para dentro da RPC `promover_para_pedido`.

---

## ORDEM DE EXECUÇÃO RECOMENDADA

1. **SQL Passo 1**: rodar `SELECT liberar_reservas_orfas(7)` — limpa o que está errado hoje
2. **SQL Passo 2 e 3**: habilitar pg_cron e agendar — evita que o problema volte
3. **SQL Pendência 3**: criar UNIQUE index em item_provisorio — trava no banco
4. **Código Pendência 1**: adicionar guarda anti-duplicata em 9b/9c/9d — 3 blocos, ~5 linhas cada
5. **Código Pendência 2**: corrigir posicoes_ja_cobertas — 4 linhas
6. **Código B10**: deletar linhas duplicadas em area_entrega_repo.py
7. **Código B7/B11**: adicionar LIMIT 30 nas queries de contexto
