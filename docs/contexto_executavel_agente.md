# Contexto Executavel do Agente

## Objetivo

Definir o formato do contexto que o backend entrega para a IA em tempo de execucao.

Este documento nao descreve tabela de banco. Ele descreve o payload pronto que o backend monta a partir das tabelas do sistema.

O objetivo e simples:

- a IA nao le tabela crua;
- a IA recebe somente o contexto consolidado que pode usar;
- fatos chegam com evidencia e nivel de confirmacao;
- acoes chegam limitadas pela etapa atual;
- bloqueios chegam explicitamente descritos.

## Fontes que alimentam este contexto

O backend monta este contexto a partir de:

- `sessao_chat`
- `mensagem_chat`
- `contexto_conversa`
- `item_provisorio`
- `cliente`, quando resolvido
- `pneu` e `estoque`, quando consultados (via VIEWs `catalogo_agente` e `compatibilidade_moto_pneu`)
- `medida_moto`, para compatibilidade moto → medida validada

## Principio do contrato

O contexto executavel existe para reduzir liberdade indevida da IA.

A IA pode:

- interpretar linguagem natural;
- escolher a melhor resposta dentro do contexto recebido;
- sugerir a proxima acao;
- propor mudancas estruturadas para o backend validar.

A IA nao pode:

- inventar fatos ausentes do contexto;
- promover fato inferido para fato validado;
- criar ids;
- burlar a etapa atual;
- assumir compatibilidade sem evidencia valida.

## Estrutura proposta do contexto

```json
{
  "sessao": {
    "sessao_id": "uuid",
    "canal": "whatsapp",
    "contato_externo": "5521999999999",
    "etapa_atual": "identificacao",
    "status_sessao": "ativa",
    "ultima_interacao_em": "2026-03-29T18:30:00Z"
  },
  "cliente": {
    "cliente_id": null,
    "nome": null,
    "telefone": "5521999999999",
    "resolvido": false
  },
  "bloqueios_ativos": [],
  "mensagens_recentes": [],
  "fatos_ativos": [],
  "resultados_busca_atuais": [],
  "itens_provisorios": [],
  "pendencias": [],
  "acoes_permitidas": [],
  "resumo_operacional": {
    "tem_item_validado": false,
    "tem_entrega_definida": false,
    "tem_pagamento_definido": false,
    "pode_avancar_etapa": false
  },
  "metadados": {
    "gerado_em": "2026-03-29T18:31:00Z",
    "versao_contexto": "v1"
  }
}
```

## Secoes do contexto

### 1. `sessao`

Representa o estado atual da conversa.

Campos obrigatorios:

- `sessao_id: string`
- `canal: string`
- `contato_externo: string`
- `etapa_atual: enum`
- `status_sessao: enum`
- `ultima_interacao_em: datetime`

Origem principal:

- `sessao_chat`

Observacao:

- esta secao define o limite operacional da IA no turno atual.

### 2. `cliente`

Representa o estado de resolucao do cliente.

Campos obrigatorios:

- `cliente_id: string | null`
- `nome: string | null`
- `telefone: string | null`
- `resolvido: boolean`

Origem principal:

- `sessao_chat.cliente_id`
- `cliente`

Observacao:

- cliente pode estar parcialmente resolvido sem bloquear a conversa inicial.

### 3. `bloqueios_ativos`

Lista de bloqueios operacionais vigentes.

Formato de cada item:

```json
{
  "codigo_motivo": "endereco_obrigatorio",
  "mensagem_motivo": "Nao e possivel fechar o pedido sem endereco de entrega.",
  "campo_relacionado": "endereco_entrega",
  "acao_bloqueada": "converter_em_pedido"
}
```

Origem principal:

- `sessao_chat`
- regras do backend

Observacao:

- se existir bloqueio ativo, a IA deve responder respeitando esse bloqueio e conduzir a coleta do dado faltante.

### 4. `mensagens_recentes`

Trecho recente da conversa para preservar continuidade linguistica.

Formato de cada item:

