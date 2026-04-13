# Relatorio de Otimizacoes — Agente 2W Pneus

**Data:** 30/03/2026
**Estado atual:** Agente funcional com GPT-5.4, pedido E2E confirmado.
**Objetivo:** Listar todas as otimizacoes possiveis em desempenho e economia
de tokens, ordenadas por impacto/risco. Nenhuma deve quebrar o sistema.

---

## Anatomia de custo atual (por turno)

```
Componente                     Tokens aprox.   % do total
──────────────────────────────────────────────────────────
System prompt (SYSTEM_PROMPT)     ~3.400          62%
Tools schema (5 tools JSON)         ~750          14%
Contexto JSON (sessao, fatos,       ~800          15%
  itens, mensagens_recentes)
Mensagem do usuario                  ~20           0.4%
Resposta do modelo (envelope)       ~350           6%
Overhead de tool call (quando)      ~500           9%
──────────────────────────────────────────────────────────
Total por chamada API           ~5.500-6.500
Total por turno (1 tool call)  ~10.000-12.000
Total conversa 7 turnos            ~49.000
```

O system prompt sozinho (3.400 tokens) e reenviado em TODA chamada API.
Numa conversa de 7 turnos com ~9 chamadas API, sao ~30.600 tokens so de prompt.

---

## Otimizacoes por prioridade

### PRIORIDADE 1 — Alto impacto, risco zero

#### 1.1 Prompt Caching da OpenAI
**Economia estimada:** 50-75% do custo de input
**Risco:** Zero — e uma feature da API, nao muda codigo

A OpenAI oferece cache automatico de prefixos de prompt. Se o system prompt
(3.400 tokens) for identico entre chamadas, a API cobra 50% menos por esses
tokens a partir da segunda chamada.

**Como ativar:** Ja esta ativo automaticamente desde out/2024 para modelos
GPT-4o e superiores. O custo cached e $1.25/1M (5.4) vs $2.50/1M (normal).

**Impacto real:** como o system prompt e 62% do input e e identico em todas
as chamadas, a economia e:
- Antes: 49.000 tokens input × $2.50/1M = $0.122
- Depois: ~30.600 cached × $1.25/1M + ~18.400 normal × $2.50/1M = $0.084
- **Economia: ~31% no input** (sem mudar nenhuma linha de codigo)

**Verificacao:** Para confirmar que o cache esta sendo usado, adicionar log
do campo `usage.prompt_tokens_details.cached_tokens` na resposta da API.

---

#### 1.2 Reduzir limite de mensagens_recentes de 20 para 6-8
**Economia estimada:** 400-800 tokens por chamada (~8-15%)
**Risco:** Minimo — conversa media tem 7-10 turnos, 6 mensagens cobre 3 turnos

No `montador_contexto.py` linha 60:
```python
# ANTES:
mensagens_db = mensagem_repo.listar_mensagens_por_sessao(sessao_id, limite=20)
# DEPOIS:
mensagens_db = mensagem_repo.listar_mensagens_por_sessao(sessao_id, limite=8)
```

20 mensagens = 10 turnos completos de historico. O modelo raramente precisa
de mais de 3-4 turnos para manter contexto. Os fatos_ativos ja carregam toda
informacao estruturada (moto, posicao, preferencia, etc).

---

#### 1.3 Remover campos redundantes de mensagens_recentes
**Economia estimada:** ~200 tokens por chamada
**Risco:** Zero — campos como `mensagem_id` e `criado_em` nao sao usados pelo modelo

No `montador_contexto.py`, simplificar `MensagemRecente`:
```python
# ANTES:
MensagemRecente(
    mensagem_id=str(m.id),      # modelo nunca usa
    direcao=m.direcao.value,
    remetente=m.remetente.value,
    conteudo_texto=m.conteudo_texto,
    criado_em=m.criado_em,       # modelo nunca usa
)
# DEPOIS:
MensagemRecente(
    direcao=m.direcao.value,
    remetente=m.remetente.value,
    conteudo_texto=m.conteudo_texto,
)
```

Cada `mensagem_id` (UUID) = 36 chars = ~10 tokens. Cada `criado_em`
(ISO datetime) = ~15 tokens. Em 8 mensagens = ~200 tokens economizados.

Requer ajustar o schema `MensagemRecente` em `contexto_executavel.py`
para tornar esses campos Optional.

---

#### 1.4 Corrigir bloqueios_identificados para evitar retries
**Economia estimada:** ~5.500 tokens por retry evitado (prompt inteiro reenviado)
**Risco:** Baixo — aceitar mais formatos, nao rejeitar menos

Bug ativo: modelo envia `bloqueios_identificados` com formato errado, causando
ParseError + retry em turnos de fechamento. Cada retry custa um prompt inteiro.

