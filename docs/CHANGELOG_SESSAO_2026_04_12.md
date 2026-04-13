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
| Commit final desta sessão | `603584e` |

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

## Resumo Executivo

| # | Bug | Risco | Status |
|---|---|---|---|
| B1 | Race condition `baixar_estoque_fisico` | Estoque negativo / desconto duplo | ✅ Corrigido `a25fa26` |
| B2 | `registrar_fato` não atômico | Perda permanente de contexto da conversa | ✅ Corrigido `6ebd20a` |
| B3 | `resolver_ou_criar_cliente` TOCTOU | Duplicação de cliente, histórico fragmentado | ✅ Corrigido `603584e` |
| B4 | Dedup promotor por `pneu_id` apenas | Cliente perde item se pedir mesmo pneu em 2 posições | ⚠️ Pendente |
| B5 | `processar_turno` recursivo sem guard | Stack overflow em loops | ⚠️ Pendente |
| B6 | Cancelamento não transacional | Pedido cancelado sem liberar reserva | ⚠️ Pendente |
| B7 | `/internal/*` sem autenticação | Qualquer IP pode disparar ações internas | ⚠️ Pendente |
| B8 | `_turno_async_locks` sem limpeza | Memory leak em produção | ⚠️ Pendente |
| B9 | Campo `acao` sem enum no schema | IA pode retornar string inválida | ⚠️ Pendente |
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
