# CHANGELOG — Sessão 2026-04-15

## Objetivo
Implementar roteamento híbrido de modelo OpenAI (2 tiers) para reduzir custo ~60-70%
substituindo `gpt-4o` pela família `gpt-5.4`.

---

## Contexto / Pesquisa feita

### Preços confirmados (pricing page oficial)
| Modelo | Input | Output |
|---|---|---|
| `gpt-5.4` | $2.50/M | $15.00/M |
| `gpt-5.4-mini` | $0.75/M | $4.50/M |
| `gpt-5.4-nano` | $0.20/M | $1.25/M |
| `gpt-5.4-pro` | $30.00/M | $180.00/M |

### ⚠️ Descoberta crítica (migrate-to-responses guide)
> "Starting with GPT-5.4, **tool calling is not supported in Chat Completions with `reasoning: none`**."

`gpt-5.4` usa `reasoning.effort = "none"` por padrão. Isso significa:
- Chamar `_client.chat.completions.create(tools=..., model="gpt-5.4")` **sem** definir `reasoning_effort` → **ERRO**
- Solução: adicionar `reasoning_effort="low"` quando o modelo for reasoning + tools estiverem presentes
- `gpt-5.4-mini` e `gpt-5.4-nano` **NÃO** são reasoning models → `temperature=0.3` funciona normalmente

### Comportamento de gpt-5.4-mini (prompt-guidance)
- Mais literal, menos inferência implícita — prompts precisam ser mais explícitos
- Por padrão tenta fazer follow-up questions → suprimir no system prompt se indesejado
- Não afeta nossa arquitetura atual (o prompt já é explícito)

---

## Lógica de roteamento implementada

```
tentativa=1 (primeira chamada)  → MINI    (temperatura=0.3, barato)
tentativa=2+  (retry)           → FLAGSHIP (reasoning_effort="low", mais inteligente)
imagem presente                 → FLAGSHIP (reasoning_effort="low", melhor visão)
sem imagem + primeira tentativa → MINI
```

**Por que Flagship em retries?** Se o JSON veio inválido na primeira tentativa, o modelo menor não conseguiu. Flagship tem mais inteligência para corrigir.

**Por que Flagship com imagem?** Qualidade de vision é melhor no modelo maior.

---

## Arquivos modificados

### `agente_2w/config.py`
**Adicionado** após `OPENAI_MODEL`:
```python
# ─── Roteamento de modelos (2 tiers) ──────────────────────────────────────────
# MINI  : ~70% dos turnos (turnos normais). Barato e rapido.
# FLAGSHIP: retries e mensagens com imagem. Mais inteligente.
# Rollback : sete OPENAI_MODEL_MINI=gpt-4o para desligar roteamento sem tocar codigo.
OPENAI_MODEL_MINI: str = os.getenv("OPENAI_MODEL_MINI", OPENAI_MODEL)
OPENAI_MODEL_FLAGSHIP: str = os.getenv("OPENAI_MODEL_FLAGSHIP", OPENAI_MODEL)
```
**Fallback de segurança:** se as variáveis não estiverem no Coolify, ambas herdam `OPENAI_MODEL` → comportamento idêntico ao estado anterior.

---

### `agente_2w/ia/agente.py`

**1. Import atualizado:**
```python
# ANTES:
from agente_2w.config import OPENAI_API_KEY, OPENAI_MODEL, MAX_TOOL_ROUNDS

# DEPOIS:
from agente_2w.config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MODEL_MINI, OPENAI_MODEL_FLAGSHIP, MAX_TOOL_ROUNDS
```

**2. Funções novas adicionadas antes de `_chamar_openai`:**
```python
def _e_modelo_reasoning(modelo: str) -> bool:
    """True se o modelo usa reasoning tokens (gpt-5.4 flagship, nao mini nem nano).

    gpt-5.4 exige reasoning_effort para usar tool_calls no Chat Completions.
    gpt-5.4-mini e gpt-5.4-nano sao modelos normais (sem restricao de reasoning).
    """
    m = modelo.lower()
    return "gpt-5." in m and "mini" not in m and "nano" not in m


def _escolher_modelo(tentativa: int, tem_imagem: bool) -> str:
    """Roteia para FLAGSHIP em retries/imagens, MINI no resto."""
    if tentativa > 1 or tem_imagem:
        return OPENAI_MODEL_FLAGSHIP
    return OPENAI_MODEL_MINI
```

