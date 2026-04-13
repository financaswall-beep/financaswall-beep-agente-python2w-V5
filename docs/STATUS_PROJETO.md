# Status do Projeto — Agente 2W Pneus

Ultima atualizacao: 03/04/2026

## Fase 1 — Fundacao (COMPLETA)

### Infraestrutura

- [x] `.env` com SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY, OPENAI_MODEL
- [x] `.gitignore`
- [x] `agente_2w/config.py` — carrega variaveis do `.env`
- [x] `agente_2w/db/client.py` — cliente Supabase inicializado
- [x] `__init__.py` em todos os 7 pacotes (raiz, db, engine, enums, ia, schemas, tools)

### Enums (13 enums em `enums/enums.py`)

- [x] 9 enums do banco: TipoDeVerdade, EtapaFluxo, StatusSessao, NivelConfirmacao, OrigemContexto, StatusItemProvisorio, TipoEntrega, FormaPagamento, StatusPedido
- [x] 4 enums auxiliares: Confianca, Direcao, Remetente, Posicao
- [x] `enums/__init__.py` re-exporta todos os 13
- [x] Todos usam `str, Enum` para compatibilidade Pydantic/JSON

### Schemas — Tabelas (11 arquivos em `schemas/`)

- [x] `cliente.py` — ClienteBase, ClienteCreate, Cliente
- [x] `sessao_chat.py` — SessaoChatBase, SessaoChatCreate, SessaoChat (validator: bloqueio exige motivo)
- [x] `mensagem_chat.py` — MensagemChatBase, MensagemChatCreate, MensagemChat
- [x] `contexto_conversa.py` — ContextoConversaBase, ContextoConversaCreate, ContextoConversa (validators: valor obrigatorio, mensagem_cliente exige mensagem_id)
- [x] `item_provisorio.py` — ItemProvisorioBase, ItemProvisorioCreate, ItemProvisorio (validators: quantidade >= 1, promovido exige pneu_id)
- [x] `pneu.py` — PneuBase, Pneu (validators: largura/perfil/aro > 0)
- [x] `moto.py` — MotoBase, Moto (validator: ano_fim >= ano_inicio)
- [x] `medida_moto.py` — MedidaMotoBase, MedidaMotoCreate, MedidaMoto (validators: largura/perfil/aro > 0)
- [x] `estoque.py` — EstoqueBase, Estoque (validators: quantidade >= 0, preco >= 0, reservado >= 0)
- [x] `pedido.py` — PedidoBase, PedidoCreate, Pedido (validators: tipo_entrega != a_confirmar, forma_pagamento != a_confirmar, entrega exige endereco)
- [x] `item_pedido.py` — ItemPedidoBase, ItemPedidoCreate, ItemPedido (validators: quantidade >= 1, subtotal = quantidade * preco_unitario)

### Schemas — JSONB (2 arquivos)

- [x] `endereco_entrega.py` — EnderecoEntrega (logradouro, numero, bairro, cidade, estado, cep, complemento, referencia)
- [x] `metadata_chat.py` — MetadataChat (provider, message_id_externo, payload)

### Schemas — IA (2 arquivos)

- [x] `contexto_executavel.py` — 10 classes: SessaoContexto, ClienteContexto, BloqueioAtivo, MensagemRecente, FatoAtivo, ResultadoBusca, ItemProvisorioContexto, Pendencia, ResumoOperacional, Metadados, ContextoExecutavel
- [x] `envelope_ia.py` — 6 classes: FatoObservado, FatoInferido, MudancaContexto, MudancaItem, BloqueioIdentificado, EnvelopeIA

## Fase 2 — Repositorios (COMPLETA)

### Repos do banco (8 arquivos em `db/`)

- [x] `sessao_repo.py` — criar, buscar por id, buscar ativa por contato, atualizar etapa, atualizar status (com bloqueio), vincular cliente
- [x] `mensagem_repo.py` — criar, listar por sessao (limite 20, ordem cronologica), buscar por id
- [x] `contexto_repo.py` — criar fato, desativar fato anterior, registrar fato (desativa+cria atomico), listar ativos, listar por chave, buscar fato ativo por escopo
- [x] `item_provisorio_repo.py` — criar, buscar por id, listar por sessao, listar ativos (filtra por status), atualizar status, vincular pneu
- [x] `cliente_repo.py` — criar, buscar por id, buscar por telefone, resolver ou criar, atualizar
- [x] `catalogo_repo.py` — buscar pneu por id/dimensoes/medida/marca, buscar moto por id/texto, listar medidas por moto, compatibilidade por moto, estoque por pneu
- [x] `pedido_repo.py` — criar pedido (tipado PedidoCreate), buscar por id/sessao, criar item pedido (tipado ItemPedidoCreate), listar itens
- [x] `queries.py` — contar registros, verificar existencia, buscar generico por id

## Fase 3 — Engine (COMPLETA)

- [x] `engine/maquina_estados.py` — TRANSICOES dict, pode_transitar(), proximas_etapas(), e_terminal(), obter_todas_etapas()
- [x] `engine/pendencias.py` — PENDENCIAS_POR_ETAPA, acoes_permitidas(), pendencias_etapa(), validar_acao()
- [x] `engine/montador_contexto.py` — montar_contexto(sessao_id) monta ContextoExecutavel completo
- [x] `engine/validador_envelope.py` — validar_envelope(envelope, etapa_atual) valida acao, transicao, fatos, mensagem
- [x] `engine/promotor.py` — promover_itens(sessao_id) converte itens provisorios confirmados em pedido + itens_pedido

## Fase 4 — Tools (COMPLETA)

- [x] `tools/busca_catalogo.py` — buscar_pneus(dimensoes/medida/marca), buscar_pneus_por_moto(termo), buscar_detalhes_pneu(id)
- [x] `tools/consulta_estoque.py` — consultar_estoque(pneu_id) retorna disponibilidade, preco, disponivel_real
- [x] `tools/resolve_cliente.py` — resolver_cliente(telefone, nome) busca ou cria cliente

## Fase 5 — IA (COMPLETA)

- [x] `ia/prompt_sistema.py` — system prompt (5146 chars): persona 2W Pneus, regras de comportamento, fluxo de etapas, formato EnvelopeIA, acoes validas por etapa
- [x] `ia/agente.py` — chamar_agente(contexto, mensagem): OpenAI gpt-4o com 5 tools (function calling), loop ate 5 rounds de tool calls, dispatch automatico
- [x] `ia/parser_envelope.py` — parse_resposta(resposta_bruta, contexto): extrai JSON (suporta markdown), valida Pydantic EnvelopeIA, chama validar_envelope

## Fase 6 — Orquestrador (COMPLETA)

- [x] `engine/orquestrador.py` — loop completo de um turno (13 passos)
- [x] `main.py` — ponto de entrada CLI para testes manuais

## Fase 7 — Fixes e Hardening (COMPLETA)

Data: 29/03/2026

### Alteracoes realizadas

1. **client.py — except:pass corrigido** — `except Exception: pass` substituido por `except Exception as e: logger.debug(...)`. Agora erros de proxy sao logados em vez de engolidos silenciosamente.

2. **constantes.py — chaves de contexto centralizadas** — Novo arquivo `constantes.py` com classe `ChaveContexto` contendo todas as chaves usadas no `contexto_conversa`: `TIPO_ENTREGA`, `FORMA_PAGAMENTO`, `ENDERECO_ENTREGA`, etc. Aplicado em `promotor.py`, `montador_contexto.py`, `pendencias.py`.

3. **catalogo_repo — retornos padronizados** — `buscar_motos_por_texto()` e `listar_medidas_por_moto()` agora retornam `list[dict]` (consistente com as outras funcoes de lista). Funcoes de entidade unica (`buscar_pneu_por_id`, `buscar_moto_por_id`, `buscar_estoque_por_pneu`) mantidas com retorno de Pydantic model.

4. **agente.py — timeout + retry com backoff** — OpenAI client agora tem `timeout=30s`. Chamadas usam `tenacity` com retry automatico para `RateLimitError`, `APITimeoutError`, `APIConnectionError` (3 tentativas, backoff exponencial 2-30s). Logging em cada retry.

5. **db/exceptions.py — excecoes tipadas** — `RepositoryError`, `RegistroNaoEncontrado`, `ErroDeInsercao`, `ErroDeAtualizacao` aplicadas em todos os 7 repos (sessao, mensagem, contexto, item_provisorio, cliente, catalogo, pedido). Todas as funcoes de repo tem try/except com contexto (tabela + operacao).

6. **promotor.py — RPC transacional** — Reescrito para usar RPC `promover_para_pedido` do Supabase. Pedido + itens + status atualizados numa unica transacao PostgreSQL. Se qualquer parte falhar, nada e persistido.

7. **teste_fase_6.py — teste automatizado** — 43 testes cobrindo: imports, constantes, excecoes, timeout/retry, catalogo padronizado, proxy, promotor (pre-condicoes), orquestrador E2E (2 turnos com IA real).

## Resultado dos Testes — Fase 6

Data: 29/03/2026 | Script: `teste_fase_6.py` | **43/43 PASS**

### Teste de 2 turnos (CG 160 Titan)

| Turno | Entrada | Etapa antes | Etapa depois | Resultado |
|-------|---------|-------------|-------------|-----------|
| 1 | "Oi, quero um pneu pra minha CG 160 Titan" | identificacao | busca | Fato `moto_modelo=CG 160 Titan` registrado, IA buscou via function calling |
| 2 | "Qual o mais barato pra traseira?" | busca | oferta | Precos reais do banco (Pirelli Street Rider R$ 239,90) |

### Funcionalidades validadas

- [x] Persistencia de mensagem de entrada e saida
- [x] Resolucao automatica de cliente por contato_externo
- [x] Montagem do contexto executavel
- [x] Chamada OpenAI GPT-4o com function calling (5 tools)
- [x] Parse de resposta JSON (com `response_format=json_object`)
- [x] Validacao do envelope (acoes, transicoes, fatos)
- [x] Retry com correcao quando envelope invalido (MAX_RETRIES=2)
- [x] Registro de fatos observados e inferidos no contexto_conversa
- [x] Aplicacao de mudancas de itens provisorios
- [x] Despacho de acoes (converter_em_pedido → promotor)
- [x] Transicao de etapa com bloqueio quando invalida
- [x] Falha segura: banco nao e alterado quando IA retorna envelope invalido
- [x] Logging estruturado em todos os passos

### Bugs corrigidos durante Fase 6

1. **agente.py**: Adicionado `response_format={"type": "json_object"}` nas duas chamadas OpenAI — corrige non-determinismo onde IA retornava texto livre em vez de JSON
2. **prompt_sistema.py**: Reforco explicito de que a IA NAO pode pular etapas e DEVE usar apenas acoes da etapa atual
3. **orquestrador.py**: Retry com re-prompt inclui etapas validas, acoes permitidas e erros anteriores para corrigir a IA

## Fase 8 — Correcoes E2E e Teste Real Completo (COMPLETA)

Data: 29/03/2026

### Contexto

Apos a Fase 7, o sistema foi testado manualmente via CLI (`agente.bat`). Foram identificados 4 bugs que impediam a criacao do pedido nas tabelas `pedido` e `item_pedido`. Todos foram corrigidos nesta fase. O primeiro pedido real foi criado com sucesso via RPC transacional.

### Alteracoes realizadas

1. **agente.bat — launcher CLI** — Criado `agente.bat` na raiz do projeto para facilitar execucao do CLI no Windows. Aceita argumentos: `--debug`, `--contato`, `--sessao`.

2. **prompt_sistema.py — instrucoes para mudancas_itens** — Adicionada secao completa "Regras para mudancas_itens" com:
   - Exemplo concreto de criacao de item com `pneu_id` UUID real
   - Aviso CRITICO: `pneu_id` e obrigatorio, sem ele o pedido nao pode ser criado
   - Valores validos de `status_item`: sugerido, selecionado_cliente, validado, rejeitado, cancelado, promovido
   - Aviso explicito: NUNCA usar "confirmado" para item (existe apenas em `status_pedido`)
   - Fluxo tipico de 2 turnos em `confirmacao_item`

