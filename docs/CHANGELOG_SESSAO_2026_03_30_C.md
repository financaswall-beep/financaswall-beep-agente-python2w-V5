# Changelog — Sessao 30/03/2026 C

Data: 30/03/2026
Fases implementadas: 11 (Historico do Ultimo Pedido + Reserva de Estoque + Alteracao de Pedido)

---

## Item 2+3 — Historico do Ultimo Pedido no Contexto (completado)

### Contexto
Na sessao anterior (30/03/2026 B) os schemas e imports do `montador_contexto.py`
foram preparados mas a logica de populacao nao foi escrita. Esta sessao completou
o preenchimento do campo `cliente.ultimo_pedido` no `ContextoExecutavel`.

### Alteracoes realizadas

**engine/montador_contexto.py**

Logica adicionada dentro do bloco `if cliente:` apos resolver o cliente:

```python
ultimo_pedido = pedido_repo.buscar_ultimo_pedido_confirmado(
    cliente.id, excluir_sessao_id=sessao_id
)
if ultimo_pedido:
    itens_pedido = pedido_repo.listar_itens_pedido(ultimo_pedido.id)
    itens_ctx = []
    for item in itens_pedido:
        pneu = catalogo_repo.buscar_pneu_por_id(item.pneu_id)
        nome_pneu = pneu.nome if pneu else str(item.pneu_id)
        itens_ctx.append(ItemUltimoPedidoContexto(
            pneu_nome=nome_pneu,
            posicao=item.posicao.value if item.posicao else None,
            quantidade=item.quantidade,
            preco_unitario=item.preco_unitario,
        ))
    ultimo_pedido_ctx = UltimoPedidoContexto(
        data=ultimo_pedido.criado_em,
        valor_total=ultimo_pedido.valor_total,
        forma_pagamento=ultimo_pedido.forma_pagamento.value,
        tipo_entrega=ultimo_pedido.tipo_entrega.value,
        itens=itens_ctx,
    )
```

O campo `cliente_ctx.ultimo_pedido` e populado somente se existir pedido confirmado
anterior a sessao atual (`excluir_sessao_id=sessao_id` garante que o pedido corrente
nao aparece como "historico").

### O que a IA ganha

A IA recebe no contexto de cada turno:
```json
"cliente": {
  "ultimo_pedido": {
    "data": "2026-03-15T14:30:00Z",
    "valor_total": 309.90,
    "forma_pagamento": "pix",
    "tipo_entrega": "retirada",
    "itens": [
      {"pneu_nome": "Ira Moby 120/80-18", "posicao": "traseiro", "quantidade": 1, "preco_unitario": 309.90}
    ]
  }
}
```

Permite personalizacao: mencionar o ultimo pneu comprado, historico de pagamento preferido, etc.

---

## Item 4 — Reserva de Estoque

### Contexto

O campo `reservado` ja existia na tabela `estoque` e era consultado na validacao
de pre-condicoes (`quantidade_disponivel - reservado`), mas nunca era atualizado.
Agora e incrementado ao confirmar o pedido e decrementado ao cancelar.

### Migration Supabase (betaAgente — vyxdquwxmgibpkoswxut)

```sql
CREATE OR REPLACE FUNCTION atualizar_reservado_estoque(
    p_pneu_id uuid,
    p_delta int
) RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE estoque
    SET reservado = GREATEST(0, reservado + p_delta)
    WHERE pneu_id = p_pneu_id;
END;
$$;
```

- Operacao atomica (sem race condition)
- `GREATEST(0, ...)` impede que `reservado` va negativo mesmo se chamado em duplicidade

### Alteracoes realizadas

**db/catalogo_repo.py** — 2 novas funcoes:

```python
def incrementar_reservado(pneu_id: UUID, quantidade: int) -> None:
    supabase.rpc("atualizar_reservado_estoque", {"p_pneu_id": str(pneu_id), "p_delta": quantidade})

def decrementar_reservado(pneu_id: UUID, quantidade: int) -> None:
    supabase.rpc("atualizar_reservado_estoque", {"p_pneu_id": str(pneu_id), "p_delta": -quantidade})
```

**engine/promotor.py — promover_para_pedido**

Apos a RPC transacional criar o pedido, incrementa `reservado` para cada item:

```python
for item_payload in itens_payload:
    catalogo_repo.incrementar_reservado(UUID(item_payload["pneu_id"]), item_payload["quantidade"])
```

Falha individual por item e logada como warning (nao interrompe a promocao — o pedido ja foi criado).

**engine/promotor.py — cancelar_pedido_sessao**

Antes de reverter os stats do cliente, busca os itens do pedido e libera o estoque:

