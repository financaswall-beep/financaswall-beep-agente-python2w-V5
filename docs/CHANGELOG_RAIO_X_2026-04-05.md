# Raio-X e Correcoes do Agente 2W Pneus
**Data:** 2026-04-05
**Escopo:** Auditoria completa do codigo + correcao de 16 inconsistencias

---

## Resumo

Auditoria completa da logica do agente identificou **23+ inconsistencias** em 12 arquivos.
10 correcoes foram aplicadas diretamente no codigo, priorizadas por impacto no cliente.

---

## Correcoes Aplicadas

### Fix #1 — Loop infinito de estoque zero (CRITICO)
**Arquivo:** `agente_2w/engine/orquestrador/_nucleo.py`
**Problema:** Quando `validar_pre_condicoes()` falhava (ex: estoque=0), o erro era logado mas nunca
comunicado a LLM. Resultado: agente ficava em loop pedindo "Confirma o pedido?" eternamente.
**Solucao:** Registrar fato `erro_promocao` no contexto com a mensagem de erro. A LLM agora ve o
motivo da falha e pode informar o cliente (ex: "pneu fora de estoque no momento").
**Locais alterados:**
- `_despachar_acoes()`: try/except de `converter_em_pedido` agora registra erro no contexto
- Auto-promocao em fechamento (passo 12): ambos os caminhos de falha registram erro

### Fix #2 — JSON parser truncava objetos aninhados (CRITICO)
**Arquivo:** `agente_2w/ia/parser_envelope.py`
**Problema:** Regex `\{.*?\}` (non-greedy) cortava JSON com sub-objetos (ex: `{"a": {"b": 1}}`
virava `{"a": {"b": 1}`). O fallback correto (bracket counting) so rodava quando o regex falhava
— mas o regex "funcionava" e retornava JSON corrompido.
**Solucao:** Removido regex, agora usa bracket counting (contagem de chaves balanceadas) como
metodo principal. Garante extracao correta de qualquer nivel de aninhamento.

### Fix #3 — montar_contexto() crash sem fallback (CRITICO)
**Arquivo:** `agente_2w/engine/orquestrador/_nucleo.py`
**Problema:** Se `montar_contexto()` lancasse excecao (sessao nao encontrada apos timeout),
o turno inteiro crashava sem retornar mensagem ao cliente.
**Solucao:** Envolvido em try/except que retorna `MENSAGEM_FALHA_SEGURA` ao cliente.

### Fix #4 — Frete antigo nao era limpo ao mudar para retirada (ALTO)
**Arquivo:** `agente_2w/engine/orquestrador/localidade_frete.py`
**Problema:** Cliente dizia "entrega em Niteroi" (frete=R$9,90), depois mudava para "vou retirar
na loja". O fato `FRETE_VALOR` antigo permanecia ativo, causando cobranca indevida no pedido.
**Solucao:** Quando `tipo_entrega=retirada`, desativar fatos `FRETE_VALOR` e `FRETE_NAO_COBERTO`
antes de retornar.

### Fix #5 — Cancelamento podia retriggerar (ALTO)
**Arquivo:** `agente_2w/engine/orquestrador/_nucleo.py`
**Problema:** O fato `PEDIDO_CANCELAMENTO_SOLICITADO` era desativado DEPOIS do cancelamento.
Se `cancelar_pedido_sessao()` falhasse parcialmente, o fato permanecia e o proximo turno
tentaria cancelar de novo.
**Solucao:** Invertida a ordem — desativar fato ANTES de executar o cancelamento.

### Fix #6 — UUID crash em enriquecimento de itens (ALTO)
**Arquivo:** `agente_2w/engine/orquestrador/enriquecimento_itens.py`
**Problema:** `UUID(mudanca.item_provisorio_id)` era chamado sem try/except. Se a LLM enviasse
um ID malformado, o turno inteiro falhava com excecao nao tratada.
**Solucao:** Envolvido em try/except que loga warning e pula a acao (continue).

### Fix #7 — Follow-up de frete descartava fatos e acoes (ALTO)
**Arquivo:** `agente_2w/engine/orquestrador/_nucleo.py`
**Problema:** O segundo chamado de LLM (follow-up apos calculo de frete) podia registrar fatos
observados, inferidos e mudancas de contexto, mas apenas a `mensagem_cliente` era aproveitada.
Todo o resto era descartado silenciosamente.
**Solucao:** Apos receber `envelope_pos_frete`, processar tambem `fatos_observados`,
`fatos_inferidos` e `mudancas_contexto` do envelope.