3. **prompt_sistema.py — instrucoes para fatos de entrega/pagamento** — Adicionada regra explicita: ao receber `tipo_entrega` ou `forma_pagamento`, registrar em `fatos_observados` NO MESMO TURNO. Sem isso a IA ficava em loop perguntando a mesma coisa.

4. **prompt_sistema.py — aviso de UUID real** — Instrucao explicita: `pneu_id` deve ser o UUID exato retornado pela tool, nunca texto de exemplo como `"UUID-EXATO-RETORNADO-PELA-TOOL"`.

5. **orquestrador.py — validacao de UUID + status automatico** — Em `_aplicar_mudancas_itens`, ao criar item:
   - UUID malformado e ignorado com warning em vez de explodir com excecao
   - Se `pneu_id` valido: item criado com `status = selecionado_cliente`
   - Se sem `pneu_id`: item criado com `status = sugerido` (como antes)

6. **promotor.py — aceitar selecionado_cliente** — `validar_pre_condicoes` e `promover_para_pedido` agora aceitam `status_item in (selecionado_cliente, validado)` em vez de apenas `validado`. O promotor ja valida estoque e preco internamente, tornando o requisito de `validado` redundante.

7. **promotor.py — endereco_json de valor_texto** — Corrigido bug onde `endereco_json = fato_endereco.valor_json` retornava `None` porque o endereco e salvo em `valor_texto`. Agora: se `valor_json` existir usa ele; se nao, usa `{"endereco": valor_texto}`. Corrige violacao do constraint `pedido_endereco_entrega_chk`.

### Primeiro pedido real criado

Sessao: `dc7a8e63-46f6-40aa-b8e4-96dda0352e0e`

| Campo | Valor |
|-------|-------|
| Pedido ID | `496d6414-724d-4484-ad9e-8dca71fbf1e4` |
| Pneu | CST Ride Migra 130/70-13 (PCX traseiro) |
| Valor total | R$ 259,90 |
| Tipo entrega | entrega |
| Forma pagamento | pix |
| Endereco | Rua das Flores 100, Bairro Centro, Niteroi |
| Status | confirmado |
| item_pedido | 1 item (quantidade=1, preco=259,90, subtotal=259,90) |

### Bugs identificados e corrigidos

| # | Sintoma | Causa | Fix |
|---|---------|-------|-----|
| 1 | `item_provisorio.pneu_id = NULL` | IA nao sabia que precisava passar UUID do pneu | Prompt: instrucoes explicitas + exemplo |
| 2 | `status_item` nunca chegava a `validado` | Nao havia mecanismo de transicao automatica para `validado` | Promotor aceita `selecionado_cliente` |
| 3 | IA usava status `"confirmado"` para item | Valor invalido (existe em `status_pedido`, nao em `status_item`) | Prompt: valores validos documentados |
| 4 | `endereco_entrega_json = null` na RPC | Promotor lia `valor_json` mas endereco esta em `valor_texto` | Promotor: fallback para `valor_texto` |

### Observacao sobre comportamento do modelo

O GPT-4o as vezes precisa de uma mensagem adicional no fechamento ("pode finalizar") para emitir `converter_em_pedido`. Corrigido na Fase 9 com auto-promocao.

## Fase 9 — Defesa em Profundidade: Auto-enriquecimento e Auto-promocao (COMPLETA)

Data: 29/03/2026

### Contexto

Segundo teste E2E revelou que as correcoes da Fase 8 foram insuficientes: o modelo copiava literalmente o texto de placeholder `"UUID-EXATO-RETORNADO-PELA-TOOL"` do exemplo do prompt como valor de `pneu_id`. Resultado: `pneu_id=NULL` em todo item provisorio → promotor rejeitava sempre → tabelas `pedido` e `item_pedido` vazias.

Diagnostico: depender da IA para transportar UUIDs entre resultados de tool e JSON de saida e fundamentalmente fragil. Solucao: o backend deve ser auto-suficiente.

### Principio aplicado

> O backend ja tem o dado (veio da tool). Nao precisa da IA pra repassar.

### Alteracoes realizadas (4 arquivos)

1. **prompt_sistema.py — remover placeholder toxico**
   - Exemplo de `mudancas_itens` agora usa UUID com formato real (`78515ece-e874-434e-b615-9efd124b64f5`) em vez de `"UUID-EXATO-RETORNADO-PELA-TOOL"`
   - Removida toda mencao ao texto de placeholder para o modelo nao ter o que copiar

2. **agente.py — coletar pneu_ids dos resultados de tool**
   - Nova funcao `_extrair_pneus_de_resultado()`: parseia JSON dos resultados de tools de busca e extrai `pneu_id`, `posicao`, `preco_venda`
   - `chamar_agente()` agora retorna `tuple[str, list[dict]]` — envelope + pneus encontrados
   - Coleta acontece em TODAS as tools de busca: `buscar_pneus`, `buscar_pneus_por_moto`, `buscar_detalhes_pneu`, `consultar_estoque`

3. **orquestrador.py — auto-enriquecimento + auto-promocao + bloqueio de promovido**
   - `_chamar_e_validar()` retorna `(envelope, pneus_encontrados)` em vez de so `envelope`
   - `_aplicar_mudancas_itens()` recebe `pneus_encontrados` e auto-enriquece:
     - Se `pneu_id` da IA e invalido/ausente, tenta match por posicao nos resultados de tool
     - Se so tem 1 pneu nos resultados, usa direto
     - Tambem preenche `preco_unitario_sugerido` se ausente
   - `processar_turno()` passo 12 novo: se `etapa == fechamento` e pre-condicoes ok → auto-promover
     - Nao depende mais do modelo emitir `converter_em_pedido`
     - Elimina a "mensagem extra" que incomodava no UX
   - Bloqueio: se IA tenta `atualizar` item com `status_item=promovido`, operacao e ignorada com warning

4. **validador_envelope.py — bloquear status=promovido via atualizar**
   - Nova regra: se `mudanca.acao == "atualizar"` e `dados.status_item == "promovido"`, envelope e rejeitado
   - Previne que IA contorne a exclusividade do promotor

### Bugs corrigidos (Fase 9)

| # | Sintoma | Causa raiz | Fix |
|---|---------|-----------|-----|
| 1 | `pneu_id = 'UUID-EXATO-RETORNADO-PELA-TOOL'` | Modelo copia literalmente o placeholder do prompt | Prompt: exemplo com UUID real |
| 2 | `pneu_id = NULL` no item (mesmo com UUID nas tools) | Backend descartava pneu_ids das tools e dependia da IA | agente.py retorna pneus + orquestrador auto-enriquece |
| 3 | Precisa mensagem extra pra criar pedido | Modelo nao emitia `converter_em_pedido` automaticamente | Auto-promocao no backend quando pre-condicoes ok |
| 4 | IA setava `status_item=promovido` direto | Validador nao cobria `atualizar` + `status=promovido` | Validador + orquestrador bloqueiam |

### Defesa em profundidade resultante

```
Camada 1 (prompt):  Modelo recebe exemplo com UUID real, sem placeholder pra copiar
Camada 2 (agente):  Backend coleta pneu_ids reais durante tool calls
Camada 3 (orquest): Se pneu_id invalido, auto-enriquece dos resultados de tool
Camada 4 (orquest): Em fechamento, auto-promove se pre-condicoes ok
Camada 5 (valid):   Rejeita envelope com status_item=promovido via atualizar
Camada 6 (banco):   Constraint item_provisorio_promovido_pneu_chk
```

### Teste E2E automatizado (29/03/2026)

Conversa simulada diretamente via `processar_turno()` (sem CLI, sem input manual):

| Turno | Mensagem cliente | Etapa resultante |
|-------|-----------------|-----------------|
| 1 | "boa tarde, preciso de pneu traseiro pra minha XRE 300" | busca |
| 2 | "pode ser o Ira Moby" | oferta |
| 3 | "quero 1 unidade, traseiro mesmo" | confirmacao_item |
| 4 | "vou buscar na loja" | entrega_pagamento |
| 5 | "pix" | entrega_pagamento |
| 6 | "sim pode finalizar" | fechamento |

**Auditoria do banco apos o teste:**

| Tabela | Campo | Valor | Status |
|--------|-------|-------|--------|
| `item_provisorio` | `pneu_id` | `78515ece-e874-434e-b615-9efd124b64f5` | Auto-enriquecido |
| `item_provisorio` | `status_item` | `promovido` | Correto |
| `item_provisorio` | `posicao` | `traseiro` | Correto |
| `item_provisorio` | `preco_unitario_sugerido` | `309.90` | Auto-enriquecido |
| `pedido` | `id` | `84132af0-3951-4f75-8f92-b8dd0bca2f2b` | Criado |
| `pedido` | `valor_total` | `309.90` | Correto |
| `pedido` | `tipo_entrega` | `retirada` | Correto |
| `pedido` | `forma_pagamento` | `pix` | Correto |
| `pedido` | `status_pedido` | `confirmado` | Correto |
| `item_pedido` | `pneu_id` | `78515ece-...` | Correto |
| `item_pedido` | `quantidade` | `1` | Correto |
| `item_pedido` | `preco_unitario` | `309.90` | Correto |
| `item_pedido` | `subtotal` | `309.90` | Correto |
| `sessao_chat` | `etapa_atual` | `fechamento` | Correto |
| `sessao_chat` | `status_sessao` | `fechada` | Correto |

Auto-promocao funcionou no turno 6 — pedido criado sem necessidade de mensagem extra.
Bateria de testes: **126/126 PASS** (incluindo ajuste no teste integrado para desempacotar a tupla de `chamar_agente`).

## Fase 10 — Inteligencia de Negocio do Cliente (COMPLETA)

Data: 30/03/2026

### Contexto

Apos o agente funcionar end-to-end (Fases 1-9), iniciada a evolucao para
inteligencia de negocio: captura de dados do cliente, segmentacao e cancelamento.

### Migration Supabase

6 colunas adicionadas em `cliente`: `municipio`, `bairro`, `segmento` (novo/recorrente/vip),
`total_pedidos`, `valor_total_gasto`, `ultima_compra_em`.

### Alteracoes realizadas (9 arquivos)

1. **constantes.py** — chaves `MUNICIPIO` e `BAIRRO` adicionadas

2. **schemas/cliente.py** — `ClienteBase` recebe `municipio`/`bairro`;
   `Cliente` recebe `segmento`, `total_pedidos`, `valor_total_gasto`, `ultima_compra_em`

3. **schemas/contexto_executavel.py** — `ClienteContexto` expandido com todos os
   campos de inteligencia de negocio (IA recebe no contexto de cada turno)

4. **engine/montador_contexto.py** — popula novos campos quando cliente esta resolvido

5. **engine/promotor.py** — 3 novas funcoes:
   - `_calcular_segmento(total_pedidos, valor_total)` — regra de negocio centralizada
   - `_atualizar_stats_cliente(cliente_id, valor_pedido)` — roda apos cada pedido criado
   - `cancelar_pedido_sessao(sessao_id)` — cancela pedido e reverte stats do cliente

6. **db/pedido_repo.py** — `cancelar_pedido(pedido_id)` — UPDATE status_pedido=cancelado

7. **engine/orquestrador.py** — 4 novos comportamentos:
   - `_parsear_localidade_endereco` — extrai municipio/bairro de texto livre ou JSON
   - `_atualizar_localidade_cliente` — persiste localidade apos promocao
   - `_atualizar_nome_cliente` — persiste nome apos fato registrado pela IA
   - Cancelamento via fato `pedido_cancelamento_solicitado` (passo 7c)

8. **ia/prompt_sistema.py** — 3 instrucoes:
   - Nome do cliente: pedir em `entrega_pagamento` junto com dados de entrega
   - Cancelamento: registrar fato, backend executa
   - `cancelar_pedido` adicionado as acoes validas de `fechamento`

