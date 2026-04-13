# Changelog — Sessao 30/03/2026 (tarde)

## Resumo

Sessao focada em inteligencia de negocio do cliente:
captura de nome, municipio/bairro, historico de compras,
segmentacao automatica e cancelamento de pedido.

Todos os recursos implementados, testados com IA real e validados no Supabase.

---

## 1. Migration Supabase — tabela `cliente` (betaAgente)

6 colunas adicionadas:

| Coluna | Tipo | Default |
|---|---|---|
| `municipio` | TEXT | NULL |
| `bairro` | TEXT | NULL |
| `segmento` | TEXT NOT NULL | `novo` |
| `total_pedidos` | INT NOT NULL | 0 |
| `valor_total_gasto` | NUMERIC(10,2) NOT NULL | 0 |
| `ultima_compra_em` | TIMESTAMPTZ | NULL |

Constraint: `cliente_segmento_chk CHECK (segmento IN ('novo', 'recorrente', 'vip'))`

---

## 2. constantes.py — novas chaves

```python
ChaveContexto.MUNICIPIO = "municipio"
ChaveContexto.BAIRRO    = "bairro"
```

---

## 3. schemas/cliente.py — novos campos

`ClienteBase` recebe `municipio` e `bairro` (opcionais).
`Cliente` recebe `segmento`, `total_pedidos`, `valor_total_gasto`, `ultima_compra_em`.

---

## 4. schemas/contexto_executavel.py — ClienteContexto expandido

```python
class ClienteContexto(BaseModel):
    # campos anteriores mantidos
    segmento: Optional[str] = None
    total_pedidos: int = 0
    valor_total_gasto: Optional[Decimal] = None
    ultima_compra_em: Optional[datetime] = None
    municipio: Optional[str] = None
    bairro: Optional[str] = None
```

A IA recebe esses dados no contexto de cada turno.

---

## 5. engine/montador_contexto.py — popula novos campos

`ClienteContexto` agora carrega todos os campos de inteligencia de negocio
quando o cliente esta resolvido.

---

## 6. engine/promotor.py — stats e cancelamento

### `_calcular_segmento(total_pedidos, valor_total) -> str`

Regra de negocio centralizada:

| Condicao | Segmento |
|---|---|
| `total_pedidos == 0` | `novo` |
| `total_pedidos >= 1 e < 5` e `valor < R$500` | `recorrente` |
| `total_pedidos >= 5` ou `valor >= R$500` | `vip` |

### `_atualizar_stats_cliente(cliente_id, valor_pedido)`

Chamada automaticamente pelo `promover_para_pedido` apos cada pedido criado.
Incrementa `total_pedidos`, soma `valor_total_gasto`, atualiza `ultima_compra_em`
e recalcula `segmento`.

### `cancelar_pedido_sessao(sessao_id) -> bool`

Cancela o pedido da sessao e reverte os stats do cliente:
- `pedido.status_pedido` → `cancelado`
- `total_pedidos` decrementado
- `valor_total_gasto` subtraido
- `segmento` recalculado
- Cadastro do cliente preservado

---

## 7. db/pedido_repo.py — cancelar_pedido

```python
def cancelar_pedido(pedido_id: UUID) -> Pedido:
    # UPDATE pedido SET status_pedido='cancelado' WHERE id=...
```

---

## 8. engine/orquestrador.py — 3 novos comportamentos

### `_parsear_localidade_endereco(fato) -> (municipio, bairro)`

Extrai municipio e bairro do fato `endereco_entrega`:
1. Tenta `valor_json` estruturado (chaves `municipio`/`cidade` e `bairro`)
2. Parseia `valor_texto` livre via heuristica:
   - Detecta "Bairro X" por prefixo
   - Ignora numeros, CEPs e siglas de estado (2 letras maiusculas)
   - Municipio = ultimo candidato; bairro = penultimo se nao encontrado por prefixo

### `_atualizar_localidade_cliente(sessao_id, cliente_id)`

Roda apos cada promocao (manual e auto). Prioridade:
1. Fatos explicitos `municipio` e `bairro` registrados pela IA
2. Parse do fato `endereco_entrega`
Nao sobrescreve campos ja preenchidos.

### `_atualizar_nome_cliente(sessao_id, cliente_id)`