```python
itens = pedido_repo.listar_itens_pedido(pedido.id)
for item in itens:
    catalogo_repo.decrementar_reservado(item.pneu_id, item.quantidade)
```

**engine/promotor.py — import**

`pedido_repo` movido para o import do topo do arquivo (era importado localmente
dentro de funcoes). Eliminados imports locais redundantes.

### Ciclo de vida do campo `reservado`

```
Cliente confirma pedido  → reservado += quantidade  (promotor.py)
Cliente cancela pedido   → reservado -= quantidade  (promotor.py)
Pedido entregue          → fora do escopo V1 (implementar no futuro com status entregue)
```

---

## Item 5 — Alteracao de Pedido pos-fechamento

### Contexto

Antes desta implementacao, se o cliente mudasse de ideia sobre endereco ou forma
de pagamento apos o pedido ja ter sido criado no banco, a IA atualizava os fatos
no contexto mas o registro na tabela `pedido` permanecia com os valores antigos.

### Alteracoes realizadas

**db/pedido_repo.py** — nova funcao:

```python
def atualizar_pedido(pedido_id: UUID, campos: dict) -> Pedido:
    resultado = supabase.table("pedido").update(campos).eq("id", str(pedido_id)).execute()
    return Pedido(**resultado.data[0])
```

Campos editaveis: `forma_pagamento`, `tipo_entrega`, `endereco_entrega_json`.

**engine/promotor.py** — nova funcao `alterar_pedido_sessao(sessao_id)`:

1. Busca pedido da sessao (so age se `status_pedido == confirmado`)
2. Le fatos ativos de `forma_pagamento`, `tipo_entrega`, `endereco_entrega`
3. Compara com valores atuais do pedido
4. Se houver diferenca, chama `pedido_repo.atualizar_pedido` com os campos alterados
5. Retorna `True` se algum campo foi alterado, `False` se nada mudou

```python
def alterar_pedido_sessao(sessao_id: UUID) -> bool:
    pedido = pedido_repo.buscar_pedido_por_sessao(sessao_id)
    if not pedido or pedido.status_pedido.value != "confirmado":
        return False
    # ... compara fatos com pedido e atualiza campos que mudaram
```

**engine/orquestrador.py** — passo 8b (novo):

Apos aplicar mudancas de contexto (passo 8), se a etapa e `fechamento`:

```python
if envelope.etapa_atual == EtapaFluxo.fechamento:
    alterado = alterar_pedido_sessao(sessao_id)
    if alterado:
        logger.info("Pedido atualizado apos mudanca de contexto")
```

Nao bloqueia o fluxo — qualquer erro e logado como warning.

**ia/prompt_sistema.py** — instrucao adicionada em fechamento:

```
Alteracao apos pedido criado: Se o cliente quiser mudar endereco ou forma de pagamento
depois do pedido ja confirmado, registre os dados novos em `fatos_observados` normalmente
(endereco_entrega, forma_pagamento, tipo_entrega). O backend sincroniza automaticamente
o pedido. Confirme ao cliente que a alteracao foi feita.
```

### Fluxo de alteracao

```
Cliente: "muda o pix pra cartao"
  → IA registra fatos_observados: [{"chave": "forma_pagamento", "valor": "cartao"}]
  → orquestrador aplica fato (passo 8)
  → passo 8b detecta fechamento + pedido existe
  → alterar_pedido_sessao compara: pedido.forma_pagamento=pix != fato=cartao
  → pedido_repo.atualizar_pedido({forma_pagamento: "cartao"})
  → IA responde: "Feito! Forma de pagamento alterada para cartao."
```

---

## Resumo das dependencias circulares eliminadas

`promotor.py` importava `pedido_repo` localmente dentro de 2 funcoes
(`cancelar_pedido_sessao` e `promover_para_pedido`). Agora `pedido_repo` esta
no import do topo junto com os demais repos — codigo mais limpo e sem imports
ocultos dentro de funcoes.

---

## Arquivos alterados nesta sessao

| Arquivo | Tipo de alteracao |
|---------|------------------|
| `engine/montador_contexto.py` | Populacao de `ultimo_pedido` no contexto |
| `db/catalogo_repo.py` | +2 funcoes: `incrementar_reservado`, `decrementar_reservado` |
| `db/pedido_repo.py` | +1 funcao: `atualizar_pedido` |
| `engine/promotor.py` | Reserva de estoque em promocao/cancelamento; +`alterar_pedido_sessao`; import limpo |
| `engine/orquestrador.py` | Import de `alterar_pedido_sessao`; +passo 8b |
| `ia/prompt_sistema.py` | Instrucao de alteracao de pedido em fechamento |
| Supabase betaAgente | Migration: `atualizar_reservado_estoque` RPC |