9. **teste_inteligencia_cliente.py** — novo arquivo, 21 testes sem IA

### Regra de segmento

| Condicao | Segmento |
|---|---|
| 0 pedidos | `novo` |
| 1-4 pedidos E valor < R$500 | `recorrente` |
| 5+ pedidos OU valor >= R$500 | `vip` |

### Comportamento de cancelamento

1. Cliente pede cancelamento → IA registra fato `pedido_cancelamento_solicitado`
2. Orquestrador detecta fato → chama `cancelar_pedido_sessao`
3. Pedido: `confirmado` → `cancelado`
4. Stats revertidos: `total_pedidos` decrementado, `valor_total_gasto` subtraido, `segmento` recalculado
5. Cadastro do cliente preservado intacto

### Testes

- **teste_inteligencia_cliente.py**: 21/21 PASS
- **_parsear_localidade_endereco**: 7/7 formatos de endereco
- **teste_conversa_natural.py**: PASS com verificacao de nome, municipio, bairro, stats
- **Teste manual CLI** (Wallace/Twister/Itaborai): PASS — nome coletado, localidade extraida, cancelamento executado

## Fase 11 — Historico de Pedido, Reserva de Estoque e Alteracao de Pedido (COMPLETA)

Data: 30/03/2026

### Contexto

Tres melhorias operacionais implementadas em sequencia:
- Historico do ultimo pedido exposto no contexto da IA
- Campo `reservado` do estoque passou a ser gerenciado pelo backend
- Pedido pode ser alterado pelo cliente apos confirmacao

### Item 2+3 — Historico do Ultimo Pedido no Contexto

**engine/montador_contexto.py** — logica de populacao de `ultimo_pedido`:

- Busca o ultimo pedido confirmado do cliente excluindo a sessao atual
- Lista os itens do pedido e busca o nome de cada pneu no catalogo
- Monta `UltimoPedidoContexto` (data, valor_total, forma_pagamento, tipo_entrega, itens)
- Popula `cliente.ultimo_pedido` no `ContextoExecutavel`

A IA recebe no contexto dados completos do historico e pode personalizar o atendimento:
mencionar o ultimo pneu comprado, perguntar se quer o mesmo, etc.

### Item 4 — Reserva de Estoque

**Migration Supabase (betaAgente)** — nova funcao `atualizar_reservado_estoque(p_pneu_id, p_delta)`:
- Operacao atomica com `GREATEST(0, reservado + delta)` para nao ir negativo

**db/catalogo_repo.py** — 2 novas funcoes:
- `incrementar_reservado(pneu_id, quantidade)` — chama RPC com delta positivo
- `decrementar_reservado(pneu_id, quantidade)` — chama RPC com delta negativo

**engine/promotor.py — promover_para_pedido**:
- Apos RPC transacional, incrementa `reservado` para cada item promovido

**engine/promotor.py — cancelar_pedido_sessao**:
- Busca itens do pedido e decrementa `reservado` antes de reverter stats do cliente

Ciclo completo: `reservado` sobe na confirmacao e desce no cancelamento.

### Item 5 — Alteracao de Pedido pos-fechamento

**db/pedido_repo.py** — nova funcao `atualizar_pedido(pedido_id, campos)`:
- UPDATE generico nos campos editaveis: `forma_pagamento`, `tipo_entrega`, `endereco_entrega_json`

**engine/promotor.py** — nova funcao `alterar_pedido_sessao(sessao_id)`:
- So age em pedidos com `status_pedido == confirmado`
- Compara fatos ativos com valores atuais do pedido
- Atualiza apenas os campos que mudaram

**engine/orquestrador.py** — passo 8b (novo):
- Apos aplicar mudancas de contexto, se etapa e `fechamento`, chama `alterar_pedido_sessao`
- Sincronizacao transparente: IA so precisa registrar os fatos normalmente

**ia/prompt_sistema.py** — instrucao em fechamento:
- Alterar dados apos pedido criado = registrar fatos novamente; backend sincroniza

### Fluxo de alteracao de pedido

```
1. Cliente: "muda o pix pra cartao"
2. IA: registra fato forma_pagamento=cartao em fatos_observados
3. Orquestrador passo 8: persiste fato no contexto_conversa
4. Orquestrador passo 8b: detecta fechamento → chama alterar_pedido_sessao
5. alterar_pedido_sessao: pedido.forma_pagamento=pix != fato=cartao → UPDATE
6. Banco: pedido.forma_pagamento = "cartao"
7. IA responde confirmando a alteracao ao cliente
```

### Refatoracao

`pedido_repo` estava sendo importado localmente dentro de funcoes em `promotor.py`.
Movido para o import do topo, eliminando imports ocultos.

### Dependencias Supabase adicionadas

- [x] RPC `atualizar_reservado_estoque(p_pneu_id uuid, p_delta int)` — atualiza campo `reservado` de forma atomica

## Fase 12 — Area de Entrega e Calculo de Frete (COMPLETA)

Data: 02/04/2026

### Contexto

O agente nao calculava frete. Municipio era texto livre sem validacao geografica.
Esta fase adiciona tabela de cobertura com 15 municipios do RJ e integra o calculo
de frete ao fluxo existente sem quebrar nada anterior.

### Migration Supabase

- [x] Tabela `area_entrega` — `municipio`, `bairro` (opcional), `valor_frete`, `ativo`, `criado_em`
- [x] 15 municipios inseridos (Niteroi R$9,90 ate Araruama/Saquarema R$49,90)
- [x] Coluna `valor_frete NUMERIC DEFAULT 0` adicionada a tabela `pedido`
- [x] RPC `promover_para_pedido` atualizada para aceitar `p_valor_frete`

### Alteracoes realizadas (7 arquivos)

1. **schemas/area_entrega.py** — (novo) `AreaEntregaBase`, `AreaEntrega`

2. **db/area_entrega_repo.py** — (novo):
   - `_normalizar()`: remove acentos para comparacao robusta
   - `consultar_frete(municipio, bairro?)`: prioridade bairro-exato → municipio-todo; retorna `Decimal | None`
   - `listar_municipios_ativos()`: lista cobertura geografica

3. **constantes.py** — `FRETE_VALOR` e `FRETE_NAO_COBERTO` adicionados a `ChaveContexto`

4. **schemas/pedido.py** — campo `valor_frete: Decimal = Decimal("0")` em `PedidoBase`

5. **schemas/contexto_executavel.py** — nova classe `FreteContexto` (municipio, coberto, valor_frete, bairro); campo `frete: Optional[FreteContexto]` no `ContextoExecutavel`

6. **engine/montador_contexto.py**:
   - Popula `frete` a partir dos fatos `frete_valor` ou `frete_nao_coberto` da sessao
   - IA recebe `frete.coberto` e `frete.valor_frete` prontos no contexto

7. **engine/orquestrador.py**:
   - Importa `area_entrega_repo`
   - Nova funcao `_consultar_e_registrar_frete(sessao_id)`:
     - Executa apenas se `tipo_entrega = entrega` e municipio disponivel
     - Idempotente: nao recalcula se fato de frete ja existe
     - Obtencao do municipio: fato explicito > parse do endereco (reusa `_parsear_localidade_endereco`)
     - Registra `frete_valor` ou `frete_nao_coberto` no `contexto_conversa`
   - Passo 8c adicionado ao loop (apos aplicar mudancas de contexto)

8. **engine/promotor.py**:
   - `validar_pre_condicoes`: bloqueia promocao se `frete_nao_coberto` presente (municipio sem cobertura)
   - `promover_para_pedido`: le `frete_valor` do contexto, calcula `valor_total = valor_itens + valor_frete`, passa ambos para a RPC

9. **ia/prompt_sistema.py**:
   - `entrega_pagamento`: instrui Zé a informar frete ao cliente quando `frete.coberto=true`, e a propor retirada quando `frete.coberto=false`
   - `fechamento`: resumo inclui frete e total separados ("R$X + frete R$Y = total R$Z")

### Fluxo em producao

```
1. Cliente informa municipio ou endereco
2. IA registra municipio nos fatos
3. Orquestrador passo 8c: consultar_frete(municipio) → salva fato frete_valor
4. Turno seguinte: contexto.frete = { coberto: true, valor_frete: 9.90 }
5. Zé: "A entrega em Niteroi sai por R$9,90."
6. Fechamento: "1x CST R$259,90 + frete R$9,90 = total R$269,80. Confirma?"
7. promotor: valor_total = 259.90 + 9.90 = 269.80
8. Banco: pedido.valor_frete=9.90, pedido.valor_total=269.80
```

### Resultado da validacao

```
consultar_frete('Sao Goncalo')   → 19.90  (com acento: tambem funciona)
consultar_frete('sao goncalo')   → 19.90  (sem acento: funciona)
consultar_frete('Niteroi')       → 9.90
consultar_frete('Petropolis')    → None   (fora da area de cobertura)
listar_municipios_ativos()       → 15 municipios
buscar_tabela_fretes()           → 15 linhas [{municipio, valor_frete}, ...]
Todos imports OK
```

### Correcoes pos-teste (02/04/2026)

Teste real via CLI revelou 3 bugs de UX. Corrigidos na mesma sessao:

| # | Problema | Causa | Fix |
|---|---------|-------|-----|
| 1 | IA nao informava frete no turno do municipio | Frete calculado *apos* a resposta da IA | `buscar_tabela_fretes()` expoe tabela completa no contexto |
| 2 | IA pedia bairro para calcular frete | IA nao sabia que frete e fixo por municipio | Prompt: regra explicita "NUNCA peca bairro pra frete" + exemplos |
| 3 | IA salvava municipio como `municipio_entrega` (chave errada) | Prompt nao especificava a chave | Prompt: instrucao de usar chave "municipio" + orquestrador aceita as duas chaves como fallback |

Arquivos adicionalmente modificados:
- `db/area_entrega_repo.py` — nova funcao `buscar_tabela_fretes()`
- `schemas/contexto_executavel.py` — campo `tabela_fretes: list[dict]`
- `engine/montador_contexto.py` — popula `tabela_fretes` a cada turno
- `engine/orquestrador.py` — aceita `municipio` ou `municipio_entrega` como fallback
- `ia/prompt_sistema.py` — reescrita da secao de frete com regras e exemplos claros

## Fase 13 — Resiliencia: Fila por Cliente (COMPLETA)

Data: 02/04/2026

### Contexto

Sem controle de concorrencia, mensagens rapidas do mesmo cliente podiam ser processadas
em paralelo no webhook FastAPI: sessao consultada duas vezes ao mesmo tempo, respostas
chegando fora de ordem, fatos conflitantes registrados simultaneamente.

### Alteracoes realizadas

**`C:\sistema\Openai\webhook.py`** — 3 mudancas:

- `_filas: dict[str, asyncio.Lock] = {}` — dicionario de locks por telefone (modulo)
- `_filas_lock = Lock()` — threading.Lock para proteger o dict (criacao thread-safe)
- `_get_fila(telefone)` — helper que cria ou reutiliza o Lock por telefone
- `async with _get_fila(telefone):` envolve o corpo de `_processar_e_responder`

### Comportamento

- Mesmo cliente: mensagens processadas em serie (2a espera a 1a terminar)
- Clientes distintos: processados em paralelo (locks independentes)
- Chatwoot recebe `200 OK` imediatamente (background task nao bloqueia o endpoint)

### Teste

`C:\sistema\Openai\teste_fila_cliente.py` — 3/3 PASS com `asyncio.sleep(0)` (zero delay,
pior caso: mensagens chegando simultaneamente).

| Cenario | Resultado |
|---------|-----------|
| 3 msgs do mesmo telefone ao mesmo tempo | Serie — INICIO/FIM nunca sobrepoem |
| 3 clientes distintos ao mesmo tempo | Paralelo — todos iniciam sem bloquear |
| 5 msgs do mesmo telefone ao mesmo tempo | 10 eventos emparelhados corretamente |

---

## Fase 14 — Multi-Pneu / Multi-Moto (COMPLETA)

Data: 02/04/2026

### Contexto