**3. `_chamar_openai` atualizado:**
- Novo parâmetro `model: str | None = None`
- Quando `tools` + `_e_modelo_reasoning(modelo)=True`: adiciona `reasoning_effort="low"` (sem `temperature`)
- Quando `tools` + modelo não-reasoning: adiciona `temperature=0.3`
- Quando sem `tools`: sempre `temperature=0.3` (reasoning:none sem tools funciona para qualquer modelo)

```python
def _chamar_openai(messages: list, tools=None, model: str | None = None) -> object:
    modelo = model or OPENAI_MODEL
    kwargs = {
        "model": modelo,
        "messages": messages,
        "response_format": { ... },  # json_schema não mudou
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
        kwargs["parallel_tool_calls"] = False
        if _e_modelo_reasoning(modelo):
            kwargs["reasoning_effort"] = "low"  # ← desbloqueia tool_calls para gpt-5.4
        else:
            kwargs["temperature"] = 0.3
    else:
        kwargs["temperature"] = 0.3
    return _client.chat.completions.create(**kwargs)
```

**4. `chamar_agente` atualizado:**
- Novo parâmetro `tentativa: int = 1`
- Log de roteamento: `[ROUTER] modelo=... imagem=... tentativa=...`
- Ambas as chamadas `_chamar_openai` recebem `model=modelo`

```python
def chamar_agente(
    contexto: ContextoExecutavel,
    mensagem_usuario: str,
    imagens: list[str] | None = None,
    tentativa: int = 1,          # ← NOVO
) -> tuple[str, list[dict]]:
    ...
    modelo = _escolher_modelo(tentativa, bool(imagens))
    logger.info("[ROUTER] modelo=%s imagem=%s tentativa=%d", modelo, bool(imagens), tentativa)
    ...
    response = _chamar_openai(messages, tools=TOOLS_SCHEMA, model=modelo)   # no loop
    ...
    response = _chamar_openai(messages, model=modelo)                        # final sem tools
```

---

### `agente_2w/tools/busca_web.py`

**Import atualizado:**
```python
# ANTES:
from agente_2w.config import OPENAI_API_KEY, OPENAI_MODEL

# DEPOIS:
from agente_2w.config import OPENAI_API_KEY, OPENAI_MODEL_MINI
```

**Chamada atualizada:**
```python
# ANTES:  model=OPENAI_MODEL,
# DEPOIS: model=OPENAI_MODEL_MINI,
```

**Racional:** `busca_web.py` usa Responses API com `web_search_preview`. O modelo só precisa escrever texto livre listando medidas de pneu — um regex faz o parsing. Mini é mais que suficiente e custa menos.

> ⚠️ Nota: `busca_web.py` usa **Responses API** (`_client.responses.create`), não Chat Completions. A restrição de `reasoning:none + tools` NÃO se aplica aqui.

---

### `agente_2w/engine/orquestrador/_nucleo.py`

**Chamada de `chamar_agente` atualizada no loop de retry:**
```python
# ANTES:
resposta_bruta, pneus_da_chamada = chamar_agente(contexto, msg, imagens=imgs)

# DEPOIS:
resposta_bruta, pneus_da_chamada = chamar_agente(
    contexto, msg, imagens=imgs, tentativa=tentativa + 1,
)
```

**Racional:** A variável `tentativa` no loop começa em `0` (`for tentativa in range(1 + MAX_RETRIES)`).
- `tentativa=0` → `tentativa+1=1` → `_escolher_modelo(1, ...)` → **MINI** ✅
- `tentativa=1` → `tentativa+1=2` → `_escolher_modelo(2, ...)` → **FLAGSHIP** ✅

---

## Como ativar em produção (Coolify)

Adicionar/atualizar estas variáveis de ambiente:

```
OPENAI_MODEL=gpt-5.4
OPENAI_MODEL_MINI=gpt-5.4-mini
OPENAI_MODEL_FLAGSHIP=gpt-5.4
```

> **Importante:** `OPENAI_MODEL` precisa ser sobrescrito também porque `busca_web.py` agora usa `OPENAI_MODEL_MINI` (que herda de `OPENAI_MODEL`). Setar `OPENAI_MODEL=gpt-5.4` garante que o fallback global também esteja atualizado.

---

## Como fazer rollback

**Rollback rápido (sem deploy):** no Coolify, mudar:
```
OPENAI_MODEL_MINI=gpt-4o
OPENAI_MODEL_FLAGSHIP=gpt-4o
```
Nenhuma mudança de código necessária. Ambos os tiers voltam a usar gpt-4o.

**Rollback total (código):** reverter os 4 arquivos para o commit anterior ao desta sessão.

---

## Testes de validação sugeridos

Antes de ativar em produção, testar:
1. Turno normal → deve aparecer no log: `[ROUTER] modelo=gpt-5.4-mini imagem=False tentativa=1`
2. Mensagem com foto de pneu → deve aparecer: `[ROUTER] modelo=gpt-5.4 imagem=True tentativa=1`
3. Retry (forçar JSON inválido) → deve aparecer: `[ROUTER] modelo=gpt-5.4 imagem=False tentativa=2`
4. `busca_web.py` → log deve mencionar `gpt-5.4-mini` (verificar via log da tool)

---

## Status final

- [x] `config.py` — `OPENAI_MODEL_MINI` e `OPENAI_MODEL_FLAGSHIP` adicionados
- [x] `agente.py` — `_e_modelo_reasoning`, `_escolher_modelo`, `_chamar_openai(model=)`, `chamar_agente(tentativa=)`
- [x] `busca_web.py` — usa `OPENAI_MODEL_MINI`
- [x] `_nucleo.py` — passa `tentativa+1` para `chamar_agente`
- [x] Zero erros de lint/tipo
- [x] git commit b17a7ba — push para GitHub V5
- [x] Variáveis configuradas no Coolify + redeploy

---

## ⚠️ PROBLEMA DESCOBERTO EM PRODUÇÃO (15/04/2026 — tarde)

### Sintoma
Após o deploy no Coolify com `OPENAI_MODEL_MINI=gpt-5.4-mini`, produção passou a retornar
`"Desculpe, tive um problema ao processar sua mensagem"` em **todas** as mensagens.
Isso significa que **todos os retries também falharam** (mini E flagship).

### Causa raiz — BUG no código implementado

A documentação diz:

> **"Starting with GPT-5.4, tool calling is not supported in Chat Completions with `reasoning: none`."**

Isso vale para **TODA a família gpt-5.x — incluindo gpt-5.4-mini**.

O código implementado só adicionava `reasoning_effort` para o flagship:
```python
if _e_modelo_reasoning(modelo):   # True só para flagship
    kwargs["reasoning_effort"] = "low"
else:
    kwargs["temperature"] = 0.3   # ← mini cai aqui → reasoning:none → tools BLOQUEADAS
```

`gpt-5.4-mini` com `tools` + **sem** `reasoning_effort` = `reasoning: none` automático → API bloqueia tool calls → chamada falha → "Desculpe".

A função `_e_modelo_reasoning` foi escrita como "mini NÃO é reasoning" — tecnicamente correto para **sem tools**, mas **errado com tools**: com tools, a família 5.x inteira precisa de `reasoning_effort` no Chat Completions.

### Pesquisa adicional realizada (documentação OpenAI lida)

Documentos lidos nesta sessão:
- `prompt-guidance` (gpt-5.4 family): padrões de prompt, `reasoning_effort` como "last-mile knob", comportamento mini vs flagship
- `structured-outputs`: confirmado suporte em gpt-5.4-mini (`gpt-4o-mini` e later)
- `function-calling`: confirmado que strict mode funciona nos modelos mini
- `migrate-to-responses`: **Responses API é mais inteligente que Chat Completions** (mesmo modelo, +3% benchmark, +40-80% cache)
- `tools-web-search`: `web_search` (GA) vs `web_search_preview` (legacy)
- `tools-tool-search`: carregamento dinâmico de tools — só gpt-5.4+
- `deep-research`: modelos dedicados (`o3-deep-research`) — não aplicável ao agente