**Opcao A — schema flexivel (recomendada):**
```python
# Em envelope_ia.py, adicionar validator:
class BloqueioIdentificado(BaseModel):
    codigo_motivo: str = ""
    mensagem_motivo: str = ""
    campo_relacionado: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def aceitar_formatos_variados(cls, data):
        if isinstance(data, str):
            return {"codigo_motivo": "bloqueio_generico", "mensagem_motivo": data}
        if isinstance(data, dict):
            # Modelo envia {chave, valor} ao inves de {codigo_motivo, mensagem_motivo}
            if "chave" in data and "codigo_motivo" not in data:
                data["codigo_motivo"] = data.pop("chave", "")
            if "valor" in data and "mensagem_motivo" not in data:
                data["mensagem_motivo"] = str(data.pop("valor", ""))
            # Modelo envia {codigo, descricao}
            if "codigo" in data and "codigo_motivo" not in data:
                data["codigo_motivo"] = data.pop("codigo", "")
            if "descricao" in data and "mensagem_motivo" not in data:
                data["mensagem_motivo"] = data.pop("descricao", "")
        return data
```

**Opcao B — prompt:**
Adicionar exemplo de bloqueios_identificados no prompt. Menos confiavel.

**Impacto:** elimina ~1 retry por turno em fechamento = 5.500 tokens + 1-2s.

---

### PRIORIDADE 2 — Medio impacto, risco baixo

#### 2.1 Remover campos desnecessarios de fatos_ativos no contexto
**Economia estimada:** ~300-500 tokens por chamada
**Risco:** Baixo

Campos que o modelo nao usa em `FatoAtivo`:
- `tipo_de_verdade` (observado/inferido/validado_tool) — modelo nao precisa
- `nivel_confirmacao` — modelo nao precisa
- `fonte` (mensagem_cliente/inferido_ia/backend) — modelo nao precisa
- `mensagem_chat_id` — modelo nao precisa
- `item_provisorio_id` — modelo nao precisa
- `coletado_em` — modelo nao precisa

O modelo so precisa de `chave` e `valor`. Todos os outros sao metadados de
auditoria que servem para o backend, nao para o LLM.

```python
# Contexto simplificado para o modelo:
fatos_ativos = [
    {"chave": f.chave, "valor": f.valor_texto or f.valor_json}
    for f in fatos_db
]
```

**Implementacao:** criar um `model_dump` simplificado para a versao que vai
pro modelo, mantendo o objeto completo para uso interno do orquestrador.

---

#### 2.2 Compactar tools schema — remover tools nao usaveis por etapa
**Economia estimada:** ~300-500 tokens por chamada em etapas que nao usam tools
**Risco:** Baixo-medio — requer logica condicional no agente

Nas etapas `confirmacao_item`, `entrega_pagamento` e `fechamento`, o modelo
quase nunca usa tools. Enviar 5 tools schema nesses turnos e desperdicio.

```python
# Em agente.py, condicionar tools por etapa:
TOOLS_POR_ETAPA = {
    "identificacao": TOOLS_SCHEMA,           # todas
    "busca": TOOLS_SCHEMA,                   # todas
    "oferta": [TOOL_CONSULTAR_ESTOQUE, TOOL_BUSCAR_DETALHES],  # 2
    "confirmacao_item": [],                  # nenhuma
    "entrega_pagamento": [],                 # nenhuma
    "fechamento": [],                        # nenhuma
}
```

**Economia:** 750 tokens × ~4 turnos sem tools = 3.000 tokens/conversa.

---

#### 2.3 Passar historico como role messages ao inves de JSON
**Economia estimada:** ~200-400 tokens por chamada
**Risco:** Medio — muda a arquitetura de chamada, pode afetar comportamento
**Melhoria qualitativa:** modelo processa conversa de forma nativa

Em vez de serializar mensagens_recentes como JSON no contexto, passa-las como
mensagens OpenAI proprias:

```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "system", "content": f"CONTEXTO (sem mensagens):\n{contexto_sem_msgs}"},
    # historico real:
    {"role": "user", "content": "fala meu filho boa noite"},
    {"role": "assistant", "content": "Opa, boa noite! Como posso te ajudar?"},
    {"role": "user", "content": "tem pneu pra pcx?"},
    {"role": "assistant", "content": "Temos pra PCX sim! Tem preferencia?"},
    # mensagem atual:
    {"role": "user", "content": mensagem_atual},
]
```

**Vantagem:** modelo interpreta melhor o contexto conversacional.
**Desvantagem:** mais complexo de implementar; precisa serializar mensagens
de saida (que sao JSON do envelope) como apenas a `mensagem_cliente`.

**Recomendacao:** fazer apos estabilizar o fluxo atual. Nao e urgente.

---

### PRIORIDADE 3 — Baixo impacto imediato, valor futuro