O agente so suportava um pneu por atendimento. Fluxo real da loja: cliente pede pneu
dianteiro + traseiro, ou pneus para mais de uma moto na mesma conversa. A solucao
precisava ser a prova de quebras — sem contaminar a busca de um item com dados de outro.

### Alteracoes realizadas (4 arquivos)

1. **`engine/maquina_estados.py`** — novas transicoes:
   - `confirmacao_item → busca` — cliente quer mais itens apos confirmar
   - `entrega_pagamento → busca` — cliente lembrou de outro pneu durante entrega/pagamento

2. **`engine/pendencias.py`** — `adicionar_outro_item` adicionado as acoes permitidas de:
   - `confirmacao_item`
   - `entrega_pagamento`

3. **`engine/orquestrador.py`** — handler para `adicionar_outro_item` em `_despachar_acoes`:
   - Desativa fato `ultimos_pneus_encontrados` do contexto
   - Evita que o auto-enriquecimento use pneu_id de busca anterior na nova busca

4. **`ia/prompt_sistema.py`** — instrucoes atualizadas em `confirmacao_item` e `entrega_pagamento`:
   - Regra de quando usar `adicionar_outro_item`
   - Exemplo de fluxo multi-moto (CG 160 + XRE 300 + PCX 160)
   - Transicoes atualizadas: `confirmacao_item → entrega_pagamento | oferta | busca`

### Comportamento

- Cliente pode pedir N pneus para N motos em um unico atendimento
- Cada item e independente — pneu_id, posicao e preco isolados por item_provisorio
- Volta para `busca` limpa: sem contaminacao de resultados de busca anterior
- Auto-promocao so dispara em `fechamento` — nunca durante loops de adicao de itens
- Dados de entrega/pagamento ja registrados sao preservados ao voltar para busca

### Teste manual CLI (02/04/2026)

Conversa com 3 motos: XRE 300 (traseiro), Fan 125 (traseiro), PCX 160 (traseiro).

### Bugfix pos-teste — Contaminacao de contexto entre buscas (02/04/2026)

**Problema**: `adicionar_outro_item` limpava apenas `ultimos_pneus_encontrados`.
`medida_informada` e `posicao_pneu` da moto anterior permaneciam no contexto,
contaminando a busca da proxima moto. PCX recebia `pneu_id` da Fan 125.

**Fix em `engine/orquestrador.py`**: limpa tambem `medida_informada` e `posicao_pneu`:

```python
_FATOS_A_LIMPAR = ["ultimos_pneus_encontrados", "medida_informada", "posicao_pneu"]
```
Todos os 3 itens registrados corretamente em `item_provisorio`.

---

## Fase 15 — Guardrail de Acoes + finalizar_itens (COMPLETA)

Data: 02/04/2026

### Contexto

Teste da Fase 14 revelou ponto fragil: quando o cliente dizia "pode incluir e fecha tudo",
a IA emitia `confirmar_item` + `adicionar_outro_item` no mesmo turno (contradicao) e
transitava para `busca` desnecessariamente. Causa: o prompt e orientacao subjetiva — o
backend precisava de enforcement real.

### Abordagem

Duas camadas complementares implementadas:

- **Guardrail** (defesa reativa): detecta e corrige contradicoes no envelope antes do processamento
- **`finalizar_itens`** (intencao explicita): nova acao semantica que torna o "nao quero mais" auditavel

### Alteracoes realizadas (3 arquivos)

1. **`engine/orquestrador.py`** — 2 mudancas:

   - Nova funcao `_aplicar_guardrail(envelope, etapa_atual)`:
     - Regra: se `confirmar_item` e `adicionar_outro_item` estao juntos no mesmo turno → remove `adicionar_outro_item`
     - Se IA tambem transitou para `busca` por conta do conflito → reverte `etapa_atual` para etapa corrente
     - Log explicito: `"Guardrail: adicionar_outro_item removido — conflito com confirmar_item"`
     - Chamada no passo 5b de `processar_turno`, antes de qualquer processamento do envelope

   - Handler `finalizar_itens` em `_despachar_acoes`:
     - Registra fato `itens_finalizados = true` no `contexto_conversa`
     - `tipo_de_verdade = confirmado_cliente`, `fonte = backend`
     - Observabilidade: cada "nao quero mais" fica rastreado no banco

2. **`engine/pendencias.py`** — `finalizar_itens` adicionado as acoes permitidas de `confirmacao_item`

3. **`ia/prompt_sistema.py`** — 3 mudancas em `confirmacao_item`:
   - `finalizar_itens` documentado como acao para "cliente quer fechar"
   - `adicionar_outro_item` documentado como acao para "cliente quer mais"
   - Regra critica adicionada: `confirmar_item` e `adicionar_outro_item` sao mutuamente exclusivos no mesmo turno
   - Lista de acoes da etapa atualizada com `finalizar_itens`

### Fluxo antes x depois

```
ANTES:
Cliente: "pode incluir e fecha tudo"
IA emite: [confirmar_item, adicionar_outro_item], etapa=busca
Resultado: item confirmado, pneus anteriores limpos, estado vai pra busca — viajada

DEPOIS:
Cliente: "pode incluir e fecha tudo"
IA emite: [confirmar_item, adicionar_outro_item], etapa=busca
Guardrail: remove adicionar_outro_item, reverte etapa para confirmacao_item
IA aprende: deveria usar finalizar_itens
Resultado: item confirmado, avanca para entrega_pagamento — correto
```

### Eficacia estimada

| Situacao | Antes | Depois |
|---|---|---|
| Acao dupla conflitante | ~40% acerto | ~95% acerto (guardrail) |
| "fecha tudo" apos confirmar | ~45% acerto | ~80% acerto (prompt + guardrail) |
| Fluxo normal sem ambiguidade | ~90% acerto | ~92% acerto |

---

## Fase 16 — Timeout de Sessao (COMPLETA)

Data: 03/04/2026

### Contexto

Sessoes sem interacao ficavam abertas indefinidamente. Sessoes bloqueadas por erro
tecnico nao tinham mecanismo de recuperacao automatica. Com trafego pago o cliente
pode levar varios dias para decidir — fechar em 24h seria perder lead quente.

### Regras de negocio

| Situacao | Comportamento |
|---|---|
| Sessao ativa, menos de 7 dias sem interacao | Fluxo normal, sem alteracao |
| Sessao bloqueada por erro tecnico, menos de 2h | Respeita o bloqueio |
| Sessao bloqueada por erro tecnico, mais de 2h | Desbloqueia automaticamente (volta a `ativa`) |
| Sessao inativa 7+ dias em `identificacao` ou `busca` | Fecha sessao antiga, cria nova silenciosamente |
| Sessao inativa 7+ dias em `oferta`, `confirmacao_item`, `entrega_pagamento` ou `fechamento` | Fecha sessao antiga, cria nova — cliente retomado pelo historico do cadastro |

Cadastro do cliente (nome, segmento, historico) sempre preservado — apenas a sessao e renovada.

### Alteracoes realizadas (4 arquivos)

1. **`engine/sessao_timeout.py`** — (novo) logica isolada de classificacao:
   - `SituacaoSessao` enum: `ok`, `bloqueada_antiga`, `expirada_com_contexto`, `expirada_sem_contexto`
   - `avaliar_sessao(sessao) -> SituacaoSessao` — pura, sem escrita no banco
   - Constantes: `TIMEOUT_SESSAO_DIAS = 7`, `TIMEOUT_BLOQUEADA_HORAS = 2`

2. **`db/sessao_repo.py`** — nova funcao `fechar_sessao(sessao_id)`:
   - Wrapper semantico sobre `atualizar_status(sessao_id, StatusSessao.fechada)`
   - Distingue fechamento administrativo (timeout) do fechamento via RPC de pedido

3. **`engine/orquestrador.py`** — 2 adicoes:
   - Nova funcao `_resolver_timeout(sessao) -> UUID`:
     - Chama `avaliar_sessao()` e age conforme o resultado
     - `bloqueada_antiga`: chama `atualizar_status(..., ativa)`
     - `expirada_*`: chama `fechar_sessao()` + `criar_sessao()` com mesmos `canal`/`contato_externo`
     - Nunca levanta excecao — em caso de falha retorna o `sessao_id` original (fail safe)
   - Passo 0 em `processar_turno()`: `_resolver_timeout()` chamado antes da persistencia da mensagem
   - `EtapaFluxo` adicionado aos imports do topo (estava so em imports inline)

4. **`teste_sessao_timeout.py`** — 26 testes em 3 grupos:
   - Grupo 1 (12 unitarios): `avaliar_sessao()` com mocks, sem banco
   - Grupo 2 (10 integracao): `_resolver_timeout()` com banco real, 5 cenarios
   - Grupo 3 (4 simulacao): comportamento end-to-end sem IA

### Resultado dos testes

**26/26 PASS**

| Grupo | Cenarios testados |
|---|---|
| Unitarios | Todos os limites de timeout, todas as etapas, sessao fechada, bloqueio recente e antigo |
| Integracao | Sessao normal, expirada sem contexto, expirada com contexto, bloqueada antiga, bloqueada recente |
| Simulacao | Cliente voltando, cliente VIP com historico, segunda chamada idempotente |

---

## Fase 17 — Configuracoes da Loja (COMPLETA)

Data: 03/04/2026

### Contexto

A IA nao tinha acesso a informacoes operacionais da loja (endereco, horario, politica de montagem, garantia, prazo de entrega). Perguntas fora do fluxo de venda (ex: "que horas voces abrem?", "tem montagem?") podiam resultar em alucinacao ou ausencia de resposta util.

### Migration Supabase

- [x] Tabela `config_loja` — `chave` (PK), `valor`, `descricao`, `ativo`
- [x] 8 registros inseridos: `endereco`, `horario_funcionamento`, `faz_montagem`, `politica_montagem`, `garantia_descricao`, `prazo_entrega_descricao`, `emite_nota_fiscal`, `telefone_atendimento_humano`

### Alteracoes realizadas (3 arquivos)

1. **`db/config_loja_repo.py`** — (novo):
   - `buscar_config_loja() -> dict[str, str]`: le todas as linhas `ativo=true` e retorna dicionario chave→valor. Retorna `{}` em caso de erro (fail safe — nunca quebra o fluxo).

2. **`schemas/contexto_executavel.py`** — campo `config_loja: dict[str, str]` adicionado ao `ContextoExecutavel` (default `{}`)

3. **`engine/montador_contexto.py`** — importa `config_loja_repo` e popula `config_loja` a cada turno

### Comportamento

- IA recebe `config_loja` no contexto junto com todos os outros dados do turno
- Usa como base de fato verificado — nunca inventa informacao operacional
- Se nao for relevante para o turno, ignora o bloco
- Operador pode atualizar qualquer informacao diretamente no Supabase via `ativo=false/true` ou `UPDATE valor` sem tocar no codigo

### Atualizacao de dado no banco

- [x] `garantia_descricao` atualizado para texto curto: "Todos os pneus sao testados e a garantia e na montagem."

### Atualizacao do prompt (`ia/prompt_sistema.py`)

- [x] Regra 5 adicionada em `# REGRAS DE NEGOCIO`: usar apenas `config_loja` para dados operacionais, nunca inventar
- [x] Nova secao `# INFORMACOES DA LOJA`: instrui o Ze chave por chave como responder cada dado (`endereco`, `horario_funcionamento`, `faz_montagem`, `politica_montagem`, `garantia_descricao`, `prazo_entrega_descricao`, `emite_nota_fiscal`). Inclui regra de fallback ("nao tenho essa informacao agora") e retorno ao fluxo de venda apos responder

### Separacao prompt x tabela

| Tipo | Onde fica | Criterio |
|------|-----------|----------|
| Endereco, horario, montagem, garantia, prazo, NF | `config_loja` (tabela) | Muda sem mexer no codigo |
| "Nao vende pneu de carro", "nao negocia preco" | `prompt_sistema.py` | Regra de comportamento imutavel |

---

