# Sessão de Desenvolvimento — 12/04/2026

## Contexto

Sessão focada em **segurança e integridade de dados**: correção de três race conditions críticos no banco de dados, limpeza completa dos dados de teste, e criação do repositório V5 como branch de trabalho principal.

---

## Repositório

| Item | Valor |
|---|---|
| Repositório V5 (PRINCIPAL) | `https://github.com/financaswall-beep/financaswall-beep-agente-python2w-V5.git` |
| Diretório local V5 | `C:\agente-python2w-V5` |
| Repositório V4 (backup estável) | `https://github.com/financaswall-beep/financaswall-beep-agente-python2w-V4.git` |
| Commit inicial V5 | `a25fa26` (clone exato do V4) |
| Commit final desta sessão | `fa280d9` |

---

## Limpeza de Dados de Teste (12/04/2026)

Antes das correções, o banco foi limpo de todos os dados de atendimento de teste. Ordem de deleção respeitando as foreign keys:

```sql
DELETE FROM contexto_conversa;
DELETE FROM mensagem_chat;
DELETE FROM escalacao;
DELETE FROM item_pedido;
DELETE FROM pedido;
DELETE FROM item_provisorio;
DELETE FROM sessao_chat;
DELETE FROM cliente;
```

**Resultado pós-limpeza:**

| Tabela | Registros |
|---|---|
| cliente | 0 |
| sessao_chat | 0 |
| pedido | 0 |
| item_pedido | 0 |
| item_provisorio | 0 |
| contexto_conversa | 0 |
| mensagem_chat | 0 |
| escalacao | 0 |

---

## Correções Implementadas

### B1 — Race Condition em `baixar_estoque_fisico`

**Commit:** `a25fa26`  
**Arquivo Python:** `agente_2w/db/catalogo_repo.py`  
**Migração Postgres:** `baixar_estoque_fisico`

**Problema:**  
A baixa de estoque ao marcar um pedido como `entregue` fazia SELECT + UPDATE em duas chamadas separadas. Dois workers simultâneos podiam ler o mesmo valor de estoque e ambos subtrair, resultando em estoque negativo ou desconto duplo.

**Antes:**
```python
# SELECT para ler quantidade atual
atual = supabase.table("estoque").select("quantidade_disponivel, reservado")...
# UPDATE com valor calculado em Python
supabase.table("estoque").update({"quantidade_disponivel": atual - qtd})...
```

**Depois:**  
RPC Postgres com operação atômica (`GREATEST` para nunca ir negativo):
```sql
CREATE OR REPLACE FUNCTION baixar_estoque_fisico(p_pneu_id UUID, p_quantidade INT)
RETURNS void AS $$
BEGIN
    UPDATE estoque
    SET quantidade_disponivel = GREATEST(0, quantidade_disponivel - p_quantidade),
        reservado = GREATEST(0, reservado - p_quantidade)
    WHERE pneu_id = p_pneu_id;
END;
$$ LANGUAGE plpgsql;
```

```python
# Python — uma única chamada RPC, atomicamente no banco
supabase.rpc("baixar_estoque_fisico", {
    "p_pneu_id": str(pneu_id),
    "p_quantidade": quantidade
}).execute()
```

---

### B2 — Race Condition em `registrar_fato`

**Commit:** `6ebd20a`  
**Arquivo Python:** `agente_2w/db/contexto_repo.py`  
**Migração Postgres:** `registrar_fato_atomico`

**Problema:**  
`registrar_fato` executava duas chamadas HTTP separadas ao Supabase:
1. `desativar_fato_anterior()` → UPDATE `ativo=False` no registro antigo
2. `criar_fato()` → INSERT do novo registro

Se o INSERT (chamada 2) falhasse por qualquer motivo (timeout, erro de rede, violação de constraint), o fato antigo já estava desativado e o novo nunca existiu — **o dado de contexto sumia completamente do sistema**. O agente esquecia informações já fornecidas pelo cliente (ex: bairro, município, posição do pneu).