#### 3.1 Compactar system prompt
**Economia estimada:** ~500-800 tokens (15-23% do prompt)
**Risco:** Medio — mexer no prompt pode afetar comportamento

O prompt atual (252 linhas, ~3.400 tokens) tem:
- Exemplos ERRADO/CORRETO repetidos (~400 tokens que so servem de guardrail)
- Secoes de JSON de exemplo (~300 tokens)
- Secao de acoes validas por etapa (~200 tokens — ja esta no contexto JSON)

**O que pode ser removido sem perda:**
- A lista de "acoes validas por etapa" (linhas 206-214) — ja vem no contexto
  como `acoes_permitidas` e o validator ja impoe isso
- Exemplos duplicados (CORRETO+ERRADO quando o ERRADO ja esta claro pelo CORRETO)

**O que NAO deve ser removido:**
- Regras de tom e estilo — definem a personalidade
- Regras de negocio — definem o comportamento anti-alucinacao
- Exemplos de JSON do envelope — modelo precisa saber o formato

---

#### 3.2 Implementar early exit para turnos sem tool call
**Economia estimada:** ~750 tokens/turno (tools schema nao enviado)
**Risco:** Baixo

Se o turno nao precisa de tools (ex: confirmacao, entrega, fechamento),
chamar a API sem `tools` no kwargs economiza o schema das 5 tools.

Ja parcialmente coberto por 2.2, mas pode ser feito de forma mais simples:
se `etapa_atual in ("confirmacao_item", "entrega_pagamento", "fechamento")`,
nao envia tools.

---

#### 3.3 Cache de contexto entre turnos de mesma sessao
**Economia estimada:** reduz chamadas ao Supabase (latencia, nao tokens)
**Risco:** Medio — cache invalidation e complexa

`montar_contexto` faz 5-6 queries ao Supabase por turno. Para conversas
rapidas (cliente responde em 5s), o contexto quase nao mudou. Um cache
com TTL de 10s reduziria queries sem risco de stale data.

---

## Tabela resumo

| # | Otimizacao | Tokens/chamada | Tokens/conversa | Risco | Requer codigo |
|---|---|---|---|---|---|
| 1.1 | Prompt caching | -1.700 (cached) | -15.300 | Zero | Nao |
| 1.2 | Mensagens 20→8 | -400 a -800 | -3.600 a -7.200 | Minimo | 1 linha |
| 1.3 | Remover campos msgs | -200 | -1.800 | Zero | 5 linhas |
| 1.4 | Fix bloqueios schema | -5.500/retry | -5.500 a -11.000 | Baixo | 15 linhas |
| 2.1 | Simplificar fatos | -300 a -500 | -2.700 a -4.500 | Baixo | 10 linhas |
| 2.2 | Tools por etapa | -750/turno s/ tool | -3.000 | Baixo-medio | 20 linhas |
| 2.3 | Role messages | -200 a -400 | -1.800 a -3.600 | Medio | 40 linhas |
| 3.1 | Compactar prompt | -500 a -800 | -4.500 a -7.200 | Medio | Prompt |
| 3.2 | Early exit no tools | -750/turno | -3.000 | Baixo | 5 linhas |
| 3.3 | Cache Supabase | 0 (latencia) | 0 (latencia) | Medio | 30 linhas |

---

## Projecao de economia total

**Cenario: aplicar todas as otimizacoes de prioridade 1**
(prompt caching + mensagens 8 + campos limpos + fix bloqueios)

| Metrica | Antes | Depois | Reducao |
|---|---|---|---|
| Tokens input/conversa | ~49.000 | ~28.000 | -43% |
| Tokens output/conversa | ~2.200 | ~2.200 | 0% |
| Custo/conversa (GPT-5.4) | $0.156 | $0.093 | -40% |
| Custo/1000 conversas | $80 | $47 | -$33/mes |
| Custo/venda (5% conv) | R$9.28 | R$5.46 | -R$3.82 |

**Cenario: aplicar prioridades 1 + 2**

| Metrica | Antes | Depois | Reducao |
|---|---|---|---|
| Tokens input/conversa | ~49.000 | ~22.000 | -55% |
| Custo/conversa (GPT-5.4) | $0.156 | $0.072 | -54% |
| Custo/1000 conversas | $80 | $36 | -$44/mes |

---

## Recomendacao de ordem de implementacao

1. **Agora (5 min):** Reduzir mensagens de 20 para 8 (1 linha)
2. **Agora (15 min):** Fix `bloqueios_identificados` schema (elimina retries)
3. **Proximo sprint:** Remover campos inuteis de `mensagens_recentes` e `fatos_ativos`
4. **Proximo sprint:** Condicionar tools por etapa
5. **Futuro:** Role messages, compactar prompt, cache Supabase

As 2 primeiras eliminam ~40% do custo sem risco de regressao.
