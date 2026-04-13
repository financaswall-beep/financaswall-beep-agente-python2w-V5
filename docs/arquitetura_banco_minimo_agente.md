# Arquitetura do Banco Minimo do Agente

## Objetivo

Desenhar o banco minimo do agente comercial da 2W Pneus com foco em confiabilidade operacional.

Este banco nao foi pensado para ser um deposito generico de contexto. Ele foi pensado para:

- registrar fatos com evidencia;
- controlar a maquina de estados da conversa;
- impedir que a IA oficialize dados sem validacao;
- permitir auditoria do motivo de cada bloqueio;
- converter conversa em pedido apenas quando os requisitos estiverem validos.

## Principios do desenho

1. A sessao e a raiz do fluxo.
2. O contexto precisa guardar metadado de evidencia junto do valor.
3. Item provisiorio e item oficial sao entidades diferentes.
4. O pedido so nasce no fim do fluxo.
5. O banco garante integridade, mas nao substitui o backend.

## Escopo do primeiro ciclo

Tabelas do primeiro ciclo:

- `sessao_chat`
- `mensagem_chat`
- `contexto_conversa`
- `item_provisorio`
- `cliente`
- `moto`
- `pneu`
- `estoque`
- `pedido`
- `item_pedido`
- `medida_moto`

Decisoes fechadas deste documento:

- compatibilidade nao sera inferida pela IA em nenhuma etapa;
- compatibilidade e resolvida pela tabela `medida_moto`, que vincula cada moto as suas medidas de pneu (dianteiro e traseiro) com dimensoes decompostas (`largura`, `perfil`, `aro`);
- `pedido` so nasce no fechamento, nunca como rascunho ambiguo;
- `contexto_conversa` e historico de fatos com controle de fato ativo;
- auditabilidade de mensagens entra ja no primeiro ciclo.

Fora do primeiro ciclo:

- comissao;
- financeiro completo;
- devolucao;
- roteirizacao;
- automacoes paralelas;
- analytics avancado.

## Enums centrais

### `tipo_de_verdade_enum`

- `observado`
- `inferido`
- `validado_tool`
- `confirmado_cliente`
- `validado_backend`
- `oficializado`

### `etapa_fluxo_enum`

- `identificacao`
- `busca`
- `oferta`
- `confirmacao_item`
- `entrega_pagamento`
- `fechamento`

### `status_sessao_enum`

- `ativa`
- `aguardando_cliente`
- `bloqueada`
- `fechada`

### `nivel_confirmacao_enum`

- `nenhum`
- `confirmado_cliente`
- `validado_tool`
- `validado_backend`
- `oficializado`

### `origem_contexto_enum`

- `mensagem_cliente`
- `inferido_ia`
- `tool`
- `backend`
- `operador`
- `sistema`

### `status_item_provisorio_enum`

- `sugerido`
- `selecionado_cliente`
- `validado`
- `rejeitado`
- `cancelado`
- `promovido`

### `tipo_entrega_enum`

- `retirada`
- `entrega`
- `a_confirmar`

### `forma_pagamento_enum`

- `pix`
- `dinheiro`
- `cartao`
- `transferencia`
- `a_confirmar`

### `status_pedido_enum`

- `confirmado`
- `cancelado`
- `entregue`

## Relacao geral entre tabelas

- uma `sessao_chat` pode ter muitas `mensagem_chat`;
- uma `sessao_chat` pode ter muitos registros em `contexto_conversa`;
- uma `sessao_chat` pode ter muitos `item_provisorio`;
- uma `sessao_chat` pode apontar para um `cliente`, quando esse cliente ja estiver resolvido;
- um `pedido` nasce de uma `sessao_chat`;
- um `pedido` possui muitos `item_pedido`;
- `item_provisorio` pode ser promovido para `item_pedido`;
- `moto`, `pneu`, `estoque` e `medida_moto` sao tabelas de apoio operacional;
- `medida_moto` vincula cada moto as dimensoes de pneu por posicao (dianteiro/traseiro).

