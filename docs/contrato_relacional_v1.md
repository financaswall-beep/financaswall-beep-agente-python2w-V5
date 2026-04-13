# Contrato Relacional V1

## Objetivo

Definir o minimo relacional do V1 para sair do desenho conceitual e entrar em implementacao sem ambiguidade.

Este documento fecha tres pontos:

- FKs minimas do V1;
- constraints obrigatorias do V1;
- o que deve ficar no backend e nao no banco.

## Principio do V1

No V1, a prioridade nao e modelar toda a operacao.

A prioridade e garantir:

- fluxo previsivel;
- separacao entre conversa, fato, pre-venda e pedido oficial;
- rastreabilidade minima;
- bloqueio de estados invalidos.

Regra pratica:

- poucas FKs bem escolhidas;
- constraints fortes;
- backend montando o contexto executavel para a IA.

## 1. FKs minimas do V1

Estas sao as relacoes que valem a pena ja no primeiro ciclo.

### `sessao_chat`

- `sessao_chat.cliente_id -> cliente.id` opcional

Motivo:

- a sessao pode comecar antes de o cliente estar resolvido.

### `mensagem_chat`

- `mensagem_chat.sessao_chat_id -> sessao_chat.id` obrigatoria

Motivo:

- toda mensagem precisa pertencer a uma sessao.

### `contexto_conversa`

- `contexto_conversa.sessao_chat_id -> sessao_chat.id` obrigatoria
- `contexto_conversa.mensagem_chat_id -> mensagem_chat.id` opcional
- `contexto_conversa.item_provisorio_id -> item_provisorio.id` opcional

Motivo:

- todo fato precisa pertencer a uma sessao;
- nem todo fato nasce de uma mensagem;
- nem todo fato pertence a um item especifico.

### `item_provisorio`

- `item_provisorio.sessao_chat_id -> sessao_chat.id` obrigatoria
- `item_provisorio.pneu_id -> pneu.id` opcional

Motivo:

- todo item provisiorio pertence a uma sessao;
- o pneu pode ainda nao estar resolvido no momento inicial.

### `estoque`

- `estoque.pneu_id -> pneu.id` obrigatoria

Motivo:

- estoque so existe para pneu real.

### `medida_moto`

- `medida_moto.moto_id -> moto.id` obrigatoria

Motivo:

- cada medida pertence a uma moto real do catalogo;
- unique constraint em `(moto_id, posicao)` garante no maximo uma medida por posicao por moto.

### `pedido`

- `pedido.sessao_chat_id -> sessao_chat.id` obrigatoria
- `pedido.cliente_id -> cliente.id` obrigatoria

Motivo:

- o pedido nasce da sessao;
- pedido oficial nao existe sem cliente resolvido.

### `item_pedido`

- `item_pedido.pedido_id -> pedido.id` obrigatoria
- `item_pedido.pneu_id -> pneu.id` obrigatoria
- `item_pedido.item_provisorio_id -> item_provisorio.id` opcional

Motivo:

- item oficial sempre pertence a um pedido;
- item oficial sempre aponta para um pneu real;
- vinculo com item provisiorio e importante para rastreabilidade, mas nao deve ser obrigatorio em todos os cenarios.

## 2. Constraints obrigatorias do V1

Aqui esta o que realmente protege o fluxo.

### `sessao_chat`

- `etapa_atual` obrigatoria e limitada ao enum do fluxo
- `status_sessao` obrigatoria e limitada ao enum de status
- se `status_sessao = bloqueada`, deve existir `codigo_motivo` e `mensagem_motivo`

### `pneu`

- `largura` obrigatorio e `> 0`
- `perfil` obrigatorio e `> 0`
- `aro` obrigatorio e `> 0`
- `tipo` limitado a `dianteiro`, `traseiro` ou `universal` (ou null)
- `medida` texto mantido para exibicao humana
- campos dimensionais (`largura`, `perfil`, `aro`) usados para busca do agente