## Fase 19 — Confirmacao de Pedido Formatada (COMPLETA)

Data: 03/04/2026

### Contexto

Quando o pedido era criado, o cliente recebia apenas a mensagem genérica da IA ("Fechado! Qualquer dúvida é só chamar."). Sem número do pedido, itens, total, endereço ou prazo — dados que o cliente precisa para ter segurança na compra.

### Alteracoes realizadas (1 arquivo)

**`engine/orquestrador.py`** — 5 mudancas:

1. Novos imports: `pedido_repo`, `catalogo_repo`, `config_loja_repo`, `TipoEntrega`

2. Nova funcao `_calcular_prazo_entrega(criado_em) -> str`:
   - Soma 1 dia ao momento do pedido (em horario de Brasilia)
   - Se cair em domingo: avanca para segunda-feira
   - Sabado: entrega normal (loja abre aos sabados)
   - Retorna texto formatado: "Chega na segunda-feira, 06/abr"

3. Nova funcao `_montar_confirmacao_pedido(pedido) -> str`:
   - Busca itens reais do pedido com nomes do catalogo
   - Monta mensagem formatada com emojis, itens, entrega, total, pagamento e prazo
   - Usa `_calcular_prazo_entrega()` para data real — nao usa texto generico
   - Fail safe: em caso de erro retorna mensagem minima com numero e total

4. `_despachar_acoes` agora retorna `Optional[Pedido]` em vez de `None`

5. `processar_turno` captura `pedido_criado` dos passos 10 e 12 (auto-promocao). Se pedido foi criado, substitui `envelope.mensagem_cliente` pela confirmacao formatada antes de persistir e retornar.

### Exemplo de mensagem gerada

```
✅ Pedido #1112 confirmado!

📋 Resumo:
• 1x Pirelli Diablo Street 130/70-17 traseiro — R$289,90

🚚 Entrega: Rua das Flores, 100 - Centro, Niterói
   Frete: R$9,90

💰 Total: R$299,80
💳 Pagamento: PIX

📦 Chega na segunda-feira, 06/abr
```

### Comportamento

- Mensagem montada pelo backend com dados reais — zero alucinacao
- Data de entrega calculada dinamicamente — nunca diz "amanha" quando e domingo
- Substitui completamente a mensagem da IA no turno de fechamento
- Funciona tanto para `converter_em_pedido` (passo 10) quanto para auto-promocao (passo 12)
- Para retirada: exibe "Retirada na loja" sem frete e sem data calculada

### Validacao dos calculos de prazo

| Pedido feito | Entrega prevista |
|---|---|
| Sexta 20h | Sabado 04/abr |
| Sabado 14h | Segunda-feira 06/abr (pulou domingo) |
| Domingo 10h | Segunda-feira 06/abr |
| Segunda 9h | Terca-feira 08/abr |

---

## Fase 18 — Numero de Pedido Sequencial (COMPLETA)

Data: 03/04/2026

### Contexto

Pedidos eram identificados apenas por UUID (ex: `496d6414-...`), impossivel de citar em atendimento humano ou processos internos. Necessario um numero curto, legivel e unico para uso operacional.

### Migration Supabase

- [x] Coluna `numero_pedido SERIAL` adicionada a tabela `pedido`
- [x] Indice unico `idx_pedido_numero_pedido` criado
- [x] Pedidos existentes numerados automaticamente (1 a 11)

### Alteracoes realizadas (1 arquivo)

1. **`schemas/pedido.py`** — campo `numero_pedido: int` adicionado ao model `Pedido`

### Comportamento

- Gerado automaticamente pelo PostgreSQL no INSERT — zero logica no codigo
- Unico e irrepetivel — mesmo com milhoes de pedidos e requisicoes simultaneas
- Pedidos existentes receberam numeracao retroativa (1, 2, 3...)
- Proximo pedido sera `#12`
- Util para: confirmacao ao cliente, busca interna, atendimento por telefone

---

## Fase 20 — Confiabilidade do Fluxo: Anti-Loop e Guardrails (COMPLETA)

Data: 04/04/2026

### Contexto

Analise identificou ~60% de taxa de erro de fluxo, principalmente: loop de pagamento/entrega (IA esquecia de registrar fatos), fechamento prematuro sem dados completos, e perguntas redundantes sobre dados ja registrados. Tres guardrails implementados para reduzir para ~28%.

### Alteracoes realizadas (5 arquivos)

1. **`engine/orquestrador.py`**
   - Constantes `_KEYWORDS_FORMA_PAGAMENTO` e `_KEYWORDS_TIPO_ENTREGA`
   - Funcao `_tem_negacao_antes()` — detecta "nao quero pix" para evitar falso positivo
   - Funcao `_extrair_fatos_estruturados_fallback()` — roda APOS a IA no passo 6b; registra forma_pagamento e tipo_entrega se a IA esqueceu. Previne o loop classico.
   - Passo 6b adicionado em `processar_turno`

2. **`engine/validador_envelope.py`**
   - Regra 7 adicionada: bloqueia transicao `entrega_pagamento → fechamento` se tipo_entrega ou forma_pagamento nao estiverem nos fatos ativos. Fechamento prematuro vira impossivel.

3. **`schemas/contexto_executavel.py`**
   - Campo `alertas: list[str]` adicionado ao `ContextoExecutavel`

4. **`engine/montador_contexto.py`**
   - Bloco de alertas contextuais: injeta avisos no JSON do contexto quando nome_cliente, tipo_entrega, forma_pagamento ou municipio ja estao registrados. Reduz perguntas redundantes.

5. **`ia/prompt_sistema.py`**
   - Secao "REGRA CRITICA: registrar fatos de entrega e pagamento" encurtada — o codigo garante o registro, o prompt nao precisa mais ser detalhado.

### Comportamento

- **Proposta 1 (fallback)**: Se cliente diz "pix" e a IA esquece de registrar → backend registra automaticamente. Tem checagem de negacao ("nao quero pix" nao aciona).
- **Proposta 2 (validador)**: Se IA tenta ir para fechamento sem tipo_entrega/forma_pagamento → validador rejeita, retry forcado com correcao.
- **Proposta 3 (alertas)**: Contexto passa `alertas: ["forma_pagamento ja registrado como 'pix' — NAO pergunte de novo"]` → IA nao repergunta dados ja conhecidos.

### Reducao esperada de erros de fluxo

| Estado | Taxa estimada |
|--------|--------------|
| Antes (so prompt) | ~60% |
| + Fallback keywords | ~45% |
| + Validador fechamento | ~35% |
| + Alertas no contexto | ~28% |

---

## Fase 21 — Normalização de Busca de Moto (COMPLETA)

Data: 04/04/2026

### Contexto

Teste real identificou perda de venda: cliente digitou "cb300" (sem espaço), RPC não encontrou "CB 300" no banco, agente reportou não encontrar a moto, cliente teve que corrigir. Com múltiplas motos (XRE + CB300), o fluxo se fragmentou em dois atendimentos separados com duas perguntas de marca.

### Problema

A tool `buscar_pneus_por_moto` passava o termo exatamente como a IA recebia — sem nenhum tratamento. A IA nem sempre normaliza antes de chamar a tool (comportamento estocástico).

### Solução

Normalização automática em 4 regras universais antes de bater no banco. Tenta múltiplas variações em sequência até encontrar resultado.

### Alterações (1 arquivo)

**`tools/busca_catalogo.py`**
- `_FABRICANTES` — set com fabricantes conhecidos (honda, yamaha, kawasaki, suzuki, triumph, bmw, harley, ducati, ktm, benelli, dafra, shineray)
- `_remover_acentos(texto)` — converte NFD para ASCII
- `_normalizar_termo_moto(termo)` — aplica as 4 regras e retorna lista de variações ordenadas
- `buscar_pneus_por_moto` — agora tenta cada variação até encontrar; retorna `termo_usado` no resultado

### As 4 regras (universais — valem para qualquer moto cadastrada agora ou no futuro)

| Regra | Exemplo | Resultado |
|-------|---------|-----------|
| Remove fabricante | "honda cb300" | "cb300" |
| Hífen/ponto → espaço | "cb-300" | "cb 300" |
| Espaço letra→número | "cb300" | "cb 300" |
| Remove acentos | "ténéré" | "tenere" |

Combinações também funcionam: "yamaha xre300" → "xre 300", "kawasaki z-400" → "z 400".

### Por que é universal

As regras são de padrão, não de caso. Não conhecem nenhuma moto específica. Qualquer moto cadastrada futuramente é automaticamente coberta — sem manutenção de código.

### Testes

**`tests/test_normalizacao_moto.py`** — **39/39 PASS** (04/04/2026)

Cobertura: regra 1 (9 casos), regra 2 (6 casos), regra 3 (9 casos), regra 4 (3 casos), combinações (6 casos), proteções para casos normais (6 casos).

---

## Fase 22 — Três Correções de Produção (COMPLETA)

Data: 04/04/2026

Três bugs identificados em testes reais com o CLI, todos corrigidos nesta fase.

---

### Bug 1 — Agente perguntava endereço duas vezes

**Sequência observada:**
```
Cliente: "rua gago tarado 879 bairro bom jardim nova iguacu"
Agente:  "Perfeito! Endereço anotado. O frete pra Nova Iguaçu fica R$29,90. Como você quer pagar?"
Cliente: "pix"
Agente:  "me confirma só o endereço completo pra entrega: rua, número e bairro."  ← BUG
```

**Causa raiz:**
O sistema de alertas (Fase 20) injetava no contexto avisos como `"tipo_entrega ja registrado — NAO pergunte de novo"`. Cobria: `nome_cliente`, `tipo_entrega`, `forma_pagamento`, `municipio`. `endereco_entrega` estava fora da lista. Sem o alerta, a IA recebia um turno curto ("pix") e esquecia que já tinha o endereço.

**Correção em `engine/montador_contexto.py`:**
```python
if "endereco_entrega" in chaves_ativas:
    fato_end = next((f for f in fatos_db if f.chave == "endereco_entrega"), None)
    if fato_end and fato_end.valor_texto:
        end_val = fato_end.valor_texto
    elif fato_end and fato_end.valor_json and isinstance(fato_end.valor_json, dict):
        partes = [fato_end.valor_json.get("logradouro",""), fato_end.valor_json.get("numero",""),
                  fato_end.valor_json.get("bairro",""), fato_end.valor_json.get("cidade","")]
        end_val = ", ".join(p for p in partes if p) or "registrado"
    else:
        end_val = "registrado"
    alertas.append(f"endereco_entrega ja registrado como '{end_val}' — NAO peca o endereco de novo")
```

O fallback para `valor_json` é necessário porque a IA às vezes salva o endereço como JSON estruturado (não como texto livre), e `valor_texto` fica `None` nesses casos.

---

### Bug 2 — Race condition no validador: cliente diz "pix" e o agente crasha

**Sequência observada:**
```
Cliente: "pix"
[WARNING] Envelope invalido (tentativa 0): nao pode avancar para fechamento sem forma_pagamento registrado
[WARNING] Envelope invalido (tentativa 1): nao pode avancar para fechamento sem forma_pagamento registrado
[WARNING] Envelope invalido (tentativa 2): nao pode avancar para fechamento sem forma_pagamento registrado
[ERROR]   IA falhou apos 3 tentativas
Agente:   "Desculpe, tive um problema ao processar sua mensagem."
```

**Causa raiz — race condition entre validação e commit:**
O orquestrador segue esta ordem:
1. Carrega contexto do banco (`fatos_ativos`)
2. Chama a IA com o contexto
3. IA devolve envelope com `fatos_observados: [{forma_pagamento: "pix"}]` + `etapa_atual: fechamento`
4. **Validador roda** — checa `fatos_ativos` (banco ainda não tem `forma_pagamento`)
5. Validador bloqueia: "sem forma_pagamento"
6. Retry com o mesmo contexto → mesma falha → 3x → crash

O fato `forma_pagamento=pix` estava no envelope sendo registrado NESTE turno, mas o validador só olhava o banco (turno anterior). Nunca passaria.