## Tabela 1: `sessao_chat`

Raiz do fluxo conversacional.

### Funcao

- identificar a conversa ativa;
- guardar a etapa atual;
- guardar o estado geral da sessao;
- registrar motivo de bloqueio quando houver;
- conectar a conversa ao cliente e ao pedido futuro.

### Campos

| Campo | Tipo sugerido | Obrigatorio | Observacao |
|---|---|---:|---|
| `id` | `uuid` | sim | chave primaria |
| `canal` | `text` | sim | ex.: whatsapp |
| `contato_externo` | `text` | sim | telefone ou identificador externo |
| `cliente_id` | `uuid` | nao | nulo enquanto cliente nao foi resolvido |
| `etapa_atual` | `etapa_fluxo_enum` | sim | etapa vigente da maquina de estados |
| `status_sessao` | `status_sessao_enum` | sim | estado macro da conversa |
| `codigo_motivo` | `text` | nao | codigo curto do bloqueio |
| `mensagem_motivo` | `text` | nao | explicacao auditavel |
| `campo_relacionado` | `text` | nao | ex.: endereco_entrega |
| `acao_bloqueada` | `text` | nao | ex.: converter_em_pedido |
| `ultima_interacao_em` | `timestamptz` | sim | ultima atividade da sessao |
| `criado_em` | `timestamptz` | sim | auditoria |
| `atualizado_em` | `timestamptz` | sim | auditoria |

### Regras

- nao pode existir sessao sem `etapa_atual`;
- tentativa de transicao invalida deve atualizar campos de bloqueio;
- `cliente_id` pode ser nulo no inicio;
- `status_sessao = bloqueada` deve carregar motivo explicito.

## Tabela 2: `mensagem_chat`

Auditoria bruta das mensagens que sustentam os fatos do fluxo.

### Funcao

- persistir as mensagens recebidas e enviadas;
- permitir rastreabilidade da evidencia usada no contexto;
- evitar que `referencia_fonte` aponte para algo inexistente;
- sustentar reprocessamento e auditoria da conversa.

### Campos

| Campo | Tipo sugerido | Obrigatorio | Observacao |
|---|---|---:|---|
| `id` | `uuid` | sim | chave primaria |
| `sessao_chat_id` | `uuid` | sim | fk para `sessao_chat` |
| `direcao` | `text` | sim | `entrada` ou `saida` |
| `remetente` | `text` | sim | cliente, agente ou operador |
| `conteudo_texto` | `text` | sim | mensagem em texto puro |
| `message_id_externo` | `text` | nao | id da plataforma quando existir |
| `metadata_json` | `jsonb` | nao | anexos, provider, payload bruto |
| `criado_em` | `timestamptz` | sim | momento da mensagem |
| `registrado_em` | `timestamptz` | sim | momento da persistencia |

### Regras

- toda mensagem relevante da conversa deve ser persistida;
- fatos observados pelo cliente devem preferencialmente apontar para `mensagem_chat.id`;
- mensagens enviadas pelo agente tambem entram para auditoria completa.

## Tabela 3: `contexto_conversa`

Registro estruturado de fatos com evidencia.

### Funcao

- guardar fatos relevantes do fluxo;
- anexar evidencia a cada dado operacional;
- evitar colunas soltas como `moto`, `forma_pagamento` e `endereco` sem metadado;
- servir de base auditavel para o backend decidir avancos.

### Estrategia de modelagem

Em vez de criar varias colunas de contexto sem controle, esta tabela funciona como historico de fatos por chave.

Cada novo fato relevante entra como um novo registro.

O valor vigente nao substitui o historico. Ele e identificado por `ativo = true` dentro do escopo aplicavel.

Exemplos de `chave`:

- `moto_modelo_informado`
- `medida_dianteira_informada`
- `medida_traseira_informada`
- `posicao_pneu`
- `tipo_entrega`
- `forma_pagamento`
- `endereco_entrega`
- `pneu_sugerido`
- `pneu_confirmado`

### Campos

| Campo | Tipo sugerido | Obrigatorio | Observacao |
|---|---|---:|---|
| `id` | `uuid` | sim | chave primaria |
| `sessao_chat_id` | `uuid` | sim | fk para `sessao_chat` |
| `item_provisorio_id` | `uuid` | nao | quando o fato pertencer a um item especifico |
| `mensagem_chat_id` | `uuid` | nao | fk para `mensagem_chat` quando a evidencia vier de mensagem |
| `chave` | `text` | sim | nome padronizado do fato |
| `valor_texto` | `text` | nao | para valores simples legiveis |
| `valor_json` | `jsonb` | nao | para valores compostos |
| `tipo_de_verdade` | `tipo_de_verdade_enum` | sim | classificacao do dado |
| `nivel_confirmacao` | `nivel_confirmacao_enum` | sim | nivel atual do fato |
| `fonte` | `origem_contexto_enum` | sim | origem do fato |
| `referencia_fonte` | `text` | nao | id de tool, regra ou descricao curta |
| `observacao` | `text` | nao | nota operacional |
| `ativo` | `boolean` | sim | indica qual fato esta valendo |
| `coletado_em` | `timestamptz` | sim | quando o fato foi registrado |
| `criado_em` | `timestamptz` | sim | auditoria |

### Regras

- a tabela base e historico, nao snapshot unico por sessao;
- para cada `chave`, pode haver historico, mas so um registro `ativo = true` por escopo relevante;
- o escopo relevante deve ser tratado como `sessao_chat + chave + item_provisorio`, quando houver item;
- `valor_texto` ou `valor_json` deve existir;
- dado `inferido` nao pode ser tratado como oficial;
- promocao para `oficializado` deve ocorrer apenas apos validacao externa;
- `mensagem_chat_id` deve ser usado sempre que a origem for mensagem do cliente ou resposta do agente.
- quando `mensagem_chat_id` ou `item_provisorio_id` existirem, esses vinculos devem respeitar a mesma `sessao_chat_id` do fato para preservar a sessao como raiz auditavel do fluxo.

### Exemplo concreto

Exemplo de registro para moto informada pelo cliente:

| Campo | Valor |
|---|---|
| `chave` | `moto_modelo_informado` |
| `valor_texto` | `Fazer 250` |
| `tipo_de_verdade` | `observado` |
| `nivel_confirmacao` | `nenhum` |
| `fonte` | `mensagem_cliente` |
| `mensagem_chat_id` | `uuid_da_mensagem` |

## Tabela 4: `item_provisorio`

Entidade de pre-venda antes de virar item oficial do pedido.

### Funcao

- representar o pneu em discussao;
- guardar a escolha do cliente antes da oficializacao;
- impedir que sugestao vire item oficial cedo demais.

### Campos

| Campo | Tipo sugerido | Obrigatorio | Observacao |
|---|---|---:|---|
| `id` | `uuid` | sim | chave primaria |
| `sessao_chat_id` | `uuid` | sim | fk para `sessao_chat` |
| `pneu_id` | `uuid` | nao | so apos resolucao real do pneu |
| `posicao` | `text` | nao | dianteiro, traseiro ou par |
| `quantidade` | `integer` | sim | default 1 |
| `preco_unitario_sugerido` | `numeric(10,2)` | nao | valor da oferta, nao oficial por si so |
| `status_item` | `status_item_provisorio_enum` | sim | estado do item |
| `cliente_confirmou_em` | `timestamptz` | nao | quando houve aceite explicito |
| `validado_backend_em` | `timestamptz` | nao | quando passou nas validacoes operacionais |
| `observacao` | `text` | nao | nota operacional |
| `criado_em` | `timestamptz` | sim | auditoria |
| `atualizado_em` | `timestamptz` | sim | auditoria |