### Fix #8 — pode_avancar_etapa incompleto (MEDIO)
**Arquivo:** `agente_2w/engine/montador_contexto.py`
**Problema:** `pode_avancar_etapa` so verificava se tinha item validado + sessao nao bloqueada.
Na etapa `entrega_pagamento`, ignorava se entrega e pagamento estavam definidos.
A LLM recebia `pode_avancar_etapa=true` mesmo sem entrega/pagamento, tentava avancar,
e o validador bloqueava — causando retry desnecessario.
**Solucao:** Logica condicional por etapa:
- `entrega_pagamento`: exige item + entrega + pagamento + nao bloqueada
- demais etapas: item + nao bloqueada

### Fix #9 — Pendencias com campo_relacionado errado (MEDIO)
**Arquivo:** `agente_2w/engine/pendencias.py`
**Problema:** Os campos `campo_relacionado` usavam strings que nao existiam em `ChaveContexto`
(`"moto_modelo_informado"`, `"resultados_busca"`, `"pneu_confirmado"`, `"item_provisorio"`).
Tornavam o sistema de pendencias inutilizavel para validacao automatica.
**Solucao:** Substituidos por constantes reais de `ChaveContexto`:
- `moto_modelo_informado` -> `ChaveContexto.MOTO_MODELO`
- `resultados_busca` -> `ChaveContexto.ULTIMOS_PNEUS_ENCONTRADOS`
- `pneu_confirmado` -> `ChaveContexto.ULTIMOS_PNEUS_ENCONTRADOS`
- `item_provisorio` -> `ChaveContexto.ITENS_FINALIZADOS`
Tambem corrigida descricao de `item_validado` para ser explicita.

### Fix #10 — Guardrails incompletos (MEDIO)
**Arquivo:** `agente_2w/engine/orquestrador/guardrails.py`
**Problema:** So tratava conflito `confirmar_item + adicionar_outro_item`. Outros conflitos
comuns da LLM nao eram capturados.
**Solucao:** Adicionadas 3 novas regras:
- `converter_em_pedido + cancelar_pedido` -> manter cancelar
- `finalizar_itens + adicionar_outro_item` -> manter finalizar
- `rejeitar_item + confirmar_item` -> manter rejeitar

---

## Nova Constante Adicionada

**Arquivo:** `agente_2w/constantes.py`
- `ChaveContexto.ERRO_PROMOCAO = "erro_promocao"` — chave para registrar erros de
pre-condicao ao tentar criar pedido. Permite que a LLM veja e comunique o problema.

---

## Problemas Identificados (nao corrigidos — requerem decisao de design)

### Reserva de estoque fora da transacao RPC
**Arquivo:** `agente_2w/engine/promotor.py` (~linha 351)
**Problema:** Estoque e reservado DEPOIS do RPC criar o pedido. Se a reserva falha, o pedido
existe sem estoque alocado.
**Recomendacao:** Incluir reserva dentro do RPC (Supabase-side) ou validar estoque atomicamente.

### FSM permite loops infinitos sem deteccao
**Arquivo:** `agente_2w/engine/maquina_estados.py`
**Problema:** `busca <-> oferta` e `confirmacao_item <-> busca` permitem ciclos infinitos.
**Recomendacao:** Contador de revisitas por par de etapas. Alertar apos 3x no mesmo ciclo.

### Nomes de acoes no prompt vs codigo
**Problema:** Prompt usa `buscar_por_moto`, `pedir_clarificacao_moto`. Codigo usa
`buscar_pneus_por_moto`. Causa retries desnecessarios.
**Recomendacao:** Alinhar vocabulario ou criar mapeamento explicito.

### Fallback de fatos pode sobrescrever decisao da LLM
**Arquivo:** `agente_2w/engine/orquestrador/fatos_fallback.py`
**Problema:** Keywords como "pix" registram fato sem verificar nivel de confirmacao do existente.
**Recomendacao:** Verificar `NivelConfirmacao` antes de sobrescrever.

### Promotor: _normalizar perde informacao
**Arquivo:** `agente_2w/engine/promotor.py` (~linha 66)
**Problema:** `"Cartao Credito"` vira `"cartao credito"`, que nao e valor valido do enum
`FormaPagamento`. Erro e engolido silenciosamente (`except ValueError: pass`).
**Recomendacao:** Criar dicionario de mapeamento (ex: `"credito" -> "cartao"`, `"debito" -> "cartao"`).

