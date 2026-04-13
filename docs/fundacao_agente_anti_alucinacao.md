# Fundacao do Agente Anti-Alucinacao

## Objetivo

Construir um agente comercial para a 2W Pneus que seja confiavel antes de ser "esperto".

O agente deve:

- interpretar linguagem natural do cliente;
- buscar dados reais no sistema;
- operar em etapas fechadas;
- nunca inventar fatos operacionais;
- so converter uma conversa em pedido quando os dados obrigatorios estiverem validados.

## Principio central

O sistema nao trabalha com "contexto solto". Ele trabalha com verdade mais evidencia.

Cada informacao relevante precisa carregar:

- valor;
- tipo_de_verdade;
- nivel de confianca;
- status de confirmacao.

Sem esses metadados, o sistema nao pode tratar um dado como base confiavel para avancar o fluxo.

## Taxonomia fixa de verdade

Toda informacao operacional deve ser classificada em uma destas categorias:

- `observado`: o cliente falou explicitamente;
- `inferido`: a IA deduziu, mas ainda nao ha confirmacao;
- `validado_tool`: veio de busca no banco, tool ou regra tecnica;
- `confirmado_cliente`: o cliente confirmou explicitamente;
- `validado_backend`: o backend validou a consistencia operacional;
- `oficializado`: o dado ja foi promovido para uma entidade oficial do sistema.

Essa taxonomia deve ser usada de forma uniforme em todo campo operacional relevante, sem excecao.

## Niveis de confirmacao

O termo `confirmado` nao deve ser usado de forma generica no sistema. Ele precisa ser desdobrado em niveis distintos:

- `confirmado_cliente`: o cliente confirmou a informacao em linguagem natural;
- `validado_tool`: a informacao foi retornada por ferramenta ou consulta confiavel;
- `validado_backend`: o backend verificou coerencia e autorizou uso operacional;
- `oficializado`: a informacao foi persistida em entidade oficial, como pedido ou item de pedido.

Esses niveis nao sao equivalentes. Um dado pode estar confirmado pelo cliente e ainda nao estar validado pelo backend.

## O que o agente nunca pode inventar

Os seguintes dados nao podem ser afirmados como verdade sem evidencia valida:

- `pneu_id`;
- compatibilidade entre pneu e moto (deve vir da tabela `medida_moto` e VIEW `compatibilidade_moto_pneu`);
- preco;
- estoque;
- moto resolvida em caso ambiguo;
- forma de pagamento;
- endereco de entrega;
- status de pedido;
- conversao de item provisiorio em item confirmado.

Se um desses dados nao vier de fonte valida, o agente deve perguntar, buscar ou declarar incerteza.

## Papels do sistema

### IA

Responsavel por:

- interpretar a mensagem do cliente;
- identificar intencao provavel;
- sugerir proxima acao;
- montar resposta em linguagem natural;
- propor mudancas estruturadas no estado.

A IA nao e autoridade de verdade operacional.

### Backend

Responsavel por:

- validar envelope de saida da IA;
- aplicar maquina de estados;
- decidir se uma acao pode ou nao acontecer;
- resolver ids reais;
- validar estoque, preco, compatibilidade e campos obrigatorios;
- autorizar conversao em pedido.

O backend e o arbitro absoluto do fluxo.

### Banco

Responsavel por:

- persistencia;
- integridade referencial;
- constraints essenciais;
- calculos automaticos previsiveis;
- historico auditavel.

O banco nao deve substituir o orquestrador.

## Regra de ouro

A IA interpreta.
O backend decide.
O banco garante integridade.

## Criterio de bloqueio

Toda acao aceita, recusada ou adiada pelo backend deve carregar um motivo explicito.

Campos minimos para bloqueio ou recusa operacional:

- `codigo_motivo`;
- `mensagem_motivo`;
- `campo_relacionado`, quando houver;
- `acao_bloqueada`.

O sistema nao deve apenas recusar. Ele deve explicar por que recusou.

## Fluxo operacional minimo