### Regras

- `pneu_id` pode ser nulo enquanto o item estiver apenas sugerido;
- item nao pode ser promovido se `pneu_id` estiver nulo;
- item confirmado pelo cliente ainda nao e item oficial;
- um item `promovido` nao deve continuar editavel como se ainda fosse provisiorio.

## Tabela 5: `cliente`

Entidade oficial do comprador.

### Funcao

- consolidar identidade do cliente;
- evitar duplicidade basica;
- permitir reuso entre sessoes futuras.

### Campos

| Campo | Tipo sugerido | Obrigatorio | Observacao |
|---|---|---:|---|
| `id` | `uuid` | sim | chave primaria |
| `nome` | `text` | nao | pode ser preenchido depois |
| `telefone` | `text` | sim | identificador principal no fluxo inicial |
| `documento` | `text` | nao | cpf ou outro identificador |
| `criado_em` | `timestamptz` | sim | auditoria |
| `atualizado_em` | `timestamptz` | sim | auditoria |

### Regras

- `telefone` deve ter indice unico quando a operacao assim permitir;
- o cliente pode nascer incompleto;
- endereco nao mora em `cliente` no V1, nem como coluna individual nem como jsonb;
- durante a conversa, endereco vive em `contexto_conversa` com chave `endereco_entrega`;
- no pedido oficial, endereco congela como snapshot em `pedido.endereco_entrega_json`;
- essa decisao e intencional para agente de IA: endereco vem de linguagem natural, e irregular, e deve ser tratado como snapshot da venda, nao como cadastro permanente do cliente.

## Tabela 6: `moto`

Catalogo de motos resolvidas operacionalmente.

### Funcao

- normalizar a moto identificada;
- servir de apoio para compatibilidade e busca futura.

### Campos

| Campo | Tipo sugerido | Obrigatorio | Observacao |
|---|---|---:|---|
| `id` | `uuid` | sim | chave primaria |
| `marca` | `text` | sim | ex.: honda |
| `modelo` | `text` | sim | ex.: cg 160 |
| `versao` | `text` | nao | ex.: titan |
| `ano_inicio` | `integer` | nao | opcional no primeiro ciclo |
| `ano_fim` | `integer` | nao | opcional no primeiro ciclo |
| `descricao_resolvida` | `text` | sim | representacao canonica |
| `criado_em` | `timestamptz` | sim | auditoria |

### Regras

- esta tabela nao recebe inferencia como fato oficial sem validacao;
- a conversa pode citar uma moto sem que `moto.id` esteja resolvido ainda.

## Tabela 7: `pneu`

Catalogo oficial de produtos vendaveis.

### Funcao

- representar pneus reais passivos de venda;
- sustentar oferta, confirmacao e pedido.

### Campos

| Campo | Tipo sugerido | Obrigatorio | Observacao |
|---|---|---:|---|
| `id` | `uuid` | sim | chave primaria |
| `sku` | `text` | nao | codigo interno, se existir |
| `marca` | `text` | sim | ex.: pirelli |
| `modelo` | `text` | sim | ex.: city dragon |
| `medida` | `text` | sim | ex.: 110/70-17 (exibicao humana) |
| `largura` | `integer` | sim | ex.: 110 (decomposicao dimensional para busca do agente) |
| `perfil` | `integer` | sim | ex.: 70 (decomposicao dimensional para busca do agente) |
| `aro` | `integer` | sim | ex.: 17 (decomposicao dimensional para busca do agente) |
| `tipo` | `text` | nao | dianteiro, traseiro ou universal (constraint fechada) |
| `descricao_comercial` | `text` | sim | nome exibivel |
| `ativo` | `boolean` | sim | disponibilidade catalogal |
| `criado_em` | `timestamptz` | sim | auditoria |
| `atualizado_em` | `timestamptz` | sim | auditoria |

### Regras