### N+1 queries no montador_contexto
**Arquivo:** `agente_2w/engine/montador_contexto.py`
**Problema:** Para cada item, faz query individual de pneu. Com 4 itens = 4 queries.
**Recomendacao:** Batch load com `buscar_pneus_por_ids([...])`.

---

## Correcoes Aplicadas — Rodada 2 (mergulho profundo)

### Fix #11 — String literal "now()" no cache de bairro (ALTO)
**Arquivo:** `agente_2w/db/bairro_municipio_cache_repo.py`
**Linhas:** 47, 81
**Problema:** `"atualizado_em": "now()"` era passado como string literal ao Supabase REST API.
O PostgreSQL nao executa `now()` quando recebe via JSON — o campo recebia a string `"now()"`
ou causava erro silencioso (engolido pelo try/except).
**Solucao:** Substituido por `datetime.now(timezone.utc).isoformat()`.

### Fix #12 — validado_backend_em nunca populado (ALTO)
**Arquivo:** `agente_2w/db/item_provisorio_repo.py`
**Linhas:** 77-94
**Problema:** `atualizar_status_item()` so setava `cliente_confirmou_em` para status
`selecionado_cliente`. Quando status mudava para `validado`, o campo `validado_backend_em`
ficava `None` eternamente. No montador_contexto, `validado_backend=item.validado_backend_em
is not None` era SEMPRE `False` — a LLM nunca via itens como "validados pelo backend".
**Solucao:** Adicionado `elif status == validado: payload["validado_backend_em"] = ...`

### Fix #13 — Mensagem vazia aceita sem validacao (MEDIO)
**Arquivo:** `agente_2w/engine/orquestrador/_nucleo.py`
**Problema:** `processar_turno()` aceitava mensagens vazias ou so com espacos/emojis e
as enviava para a LLM, gastando tokens e retornando respostas sem sentido.
**Solucao:** Validacao no inicio da funcao — retorna mensagem amigavel sem chamar a IA.

### Fix #14 — buscar_pneus_por_moto retornava vazio apos filtro de posicao (MEDIO)
**Arquivo:** `agente_2w/tools/busca_catalogo.py`
**Linhas:** 130-142
**Problema:** Se a moto tinha pneus cadastrados mas NENHUM na posicao solicitada (ex:
"dianteiro"), a funcao retornava `{"quantidade": 0}` em vez de mostrar as posicoes
disponiveis. O cliente recebia "nao encontrei" quando existiam opcoes.
**Solucao:** Quando filtro por posicao da vazio, retorna TODAS as compatibilidades com
aviso indicando que a posicao solicitada nao foi encontrada.