**Callers afetados** (todos transparentes à mudança):
- `agente_2w/engine/orquestrador/localidade_frete.py` (4 chamadas)
- `agente_2w/engine/orquestrador/fatos_fallback.py` (2 chamadas)
- `agente_2w/engine/orquestrador/_nucleo.py` (1 chamada)

**Antes:**
```python
def registrar_fato(dados: ContextoConversaCreate) -> ContextoConversa:
    desativar_fato_anterior(...)   # Chamada HTTP 1 — UPDATE
    return criar_fato(dados)       # Chamada HTTP 2 — INSERT (pode falhar!)
```

**Depois:**  
RPC Postgres que executa UPDATE + INSERT em transação única (ACID):
```sql
CREATE OR REPLACE FUNCTION registrar_fato_atomico(
    p_sessao_chat_id UUID, p_chave TEXT, p_item_provisorio_id UUID,
    p_tipo_de_verdade TEXT, p_nivel_confirmacao TEXT, p_fonte TEXT,
    p_valor_texto TEXT, p_valor_json JSONB, p_mensagem_chat_id UUID,
    p_referencia_fonte TEXT, p_observacao TEXT, p_ativo BOOLEAN
)
RETURNS SETOF contexto_conversa
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    -- Desativa fatos anteriores (com ou sem item_provisorio_id)
    IF p_item_provisorio_id IS NOT NULL THEN
        UPDATE contexto_conversa SET ativo = FALSE
        WHERE sessao_chat_id = p_sessao_chat_id AND chave = p_chave
          AND ativo = TRUE AND item_provisorio_id = p_item_provisorio_id;
    ELSE
        UPDATE contexto_conversa SET ativo = FALSE
        WHERE sessao_chat_id = p_sessao_chat_id AND chave = p_chave
          AND ativo = TRUE AND item_provisorio_id IS NULL;
    END IF;

    -- INSERT do novo fato (se falhar, UPDATE acima é revertido pelo Postgres)
    RETURN QUERY
    INSERT INTO contexto_conversa (sessao_chat_id, chave, tipo_de_verdade,
        nivel_confirmacao, fonte, valor_texto, valor_json, item_provisorio_id,
        mensagem_chat_id, referencia_fonte, observacao, ativo)
    VALUES (p_sessao_chat_id, p_chave, p_tipo_de_verdade::tipo_de_verdade_enum,
        p_nivel_confirmacao::nivel_confirmacao_enum, p_fonte::origem_contexto_enum,
        p_valor_texto, p_valor_json, p_item_provisorio_id, p_mensagem_chat_id,
        p_referencia_fonte, p_observacao, p_ativo)
    RETURNING *;
END;
$$;
```

```python
def registrar_fato(dados: ContextoConversaCreate) -> ContextoConversa:
    """Desativa fato anterior e cria o novo em transação atômica via RPC."""
    params = {
        "p_sessao_chat_id": str(dados.sessao_chat_id),
        "p_chave": dados.chave,
        "p_item_provisorio_id": str(dados.item_provisorio_id) if dados.item_provisorio_id else None,
        "p_tipo_de_verdade": dados.tipo_de_verdade.value,
        "p_nivel_confirmacao": dados.nivel_confirmacao.value,
        "p_fonte": dados.fonte.value,
        "p_valor_texto": dados.valor_texto,
        "p_valor_json": dados.valor_json,
        "p_mensagem_chat_id": str(dados.mensagem_chat_id) if dados.mensagem_chat_id else None,
        "p_referencia_fonte": dados.referencia_fonte,
        "p_observacao": dados.observacao,
        "p_ativo": dados.ativo,
    }
    resultado = supabase.rpc("registrar_fato_atomico", params).execute()
    return ContextoConversa(**resultado.data[0])
```

---

### B3 — Race Condition em `resolver_ou_criar_cliente` (TOCTOU)

**Commit:** `603584e`  
**Arquivo Python:** `agente_2w/db/cliente_repo.py`  
**Migração Postgres:** `b3_cliente_unique_telefone_e_rpc_atomica`