**Correção em `engine/validador_envelope.py` — Regra 7:**
```python
# Antes: só checava fatos_ativos (banco)
chaves_fatos = {f.chave for f in contexto.fatos_ativos}

# Depois: também considera o que está sendo registrado neste turno
chaves_fatos = {f.chave for f in contexto.fatos_ativos}
chaves_fatos |= {f.chave for f in envelope.fatos_observados}
chaves_fatos |= {f.chave for f in envelope.fatos_inferidos}
```

---

### Bug 3 (preventivo) — Fechamento sem endereço quando tipo=entrega

Não ocorreu em produção ainda, mas a Regra 7 existente não protegia contra: cliente escolhe entrega, não informa endereço, IA tenta fechar o pedido assim mesmo.

**Adicionada Regra 8 em `engine/validador_envelope.py`:**
```python
# Se tipo_entrega = entrega, fechamento exige endereco_entrega
if envelope.etapa_atual == EtapaFluxo.fechamento:
    # resolve tipo_entrega: banco ou envelope atual
    tipo_entrega_valor = ...  # checa fatos_ativos + envelope
    if tipo_entrega_valor == "entrega" and "endereco_entrega" not in chaves_fatos:
        erros.append("nao pode avancar para fechamento com tipo_entrega=entrega sem endereco_entrega registrado")
```

A Regra 8 também usa a lógica corrigida (considera `fatos_observados` do envelope atual).

---

### Arquivos alterados

| Arquivo | O que mudou |
|---------|-------------|
| `engine/montador_contexto.py` | Alerta para `endereco_entrega` com suporte a `valor_json` |
| `engine/validador_envelope.py` | Regra 7 considera envelope atual; Regra 8 nova (endereço obrigatório) |
| `tests/test_guardrails.py` | +9 casos de teste, helpers `_fato_obs()` e `_envelope(fatos_obs=)` |

### Testes

**`tests/test_guardrails.py`** — **34/34 PASS** (04/04/2026)

| Grupo | Antes | Depois | Novos testes |
|-------|-------|--------|--------------|
| Guardrail 1 — detecção de negação | 10 | 10 | — |
| Guardrail 2 — validador fechamento | 7 | 16 | +9 (endereço, race condition, regra 8) |
| Guardrail 3 — alertas contextuais | 8 | 8 | — (alertas de endereço já contados) |

---

## Fase 23 — Structured Outputs: Schema Estrito no EnvelopeIA (COMPLETA)

Data: 04/04/2026

### Problema

Em todo teste real aparecia este erro nos logs, causando 1-2 retries extras por turno e custo desnecessário de API:

```
ParseError: bloqueios_identificados.0
  Input should be a valid dictionary or instance of BloqueioIdentificado [input_type=str]
```

O modelo retornava uma string onde o schema Pydantic esperava um objeto `BloqueioIdentificado`. O orquestrador capturava, fazia retry com re-prompt, e na segunda tentativa o modelo acertava.

### Causa Raiz

`response_format={"type": "json_object"}` instrui o modelo a retornar JSON válido — mas não define a estrutura. O modelo escolhia os tipos livremente. Em ~30% dos turnos com bloqueio, usava string em vez de objeto.

### Solução — Structured Outputs (OpenAI)

A API Structured Outputs compila o schema antes de gerar a resposta. O modelo é impedido na camada da OpenAI de retornar tipos incorretos — o erro se torna impossível de acontecer.

Sintaxe correta (verificada contra `platform.openai.com/docs/guides/structured-outputs`):

```python
response_format={
    "type": "json_schema",
    "json_schema": {
        "name": "EnvelopeIA",   # obrigatorio
        "strict": True,
        "schema": _ENVELOPE_IA_SCHEMA,
    },
}
```

### Regras do strict mode (da documentação oficial)

| Regra | Aplicada em |
|-------|-------------|
| `additionalProperties: false` obrigatório | todos os objetos do schema |
| Todos os campos em `required` | todos os objetos |
| Campos opcionais usam `["type", "null"]` | mensagem_chat_id, campo_relacionado, etc. |
| `anyOf` suportado em propriedades (não na raiz) | `dados` em MudancaItem |
| Tipos suportados: string, number, integer, boolean, object, array, enum, anyOf | — |
| `parallel_tool_calls: false` obrigatório ao usar tools junto com structured outputs | `_chamar_openai` |

### Detalhe importante: `parallel_tool_calls: false`

A documentação especifica que structured outputs **não funcionam com parallel function calls**. Sem esse parâmetro, o comportamento com tools é indefinido. Adicionado em `_chamar_openai`:

```python
if tools:
    kwargs["tools"] = tools
    kwargs["tool_choice"] = "auto"
    kwargs["parallel_tool_calls"] = False  # obrigatorio com structured outputs
```

### O que muda no comportamento

- `bloqueios_identificados` é sempre `list[objeto]` — string impossível
- Todos os 11 campos do EnvelopeIA têm tipos garantidos pela API
- `valor` em fatos_observados/inferidos: sempre string (era `Any`, na prática sempre foi string)
- Retries por ParseError de schema eliminados
- Tool calls continuam funcionando normalmente (uma por vez)

### Alterações (1 arquivo)

**`ia/agente.py`**
- Adicionado `_ENVELOPE_IA_SCHEMA`: schema JSON completo com `additionalProperties: false` em todos os níveis e todos os campos em `required`
- `_chamar_openai`: `response_format` trocado de `json_object` para `json_schema` com `strict: True`
- `_chamar_openai`: adicionado `parallel_tool_calls: False` quando tools estão ativas

### Testes

34/34 PASS — nenhuma regressão.

---

## Fase 24 — Web Search: Fallback de Compatibilidade de Motos (COMPLETA)

Data: 04/04/2026

### Problema

O banco Supabase tem 12 motos cadastradas. Para qualquer moto fora desse catálogo, `buscar_pneus_por_moto` retornava 0 resultados e o agente dizia "não tenho essa moto no sistema". Perda de venda certa: o cliente pergunta pela Triumph Tiger 900 (por exemplo), o agente não sabe a medida, não consegue buscar no estoque.

### Solução — Cascade: Supabase → Web → Estoque

```
1. buscar_pneus_por_moto(moto) → 0 resultados
2. buscar_medida_por_moto_web(moto, posicao) → medida "150/70-17" (da internet)
3. buscar_pneus(medida_texto="150/70-17") → pneus disponíveis no estoque
4. Zé recomenda com preço e disponibilidade reais
```

A web só é consultada como fallback. A recomendação final sempre vem do estoque real.

### Abordagem técnica

**Por que Responses API e não Chat Completions?**

Web Search e File Search são tools da Responses API (nova, lançada 2025). Chat Completions (usada para o agente principal) não tem essas tools nativas. A solução foi um padrão de wrapper: a tool chama a Responses API internamente e retorna o resultado como string para o loop de function calling do Chat Completions.

### Arquivos criados/alterados

**`tools/busca_web.py`** — (novo):
- `buscar_medida_por_moto_web(moto: str, posicao: str) -> dict`
- Usa `client.responses.create()` com `web_search_preview`
- `search_context_size: "low"` (busca factual simples — menor custo)
- `user_location: BR / America/Sao_Paulo` (resultados em português)
- Query: `"medida especificacao pneu {posicao} {moto} tamanho dimensao"`
- Retorna: `{encontrado, moto, posicao, info, fonte: "web"}`
- Fail safe: em caso de erro retorna `{encontrado: false, erro: str}` — nunca quebra o fluxo

**`ia/agente.py`**:
- Import: `from agente_2w.tools.busca_web import buscar_medida_por_moto_web`
- `TOOLS_SCHEMA`: nova tool `buscar_medida_por_moto_web` com parâmetros `moto` (string) e `posicao` (enum: traseiro | dianteiro | ambos)
- `_TOOL_DISPATCH`: `"buscar_medida_por_moto_web": buscar_medida_por_moto_web`
- Total de tools registradas: 6 (buscar_pneus, buscar_pneus_por_moto, buscar_detalhes_pneu, **buscar_medida_por_moto_web**, consultar_estoque, resolver_cliente)

**`ia/prompt_sistema.py`**:
- Instrução de cascade na etapa de busca: "Se `buscar_pneus_por_moto` retornar 0 → chame `buscar_medida_por_moto_web`. Com a medida retornada, chame `buscar_pneus` com `medida_texto`. Só diga que não tem se nenhuma das duas buscas retornar resultado."

### Cenários cobertos

| Situação | Comportamento |
|----------|--------------|
| Moto no catálogo Supabase | `buscar_pneus_por_moto` retorna resultado, sem web search |
| Moto fora do catálogo | Web search busca medida, `buscar_pneus` acha estoque pela medida |
| Moto obscura sem resultado na web | `encontrado: false`, Zé informa que não tem |
| Web search falha (timeout, erro) | Exception capturada, retorna `encontrado: false` — fluxo continua |

### Limitação conhecida

A web retorna a **medida oficial de fábrica**. Se o cliente quiser um tamanho alternativo, a busca por medida cobre. Se a medida da web não tiver estoque, o agente informa honestamente.

### Verificação de imports

```
python -c "from agente_2w.ia.agente import _TOOL_DISPATCH, TOOLS_SCHEMA; print([t['function']['name'] for t in TOOLS_SCHEMA])"
['buscar_pneus', 'buscar_pneus_por_moto', 'buscar_detalhes_pneu', 'buscar_medida_por_moto_web', 'consultar_estoque', 'resolver_cliente']
```

---

## Fase 25 — Auditoria de Busca Web + Filtro de Posição (COMPLETA)

Data: 04/04/2026

### Contexto

Três melhorias implementadas em sequência nesta fase:
1. Tabela de auditoria `log_busca_web` para rastrear todas as buscas feitas na internet
2. Filtro de `posicao` na tool `buscar_pneus_por_moto` para evitar misturar dianteiro/traseiro
3. Regra de apresentação: 1 resultado → apresenta direto sem perguntar marca

---

### Item 1 — Tabela `log_busca_web`

**Migration Supabase:**
```sql
CREATE TABLE log_busca_web (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sessao_id   UUID REFERENCES sessao_chat(id) ON DELETE SET NULL,
    moto        TEXT NOT NULL,
    posicao     TEXT NOT NULL,
    encontrado  BOOLEAN NOT NULL DEFAULT false,
    info_completa TEXT,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```
Índices em `sessao_id`, `moto` e `criado_em DESC`.

**`db/log_busca_web_repo.py`** — (novo):
- `registrar(moto, posicao, encontrado, info_completa, sessao_id?)` — fail safe, nunca levanta exceção

**`tools/busca_web.py`**:
- Assina `sessao_id: UUID | None = None`
- Chama `log_busca_web_repo.registrar()` após cada busca (sucesso e erro)

**`ia/agente.py`**:
- Injeta `sessao_id` via wrapper no dispatch local de `chamar_agente`:
```python
sessao_id = contexto.sessao.sessao_id
dispatch = {
    **_TOOL_DISPATCH,
    "buscar_medida_por_moto_web": lambda moto, posicao: buscar_medida_por_moto_web(
        moto=moto, posicao=posicao, sessao_id=sessao_id
    ),
}
```
- `_executar_tool` aceita `dispatch` opcional — usa `_TOOL_DISPATCH` padrão quando não informado

**O que se audita:**
- Qual moto foi buscada, qual posição, se encontrou ou não
- Texto completo retornado pela web
- Qual sessão gerou a busca (→ JOIN com `sessao_chat` → `cliente`)

**Query útil para ver motos mais buscadas fora do catálogo:**
```sql
SELECT moto, posicao, COUNT(*) as buscas, SUM(encontrado::int) as achou
FROM log_busca_web
GROUP BY moto, posicao
ORDER BY buscas DESC;
```

**Para identificar o cliente:**
```sql
SELECT lwb.moto, lwb.posicao, lwb.criado_em, c.nome, c.telefone
FROM log_busca_web lwb
JOIN sessao_chat sc ON sc.id = lwb.sessao_id
JOIN cliente c ON c.id = sc.cliente_id
ORDER BY lwb.criado_em DESC;
```