### Fix #15 — Guardrail rejeitar+confirmar removido (correcao do Fix #10)
**Arquivo:** `agente_2w/engine/orquestrador/guardrails.py`
**Problema:** A regra "rejeitar_item + confirmar_item = contradicao" (adicionada no Fix #10)
era muito agressiva. Cliente pode rejeitar pneu A e confirmar pneu B no mesmo turno —
sao itens diferentes, nao contradicao. Remover `confirmar_item` causava perda da confirmacao.
**Solucao:** Regra removida. Comentario explicativo adicionado.

### Fix #16 — Sessao expirada nao limpava itens provisorios (MEDIO)
**Arquivo:** `agente_2w/engine/orquestrador/_nucleo.py`
**Problema:** Quando uma sessao expirava por inatividade e era substituida por uma nova,
os itens provisorios da sessao antiga ficavam com status ativo no banco — dados orfaos
que nunca seriam processados e poluiam consultas.
**Solucao:** Antes de criar a nova sessao, cancelar todos os itens ativos da sessao expirada.

---

## Correcoes Aplicadas — Rodada 3 (teste ao vivo)

### Fix #17 — LLM nao via erro_promocao, loop infinito de confirmacao (CRITICO)
**Arquivo:** `agente_2w/engine/montador_contexto.py`
**Problema:** O Fix #1 registrava o fato `erro_promocao` no contexto quando a criacao do pedido
falhava (ex: estoque=0), mas a LLM nao recebia nenhum alerta explicativo. O fato aparecia
nos `fatos_ativos` mas sem destaque — a LLM continuava pedindo "Confirma o pedido?" em loop.
**Solucao:** Adicionado alerta contextual critico quando `erro_promocao` esta ativo:
`"ERRO AO CRIAR PEDIDO: {mensagem}. NAO peca confirmacao de novo. Informe o cliente..."`

### Fix #18 — Frete nao recalculado quando municipio mudava (ALTO)
**Arquivo:** `agente_2w/engine/orquestrador/localidade_frete.py`
**Problema:** O guard de idempotencia retornava cedo se qualquer fato de frete existisse
(linhas 148-151), impedindo recalculo quando o municipio era corrigido pelo cliente.
Exemplo: cliente diz "entrega em Apollo" (frete_nao_coberto=Apollo), depois corrige
"Apollo fica em Sao Goncalo" — o frete antigo persistia porque a funcao nem chegava
a consultar o novo municipio.
**Solucao:** Guard agora compara o municipio atual com o usado no frete anterior.
Se mudou, desativa o frete antigo e recalcula. Se e o mesmo, retorna cedo (idempotente).

### Fix #19 — Municipio ambiguo travava agente sem resposta (CRITICO)
**Arquivos:** `agente_2w/engine/montador_contexto.py`, `agente_2w/engine/orquestrador/_nucleo.py`, `agente_2w/engine/orquestrador/localidade_frete.py`
**Problema:** Quando o bairro informado pelo cliente existia em 2+ municipios cobertos
(ex: "Venda da Cruz" → Niterói e São Gonçalo), o sistema registrava o fato `municipio_ambiguo`
corretamente mas a LLM não sabia o que fazer com ele. Resultado: respondia "Deixa eu verificar..."
e travava — nunca perguntava ao cliente qual cidade.
**Causa raiz (3 falhas combinadas):**
1. Sem alerta no `montador_contexto.py` explicando `municipio_ambiguo` para a LLM
2. Follow-up em `_nucleo.py` só disparava para `frete_valor`/`frete_nao_coberto`, ignorava ambiguidade
3. Fato `municipio_ambiguo` nunca era desativado quando o cliente esclarecia o municipio
**Solucao:**
- Adicionado alerta contextual: `"MUNICIPIO AMBIGUO: o bairro '{termo}' existe em mais de um
  municipio: {lista}. Voce DEVE perguntar ao cliente em qual cidade/municipio ele mora."`
- Follow-up agora dispara tambem quando `municipio_ambiguo` e detectado neste turno,
  com trigger especifico instruindo a LLM a perguntar a cidade
- `municipio_ambiguo` e desativado automaticamente quando municipio e definido
  (em `_consultar_e_registrar_frete`, antes do calculo)
**Abrangencia:** Funciona para qualquer bairro ambiguo, nao apenas Venda da Cruz.

### Fix #20 — Estrategia de busca de bairro otimizada (MEDIO)
**Arquivo:** `agente_2w/tools/resolver_bairro.py`
**Problema:** O prompt do web_search era generico ("é um bairro do RJ?"), fazendo o modelo
tentar responder de cabeça em vez de pesquisar. Resultava em erros (ex: Manilha → São Gonçalo,
quando o correto é Itaboraí).
**Solucao:** Prompt alterado para forcar busca no padrao `"{termo} bairro município Rio de Janeiro"`,
que o Google resolve corretamente mesmo com grafias erradas, abreviacoes e girias locais.

### Dados — Itaborai adicionado a area de entrega
**Tabela:** `area_entrega`
- Itaboraí adicionado com frete R$24,00
- Itaboraí adicionado em `_MUNICIPIOS_COBERTOS` e `_NOME_OFICIAL` no `resolver_bairro.py`
- Cache de Manilha corrigido de São Gonçalo → Itaboraí

---

## Teste ao Vivo — Validacao Completa (2026-04-06 00:01~00:05)

**Sessao:** `5cebab6d-13e1-40f4-874f-fb7a5a55b395`
**Pedido:** #1120 — `31fa8ea6-d023-408f-b300-65d83e1cd2d9`
**Cenario:** Bairro ambiguo (Venda da Cruz) + fluxo completo ate pedido confirmado

### Fluxo da conversa (22 mensagens)
```
Cliente: "vcs entregam aqui na venda da cruz?"
Agente:  "Venda da Cruz fica em qual cidade — Niterói ou São Gonçalo?"  ← Fix #19 funcionando
Cliente: "niteroi"
Agente:  "Pra Niterói o frete fica R$9,90. Qual moto ou medida do pneu?"
Cliente: "130-70-17"
Agente:  "Essa medida é pra dianteiro ou traseiro?"
Cliente: "traseiro"
Agente:  "Temos o Maggion Sportissimo por R$249,90. Esse te serve?"
Cliente: "sim" → confirma → finaliza itens
Agente:  "Me passa nome, endereço e forma de pagamento"
Cliente: "andreza tavares lopes rua salva andarilho 789 venda a cruz niteroi"
Agente:  "Anotei! Falta a forma de pagamento"
Cliente: "pix"
Agente:  "✅ Pedido #1120 confirmado! Total R$259,80"
Cliente: "obrigada beijinhos"
Agente:  "Valeu! Qualquer dúvida é só chamar!"
```

### Validacao no banco de dados

| Tabela | Campo | Valor | Status |
|--------|-------|-------|--------|
| **pedido** | numero_pedido | 1120 | OK |
| | status_pedido | confirmado | OK |
| | valor_total | 259.80 | OK (249.90 + 9.90) |
| | valor_frete | 9.90 | OK (Niterói) |
| | forma_pagamento | pix | OK |
| | tipo_entrega | entrega | OK |
| | endereco_entrega_json | Rua Salva Andarilho 789, Venda da Cruz, Niterói | OK |
| **item_pedido** | pneu | Maggion Sportissimo 130/70-17 traseiro | OK |
| | posicao | traseiro | OK |
| | quantidade | 1 | OK |
| | preco_unitario | 249.90 | OK |
| **cliente** | nome | Andreza Tavares Lopes | OK |
| | municipio | Niterói | OK |
| | bairro | Venda da Cruz | OK |
| | total_pedidos | 1 | OK |
| | valor_total_gasto | 259.80 | OK |
| **sessao_chat** | etapa_atual | fechamento | OK |
| | status_sessao | fechada | OK |
| **item_provisorio** | status_item | promovido | OK |
| | cliente_confirmou_em | preenchido | OK |
| **estoque** | reservado | +1 (incrementado) | OK |
| **contexto_conversa** | municipio | Niterói (ativo) | OK |
| | municipio_ambiguo | Niterói, São Gonçalo (desativado) | OK |
| | frete_valor | 9.9 (ativo) | OK |
| | nome_cliente | Andreza Tavares Lopes (ativo) | OK |
| | endereco_entrega | Rua Salva Andarilho 789... (ativo) | OK |
| | forma_pagamento | Pix (ativo) | OK |

### Historico de fatos (ciclo de vida correto)
1. `municipio=Venda da Cruz` → registrado → desativado (termo cru, nao e municipio)
2. `municipio_ambiguo=Niterói, São Gonçalo` → registrado → desativado (cliente esclareceu)
3. `municipio=Niterói` → registrado → ativo (municipio correto apos esclarecimento)
4. `frete_valor=9.9` → registrado apos municipio definido → ativo

### Fixes validados neste teste
- **Fix #4** — frete_nao_coberto nao persistiu (mutual exclusivity OK)
- **Fix #18** — frete recalculado quando municipio mudou de "Venda da Cruz" para "Niterói"
- **Fix #19** — follow-up de ambiguidade disparou, LLM perguntou a cidade, fato limpo apos resposta
- **Fix #20** — web_search encontrou Venda da Cruz em Niterói e São Gonçalo

### Observacao menor
O fato `erro_promocao` ficou ativo no ultimo turno ("obrigada beijinhos") porque a auto-promocao
tentou rodar novamente mas os itens ja tinham sido promovidos. Nao causou impacto — o alerta
de pedido ja criado impediu a LLM de reagir. Melhoria futura: pular auto-promocao quando ja
existe pedido confirmado na sessao.

---

## Arquivos Modificados

| Arquivo | Tipo de Alteracao |
|---------|-------------------|
| `agente_2w/engine/orquestrador/_nucleo.py` | Fix #1, #3, #5, #7, #13, #16, #19 |
| `agente_2w/ia/parser_envelope.py` | Fix #2 |
| `agente_2w/engine/orquestrador/localidade_frete.py` | Fix #4, #18, #19 |
| `agente_2w/engine/orquestrador/enriquecimento_itens.py` | Fix #6 |
| `agente_2w/engine/montador_contexto.py` | Fix #8, #17, #19 |
| `agente_2w/engine/pendencias.py` | Fix #9 |
| `agente_2w/engine/orquestrador/guardrails.py` | Fix #10, #15 |
| `agente_2w/constantes.py` | Nova constante ERRO_PROMOCAO |
| `agente_2w/db/bairro_municipio_cache_repo.py` | Fix #11 |
| `agente_2w/db/item_provisorio_repo.py` | Fix #12 |
| `agente_2w/tools/busca_catalogo.py` | Fix #14 |
| `agente_2w/tools/resolver_bairro.py` | Fix #20 + Itaboraí |