```json
{
  "mensagem_id": "uuid",
  "direcao": "entrada",
  "remetente": "cliente",
  "conteudo_texto": "Quero um pneu para minha Fazer 250.",
  "criado_em": "2026-03-29T18:20:00Z"
}
```

Campos obrigatorios por item:

- `mensagem_id: string`
- `direcao: string`
- `remetente: string`
- `conteudo_texto: string`
- `criado_em: datetime`

Origem principal:

- `mensagem_chat`

Regra pratica:

- enviar apenas a janela recente relevante, nao o historico inteiro indiscriminadamente.

### 5. `fatos_ativos`

Lista de fatos atualmente vigentes que a IA pode usar como base operacional.

Formato de cada item:

```json
{
  "chave": "moto_modelo_informado",
  "valor": "Fazer 250",
  "tipo_de_verdade": "observado",
  "nivel_confirmacao": "nenhum",
  "fonte": "mensagem_cliente",
  "mensagem_chat_id": "uuid",
  "item_provisorio_id": null,
  "coletado_em": "2026-03-29T18:20:00Z"
}
```

Campos obrigatorios por item:

- `chave: string`
- `valor: string | object | array | number | boolean | null`
- `tipo_de_verdade: enum`
- `nivel_confirmacao: enum`
- `fonte: enum`
- `mensagem_chat_id: string | null`
- `item_provisorio_id: string | null`
- `coletado_em: datetime`

Origem principal:

- `contexto_conversa`, filtrando apenas `ativo = true`

Regra central:

- a IA pode usar fato ativo como contexto;
- a IA nao pode promover sozinha o status do fato;
- compatibilidade so aparece aqui se vier validada por tool ou backend.

### 6. `resultados_busca_atuais`

Lista dos resultados retornados no turno atual por catalogo, estoque ou tool validada.

Essa secao existe para separar claramente resultado de consulta de fato consolidado.

Formato de cada item:

```json
{
  "origem": "busca_catalogo",
  "referencia_resultado": "busca_2026_03_29_001_item_1",
  "pneu_id": "uuid",
  "descricao": "Pirelli 110/70-17 dianteiro",
  "largura": 110,
  "perfil": 70,
  "aro": 17,
  "preco_venda": 189.9,
  "quantidade_disponivel": 2,
  "compatibilidade_status": "nao_validada",
  "observacao": "Opcao encontrada por medida, ainda sem confirmar aplicacao na moto."
}
```

Campos obrigatorios por item:

- `origem: string` (`busca_catalogo`, `busca_dimensoes`, `busca_moto`)
- `referencia_resultado: string`
- `pneu_id: string | null`
- `descricao: string`
- `largura: integer | null`
- `perfil: integer | null`
- `aro: integer | null`
- `preco_venda: number | null`
- `quantidade_disponivel: integer | null`
- `compatibilidade_status: string` (`nao_validada`, `validada_medida_moto`)
- `observacao: string | null`

Origem principal:

- backend, a partir de consulta em VIEWs (`catalogo_agente`, `compatibilidade_moto_pneu`) e tabelas (`pneu`, `estoque`)

Regra central:

- resultado de busca nao vira fato ativo automaticamente;
- resultado de busca nao equivale a escolha do cliente;
- a IA pode apresentar essas opcoes, mas nao pode tratá-las como item confirmado sem validacao adicional;
- quando `origem = "busca_moto"`, o resultado ja inclui `compatibilidade_status = "validada_medida_moto"` (veio da VIEW `compatibilidade_moto_pneu`).

### 7. `itens_provisorios`

Lista dos itens em discussao antes da oficializacao.

Formato de cada item:

```json
{
  "item_provisorio_id": "uuid",
  "pneu_id": null,
  "descricao_contextual": "Pneu dianteiro 110/70-17 sugerido para analise",
  "posicao": "dianteiro",
  "quantidade": 1,
  "status_item": "sugerido",
  "preco_unitario_sugerido": null,
  "cliente_confirmou": false,
  "validado_backend": false
}
```

Campos obrigatorios por item:

- `item_provisorio_id: string`
- `pneu_id: string | null`
- `descricao_contextual: string`
- `posicao: string | null`
- `quantidade: integer`
- `status_item: enum`
- `preco_unitario_sugerido: number | null`
- `cliente_confirmou: boolean`
- `validado_backend: boolean`

Origem principal:

- `item_provisorio`
- fatos ativos associados ao item

Regra central:

- item provisiorio organiza a intencao de compra;
- ele nao equivale a item oficial do pedido.

### 8. `pendencias`

Lista objetiva do que ainda falta para a conversa avancar.

Formato de cada item:

```json
{
  "codigo": "confirmar_posicao_pneu",
  "descricao": "Precisa confirmar se o pneu e dianteiro ou traseiro.",
  "campo_relacionado": "posicao_pneu",
  "obrigatoria_para": "busca"
}
```

Campos obrigatorios por item:

- `codigo: string`
- `descricao: string`
- `campo_relacionado: string | null`
- `obrigatoria_para: string`

Origem principal:

- backend, a partir da etapa atual e dos fatos faltantes

Observacao:

- a IA deve priorizar resolver pendencias reais, nao inventar resposta para contorna-las.

### 9. `acoes_permitidas`

Lista fechada das acoes autorizadas naquele turno.

Exemplo:

```json
[
  "pedir_clarificacao_moto",
  "pedir_clarificacao_medida",
  "buscar_por_moto",
  "buscar_por_medida",
  "responder_incerteza_segura"
]
```

Origem principal:

- backend, com base na etapa atual e na maquina de estados

Observacao:

- esta lista reduz a chance de a IA pular etapa ou agir fora do fluxo permitido.

### 10. `resumo_operacional`

Resumo booleano para facilitar decisao do modelo sem expor regra demais em linguagem solta.

Campos obrigatorios:

- `tem_item_validado: boolean`
- `tem_entrega_definida: boolean`
- `tem_pagamento_definido: boolean`
- `pode_avancar_etapa: boolean`

Origem principal:

- backend, a partir do estado consolidado

Observacao:

- esses campos sao auxiliares e nao substituem fatos com evidencia.

### 11. `metadados`

Informacoes tecnicas do contexto gerado.

Campos obrigatorios:

- `gerado_em: datetime`
- `versao_contexto: string`

Origem principal:

- backend

## Mapeamento das tabelas para o contexto

| Secao do contexto | Origem principal |
|---|---|
| `sessao` | `sessao_chat` |
| `cliente` | `sessao_chat` + `cliente` |
| `bloqueios_ativos` | `sessao_chat` + backend |
| `mensagens_recentes` | `mensagem_chat` |
| `fatos_ativos` | `contexto_conversa` |
| `resultados_busca_atuais` | backend + VIEWs (`catalogo_agente`, `compatibilidade_moto_pneu`) |
| `itens_provisorios` | `item_provisorio` + `contexto_conversa` |
| `pendencias` | backend |
| `acoes_permitidas` | backend |
| `resumo_operacional` | backend |
| `metadados` | backend |

## Exemplo concreto de contexto minimo