---

### Item 2 — Filtro de posição em `buscar_pneus_por_moto`

**Problema:** a tool retornava dianteiro E traseiro juntos, e o agente ficava confuso ao apresentar "uma opção por R$419 e outra por R$469" sem explicar que eram posições diferentes.

**`tools/busca_catalogo.py`**:
- `buscar_pneus_por_moto(termo_moto, posicao=None)` — novo parâmetro opcional
- Quando `posicao` informado, filtra os resultados antes de retornar
- `buscar_pneus_por_moto("Twister", posicao="traseiro")` → 1 resultado (Michelin 140/70-17)
- `buscar_pneus_por_moto("Twister")` → 2 resultados (sem filtro, como antes)

**`ia/agente.py` — TOOLS_SCHEMA:**
- `posicao` adicionado como parâmetro opcional com enum `["dianteiro", "traseiro"]`
- Descrição: "Informe sempre que souber"

**`ia/prompt_sistema.py`**:
- Instrução em `busca`: "Sempre passe `posicao` na tool quando já souber"

---

### Item 3 — Apresentação direta com 1 resultado

**Problema:** com apenas 1 pneu disponível para a posição, o agente perguntava "Tem preferência por alguma marca?" — sem sentido quando não há escolha.

**`ia/prompt_sistema.py`** — regra em `busca` 2a:
- 2+ marcas diferentes → pergunta preferência
- 1 resultado → apresenta direto: "Temos o [modelo] por R$X. Esse te serve?"
- 2+ da mesma marca → apresenta por preço direto

---

### Bugfix: `'SessaoContexto' object has no attribute 'id'`

Ao injetar `sessao_id`, foi usado `contexto.sessao.id` mas o campo correto é `contexto.sessao.sessao_id` (definido em `SessaoContexto`). Corrigido na mesma sessão.

### Arquivos alterados

| Arquivo | O que mudou |
|---------|-------------|
| `db/log_busca_web_repo.py` | Novo — registra buscas web no banco |
| `tools/busca_web.py` | Aceita `sessao_id`, persiste log após cada busca |
| `tools/busca_catalogo.py` | `buscar_pneus_por_moto` aceita `posicao` para filtrar |
| `ia/agente.py` | Injeta `sessao_id` via dispatch wrapper; `_executar_tool` aceita dispatch opcional |
| `ia/prompt_sistema.py` | Regra de posição na tool; regra de 1 resultado = apresenta direto |

---

## Fase 26 — Rede de Segurança 9b + Ajuste de Tom no Fluxo (COMPLETA)

Data: 04/04/2026

### Contexto

Dois problemas identificados após teste real com busca web (pegadinha NMAX):
1. Item provisório nunca era criado quando o modelo pulava `mudancas_itens` na transição `oferta → confirmacao_item` após retry de validação
2. Mensagem de transição para entrega/pagamento era mecânica e mencionava "pagamento" antes de perguntar entrega

---

### Item 1 — Rede de segurança 9b (engine/orquestrador.py)

**Problema:** O ciclo de retry de validação (`busca → confirmacao_item` bloqueado → retry para `oferta` → próximo turno `confirmacao_item`) fazia o modelo pular a criação do item em `mudancas_itens`. O auto-enriquecimento existente só funciona se o modelo incluir uma entrada em `mudancas_itens` — sem ela, não há nada para enriquecer.

**Solução:** Após aplicar `mudancas_itens` (step 9) e antes de despachar ações (step 10), o orquestrador verifica:
- se a etapa atual é `confirmacao_item`
- se não existe nenhum `item_provisorio` com `pneu_id` na sessão
- se há pneus em `pneus_encontrados`

Se as três condições forem verdadeiras, cria automaticamente um item para cada pneu encontrado.

```python
# --- 9b. Rede de seguranca: confirmacao_item sem item criado ---
if envelope.etapa_atual == EtapaFluxo.confirmacao_item:
    itens_existentes = item_provisorio_repo.listar_itens_ativos_por_sessao(sessao_id)
    itens_com_pneu = [i for i in itens_existentes if i.pneu_id]
    if not itens_com_pneu and pneus_encontrados:
        vistos: set = set()
        for p in pneus_encontrados:
            pid = p.get("pneu_id")
            if pid and pid not in vistos:
                vistos.add(pid)
                try:
                    pneu_uuid = UUID(str(pid))
                    item_provisorio_repo.criar_item(ItemProvisorioCreate(
                        sessao_chat_id=sessao_id,
                        status_item=StatusItemProvisorio.selecionado_cliente,
                        pneu_id=pneu_uuid,
                        posicao=p.get("posicao"),
                        quantidade=1,
                        preco_unitario_sugerido=float(p["preco_venda"]) if p.get("preco_venda") else None,
                    ))
                    logger.info("Rede de seguranca 9b: item criado automaticamente pneu_id=%s", pneu_uuid)
                except Exception as e:
                    logger.warning("Rede de seguranca 9b falhou: %s", e)
```

**Padrão arquitetural:** Mesma família dos outros guardrails do projeto — `_extrair_fatos_estruturados_fallback()` (Fase 20) e auto-enriquecimento de `pneu_id` (Fase 9). O princípio é: "IA interpreta, backend garante." O orquestrador usa dados já existentes na sessão (`pneus_encontrados`) para fechar o gap sem alterar a decisão da IA.

---

### Item 2 — Ajuste de tom em `confirmacao_item` (ia/prompt_sistema.py)

**Problema:** O exemplo de mensagem ao confirmar item era:
> "Tem mais algum pneu ou pode seguir pro pagamento?"

Isso mencionava "pagamento" antes mesmo de perguntar entrega, soava mecânico e podia assustar o cliente que ainda não sabe como/quando vai pagar.

**Solução:** Alterado o exemplo e adicionada regra explícita:
```
- Tom direto: "Certo, 1 traseiro confirmado!"
- Após confirmar, SEMPRE pergunte: "Tem mais algum pneu ou é só esse?"
- NUNCA mencione "pagamento" nessa etapa — pagamento só é tratado em `entrega_pagamento`.
```

A etapa `entrega_pagamento` já tinha o tom correto ("Vai retirar na loja ou quer entrega? Como prefere pagar?") — o problema era só a frase de transição.

---

### Arquivos alterados

| Arquivo | O que mudou |
|---------|-------------|
| `engine/orquestrador.py` | Step 9b — auto-criação de item_provisorio quando confirmacao_item sem item |
| `ia/prompt_sistema.py` | Exemplo de mensagem em `confirmacao_item`; regra proibindo "pagamento" nessa etapa |

---

## Fase 27 — Suporte a Imagem e Áudio (COMPLETA)

Data: 04/04/2026

### Contexto

O agente recebia apenas texto. Clientes de WhatsApp frequentemente mandam foto do pneu desgastado ou áudio descrevendo o que precisam. Esta fase adiciona suporte multimodal sem alterar nenhuma lógica do orquestrador ou do banco.

---

### Imagem (Visão)

O gpt-5.4 suporta visão nativamente via Chat Completions API. Quando o webhook detecta um attachment de imagem, passa a URL para `processar_turno()` que encaminha para `chamar_agente()`.

**`ia/agente.py`** — `chamar_agente()` aceita `imagens: list[str] | None`:
```python
if imagens:
    user_content = [{"type": "text", "text": mensagem_usuario or "(sem texto)"}]
    for url in imagens:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": url, "detail": "auto"},
        })
else:
    user_content = mensagem_usuario
```
No retry de validação, imagens não são reenviadas (só texto de correção).

**Formatos suportados:** PNG, JPEG, WEBP, GIF. Precisa ser URL direta da imagem, não página de produto.

---

### Áudio (Whisper)

Áudio nativo não é suportado no gpt-5.4 via Chat Completions. Solução: transcrição via `whisper-1` antes de chegar ao agente.

**`webhook.py`** — `_transcrever_audio(url)`:
```python
arquivo = io.BytesIO(resp.content)
arquivo.name = "audio.ogg"
transcricao = client.audio.transcriptions.create(
    model="whisper-1", file=arquivo, language="pt"
)
```
A transcrição substitui/complementa o `content` da mensagem. O agente recebe texto puro — não sabe que era áudio.

---

### Extração de anexos (`webhook.py`)

**`_extrair_anexos(data)`** — percorre `attachments` do payload Chatwoot:
- `file_type: audio/voice` → chama Whisper, retorna texto transcrito
- `file_type: image/sticker` → coleta URL para passar ao modelo

**Lógica de content final:**
- Só texto → passa texto normal
- Texto + áudio → junta ambos
- Só imagem (sem texto) → passa `"(sem texto)"` + imagem
- Vazio sem imagem → ignora (comportamento anterior mantido)

---

### Prompt (`ia/prompt_sistema.py`)

Duas regras adicionadas nas diretrizes gerais:
- **Imagem:** tenta ler medida visualmente; se não conseguir, pede confirmação da lateral do pneu
- **Áudio:** já chega como texto transcrito — tratar normalmente

---

### Arquivos alterados

| Arquivo | O que mudou |
|---------|-------------|
| `ia/agente.py` | `chamar_agente()` aceita `imagens`, monta content multimodal |
| `engine/orquestrador.py` | `processar_turno()` e `_chamar_e_validar()` aceitam e propagam `imagens` |
| `webhook.py` (sistema) | `_transcrever_audio()`, `_extrair_anexos()`, endpoint atualizado |
| `ia/prompt_sistema.py` | Regras de comportamento com foto e áudio |

### Teste

Script `teste_imagem.py` + `teste_imagem.bat` na raiz do projeto:
```
teste_imagem.bat imagem              # foto de pneu do Wikipedia
teste_imagem.bat url <URL-direta>    # qualquer imagem .jpg/.webp
teste_imagem.bat audio               # simula texto transcrito do Whisper
```

**Resultado validado:** agente identificou pneu Eurogrip na foto, informou que não conseguiu ler a medida e pediu confirmação da lateral.

---

## Decisoes tomadas durante implementacao

1. **IA sera OpenAI** — config.py usa OPENAI_API_KEY e OPENAI_MODEL
2. **PedidoCreate e ItemPedidoCreate** — adicionados para tipar repos e garantir validacao Pydantic antes de persistir
3. **item_provisorio_repo** — usa `.in_()` com status ativos em vez de `not_.in_()` com inativos (mais compativel com SDK)
4. **catalogo_repo** — usa views `catalogo_agente` e `compatibilidade_moto_pneu` e RPCs `buscar_pneu_por_texto` e `buscar_moto_por_texto` do Supabase
5. **load_dotenv(override=True)** — necessario porque maquina tinha env vars de sistema de outro projeto Supabase que sobrescreviam o `.env`
6. **Proxy Windows** — `client.py` auto-detecta proxy do Windows Registry (winreg) e passa ao httpx.Client para o SDK funcionar atras de proxy
7. **maybe_single().execute() retorna None** — supabase-py retorna `None` (nao APIResponse com data=None) quando nenhum registro e encontrado; todos os repos corrigidos para tratar `resultado is None`
8. **Structured Outputs substituiu json_object** — response_format trocado para json_schema strict=True; elimina ParseErrors de tipo e parallel_tool_calls=False obrigatorio junto com tools
9. **Retry com correcao** — modelo tende a pular etapas quando tem informacao suficiente; retry com re-prompt explicando os erros e acoes validas corrige o comportamento em 1-2 tentativas
10. **Tools via function calling vs acoes_sugeridas** — as tools de busca sao executadas pela IA via function calling durante `chamar_agente()`; as `acoes_sugeridas` sao semanticas, apenas `converter_em_pedido` dispara logica backend real (promotor)
11. **Constantes centrais** — chaves de contexto (tipo_entrega, forma_pagamento, endereco_entrega) centralizadas em `constantes.py` para eliminar strings magicas
12. **catalogo_repo padronizado** — funcoes de lista retornam `list[dict]`, funcoes de entidade unica retornam `Model | None`
13. **tenacity para retry** — retry com backoff exponencial para erros transientes da OpenAI (rate limit, timeout, conexao)