Roda apos aplicar fatos (passo 7b) em todo turno.
Se `nome_cliente` foi registrado e o cliente ainda nao tem nome, persiste no banco.

### Cancelamento via fato (passo 7c)

Detecta fato `pedido_cancelamento_solicitado` apos aplicar fatos.
Chama `cancelar_pedido_sessao` e desativa o fato para nao cancelar novamente.

---

## 9. ia/prompt_sistema.py — 3 instrucoes adicionadas

1. **Nome do cliente em entrega_pagamento** — regra explicita para pedir o nome
   junto com os dados de entrega/retirada e registrar como `fato_observado`.

2. **Cancelamento** — instrucao para registrar `pedido_cancelamento_solicitado`
   como fato quando o cliente pedir cancelamento pos-fechamento.
   Acao `cancelar_pedido` adicionada as acoes validas de `fechamento`.

3. **Chave `pedido_cancelamento_solicitado`** adicionada as chaves de fatos comuns.

---

## Testes realizados

### teste_inteligencia_cliente.py (novo) — 21/21 PASS

Cobre sem chamar a IA:
- Imports dos novos simbolos
- Logica de segmento (6 cenarios)
- Schema `ClienteCreate` e `Cliente` com novos campos
- `ClienteContexto` defaults e preenchido
- Banco: criar cliente com municipio/bairro, `_atualizar_stats_cliente`,
  progressao novo→recorrente→vip, localidade persiste apos updates
- `montador_contexto` carrega campos de BI no `ClienteContexto`

### _parsear_localidade_endereco — 7/7 PASS

Formatos cobertos:
- "Rua X, 123, Bairro Centro, Caxias do Sul"
- "Rua X, 123, Bairro Centro, Caxias do Sul, RS"
- "Rua X, 123, Centro, Niteroi"
- "Av Brasil, 500, Tijuca, Rio de Janeiro, RJ"
- "Rua X, 10, Duque de Caxias" (sem bairro)
- JSON `{municipio, bairro}`
- JSON `{cidade, bairro}`

### teste_conversa_natural.py — E2E com IA real — PASS

Conversa completa: 7 turnos, pedido criado, todos os campos verificados.
Cliente: nome="Joao Silva", municipio="Caxias do Sul", bairro="Centro",
total_pedidos=1, valor=R$239,90, segmento=recorrente.

### Teste manual CLI — Wallace / Twister / Itaborai — PASS

Conversa real via CLI com comportamentos validados:
- IA pediu nome junto com dados de entrega: "Entregamos sim! Me passa seu nome e o endereco completo..."
- Nome capturado e persistido: "Wallace"
- Municipio/bairro extraidos do endereco: Itaborai / Nova Cidade
- Pedido criado: R$469,90, pix, entrega
- Stats atualizados: total_pedidos=1, segmento=recorrente
- Cancelamento solicitado → pedido cancelado, stats revertidos: total_pedidos=0, segmento=novo

### cancelar_pedido_sessao — teste direto — PASS

Pedido Wallace: confirmado → cancelado
Cliente Wallace: total_pedidos=1, R$469,90, recorrente → total_pedidos=0, R$0, novo

---

## Arquivos modificados nesta sessao

| Arquivo | Tipo de alteracao |
|---|---|
| Supabase migration | ADD COLUMNS em `cliente` |
| `constantes.py` | +2 chaves |
| `schemas/cliente.py` | +5 campos |
| `schemas/contexto_executavel.py` | ClienteContexto +6 campos |
| `engine/montador_contexto.py` | popula novos campos |
| `engine/promotor.py` | +`_calcular_segmento`, +`_atualizar_stats_cliente`, +`cancelar_pedido_sessao` |
| `db/pedido_repo.py` | +`cancelar_pedido` |
| `engine/orquestrador.py` | +`_parsear_localidade_endereco`, +`_atualizar_localidade_cliente`, +`_atualizar_nome_cliente`, +cancelamento via fato |
| `ia/prompt_sistema.py` | +nome_cliente, +cancelamento, +cancelar_pedido em acoes |
| `teste_conversa_natural.py` | +verificacao de BI e nome |
| `teste_inteligencia_cliente.py` | novo — 21 testes |