O primeiro fluxo do projeto deve ser pequeno e fechado.

Etapas iniciais:

1. `identificacao`
2. `busca`
3. `oferta`
4. `confirmacao_item`
5. `entrega_pagamento`
6. `fechamento`

Essas etapas devem virar uma maquina de estados real. O agente nao pode pular livremente entre elas.

## Maquina de estados formal

Transicoes permitidas no fluxo minimo:

- `identificacao -> busca`
- `busca -> oferta`
- `oferta -> confirmacao_item`
- `confirmacao_item -> entrega_pagamento`
- `entrega_pagamento -> fechamento`

Transicoes de retorno permitidas:

- `busca -> identificacao`, quando houver ambiguidade ou dado insuficiente;
- `oferta -> busca`, quando o cliente mudar criterio, medida ou moto;
- `confirmacao_item -> oferta`, quando o cliente rejeitar a opcao atual;
- `entrega_pagamento -> confirmacao_item`, quando faltar item valido ou houver mudanca na compra;

Transicoes proibidas no fluxo minimo:

- `identificacao -> fechamento`
- `busca -> fechamento`
- `oferta -> fechamento`
- `confirmacao_item -> fechamento`, sem etapa de entrega e pagamento;

Toda tentativa de transicao invalida deve ser bloqueada pelo backend com motivo explicito.

## Regras por etapa

### 1. identificacao

Objetivo:

- entender quem e o cliente;
- descobrir moto, medida ou necessidade.

Permitido:

- perguntar clarificacao;
- buscar moto;
- buscar medida;
- registrar fatos observados.

Bloqueios:

- nao pode ofertar como fato algo nao buscado;
- nao pode confirmar compatibilidade.

### 2. busca

Objetivo:

- localizar opcoes reais no catalogo e no estoque.

Permitido:

- buscar por moto (via VIEW `compatibilidade_moto_pneu` — retorna pneus compativeis);
- buscar por medida exata ou por dimensoes parciais (largura, perfil, aro) via VIEW `catalogo_agente`;
- buscar por marca/modelo de pneu com tolerancia a typos (`pg_trgm`);
- registrar opcoes encontradas.

Bloqueios:

- nao pode afirmar compatibilidade se nao veio da VIEW `compatibilidade_moto_pneu`;
- nao pode transformar resultado de busca em confirmacao automatica;
- resultado de busca por dimensoes nao implica compatibilidade com a moto do cliente.

### 3. oferta

Objetivo:

- apresentar opcoes reais e explicar faltas ou incertezas.

Permitido:

- mostrar opcoes retornadas por tool;
- apontar promocao, estoque e preco se vieram de fonte valida;
- pedir escolha do cliente.

Bloqueios:

- nao pode inventar opcao;
- nao pode inventar estoque;
- nao pode prometer compatibilidade nao validada.

### 4. confirmacao_item

Objetivo:

- transformar uma sugestao em item provisiorio confirmado.

Permitido:

- confirmar item escolhido;
- registrar quantidade e posicao;
- manter item provisiorio no contexto.

Bloqueios:

- item so vira confirmado se houver pneu real resolvido;
- nao pode confirmar item com UUID inventado.

### 5. entrega_pagamento

Objetivo:

- coletar dados minimos para finalizar venda.

Permitido:

- perguntar tipo de entrega;
- perguntar endereco;
- perguntar forma de pagamento.

Bloqueios:

- nao pode converter em pedido sem os campos obrigatorios definidos pelo backend.

### 6. fechamento

Objetivo:

- revisar tudo e converter em pedido oficial.

Permitido:

- revisar itens confirmados;
- converter em pedido se todos os requisitos estiverem validos.

Bloqueios:

- sem item confirmado, nao ha pedido;
- sem pagamento ou entrega necessarios, nao ha pedido;
- sem validacao final do backend, nao ha pedido.

## Entidades minimas do projeto

O primeiro ciclo deve usar poucas entidades.