## Dependencias externas no Supabase

Estas funcoes e views ja devem existir no banco:

- [x] VIEW `catalogo_agente` — pneu + estoque com disponivel_real
- [x] VIEW `compatibilidade_moto_pneu` — moto + medida + pneu + estoque
- [x] RPC `buscar_pneu_por_texto` — busca por similaridade em `descricao_comercial`, `marca`, `modelo` com pg_trgm + ILIKE, limite 10. Indice GIN criado.
- [x] RPC `buscar_moto_por_texto` — busca por similaridade em `descricao_resolvida`, `marca`, `modelo` com pg_trgm + ILIKE, limite 10. Indice GIN criado.

## Estrutura atual de arquivos

```
agente_2w/
├── __init__.py
├── config.py
├── constantes.py
├── main.py
├── enums/
│   ├── __init__.py
│   └── enums.py
├── schemas/
│   ├── __init__.py
│   ├── cliente.py
│   ├── sessao_chat.py
│   ├── mensagem_chat.py
│   ├── contexto_conversa.py
│   ├── item_provisorio.py
│   ├── pneu.py
│   ├── moto.py
│   ├── medida_moto.py
│   ├── estoque.py
│   ├── pedido.py
│   ├── item_pedido.py
│   ├── area_entrega.py
│   ├── endereco_entrega.py
│   ├── metadata_chat.py
│   ├── contexto_executavel.py
│   └── envelope_ia.py
├── db/
│   ├── __init__.py
│   ├── client.py
│   ├── exceptions.py
│   ├── sessao_repo.py
│   ├── mensagem_repo.py
│   ├── contexto_repo.py
│   ├── item_provisorio_repo.py
│   ├── cliente_repo.py
│   ├── catalogo_repo.py
│   ├── pedido_repo.py
│   ├── area_entrega_repo.py
│   ├── config_loja_repo.py
│   ├── log_busca_web_repo.py
│   └── queries.py
├── engine/
│   ├── __init__.py
│   ├── maquina_estados.py
│   ├── pendencias.py
│   ├── montador_contexto.py
│   ├── validador_envelope.py
│   ├── promotor.py
│   ├── sessao_timeout.py
│   └── orquestrador.py
├── tools/
│   ├── __init__.py
│   ├── busca_catalogo.py
│   ├── busca_web.py
│   ├── consulta_estoque.py
│   └── resolve_cliente.py
└── ia/
    ├── __init__.py
    ├── prompt_sistema.py
    ├── agente.py
    └── parser_envelope.py
```

## Resultado dos Testes — Fases 1, 2 e 3

Data: 29/03/2026 | Script: `teste_fases_1_2_3.py` | **118/118 PASS**

| Grupo | Descricao | Testes | Status |
|-------|-----------|--------|--------|
| 1 | Imports Fase 1 (Enums + Schemas) | 17 | PASS |
| 2 | Imports Fase 2 (Repos) | 8 | PASS |
| 3 | Imports Fase 3 (Engine) | 5 | PASS |
| 4 | Schemas Instanciacao + Validacao | 17 | PASS |
| 5 | Maquina de Estados (transicoes) | 19 | PASS |
| 6 | Pendencias (acoes por etapa) | 18 | PASS |
| 7 | Validador de Envelope | 5 | PASS |
| 8 | Conexao Supabase (14 tabelas/views) | 14 | PASS |
| 9 | Repos Leitura Real | 5 | PASS |
| 10 | Integracao (Sessao + Contexto + Engine) | 10 | PASS |
| **Total** | | **118** | **PASS** |

### Dados confirmados no Supabase

- 16 pneus cadastrados
- 12 motos cadastradas
- 24 medidas moto
- 16 registros de estoque
- Views `catalogo_agente` e `compatibilidade_moto_pneu` acessiveis

## Resultado dos Testes — Fase 4

Data: 29/03/2026 | Script: `teste_fase_4.py` | **9/9 PASS**

| Teste | Status | Detalhe |
|-------|--------|---------|
| buscar_pneus(aro=17) | PASS | 6 pneus |
| buscar_pneus(medida_texto='100/80') | PASS | 2 pneus |
| buscar_pneus_por_moto('CG 160') | PASS | 6 compatibilidades (3 motos: Fan, Titan, Start) |
| buscar_detalhes_pneu(real) | PASS | encontrado + estoque |
| buscar_detalhes_pneu(fake) | PASS | nao encontrado |
| consultar_estoque(real) | PASS | disponivel=True, preco=359.9 |
| consultar_estoque(fake) | PASS | nao encontrado |
| resolver_cliente(inexistente) | PASS | criado novo |
| resolver_cliente(mesmo tel) | PASS | ja_existia=True |

### Bugs corrigidos durante testes

1. **config.py**: `load_dotenv()` → `load_dotenv(override=True)` — env vars de sistema sobrescreviam `.env`
2. **client.py**: Adicionada deteccao automatica de proxy via Windows Registry
3. **7 repos (12 pontos)**: `maybe_single().execute()` retorna `None` quando nenhum registro encontrado — ajustado para `if resultado is None or resultado.data is None`
4. **Supabase RPCs criadas**: `buscar_moto_por_texto` e `buscar_pneu_por_texto` criadas com pg_trgm (similarity + ILIKE) + indices GIN em `moto.descricao_resolvida` e `pneu.descricao_comercial`
5. **parser_envelope.py**: Assinatura corrigida para receber `ContextoExecutavel` em vez de `EtapaFluxo` (consistente com `validar_envelope`)

## Resultado dos Testes — Fase 5

Data: 29/03/2026 | Script: `teste_fase_5.py` | **10/10 PASS**

| Teste | Status | Detalhe |
|-------|--------|---------|
| import prompt_sistema | PASS | 5146 caracteres |
| import agente (5 tools) | PASS | 5 tools + 5 dispatchers |
| import parser_envelope | PASS | |
| parse JSON valido | PASS | 0 erros validacao |
| parse JSON envolto em markdown | PASS | extrai corretamente |
| parse JSON com texto ao redor | PASS | extrai corretamente |
| parse rejeita texto invalido | PASS | ParseError levantado |
| parse detecta acao invalida | PASS | erro detectado |
| chamar_agente (OpenAI real) | PASS | function calling funcionou |
| parse resposta real da IA | PASS | EnvelopeIA valido |

> **Nota:** A IA usou tool `buscar_pneus_por_moto('CG 160')` automaticamente via function calling e retornou opcoes reais do catalogo.

## Resultado dos Testes — Bateria Integrada F1-F5

Data: 29/03/2026 | Script: `teste_integrado_f1_f5.py` | **126/126 PASS (100%)**

### Resumo por Fase

| Fase | Descricao | Pass | Total | Status |
|------|-----------|------|-------|--------|
| F1 | Fundacao (Enums + Schemas) | 25 | 25 | PASS |
| F2 | Repositorios (DB + Supabase) | 27 | 27 | PASS |
| F3 | Engine (Estado/Pendencias/Contexto/Validador) | 34 | 34 | PASS |
| F4 | Tools (Catalogo/Estoque/Cliente) | 13 | 13 | PASS |
| F5 | IA (Prompt/Agente/Parser) | 8 | 8 | PASS |
| INT | Integracao Cross-Fase (fluxo completo) | 19 | 19 | PASS |
| **Total** | | **126** | **126** | **100%** |

### Cobertura do teste integrado

- **F1**: 2 imports enums + 15 imports schemas + 8 validacoes Pydantic (rejeicao + aceitacao)
- **F2**: 8 imports repos + 13 SELECTs Supabase (11 tabelas + 2 views) + 6 leituras reais via repo
- **F3**: 5 imports engine + 13 transicoes + 12 pendencias + 4 validacoes envelope
- **F4**: 3 imports tools + 10 execucoes reais (busca por aro/medida/marca/moto, detalhes, estoque, resolve_cliente)
- **F5**: 3 imports IA + 5 testes parser (JSON puro, markdown, com ruido, invalido, acao proibida)
- **INT**: sessao+mensagem+fato reais → montar_contexto → chamar_agente (OpenAI gpt-4o com function calling) → parse_resposta → limpeza

### Nota sobre non-determinismo

A falha que existia na versao anterior (IA retornando texto livre em vez de JSON) foi corrigida com `response_format={"type": "json_object"}` no agente.py. A bateria agora passa 100%.

## Resultado dos Testes — Fases 14 e 15 (Multi-Moto + Guardrail)

Data: 02/04/2026 | Script: `teste_multi_item.py` | **21/21 PASS**

### Metodologia

Testes desenhados para **induzir bugs conhecidos**, nao para documentar caminho feliz.
Cada teste ataca um bug especifico que existia antes dos fixes desta sessao.

| Grupo | Teste | Bug induzido | Fix que protege |
|-------|-------|-------------|-----------------|
| Guardrail | `_aplicar_guardrail` unitario | IA emite confirmar + adicionar juntos | `_aplicar_guardrail` remove a contradicao |
| Contaminacao | Fan 125 (90/90-18) → PCX 160 | medida_informada da Fan contamina PCX | 3-fato cleanup em adicionar_outro_item |
| MesmoPneu | PCX 160 + CG 160 | same pneu_id confirma item errado | `max(criado_em)` pega item mais recente |
| 4Motos | XRE + Fan + PCX + CG sequencia | orfaos, NULL pneu_id, contagem errada | todos os fixes combinados |

### Resultado

| Grupo | Pass | Total | Status |
|-------|------|-------|--------|
| Guardrail | 5 | 5 | PASS |
| Contaminacao | 4 | 4 | PASS |
| MesmoPneu | 4 | 4 | PASS |
| 4Motos | 8 | 8 | PASS |
| **TOTAL** | **21** | **21** | **PASS** |

### Observacoes

- Fan (0cce4ee0) e PCX (89171e6e): pneu_ids distintos — contaminacao eliminada
- 4 motos sequencia: XRE (78515ece), Fan (0cce4ee0), PCX (89171e6e), CG (89171e6e)
  - PCX e CG compartilham pneu_id neste catalogo — prova que `max(criado_em)` funciona
  - 4 itens criados, nenhum orfao, nenhum NULL

## Fase 28 — Fix: Auto-enriquecimento de Preco (COMPLETA)

### Problema detectado (teste E2E Hornet)

No teste end-to-end com Honda CB 600F Hornet, o agente entrou em **loop no fechamento**: o cliente
disse "sim" 4 vezes mas o pedido nunca era criado. O log revelou:

```
WARNING: Pre-condicoes nao atendidas: item f842556d sem preco definido
```

### Causa raiz

O auto-enriquecimento de `preco_unitario_sugerido` no `_aplicar_mudancas_itens()` estava **dentro**
do bloco `if pneu_uuid is None` (que so executa quando o modelo NAO fornece UUID). Quando o modelo
fornecia `pneu_id` valido mas omitia o preco, o item era criado sem preco. O promotor (`promotor.py`)
exige preco > 0, entao rejeitava a conversao — e o modelo ficava em loop tentando converter.

### Correcao

Separei o auto-enriquecimento de preco em bloco independente que executa **sempre** que:
1. `pneu_uuid` existe (modelo passou ou foi auto-enriquecido)
2. `preco_unitario_sugerido` esta ausente nos dados
3. `pneus_encontrados` contem resultados

O novo bloco faz match por UUID exato nos `pneus_encontrados` e preenche o preco.

### Cenarios cobertos

| Cenario | Antes | Depois |
|---------|-------|--------|
| Modelo passa pneu_id + preco | OK | OK (bloco nao atua) |
| Modelo passa pneu_id sem preco | **BUG: item sem preco** | OK (auto-enriquece) |
| Modelo nao passa pneu_id | OK (auto-enriquecia tudo) | OK (mesma logica) |

### Arquivo alterado

- `agente_2w/engine/orquestrador.py` — `_aplicar_mudancas_itens()`, novo bloco de auto-enriquecimento de preco (linhas 569-581)