### Achados relevantes para o projeto

| Achado | Impacto |
|--------|---------|
| gpt-5.4-mini com tools no Chat Completions precisa de `reasoning_effort` | **CRÍTICO — causa do bug** |
| Responses API = +inteligência +40-80% cache vs Chat Completions | Oportunidade futura |
| `web_search` (GA) substituiu `web_search_preview` em `busca_web.py` | Melhoria futura |
| `tool_search` para carregar tools dinamicamente (só gpt-5.4+) | Baixa prioridade (9 tools) |
| `reasoning_effort="medium"` dá melhores respostas em casos complexos | Ajuste futuro |

---

## Guia de rollback completo

### Rollback IMEDIATO (30 segundos, sem código)
No Coolify → Environment Variables → alterar:
```
OPENAI_MODEL_MINI=gpt-4o
OPENAI_MODEL_FLAGSHIP=gpt-4o
```
Redeploy. Produção volta a usar gpt-4o para todos os turnos. Custo igual ao estado anterior, sem quebrar nada.

### Rollback PARCIAL (só mini)
```
OPENAI_MODEL_MINI=gpt-4o
OPENAI_MODEL_FLAGSHIP=gpt-5.4
```
Mini usa gpt-4o (seguro), flagship usa gpt-5.4 com `reasoning_effort="low"` (funciona).

### Rollback TOTAL (código)
```
git revert b17a7ba
git push
```
Reverte os 4 arquivos para o estado pré-sessão (gpt-4o puro, sem roteamento).

### Variáveis de ambiente — estado atual no Coolify
```
OPENAI_MODEL=gpt-5.4
OPENAI_MODEL_MINI=gpt-5.4-mini      ← causa do bug (precisa de fix no código)
OPENAI_MODEL_FLAGSHIP=gpt-5.4
```

---

## Fix planejado (Fase: pendente de autorização)

**Opção A — Fix cirúrgico no código** (manter gpt-5.4-mini):
Estender `_e_modelo_reasoning` para retornar `True` para qualquer `gpt-5.x` quando há tools,
independente de ser mini ou não. Uma linha de diferença:

```python
def _e_precisa_reasoning_effort(modelo: str, tem_tools: bool) -> bool:
    """Toda a familia gpt-5.x precisa de reasoning_effort quando usa tools no Chat Completions."""
    if not tem_tools:
        return False
    m = modelo.lower()
    return "gpt-5." in m  # mini, nano, flagship — todos precisam

# Em _chamar_openai:
if tools:
    kwargs["tools"] = tools
    kwargs["tool_choice"] = "auto"
    kwargs["parallel_tool_calls"] = False
    if _e_precisa_reasoning_effort(modelo, tem_tools=True):
        kwargs["reasoning_effort"] = "low"   # vale para mini E flagship
    # sem temperature quando há reasoning_effort
```

**Opção B — Rollback imediato + fix depois** (mais seguro):
1. Coolify: `OPENAI_MODEL_MINI=gpt-4o` → redeploy → produção volta
2. Código: implementar fix da Opção A
3. Teste local antes de reativar mini

**Opção C — Migrar para Responses API** (mais inteligente, mais cache):
A Responses API não tem a restrição de `reasoning:none`. Ferramentas funcionam sem `reasoning_effort`.
Custo adicional: refatorar `agente.py` para `client.responses.create` com `text.format` (Structured Outputs).

---

## Resumo de estado em 15/04/2026

| Item | Estado |
|------|--------|
| Código implementado | ✅ commit b17a7ba |
| Produção (Coolify) | ❌ QUEBRADA — gpt-5.4-mini + tools + Chat Completions |
| Rollback disponível | ✅ via env vars no Coolify (sem código) |
| Fix planejado | ⏳ aguardando autorização |