- a IA nunca inventa `pneu.id`;
- item oficial e item provisiorio resolvido precisam apontar para um `pneu` real;
- compatibilidade nao pode ser inferida pela IA;
- compatibilidade e resolvida pela tabela `medida_moto` que vincula motos a dimensoes de pneu;
- busca dimensional usa `largura`, `perfil` e `aro` como inteiros, nao o campo `medida` texto;
- `tipo` e limitado a `dianteiro`, `traseiro` ou `universal` por constraint.

## Tabela 8: `estoque`

Estado operacional de disponibilidade do pneu.

### Funcao

- separar produto de disponibilidade;
- permitir consulta real de quantidade e preco vigente.

### Campos

| Campo | Tipo sugerido | Obrigatorio | Observacao |
|---|---|---:|---|
| `id` | `uuid` | sim | chave primaria |
| `pneu_id` | `uuid` | sim | fk para `pneu` |
| `quantidade_disponivel` | `integer` | sim | saldo atual |
| `preco_venda` | `numeric(10,2)` | sim | preco operacional vigente |
| `reservado` | `integer` | sim | default 0 |
| `atualizado_por` | `text` | nao | ex.: importacao_manual, sistema, operador |
| `atualizado_em` | `timestamptz` | sim | ultima atualizacao |
| `criado_em` | `timestamptz` | sim | auditoria |

### Regras

- no V1, a modelagem de estoque deve assumir uma linha por `pneu`;
- estoque e preco validos devem vir daqui ou de camada equivalente validada;
- o agente nao afirma disponibilidade sem consulta confiavel;
- `quantidade_disponivel` nao pode ser negativa.

## Tabela 9: `medida_moto`

Vinculo dimensional entre moto e medida de pneu por posicao.

### Funcao

- permitir que o agente resolva "quero pneu pra minha CG 160" sem inventar medida;
- vincula cada moto a suas medidas de pneu (dianteiro e traseiro);
- usa dimensoes decompostas (`largura`, `perfil`, `aro`) para cruzamento dimensional com `pneu`;
- dados vem de curadoria ou manual do fabricante, nunca de inferencia da IA.

### Campos

| Campo | Tipo sugerido | Obrigatorio | Observacao |
|---|---|---:|---|
| `id` | `uuid` | sim | chave primaria |
| `moto_id` | `uuid` | sim | fk para `moto` |
| `posicao` | `text` | sim | dianteiro ou traseiro (constraint fechada) |
| `largura` | `integer` | sim | ex.: 80 |
| `perfil` | `integer` | sim | ex.: 100 |
| `aro` | `integer` | sim | ex.: 18 |
| `fonte` | `text` | sim | ex.: manual_fabricante, curadoria_2w |
| `criado_em` | `timestamptz` | sim | auditoria |

### Regras

- cada moto tem no maximo uma medida por posicao (unique `moto_id + posicao`);
- todos os campos dimensionais devem ser positivos;
- `posicao` e limitada a `dianteiro` ou `traseiro` por constraint;
- a IA nao pode inserir dados nesta tabela; alimentacao e responsabilidade da curadoria ou importacao.

## Views operacionais

O banco inclui duas views pre-montadas para simplificar as queries do agente:

### `catalogo_agente`

Visao plana de `pneu` + `estoque` com `disponivel_real` calculado (`quantidade_disponivel - reservado`).

Usada para qualquer busca dimensional ou por marca/modelo de pneu.

### `compatibilidade_moto_pneu`

Cruzamento completo de `moto` → `medida_moto` → `pneu` → `estoque`.

Retorna moto, posicao, dimensoes, pneu compativel (ou null se nao houver no catalogo), preco e disponibilidade real. Usada quando o cliente informa a moto e o agente precisa encontrar pneus compativeis.

## Extensoes habilitadas

- `pg_trgm`: busca por similaridade textual (ex.: "pireli" encontra "Pirelli");
- `unaccent`: ignora acentos na busca textual.