**Problema:**  
`resolver_ou_criar_cliente` executava SELECT + INSERT em duas chamadas separadas — padrão clássico de TOCTOU (Time Of Check To Time Of Use). Com dois workers processando mensagens simultâneas do mesmo número (frequente com mensagens rápidas), ambos podiam fazer o SELECT (encontrar nenhum cliente), e ambos então executar o INSERT — criando **dois registros para o mesmo telefone**. Isso fragmentava o histórico do cliente entre dois registros distintos.

Agravante descoberto durante análise: **a tabela `cliente` não tinha UNIQUE constraint em `telefone`**, tornando o banco completamente incapaz de rejeitar duplicatas no nível mais baixo.

**Callers afetados** (todos transparentes):
- `agente_2w/engine/orquestrador/_nucleo.py:897`
- `agente_2w/tools/resolve_cliente.py:23`

**Antes:**
```python
def resolver_ou_criar_cliente(telefone: str, nome: str | None = None) -> Cliente:
    existente = buscar_cliente_por_telefone(telefone)  # SELECT — pode retornar None
    if existente is not None:
        return existente
    return criar_cliente(ClienteCreate(telefone=telefone, nome=nome))  # INSERT — duplicata possível!
```

**Depois:**

Passo 1 — constraint no banco (garante integridade independente do código):
```sql
ALTER TABLE cliente ADD CONSTRAINT cliente_telefone_unique UNIQUE (telefone);
```

Passo 2 — RPC atômica com `ON CONFLICT DO NOTHING`:
```sql
CREATE OR REPLACE FUNCTION resolver_ou_criar_cliente_atomico(
    p_telefone TEXT, p_nome TEXT
)
RETURNS SETOF cliente
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    INSERT INTO cliente (telefone, nome)
    VALUES (p_telefone, p_nome)
    ON CONFLICT (telefone) DO NOTHING;  -- se já existir, ignora silenciosamente

    RETURN QUERY SELECT * FROM cliente WHERE telefone = p_telefone;
END;
$$;
```

```python
def resolver_ou_criar_cliente(telefone: str, nome: str | None = None) -> Cliente:
    """Busca ou cria cliente de forma atômica via RPC.
    
    INSERT ... ON CONFLICT (telefone) DO NOTHING garante que dois workers
    simultâneos para o mesmo telefone nunca criem duplicatas.
    """
    resultado = supabase.rpc(
        "resolver_ou_criar_cliente_atomico",
        {"p_telefone": telefone, "p_nome": nome},
    ).execute()
    return Cliente(**resultado.data[0])
```

---

### Commits adicionais nesta sessão