- `sessao_chat`
- `mensagem_chat`
- `contexto_conversa`
- `item_provisorio`
- `cliente`
- `moto`
- `medida_moto` (compatibilidade moto → medida por posicao)
- `pneu`
- `estoque`
- `pedido`
- `item_pedido`

Tudo que nao for essencial ao fluxo principal deve ficar para depois.

Exemplos do que nao entra no primeiro ciclo:

- comissao;
- financeiro completo;
- devolucao completa;
- roteirizacao complexa;
- automacoes paralelas.

## Contrato executavel da IA

A IA nao deve retornar apenas texto. Ela deve retornar um envelope estruturado, fechado e validavel pelo backend.

Campos obrigatorios do envelope:

- `mensagem_cliente`
- `etapa_atual`
- `intencao_atual`
- `acoes_sugeridas`
- `pendencias`
- `confianca`

Campos estruturados recomendados:

- `fatos_observados`
- `fatos_inferidos`
- `mudancas_contexto`
- `mudancas_itens`
- `bloqueios_identificados`

Enums minimos esperados:

- `etapa_atual`: `identificacao`, `busca`, `oferta`, `confirmacao_item`, `entrega_pagamento`, `fechamento`
- `confianca`: `alta`, `media`, `baixa`
- `acoes_sugeridas`: lista fechada definida pelo backend

Principios do contrato:

- todo campo deve ser validavel pelo backend;
- o envelope nao deve carregar ids inventados;
- o envelope nao deve promover fatos inferidos para fatos confirmados sem validacao externa;
- resultado de busca nao deve ser tratado como item confirmado automaticamente.

## Contexto minimo executavel

O contexto persistido do fluxo deve ser pensado como contrato, nao como deposito generico.

Cada campo operacional relevante deve carregar pelo menos:

- `valor`
- `tipo_de_verdade`
- `fonte`
- `nivel_de_confirmacao`
- `timestamp`

Campos como moto, medida, posicao, pneu sugerido, pneu confirmado, forma de pagamento e endereco nao devem existir no contexto sem metadado de evidencia.

## Politica de falha segura

Quando nao houver evidencia suficiente, o sistema deve falhar de forma segura.

Respostas aceitaveis:

- "Nao consegui confirmar essa compatibilidade ainda."
- "Encontrei medida proxima, mas preciso validar antes de afirmar que serve."
- "Preciso que voce confirme a posicao do pneu."
- "Ainda nao tenho dados suficientes para fechar o pedido."

Quando o cliente perguntar algo como "esse pneu serve na minha moto?", o sistema deve consultar a VIEW `compatibilidade_moto_pneu` via `buscar_por_moto`. Se a moto estiver cadastrada em `medida_moto`, a resposta vem do banco (tipo_de_verdade = `validado_tool`). Se a moto nao estiver cadastrada, a resposta deve ser de incerteza segura, nunca de afirmacao especulativa.

Respostas inaceitaveis:

- afirmar como fato algo apenas inferido;
- inventar id;
- inventar estoque;
- inventar compatibilidade;
- criar pedido sem validacao completa.

## Ordem de implementacao

O projeto novo deve nascer nesta ordem:

1. ~~fechar fluxo e regras operacionais~~ — concluido;
2. ~~modelar entidades minimas do banco~~ — concluido (banco `betaAgente` no Supabase);
3. definir contrato de saida da IA — em andamento (documentado, falta validar com codigo);
4. implementar schemas e validadores Python (Pydantic);
5. implementar orquestrador (maquina de estados + montagem do contexto executavel);
6. implementar tools de leitura (catalogo, estoque, compatibilidade via `medida_moto` e views);
7. conectar a IA (envelope estruturado + validacao do backend);
8. por ultimo, implementar conversao oficial em pedido.

## Criterio de sucesso

O projeto esta no caminho certo quando:

- a IA nao precisa inventar nada para responder;
- o backend consegue explicar por que uma acao foi aceita ou bloqueada;
- o banco reflete fatos operacionais reais;
- uma conversa ambigua nao vira pedido por acidente;
- o sistema prefere pedir clarificacao a responder errado.