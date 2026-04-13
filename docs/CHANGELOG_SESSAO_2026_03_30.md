# Changelog — Sessao 30/03/2026

## Resumo

Sessao focada em: (1) teste do agente com GPT-5.4-mini, (2) correcao de bugs
encontrados no mini, (3) comparacao mini vs 5.4, (4) analise de custos.

**Resultado final:** agente funcional com GPT-5.4, pedido criado end-to-end.
Backup disponivel em `backup_sessao_2026_03_30/`.

---

## Alteracoes realizadas

### 1. validador_envelope.py — Tolerancia a confusao pneu_id/item_provisorio_id

**Problema:** O modelo (especialmente o mini) confunde `pneu_id` com
`item_provisorio_id` ao confirmar itens. UUID `0cce4ee0-...` era o pneu_id
mas o modelo usava como item_provisorio_id. Validator rejeitava, retry
falhava, item nunca era confirmado, pedido nunca criado.

**Correcao:** Antes de rejeitar, verifica se o UUID informado e um `pneu_id`
de algum item no contexto. Se for, deixa passar — o orquestrador auto-corrige.

```python
# ANTES:
ids_itens = {ip.item_provisorio_id for ip in contexto.itens_provisorios}
for mudanca in envelope.mudancas_itens:
    if mudanca.item_provisorio_id and mudanca.item_provisorio_id not in ids_itens:
        erros.append(...)

# DEPOIS:
ids_itens = {ip.item_provisorio_id for ip in contexto.itens_provisorios}
pneu_ids_de_itens = {ip.pneu_id for ip in contexto.itens_provisorios if ip.pneu_id}
for mudanca in envelope.mudancas_itens:
    if mudanca.item_provisorio_id and mudanca.item_provisorio_id not in ids_itens:
        if mudanca.item_provisorio_id not in pneu_ids_de_itens:
            erros.append(...)
```

**Arquivo:** `agente_2w/engine/validador_envelope.py` linhas 55-66

---

### 2. orquestrador.py — Auto-correcao de item_provisorio_id

**Problema:** Mesmo que o validator deixe passar, o orquestrador precisa
resolver o UUID correto para atualizar o status do item no banco.

**Correcao:** Em `_aplicar_mudancas_itens`, para acoes `confirmar/rejeitar/
cancelar/atualizar`, adicionada logica de fallback em 3 niveis:

1. Busca direta pelo UUID como `item.id` (comportamento normal)
2. Se nao encontrar, busca pelo UUID como `item.pneu_id` (confusao do modelo)
3. Se ainda nao encontrar e so tem 1 item ativo, usa esse item

```python
# Auto-correcao: modelo as vezes passa pneu_id no lugar de item_provisorio_id
itens_ativos = item_provisorio_repo.listar_itens_ativos_por_sessao(sessao_id)
item_direto = next((i for i in itens_ativos if i.id == item_id), None)
if item_direto is None:
    item_por_pneu = next(
        (i for i in itens_ativos if i.pneu_id and str(i.pneu_id) == str(item_id)),
        None,
    )
    if item_por_pneu:
        item_id = item_por_pneu.id  # auto-correcao
    elif len(itens_ativos) == 1:
        item_id = itens_ativos[0].id  # fallback para item unico
```

**Arquivo:** `agente_2w/engine/orquestrador.py` linhas 301-340

---

### 3. prompt_sistema.py — Aviso sobre pneu_id vs item_provisorio_id

**Problema:** O modelo nao tem instrucao clara sobre qual UUID usar na
confirmacao de item.

**Correcao:** Adicionada nota critica apos o exemplo de JSON de confirmacao:

```
CRITICO: o valor de `item_provisorio_id` aqui deve ser copiado de
`itens_provisorios[].item_provisorio_id` no contexto — NAO use o pneu_id.
```

**Arquivo:** `agente_2w/ia/prompt_sistema.py` linha 189

---

## Testes realizados

### Teste automatizado (teste_conversa_natural.py) com GPT-5.4-mini
- **Resultado:** PASS
- Pedido criado: R$239,90, Pirelli Street Rider, entrega, dinheiro
- 1 retry no turno 4 (busca→confirmacao_item skip tentado), auto-corrigido

### Teste manual CLI com GPT-5.4-mini
- **Resultado:** FAIL — pedido NAO criado
- Bugs observados:
  - `bloqueios_identificados` schema errado (modelo usa `{chave, valor}` em vez de `{codigo_motivo, mensagem_motivo}`) — causa ParseError+retry em todo turno de fechamento
  - Item provisorio nao criado (modelo manda `atualizar` sem item_provisorio_id)
  - Ficou em loop de "Confirma?" no fechamento sem nunca criar o pedido

### Teste manual CLI com GPT-5.4
- **Resultado:** PASS
- Pedido criado: R$259,90, CST Ride Migra, entrega em Caxias, cartao
- Auto-promocao funcionou: `promover_para_pedido` chamado via RPC
- 1 retry por ParseError em `bloqueios_identificados` (string ao inves de dict)
- Tom natural, fluiu como conversa humana real

---

## Comparacao GPT-5.4-mini vs GPT-5.4

| Aspecto | Mini | 5.4 |
|---|---|---|
| Pedido criado (teste auto) | Sim (com fixes) | Sim |
| Pedido criado (teste manual) | Nao | Sim |
| Retries por turno | 1-2 | 0-1 |
| Schema bloqueios correto | Nunca | As vezes (1 retry) |
| Item provisorio criado | As vezes | Sempre |
| item_provisorio_id correto | Quase nunca | Sempre |
| Tom de conversa | Bom | Excelente |
| Processamento multi-info | Parcial | Completo |
| Custo por conversa (7 turnos) | ~$0.047 | ~$0.156 |

**Conclusao:** GPT-5.4 e superior em qualidade de atendimento e confiabilidade.
O custo adicional (~R$0.63/conversa) e irrelevante frente a margem de um pneu.

---

## Bug ativo nao corrigido

**`bloqueios_identificados` schema mismatch:**
Tanto mini quanto 5.4 enviam `bloqueios_identificados` com formato errado.
O schema Pydantic exige `{codigo_motivo: str, mensagem_motivo: str}` mas os
modelos enviam `{chave: str, valor: str}` ou uma string solta.

Causa: ParseError + 1 retry em turnos de fechamento.
Impacto: ~1-2 segundos extras + tokens desperdicados por turno.
Solucao possivel: aceitar mais formatos no schema ou exemplo no prompt.