### `mensagem_chat`

- `sessao_chat_id` obrigatorio
- `direcao` obrigatoria
- `conteudo_texto` obrigatorio

### `contexto_conversa`

- `sessao_chat_id` obrigatorio
- `chave` obrigatoria
- `tipo_de_verdade` obrigatorio
- `nivel_confirmacao` obrigatorio
- `fonte` obrigatoria
- pelo menos um entre `valor_texto` e `valor_json` deve existir
- deve existir no maximo um fato `ativo = true` por escopo logico

Definicao de escopo logico:

- `sessao_chat_id + chave + item_provisorio_id`, quando houver item
- `sessao_chat_id + chave`, quando nao houver item

Implementacao recomendada:

- dois indices unicos parciais para fatos ativos, por causa da semantica de `NULL` em chaves unicas do PostgreSQL:
- um indice para fatos ativos sem `item_provisorio_id`, baseado em `sessao_chat_id + chave`
- um indice para fatos ativos com `item_provisorio_id`, baseado em `sessao_chat_id + chave + item_provisorio_id`
- coerencia por sessao deve ser preservada quando houver `mensagem_chat_id` e `item_provisorio_id`
- FKs compostas com `sessao_chat_id` foram implementadas para impedir referencia cruzada entre sessoes:
  - `(sessao_chat_id, mensagem_chat_id)` → `mensagem_chat(sessao_chat_id, id)`
  - `(sessao_chat_id, item_provisorio_id)` → `item_provisorio(sessao_chat_id, id)`
- essas FKs compostas exigem indices unicos compostos em `mensagem_chat(id, sessao_chat_id)` e `item_provisorio(id, sessao_chat_id)`, que estao implementados

### `item_provisorio`

- `sessao_chat_id` obrigatorio
- `quantidade >= 1`
- `status_item` obrigatorio
- item nao pode ser marcado como `promovido` sem `pneu_id`

### `medida_moto`

- `moto_id` obrigatorio
- `posicao` obrigatoria e limitada a `dianteiro` ou `traseiro`
- `largura > 0`, `perfil > 0`, `aro > 0`
- unique `(moto_id, posicao)` — no maximo uma medida por posicao por moto
- `fonte` obrigatoria (ex.: `manual_fabricante`, `curadoria_2w`)

### `estoque`

- `pneu_id` obrigatorio
- `quantidade_disponivel >= 0`
- `reservado >= 0`
- `preco_venda >= 0`

Campo de auditoria recomendado:

- `atualizado_por` para registrar a origem minima da atualizacao de estoque

### `pedido`

- `sessao_chat_id` obrigatorio
- `cliente_id` obrigatorio
- `tipo_entrega` obrigatorio
- `forma_pagamento` obrigatorio
- `valor_total >= 0`
- se `tipo_entrega = entrega`, `endereco_entrega_json` deve existir
- `tipo_entrega` nao pode ser `a_confirmar`
- `forma_pagamento` nao pode ser `a_confirmar`

Constraint de negocio recomendada:

- um pedido oficial por sessao, se essa for a regra operacional do V1

### `item_pedido`

- `pedido_id` obrigatorio
- `pneu_id` obrigatorio
- `quantidade >= 1`
- `preco_unitario >= 0`
- `subtotal >= 0`

Constraint de coerencia recomendada:

- `subtotal = quantidade * preco_unitario`

## 3. O que fica no backend e nao no banco

O banco segura integridade estrutural.
O backend segura decisao operacional.

Estas regras devem ficar no backend no V1:

### Maquina de estados

- validar transicoes permitidas entre etapas
- bloquear salto indevido de etapa
- registrar motivo explicito de bloqueio

### Montagem do contexto executavel

- consolidar fatos ativos
- separar `fatos_ativos` de `resultados_busca_atuais`
- limitar `mensagens_recentes`
- calcular `pendencias`
- calcular `acoes_permitidas`

