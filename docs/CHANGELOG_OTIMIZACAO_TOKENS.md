# Changelog — Otimização de Tokens OpenAI

## Data: 11/04/2026

---

## Step 1 — exclude_none na serialização do contexto

### Arquivo alterado
`agente_2w/ia/agente.py` — linha 101

### O que era (ANTES)
```python
contexto_json = contexto.model_dump_json(indent=None)
```

### O que ficou (DEPOIS)
```python
contexto_json = contexto.model_dump_json(indent=None, exclude_none=True)
```

### O que faz
Remove todos os campos com valor `None` do JSON enviado à OpenAI.
Campos como `pneu_id: null`, `mensagem_chat_id: null`, `endereco_entrega_json: null` deixam de ser enviados.

### Por que é seguro
- O `contexto_json` só é usado em 1 lugar: `agente.py` linha 118, como texto dentro da mensagem pro OpenAI.
- Nenhum código Python lê esse JSON de volta (não existe `json.loads(contexto_json)` em lugar nenhum).
- A IA não toma decisão baseada em "esse campo é null" — campo ausente tem o mesmo significado.
- Os exemplos de `null` no prompt_sistema.py são a IA ESCREVENDO null na resposta dela, não lendo do contexto.

### Economia estimada
~200-500 tokens por turno

### Como reverter
Trocar a linha 101 de volta para:
```python
contexto_json = contexto.model_dump_json(indent=None)
```