## Tabela 10: `pedido`

Entidade oficial da venda.

### Funcao

- consolidar os dados finais da compra;
- registrar somente o que passou pela validacao final;
- nascer apenas no fechamento do fluxo.

### Campos

| Campo | Tipo sugerido | Obrigatorio | Observacao |
|---|---|---:|---|
| `id` | `uuid` | sim | chave primaria |
| `sessao_chat_id` | `uuid` | sim | origem do pedido |
| `cliente_id` | `uuid` | sim | cliente resolvido |
| `tipo_entrega` | `tipo_entrega_enum` | sim | retirada ou entrega |
| `forma_pagamento` | `forma_pagamento_enum` | sim | modo final da venda |
| `endereco_entrega_json` | `jsonb` | nao | obrigatorio quando `tipo_entrega = entrega` |
| `valor_total` | `numeric(10,2)` | sim | total consolidado |
| `status_pedido` | `status_pedido_enum` | sim | estado oficial |
| `criado_em` | `timestamptz` | sim | auditoria |
| `atualizado_em` | `timestamptz` | sim | auditoria |

### Regras

- pedido nao existe como rascunho no primeiro ciclo;
- pedido nao nasce sem cliente resolvido;
- pedido nao nasce sem item oficial;
- pedido nao nasce sem validacao final do backend;
- pedido nao deve aceitar `tipo_entrega = a_confirmar`;
- pedido nao deve aceitar `forma_pagamento = a_confirmar`;
- se `tipo_entrega = entrega`, endereco precisa existir;
- `valor_total` deve ser coerente com os itens oficiais.

## Tabela 11: `item_pedido`

Item oficial que compoe o pedido.

### Funcao

- registrar pneus oficialmente vendidos;
- congelar quantidade e preco usados na venda;
- separar estado provisiorio do estado oficial.

### Campos

| Campo | Tipo sugerido | Obrigatorio | Observacao |
|---|---|---:|---|
| `id` | `uuid` | sim | chave primaria |
| `pedido_id` | `uuid` | sim | fk para `pedido` |
| `item_provisorio_id` | `uuid` | nao | rastreabilidade da origem |
| `pneu_id` | `uuid` | sim | pneu oficial resolvido |
| `quantidade` | `integer` | sim | quantidade oficial |
| `preco_unitario` | `numeric(10,2)` | sim | preco consolidado |
| `subtotal` | `numeric(10,2)` | sim | preco x quantidade |
| `posicao` | `text` | nao | dianteiro, traseiro ou par |
| `criado_em` | `timestamptz` | sim | auditoria |

### Regras

- so pode existir com `pedido_id` valido;
- so pode existir com `pneu_id` valido;
- `subtotal` deve ser coerente com `quantidade` e `preco_unitario`;
- uma vez criado, vira registro oficial da venda.

## Relacoes recomendadas

| Origem | Destino | Tipo |
|---|---|---|
| `sessao_chat.cliente_id` | `cliente.id` | muitos para um |
| `mensagem_chat.sessao_chat_id` | `sessao_chat.id` | muitos para um |
| `contexto_conversa.sessao_chat_id` | `sessao_chat.id` | muitos para um |
| `contexto_conversa.mensagem_chat_id` | `mensagem_chat.id` | muitos para um |
| `contexto_conversa.item_provisorio_id` | `item_provisorio.id` | muitos para um |
| `item_provisorio.sessao_chat_id` | `sessao_chat.id` | muitos para um |
| `item_provisorio.pneu_id` | `pneu.id` | muitos para um |
| `estoque.pneu_id` | `pneu.id` | muitos para um |
| `medida_moto.moto_id` | `moto.id` | muitos para um |
| `pedido.sessao_chat_id` | `sessao_chat.id` | um para um logico |
| `pedido.cliente_id` | `cliente.id` | muitos para um |
| `item_pedido.pedido_id` | `pedido.id` | muitos para um |
| `item_pedido.pneu_id` | `pneu.id` | muitos para um |
| `item_pedido.item_provisorio_id` | `item_provisorio.id` | muitos para um |