```json
{
  "sessao": {
    "sessao_id": "8af1d3f7-1111-4d9a-9e0a-111111111111",
    "canal": "whatsapp",
    "contato_externo": "5521998887777",
    "etapa_atual": "identificacao",
    "status_sessao": "ativa",
    "ultima_interacao_em": "2026-03-29T19:10:00Z"
  },
  "cliente": {
    "cliente_id": null,
    "nome": null,
    "telefone": "5521998887777",
    "resolvido": false
  },
  "bloqueios_ativos": [],
  "mensagens_recentes": [
    {
      "mensagem_id": "c1a11111-1111-4444-9999-111111111111",
      "direcao": "entrada",
      "remetente": "cliente",
      "conteudo_texto": "Quero um pneu pra minha Fazer 250",
      "criado_em": "2026-03-29T19:09:10Z"
    }
  ],
  "fatos_ativos": [
    {
      "chave": "moto_modelo_informado",
      "valor": "Fazer 250",
      "tipo_de_verdade": "observado",
      "nivel_confirmacao": "nenhum",
      "fonte": "mensagem_cliente",
      "mensagem_chat_id": "c1a11111-1111-4444-9999-111111111111",
      "item_provisorio_id": null,
      "coletado_em": "2026-03-29T19:09:10Z"
    }
  ],
  "resultados_busca_atuais": [
    {
      "origem": "busca_catalogo",
      "referencia_resultado": "busca_2026_03_29_001_item_1",
      "pneu_id": "d2b22222-2222-4444-9999-222222222222",
      "descricao": "Pirelli 110/70-17 dianteiro",
      "preco_venda": 189.9,
      "quantidade_disponivel": 2,
      "compatibilidade_status": "nao_validada",
      "observacao": "Resultado encontrado por medida. Ainda nao ha validacao de compatibilidade para a moto informada."
    }
  ],
  "itens_provisorios": [],
  "pendencias": [
    {
      "codigo": "confirmar_medida_ou_posicao",
      "descricao": "Precisa confirmar a medida do pneu ou a posicao desejada para iniciar a busca.",
      "campo_relacionado": "medida_ou_posicao",
      "obrigatoria_para": "busca"
    }
  ],
  "acoes_permitidas": [
    "pedir_clarificacao_medida",
    "pedir_clarificacao_posicao",
    "buscar_por_moto",
    "buscar_por_dimensoes"
  ],
  "resumo_operacional": {
    "tem_item_validado": false,
    "tem_entrega_definida": false,
    "tem_pagamento_definido": false,
    "pode_avancar_etapa": false
  },
  "metadados": {
    "gerado_em": "2026-03-29T19:10:05Z",
    "versao_contexto": "v1"
  }
}
```

## Regras de montagem pelo backend

1. `mensagens_recentes` deve ser limitado ao trecho relevante para nao inflar prompt.
2. `fatos_ativos` deve incluir apenas fatos vigentes e utilizaveis no turno atual.
3. `resultados_busca_atuais` deve carregar apenas o resultado da consulta do turno ou da ultima consulta relevante ainda vigente.
4. fatos contraditorios nao devem ser enviados como se fossem equivalentes; o backend deve escolher o ativo ou marcar a ambiguidade em `pendencias`.
5. compatibilidade so entra em `fatos_ativos` quando houver `tipo_de_verdade = validado_tool` ou `validado_backend`. Resultados de `buscar_por_moto` (via VIEW `compatibilidade_moto_pneu`) ja carregam `compatibilidade_status = "validada_medida_moto"`.
6. item encontrado em busca nao deve virar `item_provisorio` automaticamente sem acao validada do backend.
7. `acoes_permitidas` deve ser lista fechada calculada pela etapa atual.
8. `pendencias` deve ser derivada do que realmente falta para a proxima etapa, nao de heuristica solta da IA.

## O que a IA deve fazer com esse contexto

Com este contexto, a IA deve:

- responder ao cliente de forma natural;
- respeitar a etapa atual;
- priorizar resolver pendencias;
- usar fatos ativos como base;
- usar resultados de busca como opcoes do turno, nao como verdades consolidadas;
- declarar incerteza quando faltar validacao;
- propor apenas mudancas coerentes com `acoes_permitidas`.

Com este contexto, a IA nao deve:

- inventar compatibilidade;
- inventar `pneu_id`;
- assumir preco ou estoque sem consulta;
- tratar item provisiorio como item oficial;
- ignorar bloqueios ativos.

## Conclusao

Estas quatro tabelas sao suficientes como nucleo do contexto conversacional persistido:

- `sessao_chat`
- `mensagem_chat`
- `contexto_conversa`
- `item_provisorio`

O contexto executavel completo do turno pode ser enriquecido pelo backend com dados validados de cliente, catalogo, estoque e compatibilidade.

O banco guarda a verdade auditavel.
O backend monta o contexto executavel.
A IA recebe apenas o que pode usar.