| Commit | Descrição |
|---|---|
| `a755975` | fix(B7): middleware autenticacao /internal/* |
| `670ab7a` | test(B7): teste de autenticacao |
| `a73e3ae` | docs: atualiza changelog com B7 |
| `93465d7` | fix(B9): enum no campo acao de mudancas_itens |
| `fa280d9` | test(B9): 14 testes para enum do campo acao |
| `9ee23b4` | fix(B4): dedup promotor por pneu_id+posicao |
| `d492dac` | fix(B5): guard de profundidade em processar_turno |
| `f934aa1` | docs: changelog sessão |
| `2f354ce` | test(B3): teste de concorrência |
| `d1a5cd1` | test(B4,B5): testes de dedup e guard de recursão |

---

### B4 — Dedup do Promotor por `pneu_id` Apenas

**Commit:** `9ee23b4`  
**Arquivo:** `agente_2w/engine/promotor.py`  
**Teste:** `tests/test_b4_b5.py`

**Problema:**  
O dedup de itens provisórios no promotor usava apenas `pneu_id` como chave. Se um cliente pedisse o **mesmo pneu para dianteira E traseira** (comum em motos que usam o mesmo modelo nas duas rodas), o dedup eliminava um dos dois itens silenciosamente — o pedido saía com apenas 1 pneu em vez de 2.

**Antes:**
```python
chave = str(item.pneu_id)   # "abc-123"
```

**Depois:**
```python
chave = f"{item.pneu_id}|{item.posicao_moto or ''}"  # "abc-123|dianteira" vs "abc-123|traseira"
```

**Testes (3 cenários):**
- Mesmo pneu em dianteira + traseira → ambos mantidos ✅
- Mesmo pneu na mesma posição → antigo eliminado, novo fica ✅
- Sem posição → dedup por pneu_id continua igual ✅

---

### B5 — Recursão Sem Guard em `processar_turno`

**Commit:** `d492dac`  
**Arquivo:** `agente_2w/engine/orquestrador/_nucleo.py`  
**Teste:** `tests/test_b4_b5.py`

**Problema:**  
O Layer 2 (detecção de nova compra pós-pedido) chama `processar_turno` recursivamente. O comentário no código dizia "recursão controlada — 1 nível", mas não havia nenhum código que garantisse isso. Se a nova sessão nascesse com estado corrompido, a condição do Layer 2 disparava novamente → loop infinito → stack overflow, derrubando o worker do webhook inteiro.

**Antes:**
```python
def processar_turno(sessao_id, mensagem_texto, ...):
    # sem nenhum guard de profundidade
    ...
    return processar_turno(nova_sessao.id, ...)  # pode lopar infinitamente
```

**Depois:**
```python
def processar_turno(sessao_id, mensagem_texto, ..., _profundidade: int = 0):
    # Guard B5: nunca entrar em recursao infinita no Layer 2
    if _profundidade > 1:
        logger.error("processar_turno: profundidade maxima atingida (sessao=%s)", sessao_id)
        return RespostaTurno(texto="Ocorreu um erro interno. Por favor, envie sua mensagem novamente.")
    ...
    return processar_turno(nova_sessao.id, ..., _profundidade=_profundidade + 1)
```

**Impacto nos callers:** zero — `_profundidade` tem valor padrão `0`, todos os callers externos continuam funcionando sem alteração.

**Teste:**
- `_profundidade=2` → guard ativa, banco e IA não são chamados ✅

---

### B7 — Endpoints `/internal/*` sem Autenticação

**Commit:** `a755975`  
**Arquivo:** `webhook_server.py`  
**Teste:** `tests/test_b7_auth_internal.py`

**Problema:**  
O servidor expõe 7 endpoints de controle interno sem nenhuma autenticação:
- `POST /internal/auto-resolve?horas=0` → fecha **todas** as conversas ativas
- `POST /internal/stop-bot/{id}` → para o bot em qualquer conversa
- `POST /internal/sync-etapa`, `/sync-pedido`, `/devolver-ao-bot`, etc.

Qualquer pessoa com o IP do servidor (exposto via Coolify na internet) podia chamar esses endpoints livremente.

**Solução:**  
Middleware FastAPI que intercepta todas as requisições a `/internal/*` e verifica o header `Authorization: Bearer <token>`.

```python
_INTERNAL_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")

@app.middleware("http")
async def _auth_internal(request: Request, call_next):
    if request.url.path.startswith("/internal/"):
        if not _INTERNAL_TOKEN:
            return JSONResponse(status_code=503, content={"detail": "Servico nao configurado"})
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        if not hmac.compare_digest(token, _INTERNAL_TOKEN):  # resistente a timing attack
            logger.warning("Acesso nao autorizado a %s (IP=%s)", request.url.path, request.client.host)
            return JSONResponse(status_code=401, content={"detail": "Nao autorizado"})
    return await call_next(request)
```

**Token configurado em:**
- Coolify: variável de ambiente `INTERNAL_API_TOKEN`
- `.env` local: idem
- `.env.example`: atualizado com instrução de geração

**Testes (4 cenários):**
- Sem token → 401 ✅
- Token errado → 401 ✅
- Token correto → passa (200) ✅
- `/health` sem token → não bloqueado ✅

---

### B9 — Campo `acao` sem Enum no Schema do Envelope

**Commit fix:** `93465d7`  
**Commit teste:** `fa280d9`  
**Arquivo:** `agente_2w/ia/schemas_envelope.py`  
**Teste:** `tests/test_b9_acao_enum.py`

**Problema:**  
O campo `mudancas_itens[].acao` tinha apenas `{"type": "string"}` — sem enum. O modelo poderia retornar qualquer string (`"deletar"`, `"adicionar"`, `"update"`, etc.) e o código em `enriquecimento_itens.py` silenciosamente ignoraria a mudança (cai fora de todos os `if/elif`). O cliente perderia a operação sem erro nem log visível.

**Valores válidos confirmados** (lendo `enriquecimento_itens.py`):

| Ação | Efeito |
|---|---|
| `criar` | Cria novo item provisório |
| `confirmar` | Confirma item → avança para pedido |
| `atualizar` | Atualiza campos do item |
| `cancelar` | Cancela item ativo |
| `rejeitar` | Rejeita item proposto |

**Antes:**
```python
"acao": {"type": "string"}
```

**Depois:**
```python
"acao": {"type": "string", "enum": ["criar", "confirmar", "atualizar", "cancelar", "rejeitar"]}
```

**Por que não causa loop:**  
O schema é enviado com `"strict": True` para a OpenAI via `response_format: json_schema`. A OpenAI aplica o enum no **nível de samplig de tokens** — o modelo fisicamente não consegue gerar um valor fora do enum. Não há `ValidationError`, não há retry, não há loop.

**Testes (14 cenários):**
- 5 valores válidos → aceitos pelo schema ✅
- 6 valores inválidos (`deletar`, `adicionar`, `remover`, `update`, `create`, `CRIAR`, string vazia) → rejeitados com `ValidationError` ✅
- Lista vazia → válida ✅
- Todas as 5 ações juntas numa lista → válida ✅

---

## Resumo Executivo

| # | Bug | Risco | Status |
|---|---|---|---|
| B1 | Race condition `baixar_estoque_fisico` | Estoque negativo / desconto duplo | ✅ Corrigido `a25fa26` |
| B2 | `registrar_fato` não atômico | Perda permanente de contexto da conversa | ✅ Corrigido `6ebd20a` |
| B3 | `resolver_ou_criar_cliente` TOCTOU | Duplicação de cliente, histórico fragmentado | ✅ Corrigido `603584e` |
| B4 | Dedup promotor por `pneu_id` apenas | Cliente perde item se pedir mesmo pneu em 2 posições | ✅ Corrigido `9ee23b4` |
| B5 | `processar_turno` recursivo sem guard | Stack overflow em loops de estado corrompido | ✅ Corrigido `d492dac` |
| B6 | Cancelamento não transacional | Pedido cancelado sem liberar reserva | ⏭️ Pulado (ocorrência rara) |
| B7 | `/internal/*` sem autenticação | Qualquer IP pode fechar conversas ou parar o bot | ✅ Corrigido `a755975` |
| B7 | `/internal/*` sem autenticação | Qualquer IP pode disparar ações internas | ⚠️ Pendente |
| B8 | `_turno_async_locks` sem limpeza | Memory leak em produção | ⚠️ Pendente |
| B9 | Campo `acao` sem enum no schema | IA pode retornar string inválida | ✅ Corrigido `93465d7` |
| B10 | HMAC webhook vazio | Webhook sem validação de origem | ⚠️ Pendente |

### Features Pendentes

| # | Feature | Prioridade |
|---|---|---|
| F1 | `cliente_perdido` — hesitação → recovery → label | Alta |
| F2 | Session timeout automático | Alta |
| F3 | Handoffs H1-H7 | Média |
| F4 | Trigger `estoque_zerado` | Média |
| F5 | `atualizar_quantidade` em `item_provisorio_repo` | Baixa |
| F6 | Rate limiting | Baixa |
| F7 | Métricas e telemetria | Baixa |

### RPCs Postgres criadas nesta sessão

| RPC | Propósito |
|---|---|
| `baixar_estoque_fisico(p_pneu_id, p_quantidade)` | Baixa estoque + reserva atomicamente |
| `registrar_fato_atomico(...)` | Desativa fato anterior + insere novo em transação |
| `resolver_ou_criar_cliente_atomico(p_telefone, p_nome)` | Cria cliente com ON CONFLICT para zero duplicatas |

### Constraints adicionadas

| Tabela | Constraint | Propósito |
|---|---|---|
| `cliente` | `UNIQUE(telefone)` | Impede duplicatas no nível do banco, independente do código |