## Ordem pratica de criacao no banco

1. criar enums centrais;
2. criar `cliente`, `moto`, `pneu`;
3. criar `sessao_chat`;
4. criar `mensagem_chat`;
5. criar `estoque`;
6. criar `medida_moto`;
7. criar `item_provisorio`;
8. criar `contexto_conversa`;
9. criar `pedido`;
10. criar `item_pedido`.

## Campos JSON do banco

O banco tem exatamente tres campos do tipo `jsonb`. Cada um tem estrategia de validacao diferente.

### `contexto_conversa.valor_json`

Dinamico. Sem schema fixo.

- o valor varia conforme a `chave` do fato;
- pode ser string, numero, booleano, array ou objeto;
- o backend sabe o que esperar por chave, nao o banco;
- Python nao valida schema do valor_json neste campo;
- exemplos: array de medidas compativeis, objeto com dianteiro e traseiro, string de moto informada.

### `pedido.endereco_entrega_json`

Estruturado. Pydantic model obrigatorio antes de persistir.

- snapshot do endereco usado na venda;
- estrutura minima esperada: logradouro, numero, bairro, cidade, estado, cep;
- campos opcionais: complemento, referencia;
- o backend valida via Pydantic antes de inserir;
- nao deve ser preenchido com dado nao validado.

### `mensagem_chat.metadata_json`

Semi-estruturado. Validacao minima no backend.

- varia por provider (WhatsApp, Telegram, etc);
- campo obrigatorio: `provider`;
- restante e livre e depende do canal;
- Python valida apenas o minimo estrutural.

## Trigger de `atualizado_em`

As colunas `atualizado_em` existem nas tabelas que precisam de controle de modificacao.

O banco nao atualiza essas colunas automaticamente sem trigger ou logica de aplicacao.

Tabelas que precisam de trigger ou atualizacao explicita no backend:

- `sessao_chat.atualizado_em`
- `cliente.atualizado_em`
- `item_provisorio.atualizado_em`
- `pneu.atualizado_em`
- `estoque.atualizado_em`
- `pedido.atualizado_em`

Implementacao recomendada no Supabase: trigger `BEFORE UPDATE` com `NEW.atualizado_em = now()`.

## Status de implementacao do banco

O banco do V1 foi implementado no projeto `betaAgente` no Supabase (sa-east-1).

Decisoes confirmadas na implementacao:

- FKs compostas para integridade entre sessoes estao implementadas em `contexto_conversa`;
- dois indices unicos parciais para `ativo = true` em `contexto_conversa` estao implementados;
- `cliente` lean sem endereco foi implementado como decidido;
- constraints de negocio no `pedido` (sem `a_confirmar`) estao implementadas;
- indice unico por sessao em `pedido` esta implementado;
- `estoque` com uma linha por `pneu` e indice unico em `pneu_id` esta implementado.

Decisoes adicionais confirmadas na otimizacao para agente de IA:

- extensoes `pg_trgm` e `unaccent` habilitadas para busca por similaridade e sem acento;
- campos dimensionais `largura`, `perfil` e `aro` decompostos como inteiros em `pneu` para busca dimensional;
- tabela `medida_moto` criada com 24 registros (12 motos x 2 posicoes), vinculando dimensoes de pneu por moto;
- VIEW `catalogo_agente` criada como visao plana de `pneu` + `estoque` com `disponivel_real` calculado;
- VIEW `compatibilidade_moto_pneu` criada para cruzar moto, medida, pneu e estoque numa unica query;
- 10 indexes otimizados para busca dimensional e trigram;
- constraint `pneu.tipo` limitada a `dianteiro`, `traseiro` ou `universal`.

O proximo passo e implementar schemas Python e o orquestrador backend.