### Validacao operacional

- decidir se um item pode sair de sugestao para validado
- decidir se um pedido pode nascer
- garantir que pedido nao seja criado sem item oficial, no V1
- decidir se a compatibilidade esta validada
- decidir se estoque e preco consultados ainda sao usaveis naquele turno

### Promocao de estados

- promover item provisiorio para item oficial
- promover fatos para `validado_backend`
- promover fatos para `oficializado` quando a entidade oficial existir

### Falha segura

- impedir que inferencia da IA vire verdade operacional
- recusar criacao de pedido sem requisitos completos
- responder com incerteza controlada quando faltar evidencia

## 4. O que nao deve entrar no V1

Para proteger a simplicidade do primeiro ciclo, estes pontos devem ficar fora:

- historico completo de movimentacao de estoque
- fluxo financeiro completo
- modelagem complexa de endereco
- modelagem complexa de pagamento
- automacoes paralelas ao fluxo principal

## 6. Ajustes pos-auditoria do SQL V1

Depois da primeira auditoria critica, estes pontos foram assumidos como contrato de implementacao do V1:

- `pedido` e entidade oficial e nao aceita `tipo_entrega = a_confirmar`
- `pedido` e entidade oficial e nao aceita `forma_pagamento = a_confirmar`
- `contexto_conversa` deve preservar coerencia por sessao quando apontar para `mensagem_chat`
- `contexto_conversa` deve preservar coerencia por sessao quando apontar para `item_provisorio`

E estes pontos foram mantidos deliberadamente fora do banco nesta etapa:

- o banco nao exige ainda que todo `pedido` tenha ao menos um `item_pedido`
- o banco nao reforca ainda coerencia por sessao em `item_pedido -> item_provisorio`

Esses dois pontos permanecem sob responsabilidade do backend no V1 para evitar endurecimento excessivo cedo demais.

## 7. Otimizacao para agente de IA

Apos a analise de cenarios reais de atendimento, estas otimizacoes foram aplicadas ao banco:

### Decomposicao dimensional em `pneu`

- campos `largura`, `perfil` e `aro` decompostos como inteiros NOT NULL
- permite busca dimensional (`WHERE aro = 17 AND largura = 110`) em vez de parsing de texto
- campo `medida` texto mantido para exibicao humana
- constraint `tipo` limitada a valores padronizados (`dianteiro`, `traseiro`, `universal`)

### Tabela `medida_moto`

- vincula cada moto as dimensoes de pneu por posicao (dianteiro/traseiro)
- permite resolver "quero pneu pra minha CG 160" sem inferencia da IA
- unique `(moto_id, posicao)` — no maximo uma medida por posicao
- dados alimentados por curadoria ou manual do fabricante

### Views operacionais

- `catalogo_agente`: visao plana de `pneu` + `estoque` com `disponivel_real` calculado
- `compatibilidade_moto_pneu`: cruzamento moto → medida → pneu → estoque numa unica query

### Extensoes

- `pg_trgm`: busca por similaridade textual (tolera typos)
- `unaccent`: ignora acentos na busca

### Indexes

- dimensionais em `pneu` (`largura, perfil, aro`)
- trigram GIN em `pneu.marca`, `pneu.modelo`, `moto.descricao_resolvida`, `moto.marca`, `moto.modelo`
- dimensionais e por `moto_id` em `medida_moto`

## 5. Regra de implementacao pratica

Se houver duvida entre colocar uma regra no banco ou no backend, usar este criterio:

- se for integridade estrutural ou impossibilidade matematica, vai para o banco
- se for decisao de fluxo, validacao operacional ou autorizacao, vai para o backend

## Conclusao

O minimo saudavel do V1 e este:

- poucas FKs bem escolhidas
- constraints fortes nas tabelas centrais
- backend controlando fluxo, promocao de estado e contexto executavel

Isso e suficiente para implementar um primeiro sistema confiavel sem inflar o projeto cedo demais.