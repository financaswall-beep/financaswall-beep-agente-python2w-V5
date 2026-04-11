# Documentacao da Implementacao — Agente 2W Pneus

## Visao geral

Este documento descreve o que foi implementado no projeto `agente_2w`. O agente e um sistema comercial anti-alucinacao para a 2W Pneus, operando inteiramente via Supabase (PostgreSQL 17) como banco de dados e OpenAI GPT-4o como modelo de IA.

**Regra de ouro do sistema:**
> A IA interpreta. O backend decide. O banco garante integridade.

---

## Estrutura de arquivos

```
agente_2w/
├── __init__.py
├── main.py                          # ponto de entrada CLI para testes
├── config.py                        # configuracoes e variaveis de ambiente
├── constantes.py                    # chaves de contexto centralizadas (ChaveContexto)
│
├── enums/
│   ├── __init__.py
│   └── enums.py                     # todos os enums do banco
│
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
│   ├── area_entrega.py              # schema da tabela de cobertura e fretes
│   ├── endereco_entrega.py
│   ├── metadata_chat.py
│   ├── contexto_executavel.py       # payload entregue a IA (inclui FreteContexto)
│   └── envelope_ia.py               # resposta estruturada da IA
│
├── db/
│   ├── __init__.py
│   ├── client.py                    # cliente Supabase (com deteccao de proxy Windows)
│   ├── exceptions.py                # excecoes tipadas (RepositoryError, RegistroNaoEncontrado, etc.)
│   ├── sessao_repo.py
│   ├── mensagem_repo.py
│   ├── contexto_repo.py
│   ├── item_provisorio_repo.py
│   ├── cliente_repo.py
│   ├── catalogo_repo.py             # pneu + estoque + moto + medida_moto + views
│   ├── pedido_repo.py
│   ├── area_entrega_repo.py         # consultar_frete + listar_municipios_ativos
│   ├── config_loja_repo.py          # buscar_config_loja -> dict[str, str]
│   └── queries.py                   # queries auxiliares (contar, verificar, buscar generico)
│
├── engine/
│   ├── __init__.py
│   ├── maquina_estados.py           # transicoes permitidas e bloqueios
│   ├── pendencias.py                # acoes e pendencias por etapa
│   ├── montador_contexto.py         # monta o ContextoExecutavel do turno
│   ├── validador_envelope.py        # valida a resposta da IA
│   ├── promotor.py                  # converte itens em pedido (RPC transacional)
│   ├── sessao_timeout.py            # classifica estado de timeout da sessao
│   └── orquestrador.py              # loop completo de um turno (14 passos + retry)
│
├── tools/
│   ├── __init__.py
│   ├── busca_catalogo.py            # busca pneus por dimensoes, moto ou marca (usa views)
│   ├── consulta_estoque.py          # verifica disponibilidade
│   └── resolve_cliente.py           # resolve ou cria cliente
│
└── ia/
    ├── __init__.py
    ├── prompt_sistema.py            # system prompt do agente
    ├── parser_envelope.py           # parse da resposta da IA
    └── agente.py                    # chamada ao OpenAI GPT-4o (timeout + retry + function calling)
```

---

## Configuracao (`config.py`)

Usa `python-dotenv` com `load_dotenv(override=True)`. Le variaveis do arquivo `.env`.

| Variavel | Descricao | Default |
|---|---|---|
| `SUPABASE_URL` | URL do projeto Supabase | obrigatorio |
| `SUPABASE_KEY` | Service role key do Supabase | obrigatorio |
| `OPENAI_API_KEY` | Chave da API OpenAI | obrigatorio |
| `OPENAI_MODEL` | Modelo OpenAI a usar | `gpt-4o` |

Acesso direto via imports: `from agente_2w.config import SUPABASE_URL`.

## Constantes (`constantes.py`)

Classe `ChaveContexto` com todas as chaves usadas no `contexto_conversa`:

| Constante | Valor | Usada em |
|---|---|---|
| `TIPO_ENTREGA` | `"tipo_entrega"` | promotor, montador_contexto, pendencias |
| `FORMA_PAGAMENTO` | `"forma_pagamento"` | promotor, montador_contexto, pendencias |
| `ENDERECO_ENTREGA` | `"endereco_entrega"` | promotor |
| `MOTO_MARCA` | `"moto_marca"` | prompt_sistema (referencia) |
| `MOTO_MODELO` | `"moto_modelo"` | prompt_sistema (referencia) |
| `MOTO_ANO` | `"moto_ano"` | prompt_sistema (referencia) |
| `MEDIDA_INFORMADA` | `"medida_informada"` | orquestrador (limpeza em adicionar_outro_item) |
| `POSICAO_PNEU` | `"posicao_pneu"` | orquestrador (limpeza em adicionar_outro_item) |
| `NOME_CLIENTE` | `"nome_cliente"` | orquestrador (_atualizar_nome_cliente) |
| `TELEFONE_CLIENTE` | `"telefone_cliente"` | prompt_sistema (referencia) |
| `MUNICIPIO` | `"municipio"` | orquestrador, promotor |
| `BAIRRO` | `"bairro"` | orquestrador |
| `FRETE_VALOR` | `"frete_valor"` | orquestrador, montador_contexto, promotor |
| `FRETE_NAO_COBERTO` | `"frete_nao_coberto"` | orquestrador, montador_contexto, promotor |

Evita strings magicas duplicadas em multiplos arquivos.

---

## Enums (`enums/enums.py`)

Todos os enums refletem exatamente os tipos do banco PostgreSQL. Sao `str, Enum` para compatibilidade com Pydantic e JSON.

| Enum | Valores |
|---|---|
| `TipoDeVerdade` | `observado`, `inferido`, `validado_tool`, `confirmado_cliente`, `validado_backend`, `oficializado` |
| `EtapaFluxo` | `identificacao`, `busca`, `oferta`, `confirmacao_item`, `entrega_pagamento`, `fechamento` |
| `StatusSessao` | `ativa`, `aguardando_cliente`, `bloqueada`, `fechada` |
| `NivelConfirmacao` | `nenhum`, `confirmado_cliente`, `validado_tool`, `validado_backend`, `oficializado` |
| `OrigemContexto` | `mensagem_cliente`, `inferido_ia`, `tool`, `backend`, `operador`, `sistema` |
| `StatusItemProvisorio` | `sugerido`, `selecionado_cliente`, `validado`, `rejeitado`, `cancelado`, `promovido` |
| `TipoEntrega` | `retirada`, `entrega`, `a_confirmar` |
| `FormaPagamento` | `pix`, `dinheiro`, `cartao`, `transferencia`, `a_confirmar` |
| `StatusPedido` | `confirmado`, `cancelado`, `entregue` |
| `Confianca` | `alta`, `media`, `baixa` |
| `Direcao` | `entrada`, `saida` |
| `Remetente` | `cliente`, `agente`, `operador` |
| `Posicao` | `dianteiro`, `traseiro`, `par` |

---

## Schemas Pydantic (`schemas/`)

Cada schema reflete uma tabela do banco. Validacoes espelham as constraints SQL (defesa em profundidade).

### Schemas de entidades do banco

**`SessaoChatCreate` / `SessaoChat`**
- Valida: `status_sessao=bloqueada` exige `codigo_motivo` e `mensagem_motivo`
- Inclui `SessaoChatUpdate` para atualizacoes parciais

**`MensagemChatCreate` / `MensagemChat`**
- Campos: `sessao_chat_id`, `direcao`, `remetente`, `conteudo_texto`, `criado_em`
- Opcionais: `message_id_externo`, `metadata_json`

**`ContextoConversaCreate` / `ContextoConversa`**
- Valida: `valor_texto` ou `valor_json` deve existir (ao menos um)
- Valida: `fonte=mensagem_cliente` exige `mensagem_chat_id`

**`ItemProvisorioCreate` / `ItemProvisorio` / `ItemProvisorioUpdate`**
- Valida: `quantidade >= 1`
- Valida: `status_item=promovido` exige `pneu_id`

**`ClienteBase` / `ClienteCreate` / `Cliente`**
- `ClienteBase`: `telefone`, `nome`, `documento`, `municipio`, `bairro`
- `Cliente` adiciona: `segmento` ("novo"/"recorrente"/"vip"), `total_pedidos`, `valor_total_gasto`, `ultima_compra_em`
- Esses campos sao atualizados pelo promotor apos cada pedido (sem trigger no banco)

**`PedidoCreate` / `Pedido`**
- Valida: `tipo_entrega != a_confirmar`
- Valida: `forma_pagamento != a_confirmar`
- Valida: `tipo_entrega=entrega` exige `endereco_entrega_json`
- Valida: `valor_total >= 0`
- Campo `valor_frete: Decimal = Decimal("0")` — frete separado do total para auditoria
- Campo `numero_pedido: int` — numero sequencial gerado pelo banco (SERIAL), unico e irrepetivel. Nunca definido pelo codigo — preenchido automaticamente pelo PostgreSQL no INSERT.

**`AreaEntregaBase` / `AreaEntrega`** (`area_entrega.py`)
- `municipio`: nome do municipio (armazenado com acento correto)
- `bairro`: opcional — se preenchido, aplica a bairro especifico; se `NULL`, cobre todo o municipio
- `valor_frete`: preco do frete para esta linha
- `ativo`: permite desativar sem deletar

**`ItemPedidoCreate` / `ItemPedido`**
- Valida: `quantidade >= 1`
- Valida: `preco_unitario >= 0`
- Valida: `subtotal == quantidade * preco_unitario`

**`EstoqueBase` / `Estoque`**
- Valida: `quantidade_disponivel >= 0`
- Valida: `preco_venda >= 0`
- Valida: `reservado >= 0`

**`MotoBase` / `Moto`**
- Valida: `ano_fim >= ano_inicio` quando ambos existirem

**`PneuBase` / `Pneu`**
- Valida: `largura > 0`, `perfil > 0`, `aro > 0` (campos dimensionais NOT NULL)
- `medida` texto mantido para exibicao humana
- `tipo` limitado a `dianteiro`, `traseiro`, `universal` (ou null)

### Schemas JSONB

**`EnderecoEntrega`**
Valida a estrutura do campo `pedido.endereco_entrega_json` antes de persistir.
Campos obrigatorios: `logradouro`, `numero`, `bairro`, `cidade`, `estado`, `cep`.
Campos opcionais: `complemento`, `referencia`.

**`MetadataChat`**
Schema minimo para `mensagem_chat.metadata_json`.
Campos: `provider` (obrigatorio), `message_id_externo`, `payload`.

### Schemas do contrato IA

**`ItemUltimoPedidoContexto`** / **`UltimoPedidoContexto`** (`contexto_executavel.py`)
Historico do ultimo pedido confirmado do cliente, excluindo a sessao atual:
```python
class ItemUltimoPedidoContexto(BaseModel):
    pneu_nome: str
    posicao: Optional[str]
    quantidade: int
    preco_unitario: Decimal

class UltimoPedidoContexto(BaseModel):
    data: datetime
    valor_total: Decimal
    forma_pagamento: str
    tipo_entrega: str
    itens: list[ItemUltimoPedidoContexto]
```

**`ClienteContexto`** (`contexto_executavel.py`)
Expoe inteligencia de negocio do cliente a IA:
```
cliente_id, nome, telefone, resolvido
segmento          → "novo" | "recorrente" | "vip"
total_pedidos     → contagem de pedidos confirmados
valor_total_gasto → soma dos valores
ultima_compra_em  → data do ultimo pedido
municipio, bairro → localidade extraida do historico
ultimo_pedido     → UltimoPedidoContexto ou None
```

**`FreteContexto`** (`contexto_executavel.py`)
Resultado do calculo de frete exposto a IA:
```python
class FreteContexto(BaseModel):
    municipio: str
    coberto: bool          # True = tem frete; False = fora da area de cobertura
    valor_frete: Optional[Decimal] = None  # presente apenas quando coberto=True
    bairro: Optional[str] = None
```

**`ContextoExecutavel`**
Payload completo que o backend monta e entrega a IA a cada turno.

```
sessao              → estado atual, etapa, canal
cliente             → resolvido ou nao, telefone, segmento, historico, ultimo_pedido
bloqueios_ativos    → impedimentos operacionais vigentes
mensagens_recentes  → janela recente da conversa
fatos_ativos        → fatos com evidencia (tipo_de_verdade, nivel_confirmacao, fonte)
resultados_busca_atuais → opcoes do turno atual (nao sao fatos confirmados)
itens_provisorios   → itens em discussao
pendencias          → o que falta para avancar
acoes_permitidas    → lista fechada do que a IA pode propor
resumo_operacional  → tem_item_validado, tem_entrega_definida, tem_pagamento_definido
frete               → FreteContexto calculado (coberto, valor, municipio) ou None
tabela_fretes       → lista [{municipio, valor_frete}] exposta a cada turno — IA responde perguntas de frete sem tool call
config_loja         → dict {chave: valor} com configuracoes operacionais da loja (endereco, horario, montagem, garantia, prazo)
metadados           → gerado_em, versao_contexto
```

**`EnvelopeIA`**
Resposta estruturada que a IA retorna ao backend.

```
mensagem_cliente      → resposta em linguagem natural
etapa_atual           → etapa vigente ou proposta
intencao_atual        → o que o cliente quer
acoes_sugeridas       → lista de acoes propostas (restrita a acoes_permitidas)
pendencias            → lista do que falta
confianca             → alta | media | baixa
fatos_observados      → fatos identificados na mensagem (tipo=observado)
fatos_inferidos       → deducoes com justificativa (tipo=inferido)
mudancas_contexto     → propostas de alteracao de fatos
mudancas_itens        → propostas de criacao/alteracao de itens provisorios
bloqueios_identificados → problemas que impedem avanco
```

---

## Banco de dados (`db/`)

### `exceptions.py`

Excecoes tipadas para todos os repos:

| Excecao | Herda de | Uso |
|---|---|---|
| `RepositoryError` | `Exception` | Base com `operacao`, `tabela`, `detalhe` |
| `RegistroNaoEncontrado` | `RepositoryError` | Busca que falhou |
| `ErroDeInsercao` | `RepositoryError` | Insert que falhou |
| `ErroDeAtualizacao` | `RepositoryError` | Update que falhou |

Todos os 7 repos usam try/except com essas excecoes em todas as funcoes.

### `client.py`

Cliente Supabase inicializado como variavel de modulo.
Auto-detecta proxy do Windows via Registry (`winreg`) e env vars (`HTTPS_PROXY`/`HTTP_PROXY`).
Erros de deteccao de proxy sao logados (nao engolidos silenciosamente).

### `sessao_repo.py`

| Funcao | Descricao |
|---|---|
| `criar_sessao(dados)` | Cria nova sessao com `ultima_interacao_em` automatico |
| `buscar_sessao(sessao_id)` | Retorna `SessaoChat` ou `None` |
| `atualizar_sessao(sessao_id, dados)` | Atualiza campos parciais, toca `atualizado_em` e `ultima_interacao_em` |
| `atualizar_etapa(sessao_id, etapa)` | Atalho: atualiza etapa e define status como `ativa` |
| `registrar_bloqueio(...)` | Define `status_sessao=bloqueada` com motivo explicito |
| `resolver_cliente_na_sessao(sessao_id, cliente_id)` | Vincula cliente resolvido a sessao |
| `fechar_sessao(sessao_id)` | Define `status_sessao=fechada` |

### `mensagem_repo.py`

| Funcao | Descricao |
|---|---|
| `registrar_mensagem(dados)` | Insere mensagem generica |
| `registrar_mensagem_entrada(...)` | Atalho para mensagem de cliente (`direcao=entrada`, `remetente=cliente`) |
| `registrar_mensagem_saida(...)` | Atalho para mensagem do agente (`direcao=saida`, `remetente=agente`) |
| `buscar_mensagens_recentes(sessao_chat_id)` | Retorna janela limitada em ordem cronologica |

### `contexto_repo.py`

| Funcao | Descricao |
|---|---|
| `registrar_fato(dados)` | Desativa fato anterior (mesma chave+escopo) e insere novo. Garante apenas um fato ativo por escopo. |
| `buscar_fatos_ativos(sessao_chat_id, item_provisorio_id?)` | Retorna todos os fatos com `ativo=True` da sessao |
| `buscar_fato_por_chave(sessao_chat_id, chave, item_provisorio_id?)` | Retorna fato ativo de uma chave especifica |

O escopo e definido por `sessao_chat_id + chave + item_provisorio_id` (quando houver item).

### `item_provisorio_repo.py`

| Funcao | Descricao |
|---|---|
| `criar_item(dados)` | Cria novo item provisorio |
| `buscar_item(item_id)` | Busca por ID |
| `buscar_itens_da_sessao(sessao_chat_id, status?)` | Lista itens, filtravel por status |
| `atualizar_item(item_id, dados)` | Atualizacao parcial com `atualizado_em` automatico |
| `confirmar_item(item_id)` | Define `status=selecionado_cliente` e `cliente_confirmou_em` |
| `validar_item_backend(item_id)` | Valida item antes de marcar `status=validado`: verifica pneu existe, preco > 0, estoque suficiente. Levanta `ValueError` se falhar. |
| `promover_item(item_id)` | Define `status=promovido` (so chamado pelo promotor) |
| `rejeitar_item(item_id)` | Define `status=rejeitado` |

### `cliente_repo.py`

| Funcao | Descricao |
|---|---|
| `buscar_por_telefone(telefone)` | Busca cliente por telefone |
| `criar_cliente(dados)` | Cria cliente com dados minimos |
| `resolver_ou_criar(telefone, nome?)` | Retorna existente ou cria novo |
| `buscar_por_id(cliente_id)` | Busca by UUID |

### `catalogo_repo.py`

| Funcao | Descricao |
|---|---|
| `buscar_pneu_por_id(pneu_id)` | Busca pneu ativo por ID |
| `buscar_pneus_por_medida(medida)` | Busca pneus ativos com medida exata |
| `buscar_pneus_por_marca_modelo(marca, modelo)` | Busca aproximada via `ilike` |
| `buscar_estoque_por_pneu(pneu_id)` | Retorna registro de estoque (1 por pneu no V1) |
| `buscar_pneus_com_estoque(medida?)` | Retorna pneus com estoque disponivel (JOIN com estoque) |
| `buscar_por_dimensoes(largura?, perfil?, aro?, tipo?)` | Busca dimensional em `catalogo_agente` |
| `buscar_compatibilidade_moto(moto_id)` | Busca na view `compatibilidade_moto_pneu` por moto |
| `buscar_compatibilidade_texto(texto)` | Busca fuzzy na view `compatibilidade_moto_pneu` por texto (pg_trgm) |
| `buscar_medidas_da_moto(moto_id)` | Retorna medidas da moto em `medida_moto` |
| `buscar_moto_por_id(moto_id)` | Busca moto por ID |
| `buscar_motos(marca?, modelo?)` | Busca motos com filtros opcionais |

### `pedido_repo.py`

| Funcao | Descricao |
|---|---|
| `criar_pedido(dados)` | Cria pedido oficial |
| `buscar_pedido_da_sessao(sessao_chat_id)` | Retorna o pedido da sessao (max 1 no V1) |
| `buscar_pedido_por_id(pedido_id)` | Busca by UUID |
| `criar_item_pedido(dados)` | Cria item oficial do pedido |
| `buscar_itens_pedido(pedido_id)` | Lista itens de um pedido |
| `fechar_sessao(sessao_id)` | Fecha sessao administrativamente (timeout). Wrapper semantico sobre `atualizar_status(..., fechada)`. Distinto do fechamento via RPC de pedido. |
| `cancelar_pedido(pedido_id)` | UPDATE status_pedido=cancelado |
| `atualizar_pedido(pedido_id, campos)` | UPDATE parcial dos campos editaveis |
| `buscar_ultimo_pedido_confirmado(cliente_id, excluir_sessao_id?)` | Historico do cliente |

### `area_entrega_repo.py`

| Funcao | Descricao |
|---|---|
| `consultar_frete(municipio, bairro?)` | Retorna `Decimal` com o frete ou `None` se nao coberto. Busca todos os registros ativos e filtra em Python com normalizacao de acentos. Prioridade: bairro exato > municipio inteiro |
| `listar_municipios_ativos()` | Lista municipios com linha `bairro IS NULL` ativa |
| `buscar_tabela_fretes()` | Retorna `list[dict]` com `{municipio, valor_frete}` de todas as linhas ativas sem bairro especifico. Exposta no `ContextoExecutavel.tabela_fretes` a cada turno — IA responde perguntas de frete proativamente sem nova consulta ao banco |

**Funcao interna `_normalizar(texto)`**: Remove acentos (NFD + ASCII) e converte para minusculo. Permite que `"sao goncalo"` encontre `"Sao Goncalo"` no banco.

### `config_loja_repo.py`

| Funcao | Descricao |
|---|---|
| `buscar_config_loja()` | Retorna `dict[str, str]` com todas as chaves ativas da tabela `config_loja`. Exposta no `ContextoExecutavel.config_loja` a cada turno — IA responde perguntas operacionais (endereco, horario, montagem, garantia) sem inventar. Retorna `{}` em caso de erro (fail safe). |

---

## Tabelas, Views e Extensoes

### Extensoes habilitadas

- `pg_trgm`: busca por similaridade textual (ex.: "pireli" encontra "Pirelli")
- `unaccent`: ignora acentos na busca textual

### TABELA `area_entrega`

Cobertura geografica e precos de frete da loja.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `id` | UUID | PK gerado automaticamente |
| `municipio` | TEXT NOT NULL | Nome do municipio com acento correto |
| `bairro` | TEXT | NULL = cobre todo o municipio; preenchido = regra especifica por bairro |
| `valor_frete` | NUMERIC(10,2) | Preco do frete. CHECK >= 0 |
| `ativo` | BOOLEAN DEFAULT TRUE | Permite desativar sem deletar |
| `criado_em` | TIMESTAMPTZ | Automatico |

**Logica de lookup (feita em Python no `area_entrega_repo`):**
1. Filtra por municipio (normalizacao: sem acento, minusculo)
2. Prioridade 1: linha com `bairro` = bairro informado
3. Prioridade 2: linha com `bairro IS NULL`
4. Se nenhuma encontrada: retorna `None` (nao coberto)

### TABELA `config_loja`

Configuracoes operacionais da loja expostas para a IA.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `chave` | TEXT PK | Identificador unico da configuracao |
| `valor` | TEXT NOT NULL | Valor da configuracao em texto livre |
| `descricao` | TEXT | Documentacao interna do proposito da chave |
| `ativo` | BOOLEAN DEFAULT TRUE | Permite desativar sem deletar |

**Chaves pre-cadastradas:**

| Chave | Exemplo de valor |
|-------|-----------------|
| `endereco` | Av. Dr. Eugenio Borges, 3990 - Rio do Ouro, Sao Goncalo - RJ |
| `horario_funcionamento` | Segunda a Sexta das 9h as 17h. Sabado das 9h as 15h. |
| `faz_montagem` | true |
| `politica_montagem` | Montagem gratis pra quem compra pneu acima de R$180. Abaixo disso cobra R$15. |
| `garantia_descricao` | A gente confere o pneu na hora de montar. Depois que montou e saiu certo, a garantia da montagem encerrou. |
| `prazo_entrega_descricao` | Seu pneu chega no dia seguinte depois que o pedido for confirmado. |
| `emite_nota_fiscal` | false |
| `telefone_atendimento_humano` | 21976674264 |

**Como atualizar:** edite diretamente no Supabase. Nenhuma alteracao de codigo necessaria.

### VIEW `catalogo_agente`

Visao plana de `pneu` + `estoque`:

| Coluna | Origem |
|---|---|
| `pneu_id`, `pneu_marca`, `pneu_modelo`, `medida`, `largura`, `perfil`, `aro`, `pneu_tipo`, `descricao_comercial` | `pneu` |
| `preco_venda`, `quantidade_disponivel`, `reservado` | `estoque` |
| `disponivel_real` | calculado: `quantidade_disponivel - reservado` |
| `ativo` | `pneu` |

Usada para qualquer busca dimensional ou por marca/modelo de pneu.

### VIEW `compatibilidade_moto_pneu`

Cruzamento completo moto → medida → pneu → estoque:

| Coluna | Origem |
|---|---|
| `moto_id`, `moto_marca`, `moto_modelo`, `moto_versao`, `moto` | `moto` |
| `posicao`, `largura`, `perfil`, `aro` | `medida_moto` |
| `pneu_id`, `pneu`, `pneu_marca` | `pneu` (LEFT JOIN, pode ser null) |
| `preco_venda`, `disponivel_real` | `estoque` (LEFT JOIN, pode ser null) |

Usada quando o cliente informa a moto. Retorna pneus compativeis ou null quando nao ha pneu para a medida no catalogo.

### RPCs

**`buscar_pneu_por_texto(termo_busca)`** — Busca por similaridade em `descricao_comercial`, `marca`, `modelo` com pg_trgm + ILIKE. Limite 10. Indice GIN.

**`buscar_moto_por_texto(termo_busca)`** — Busca por similaridade em `descricao_resolvida`, `marca`, `modelo` com pg_trgm + ILIKE. Limite 10. Indice GIN.

**`promover_para_pedido(p_sessao_id, p_cliente_id, p_tipo_entrega, p_forma_pagamento, p_valor_total, p_endereco_json, p_itens)`** — RPC transacional (plpgsql). Recebe itens como JSON array. Numa unica transacao: cria pedido, cria item_pedido para cada item, marca item_provisorio como promovido, fecha sessao. Se qualquer passo falhar, rollback automatico.

### Indexes otimizados

- `idx_pneu_dimensoes`: `(largura, perfil, aro)` em `pneu`
- `idx_pneu_aro`: `(aro)` em `pneu`
- `idx_pneu_tipo`: `(tipo)` em `pneu` onde tipo nao e null
- `idx_pneu_marca_trgm`, `idx_pneu_modelo_trgm`: trigram GIN em `pneu`
- `idx_moto_descricao_trgm`, `idx_moto_marca_trgm`, `idx_moto_modelo_trgm`: trigram GIN em `moto`
- `idx_medida_moto_dimensoes`: `(largura, perfil, aro)` em `medida_moto`
- `idx_medida_moto_moto`: `(moto_id)` em `medida_moto`

---

## Engine (`engine/`)

### `maquina_estados.py`

Mapa de transicoes permitidas no fluxo V1:

```
identificacao     → busca
busca             → oferta, identificacao (retorno por ambiguidade)
oferta            → confirmacao_item, busca (retorno por mudanca de criterio)
confirmacao_item  → entrega_pagamento, oferta (retorno por rejeicao),
                    busca (adicionar_outro_item: cliente quer mais pneus)
entrega_pagamento → fechamento, confirmacao_item (retorno por mudanca),
                    busca (adicionar_outro_item: cliente lembrou de outro pneu)
fechamento        → (estado terminal, sem transicoes)
```

Funcoes:
- `transicao_permitida(atual, destino) -> bool`
- `motivo_bloqueio(atual, destino) -> str`
- `proximas_etapas(atual) -> list[EtapaFluxo]`
- `e_etapa_terminal(etapa) -> bool`

### `pendencias.py`

Define o conjunto fechado de acoes por etapa (`ACOES_POR_ETAPA`) e as pendencias estruturais (`PENDENCIAS_POR_ETAPA`).

Acoes notaveis por etapa:

| Etapa | Acoes |
|---|---|
| `identificacao` | pedir_clarificacao_moto/medida/posicao, buscar_por_moto/medida, registrar_fato_observado, responder_incerteza_segura |
| `busca` | buscar_por_moto/medida, buscar_medida_proxima, pedir_clarificacao, registrar_opcoes_encontradas |
| `oferta` | apresentar_opcoes, explicar_falta, pedir_escolha_cliente |
| `confirmacao_item` | confirmar_item, registrar_quantidade/posicao, rejeitar_item, **adicionar_outro_item**, **finalizar_itens** |
| `entrega_pagamento` | perguntar_tipo_entrega/endereco/forma_pagamento, registrar_entrega/pagamento, **adicionar_outro_item** |
| `fechamento` | revisar_pedido, converter_em_pedido |

- **`adicionar_outro_item`** — cliente quer mais pneus; aciona limpeza de contexto de busca anterior no orquestrador e transita para `busca`
- **`finalizar_itens`** — cliente confirmou que nao quer mais itens; registra fato `itens_finalizados=true` para observabilidade

Funcoes:
- `acoes_permitidas(etapa) -> list[str]` — usado pelo montador para preencher `acoes_permitidas` do contexto
- `pendencias_da_etapa(etapa) -> list[Pendencia]` — pendencias estaticas da etapa

### `sessao_timeout.py`

Logica de classificacao de timeout isolada do orquestrador. Nao faz escrita no banco — apenas classifica.

**Constantes configuráveis:**
- `TIMEOUT_SESSAO_DIAS = 7` — dias sem interacao para expirar
- `TIMEOUT_BLOQUEADA_HORAS = 2` — horas para desbloquear sessao travada por erro tecnico

**`SituacaoSessao`** (enum):

| Valor | Significado |
|---|---|
| `ok` | Sessao normal, nenhuma acao necessaria |
| `bloqueada_antiga` | Bloqueada por erro tecnico ha mais de 2h — desbloquear |
| `expirada_com_contexto` | Inativa 7+ dias em etapa com contexto valioso (oferta em diante) |
| `expirada_sem_contexto` | Inativa 7+ dias em etapa inicial (identificacao/busca) |

**`avaliar_sessao(sessao) -> SituacaoSessao`**
Recebe um `SessaoChat` e retorna a situacao. Pura (sem efeitos colaterais). Sessoes ja fechadas retornam `ok` por seguranca.

### `montador_contexto.py`

Funcao principal: `montar_contexto(sessao_id) -> ContextoExecutavel`

Executa 11 passos em sequencia:
1. Busca sessao (levanta `ValueError` se nao encontrar)
2. Busca e monta dados do cliente
3. Busca mensagens recentes e converte para `MensagemRecente`
4. Busca fatos ativos, carrega `resultados_busca_atuais` de fatos internos (`_resultados_busca`), filtra fatos com prefixo `_` do payload visivel a IA
5. Busca itens provisorios e converte para `ItemProvisorioContexto`
6. Calcula bloqueios ativos a partir do status da sessao
7. Calcula pendencias dinamicas baseadas no estado real (chaves presentes, itens validados, endereco)
8. Calcula acoes permitidas para a etapa atual
9. Calcula resumo operacional (`tem_item_validado`, `tem_entrega_definida`, `tem_pagamento_definido`, `pode_avancar_etapa`)
10. Popula `frete` (FreteContexto), `tabela_fretes` e `config_loja`
11. Monta e retorna `ContextoExecutavel` completo

**Calculo dinamico de pendencias** — vai alem das pendencias estaticas:
- `identificacao`: verifica se moto ou medida foi informada
- `entrega_pagamento`: verifica `tipo_entrega`, `forma_pagamento` e `endereco_entrega` (quando entrega)
- `confirmacao_item`: verifica se existe item com `status=validado` e `pneu_id`
- `fechamento`: verifica item valido para conversao

### `validador_envelope.py`

Funcao: `validar_envelope(envelope, contexto) -> list[str]`

Retorna lista de erros. Lista vazia = envelope valido. Backend nunca aplica mudancas com erros.

7 regras validadas:
1. `acoes_sugeridas` devem estar em `acoes_permitidas` do contexto
2. `etapa_atual` do envelope deve ser igual ou transicao valida da etapa atual
3. `fatos_observados` nao podem ter chave vazia ou valor nulo
4. `fatos_inferidos` devem ter `justificativa` nao vazia
5. `mudancas_itens` com `item_provisorio_id` devem referenciar item existente no contexto
6. `confianca` deve ser `alta`, `media` ou `baixa`
7. `mensagem_cliente` nao pode ser vazia
8. **Fase 9:** `mudancas_itens` com `acao=atualizar` e `dados.status_item=promovido` sao rejeitadas (exclusividade do promotor)

### `promotor.py`

**`ErroPromocao`** — excecao levantada quando qualquer pre-condicao falha.

**`_calcular_segmento(total_pedidos, valor_total) -> str`**
Regra de negocio de segmentacao:
- 0 pedidos → `"novo"`
- 1-4 pedidos e valor < R$500 → `"recorrente"`
- 5+ pedidos OU valor >= R$500 → `"vip"`

**`_atualizar_stats_cliente(cliente_id, valor_pedido)`**
Chamada apos cada pedido criado. Incrementa `total_pedidos`, `valor_total_gasto`, `ultima_compra_em` e recalcula `segmento` via `_calcular_segmento`. Sem trigger no banco — logica 100% no Python.

**`cancelar_pedido_sessao(sessao_id) -> bool`**
Cancela o pedido da sessao, libera estoque reservado e reverte stats do cliente.
1. Busca pedido da sessao; retorna `False` se nao encontrar ou ja cancelado
2. Chama `pedido_repo.cancelar_pedido()` → `status_pedido=cancelado`
3. Para cada `item_pedido`: chama `catalogo_repo.decrementar_reservado()` (RPC atomica)
4. Reverte `total_pedidos`, `valor_total_gasto` e `segmento` do cliente

**`alterar_pedido_sessao(sessao_id) -> bool`**
Sincroniza `forma_pagamento`, `tipo_entrega` e `endereco_entrega_json` do pedido com os fatos ativos da sessao. So age em pedidos com `status_pedido=confirmado`. Retorna `True` se algum campo foi alterado. Chamado pelo orquestrador no passo 8b.

**`validar_pre_condicoes(sessao_id) -> list[str]`**
Retorna lista de erros. Lista vazia = pode promover. Chamada pelo orquestrador na auto-promocao (passo 12).

**`promover_para_pedido(sessao_id) -> Pedido`**

Levanta `ErroPromocao` se qualquer pre-condicao falhar. **Nenhuma escrita ocorre antes de todas as pre-condicoes passarem.**

Pre-condicoes (7):
1. `sessao.etapa_atual == fechamento`
2. `sessao.cliente_id` existe (cliente resolvido)
3. Pelo menos um `item_provisorio` com `status=selecionado_cliente` ou `validado` e `pneu_id`
4. Fato `tipo_entrega` existe no contexto e nao e `a_confirmar`
5. Fato `forma_pagamento` existe no contexto e nao e `a_confirmar`
6. Se `tipo_entrega=entrega`: fato `endereco_entrega` existe E fato `frete_nao_coberto` nao existe. O promotor tenta `valor_json` primeiro; se ausente, usa `valor_texto` embrulhado em `{"endereco": valor_texto}`
7. Estoque suficiente E `preco_unitario_sugerido > 0` para cada item validado

Processo (apos todas as pre-condicoes):
1. Le fato `frete_valor` do contexto (apenas para entregas); default `Decimal("0")`
2. Calcula `valor_itens` somando `preco_unitario_sugerido * quantidade` de cada item validado
3. Calcula `valor_total = valor_itens + valor_frete`
4. Chama RPC `promover_para_pedido` no Supabase — **transacao atomica**:
   - Cria `pedido` com `valor_total` e `valor_frete` separados
   - Para cada item: cria `item_pedido` com preco e quantidade congelados
   - Marca cada `item_provisorio` como `promovido`
   - Fecha a sessao (`status_sessao=fechada`)
   - Se qualquer passo falhar, **nada e persistido** (rollback automatico)
5. Para cada item promovido: chama `catalogo_repo.incrementar_reservado()` (RPC atomica)
6. Chama `_atualizar_stats_cliente()` para atualizar historico do cliente
7. Retorna `Pedido` criado

### `orquestrador.py`

Funcao principal: `processar_turno(sessao_id, mensagem_texto, criado_em?, message_id_externo?) -> str`

Retorna a mensagem em linguagem natural para enviar ao cliente.

Passos em sequencia:
0. **Resolver timeout da sessao** — `_resolver_timeout(sessao)`: avalia `avaliar_sessao()` e age conforme o resultado. Se bloqueada antiga: desbloqueia. Se expirada: fecha sessao antiga e cria nova com mesmo `canal`/`contato_externo`. Retorna o `sessao_id` correto para todos os passos seguintes. Nunca levanta excecao — em caso de falha retorna o `sessao_id` original (fail safe).
1. **Persistir mensagem de entrada** em `mensagem_chat`
2. **Resolver cliente** automaticamente se sessao tem `contato_externo` mas nao tem `cliente_id`
3. **Montar `ContextoExecutavel`** completo do turno
4+5. **Chamar IA + parsear/validar** (GPT-4o com function calling e `response_format=json_object`) — **retry ate 2x**. No retry, envia mensagem de correcao com erros anteriores, acoes validas e etapas permitidas. Se falhar apos 3 tentativas, retorna resposta de falha segura sem mudar o banco.
5b. **Guardrail** — `_aplicar_guardrail(envelope, etapa_atual)`: detecta e corrige acoes conflitantes antes de qualquer processamento. Regra principal: se `confirmar_item + adicionar_outro_item` no mesmo turno, remove `adicionar_outro_item` e reverte etapa se foi para `busca`.
6. **Aplicar `fatos_observados`** como `tipo=observado` no `contexto_conversa`
7. **Aplicar `fatos_inferidos`** como `tipo=inferido` no `contexto_conversa`
7b. **Persistir nome do cliente** — se fato `nome_cliente` foi registrado neste turno e o cliente ainda nao tem nome, chama `cliente_repo.atualizar_cliente`
7c. **Cancelamento** — se fato `pedido_cancelamento_solicitado` ativo, chama `cancelar_pedido_sessao()` e desativa o fato (idempotente)
8. **Aplicar `mudancas_contexto`** como `tipo=inferido` no `contexto_conversa`
8b. **Sincronizar pedido existente** — se `etapa == fechamento` e ja existe pedido confirmado, chama `alterar_pedido_sessao()` para refletir mudancas de entrega/pagamento/endereco
8c. **Consultar e registrar frete** — `_consultar_e_registrar_frete(sessao_id)`: executa apenas se `tipo_entrega=entrega` e ha municipio; idempotente (nao recalcula se fato ja existe); registra `frete_valor` ou `frete_nao_coberto`
9. **Aplicar `mudancas_itens`** em `item_provisorio` (criar, confirmar, rejeitar, cancelar, atualizar). Ao criar: valida UUID; se valido, item nasce com `status=selecionado_cliente`; se ausente/invalido, auto-enriquece dos resultados de tool (match por posicao ou pneu unico) e auto-preenche `preco_unitario_sugerido`. Bloqueia `status_item=promovido` via `atualizar`.
10. **Despachar `acoes_sugeridas`** — a maioria sao semanticas. Acoes com logica backend: `converter_em_pedido` (promotor), `adicionar_outro_item` (limpa fatos de busca anterior), `finalizar_itens` (registra fato de observabilidade)
11. **Avaliar transicao de etapa**: se valida, atualiza `sessao_chat.etapa_atual`; se invalida, registra bloqueio na sessao
12. **Auto-promocao em fechamento** — se `etapa == fechamento` e `converter_em_pedido` nao foi emitido, verifica `validar_pre_condicoes()`. Se todas passam, chama `promover_para_pedido()` automaticamente. Elimina necessidade de mensagem extra do cliente.
13. **Montar mensagem final** — se um pedido foi criado neste turno (passo 10 ou 12), substitui `envelope.mensagem_cliente` pela confirmacao formatada de `_montar_confirmacao_pedido()`. Caso contrario, usa a mensagem da IA normalmente. A confirmacao inclui numero do pedido, itens com nomes reais, entrega, frete, total, pagamento e data real calculada por `_calcular_prazo_entrega()` (pula domingo, sabado ok).
14. **Persistir mensagem de saida** em `mensagem_chat`
15. **Retornar** mensagem final ao canal

**Retry:** GPT-4o tende a pular etapas quando tem informacao suficiente. O retry com re-prompt (incluindo erros, acoes validas e etapas permitidas) corrige o comportamento em 1-2 tentativas. **Fase 9:** `_chamar_e_validar` retorna `(envelope, pneus_encontrados)` — acumula pneus de todas as tentativas.

**Logging:** Todas as falhas (parse, validacao, transicao bloqueada, promocao) sao registradas via `logging` com nivel `WARNING` ou `ERROR`. Execucoes de tools e pedidos criados sao registrados com nivel `INFO`.

---

## Tools (`tools/`)

### `busca_catalogo.py`

**`buscar_por_medida(medida) -> list[ResultadoBusca]`**
Busca pneus ativos com medida exata. Retorna preco e estoque disponivel (descontando reservas).
`compatibilidade_status = "nao_validada"` — a IA nao pode afirmar compatibilidade.

**`buscar_por_dimensoes(largura?, perfil?, aro?, tipo?) -> list[ResultadoBusca]`**
Busca dimensional na VIEW `catalogo_agente`. Aceita qualquer combinacao parcial de dimensoes.
Permite queries como "aro 17 dianteiro" sem parsing de texto.

**`buscar_por_moto(marca, modelo) -> list[ResultadoBusca]`**
Busca motos no catalogo e cruza com a VIEW `compatibilidade_moto_pneu`.
Retorna pneus compativeis com preco e estoque, ou null quando nao houver pneu para a medida.
Usa `pg_trgm` para busca fuzzy que tolera typos.

### `consulta_estoque.py`

**`consultar_disponibilidade(pneu_id) -> Optional[Estoque]`**
Retorna estoque ou `None`. `None` deve ser interpretado como "nao foi possivel confirmar", nao como "sem estoque".

**`disponivel_para_quantidade(pneu_id, quantidade) -> bool`**
Verifica disponibilidade real considerando `quantidade_disponivel - reservado >= quantidade`.

### `resolve_cliente.py`

**`resolver_cliente(telefone, sessao_id, nome?) -> Cliente`**
Busca cliente por telefone. Se nao existir, cria com dados minimos.
Apos resolver, vincula `cliente_id` a sessao automaticamente via `resolver_cliente_na_sessao`.

---

## Integracao com IA (`ia/`)

### `prompt_sistema.py`

System prompt com:
- Identidade do agente (especialista em pneus de moto da 2W Pneus)
- 8 regras absolutas (nunca inventar, nunca pular etapas, nunca promover sem validacao, sempre em PT-BR)
- Descricao do contexto que o agente recebe
- Descricao exata do JSON que o agente deve retornar
- Regras do envelope de saida
- Exemplos de respostas de incerteza segura
- **Fase 8:** Nota explicita que `buscar_pneus` e `buscar_pneus_por_moto` retornam `pneu_id` UUID e que ele deve ser guardado para `mudancas_itens`
- **Fase 8:** Secao "Regras para mudancas_itens" com exemplos concretos de criar, confirmar, atualizar item e lista dos valores validos de `status_item` (NUNCA "confirmado")
- **Fase 8:** Regra critica de registrar `tipo_entrega` e `forma_pagamento` em `fatos_observados` no mesmo turno em que o cliente informa
- **Fase 8:** Regra critica de que `pneu_id` deve ser o UUID real da tool, nunca um placeholder
- **Fase 9:** Exemplo de `mudancas_itens` usa UUID com formato real em vez de placeholder textual toxico
- **Fase 9:** Toda mencao ao texto `"UUID-EXATO-RETORNADO-PELA-TOOL"` removida do prompt
- **Fase 17:** Regra 5 adicionada em `# REGRAS DE NEGOCIO`: usar apenas `config_loja` para dados operacionais, nunca inventar
- **Fase 17:** Nova secao `# INFORMACOES DA LOJA`: instrui o Ze a usar cada chave de `config_loja` para responder perguntas operacionais (endereco, horario, montagem, garantia, prazo, NF). Inclui regra de fallback e retorno ao fluxo apos responder

### `parser_envelope.py`

**`parsear_envelope(texto_resposta) -> EnvelopeIA`**

Estrategia de parse em 2 tentativas:
1. Parse direto do texto como JSON
2. Extrai bloco `\`\`\`json ... \`\`\`` do markdown e faz parse

Levanta `ErroParserEnvelope` com detalhes se ambas falharem.
Nunca retorna envelope parcial.

### `agente.py`

**`chamar_agente(contexto, mensagem_usuario) -> tuple[str, list[dict]]`**

Serializa `ContextoExecutavel` como JSON compacto.
Monta mensagens (system prompt + contexto + mensagem do cliente).
Chama GPT-4o via `openai.OpenAI()` com:
- `response_format={"type": "json_object"}` — forca saida JSON pura
- `tools=TOOLS_SCHEMA` — 5 tools para function calling (buscar_pneus, buscar_pneus_por_moto, buscar_detalhes_pneu, consultar_estoque, resolver_cliente)
- `tool_choice="auto"` — IA decide quando chamar tools
- `timeout=30s` — evita chamadas penduradas
- **Retry com backoff exponencial** (via `tenacity`) para `RateLimitError`, `APITimeoutError`, `APIConnectionError` (3 tentativas, 2-30s)

Loop de ate 5 rounds de tool calls. Cada tool call e despachada automaticamente via `_TOOL_DISPATCH`.

**Fase 9:** Retorna tupla `(envelope_texto, pneus_encontrados)` em vez de apenas string. Durante o loop de tool calls, `_extrair_pneus_de_resultado()` parseia o JSON de cada resultado e coleta `pneu_id`, `posicao` e `preco_venda`. Esses dados sao usados pelo orquestrador para auto-enriquecimento quando a IA nao propaga o UUID corretamente.

---

## Ponto de entrada (`main.py`)

CLI interativo para testes manuais.

```bash
# nova sessao
python -m agente_2w.main

# retomar sessao existente
python -m agente_2w.main --sessao <uuid>

# definir contato
python -m agente_2w.main --contato 5521999999999
```

Valida configuracao antes de iniciar. Cria ou retoma sessao. Loop de conversa via `input()` com saida via `sair`.

---

## Fluxo completo de um turno

```
Cliente envia mensagem
        │
        ▼
[orquestrador] processar_turno()
        │
        ├─ 0. [timeout] _resolver_timeout()
        │   ├─ ok -> segue com mesmo sessao_id
        │   ├─ bloqueada_antiga -> desbloqueia, segue com mesmo sessao_id
        │   └─ expirada -> fecha antiga, cria nova, segue com novo sessao_id
        │
        ├─ 1. persiste mensagem de entrada (mensagem_chat)
        │
        ├─ 2. resolve cliente automaticamente (se contato sem cliente_id)
        │
        ├─ 3. [montador_contexto] montar_contexto()
        │   ├─ busca sessao, cliente, mensagens, fatos, itens
        │   ├─ popula cliente.ultimo_pedido (historico)
        │   ├─ popula frete (FreteContexto), tabela_fretes e config_loja
        │   ├─ calcula bloqueios, pendencias, acoes, resumo
        │   └─ retorna ContextoExecutavel completo
        │
        ├─ 4+5. [agente] chamar_ia → [parser/validador] com retry ate 2x
        │
        ├─ 5b. [guardrail] _aplicar_guardrail()
        │   └─ remove adicionar_outro_item se conflita com confirmar_item
        │
        ├─ 6. aplica fatos_observados → contexto_conversa (tipo=observado)
        ├─ 7. aplica fatos_inferidos → contexto_conversa (tipo=inferido)
        │
        ├─ 7b. persiste nome do cliente se registrado neste turno
        │
        ├─ 7c. cancelamento — se fato pedido_cancelamento_solicitado ativo:
        │   └─ cancelar_pedido_sessao() → cancela + libera estoque + reverte stats
        │
        ├─ 8. aplica mudancas_contexto → contexto_conversa (tipo=inferido)
        │
        ├─ 8b. sincroniza pedido existente (se fechamento)
        │   └─ alterar_pedido_sessao() → atualiza entrega/pagamento/endereco
        │
        ├─ 8c. consulta e registra frete (se entrega + municipio disponivel)
        │   └─ _consultar_e_registrar_frete() → frete_valor ou frete_nao_coberto
        │
        ├─ 9. aplica mudancas_itens → item_provisorio
        │   ├─ criar: auto-enriquece pneu_id e preco dos resultados de tool
        │   └─ atualizar: bloqueia status_item=promovido
        │
        ├─ 10. [dispatcher] despacha acoes_sugeridas
        │   ├─ converter_em_pedido → [promotor] promover_para_pedido()
        │   ├─ adicionar_outro_item → limpa fatos de busca anterior
        │   └─ finalizar_itens → registra fato itens_finalizados
        │
        ├─ 11. [maquina_estados] avalia transicao de etapa
        │   ├─ transicao valida → atualiza sessao_chat.etapa_atual
        │   └─ transicao invalida → registra bloqueio na sessao
        │
        ├─ 12. auto-promocao em fechamento (se pre-condicoes ok e nao ja promoveu)
        │
        ├─ 13. persiste mensagem de saida (mensagem_chat)
        │
        └─ 14. retorna mensagem_cliente para o canal
```

---

## Fluxo de fechamento (promocao para pedido)

```
IA sugere acao "converter_em_pedido" no envelope
(ou auto-promocao no passo 12 do orquestrador)
        │
        ▼
[promotor] promover_para_pedido()
        │
        ├─ validar_pre_condicoes():
        │   ├─ etapa == fechamento
        │   ├─ cliente_id existe
        │   ├─ item_provisorio com status=selecionado_cliente|validado e pneu_id
        │   ├─ fato tipo_entrega != a_confirmar
        │   ├─ fato forma_pagamento != a_confirmar
        │   ├─ (se entrega) endereco_entrega existe + frete_nao_coberto ausente
        │   └─ estoque suficiente e preco > 0 para cada item
        │
        ├─ [TODAS PASSARAM]
        │
        ├─ le fato frete_valor (apenas se tipo_entrega=entrega)
        ├─ calcula valor_itens + valor_frete = valor_total
        │
        ├─ RPC transacional promover_para_pedido:
        │   ├─ cria pedido (valor_total e valor_frete separados)
        │   ├─ para cada item: cria item_pedido (preco e qtd congelados)
        │   ├─ marca cada item_provisorio como promovido
        │   └─ fecha sessao (status_sessao=fechada)
        │
        ├─ para cada item promovido: incrementar_reservado() (RPC atomica)
        │
        ├─ _atualizar_stats_cliente():
        │   ├─ total_pedidos++, valor_total_gasto += valor_total
        │   └─ segmento recalculado (novo/recorrente/vip)
        │
        └─ retorna Pedido criado
```

---

## Politica de falha segura

O sistema prioriza confiabilidade sobre completude.

| Situacao | Comportamento |
|---|---|
| IA retorna JSON invalido (`ErroParserEnvelope`) | Resposta padrao de falha segura, banco nao e alterado |
| Envelope invalido (erros de validacao) | Resposta padrao de falha segura, banco nao e alterado |
| Transicao de etapa invalida | Bloqueio registrado na sessao, nenhuma transicao ocorre |
| Pre-condicao do promotor nao atendida | `ErroPromocao` levantado, pedido nao e criado |
| Estoque insuficiente no fechamento | `ErroPromocao`, pedido nao e criado |
| Item sem preco definido no fechamento | `ErroPromocao`, pedido nao e criado (preco None ou <= 0) |
| `validar_item_backend` com pneu/preco/estoque invalido | `ValueError`, item nao e marcado como validado |
| Sessao nao encontrada | `ValueError` explicito |

---

## Como rodar pela primeira vez

1. Copiar `.env.example` para `.env` e preencher as chaves:

```env
SUPABASE_URL=https://vyxdquwxmgibpkoswxut.supabase.co
SUPABASE_KEY=sua_service_role_key
OPENAI_API_KEY=sua_chave_openai
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Garantir que o banco `betaAgente` no Supabase esta com o schema aplicado (arquivo `2w_pneus_v1_initial.sql` + correcoes pos-auditoria documentadas em `contrato_relacional_v1.md` secao 6).

4. Executar o agente em modo manual:

```bash
python -m agente_2w.main
# ou via launcher (Windows):
agente.bat
agente.bat --sessao <uuid>
agente.bat --contato 5521999999999
```

---

## Dependencias

```
pydantic>=2.0,<3.0
pydantic-settings>=2.0,<3.0
supabase>=2.0,<3.0
openai>=1.0,<2.0
python-dotenv>=1.0,<2.0
```

---

## Fase 8 — Correcoes E2E (2026-03-29)

Apos o primeiro teste real completo via CLI, 6 bugs foram identificados e corrigidos.

### Bugs corrigidos

| Bug | Causa raiz | Arquivo | Correcao |
|---|---|---|---|
| `item_provisorio.pneu_id = NULL` | IA nao sabia que devia incluir pneu_id UUID em mudancas_itens | `prompt_sistema.py` | Secao "Regras para mudancas_itens" com exemplo explicito |
| Item nunca chegava ao status `validado` para a promocao | Promotor so aceitava `status=validado`, mas fluxo parava em `selecionado_cliente` | `promotor.py` | Promotor agora aceita `selecionado_cliente` OU `validado` |
| IA usava `"confirmado"` como status_item | Valor invalido no enum `StatusItemProvisorio` | `prompt_sistema.py` | Lista de valores validos documentada; "NUNCA confirmado" explicitado |
| Loop perguntando entrega/pagamento repetidamente | IA registrava com `registrar_entrega` (semantica) mas nao populava `fatos_observados` | `prompt_sistema.py` | Regra critica: registrar no mesmo turno em `fatos_observados` |
| `badly formed hexadecimal UUID string` | IA usava o texto de placeholder do exemplo como pneu_id | `orquestrador.py` + `prompt_sistema.py` | Validacao UUID no codigo; aviso no prompt |
| `pedido_endereco_entrega_chk` constraint violation | Promotor so lia `valor_json`, mas endereco estava em `valor_texto` | `promotor.py` | Fallback: se `valor_json` vazio, usa `{"endereco": valor_texto}` |

### Novo arquivo

**`agente.bat`** — launcher Windows para uso no CLI sem digitar `python -m agente_2w.main`:

```bat
@echo off
cd /d "%~dp0"
python -m agente_2w.main %*
pause
```

### Comportamento observado (nao e bug)

Na etapa `fechamento`, a IA nao emite `converter_em_pedido` automaticamente ao revisar o pedido. Requer uma mensagem explicita do cliente ("confirmar", "finalizar", etc.) para disparar a promocao. Isso e comportamento esperado do modelo — a confirmacao explicita do cliente e desejavel antes de criar o pedido oficial.

### Primeiro pedido real criado

- Sessao: `dc7a8e63-...`
- Pedido: `496d6414-...`
- Pneu: CST Ride Migra 130/70-13
- Valor: R$ 259,90
- Entrega: entrega (pix)
- Status: `confirmado`

---

## Fase 9 — Defesa em Profundidade (2026-03-29)

Segundo teste E2E revelou falha persistente: modelo copiava placeholder `"UUID-EXATO-RETORNADO-PELA-TOOL"` como valor de `pneu_id`. Depender da IA para transportar UUIDs entre resultados de tool e JSON de saida e fundamentalmente fragil.

### Principio

> O backend ja tem o dado. Nao precisa da IA pra repassar.

### Alteracoes

| Arquivo | Mudanca | Motivo |
|---|---|---|
| `prompt_sistema.py` | Exemplo de UUID real em vez de placeholder toxico | Modelo copiava o placeholder literalmente |
| `agente.py` | `chamar_agente` retorna `tuple[str, list[dict]]` com pneus coletados das tools | Backend precisa dos pneu_ids independente da IA |
| `agente.py` | Nova funcao `_extrair_pneus_de_resultado()` | Parseia resultados de tools e extrai pneu_id/posicao/preco |
| `orquestrador.py` | Auto-enriquecimento de `pneu_id` em `_aplicar_mudancas_itens` | Se IA falha em passar UUID, backend preenche dos resultados de tool |
| `orquestrador.py` | Auto-promocao em fechamento (passo 12) | Elimina necessidade de mensagem extra do cliente |
| `orquestrador.py` | Bloqueio de `status_item=promovido` via `atualizar` | Exclusividade do promotor |
| `validador_envelope.py` | Regra 8: rejeita `atualizar` + `status_item=promovido` | Previne contorno da exclusividade do promotor |

---

## Fase 21 — Normalização de Busca de Moto

Data: 04/04/2026

### Problema identificado em teste real

Cliente digitou `"cb300"` (sem espaço). A tool passou o termo direto para o RPC do Supabase. O banco tem `"CB 300"` — não bateu. Agente reportou moto não encontrada. Cliente teve que corrigir. Com dois pneus pedidos (XRE + CB300), o fluxo fragmentou em dois atendimentos separados.

A IA às vezes normaliza antes de chamar a tool, às vezes não — comportamento estocástico. Não dá pra depender disso.

### Solução — `tools/busca_catalogo.py`

**Três novas funções:**

`_remover_acentos(texto)` — normalização Unicode NFD → ASCII:
```python
unicodedata.normalize("NFD", texto) → filtra categoria "Mn"
# "ténéré" → "tenere"
```

`_normalizar_termo_moto(termo) -> list[str]` — gera variações em ordem de prioridade:
1. Termo original (sempre primeiro)
2. Aplica as 4 regras em sequência → versão mais normalizada
3. Variações intermediárias

**As 4 regras (universais):**
```
Regra 1 — Remove fabricante:       "honda cb300"  → "cb300"
Regra 2 — Hífen/ponto → espaço:    "cb-300"       → "cb 300"
Regra 3 — Espaço letra→número:     "cb300"        → "cb 300"
Regra 4 — Remove acentos:          "ténéré"       → "tenere"
```

`buscar_pneus_por_moto` — agora itera as variações:
```python
for termo in _normalizar_termo_moto(termo_moto):
    compatibilidades = catalogo_repo.buscar_compatibilidade_por_moto_texto(termo)
    if compatibilidades:
        return {"quantidade": ..., "compatibilidades": ..., "termo_usado": termo}
return {"quantidade": 0, "compatibilidades": [], "termo_usado": termo_moto}
```

### Por que as regras são universais

São regras de padrão, não de caso. Não conhecem nenhuma moto específica. Qualquer moto cadastrada futuramente — com ou sem espaço, com ou sem acento, digitada com fabricante ou sem — é coberta automaticamente.

### Cobertura de casos

```
"cb300"              → "cb 300"        ✓
"honda cb300"        → "cb 300"        ✓
"cb-300"             → "cb 300"        ✓
"yamaha xre300"      → "xre 300"       ✓
"kawasaki z-400"     → "z 400"         ✓
"yamaha ténéré 250"  → "tenere 250"    ✓
"CG 160"             → "cg 160"        ✓  (não quebra caso normal)
```

### Testes

**`tests/test_normalizacao_moto.py`** — **39/39 PASS** (04/04/2026)

---

### Defesa em profundidade

```
Camada 1 (prompt):  Exemplo com UUID real, sem placeholder
Camada 2 (agente):  Coleta pneu_ids durante tool calls
Camada 3 (orquest): Auto-enriquece se pneu_id ausente
Camada 4 (orquest): Auto-promove em fechamento
Camada 5 (valid):   Rejeita status=promovido via atualizar
Camada 6 (banco):   Constraint item_provisorio_promovido_pneu_chk
```

---

## Fase 20 — Guardrails de Confiabilidade do Fluxo

Data: 04/04/2026

### Motivação

Taxa de erro de fluxo estimada em ~60%, principalmente: loop de pagamento/entrega (IA esquecia de registrar fatos), fechamento prematuro sem dados completos, perguntas redundantes sobre dados já registrados. Três guardrails implementados para reduzir a ~28%.

### Guardrail 1 — Fallback de extração de fatos estruturados

**Arquivo:** `engine/orquestrador.py`

Passo **6b** adicionado em `processar_turno`, roda APÓS a IA aplicar `fatos_observados`:

```python
_extrair_fatos_estruturados_fallback(sessao_id, mensagem_texto, msg_entrada.id)
```

**Lógica:**
- Verifica se `forma_pagamento` e `tipo_entrega` já existem nos fatos
- Se não, escaneia a mensagem do cliente por keywords
- Antes de registrar, checa negação (`_tem_negacao_antes`) para evitar "não quero pix" → registrar pix

**Keywords mapeadas:**
```python
_KEYWORDS_FORMA_PAGAMENTO = [("pix","pix"), ("dinheiro","dinheiro"),
                              ("cartão","cartao"), ("transferência","transferencia")]
_KEYWORDS_TIPO_ENTREGA    = [("retirada","retirada"), ("retiro","retirada"),
                              ("busco","retirada"), ("entrega","entrega"),
                              ("entregar","entrega"), ("delivery","entrega")]
```

**Efeito no prompt:** seção "REGRA CRITICA: registrar fatos de entrega e pagamento" encurtada de 15 linhas para 2. O código garante o registro mesmo que a IA esqueça.

### Guardrail 2 — Validador bloqueia fechamento sem dados

**Arquivo:** `engine/validador_envelope.py`

Regra 7 adicionada a `validar_envelope()`:

```python
# Regra 7: entrega_pagamento -> fechamento exige dados completos
if (contexto.sessao.etapa_atual == EtapaFluxo.entrega_pagamento
        and envelope.etapa_atual == EtapaFluxo.fechamento):
    chaves_fatos = {f.chave for f in contexto.fatos_ativos}
    if "tipo_entrega" not in chaves_fatos:
        erros.append("nao pode avancar para fechamento sem tipo_entrega registrado")
    if "forma_pagamento" not in chaves_fatos:
        erros.append("nao pode avancar para fechamento sem forma_pagamento registrado")
```

O retry existente (`MAX_RETRIES=2`) força a IA a ficar em `entrega_pagamento` e pedir os dados que faltam. Fechamento prematuro vira impossível por código.

### Guardrail 3 — Alertas contextuais

**Arquivos:** `schemas/contexto_executavel.py` + `engine/montador_contexto.py`

Campo `alertas: list[str]` adicionado ao `ContextoExecutavel`. Populado pelo `montador_contexto` com avisos explícitos sobre dados já registrados:

```python
# Exemplo de alertas gerados quando fatos existem:
alertas = [
    "tipo_entrega ja registrado como 'retirada' — NAO pergunte de novo",
    "forma_pagamento ja registrado como 'pix' — NAO pergunte de novo",
    "nome_cliente ja registrado como 'João' — NAO pergunte o nome de novo",
]
```

Chaves monitoradas: `nome_cliente`, `tipo_entrega`, `forma_pagamento`, `municipio`.

### Testes automatizados

**Arquivo:** `tests/test_guardrails.py` — **25/25 PASS** (04/04/2026)

Cobertura:
- Guardrail 1: 10 casos de detecção de negação (com/sem acento, variações)
- Guardrail 2: 7 cenários de validação (sem dados, dados parciais, dados completos, outras etapas)
- Guardrail 3: 8 casos de geração e serialização de alertas

### Redução de erros de fluxo

| Estado | Taxa estimada |
|--------|--------------|
| Antes (só prompt) | ~60% |
| + Fallback keywords | ~45% |
| + Validador fechamento | ~35% |
| + Alertas no contexto | ~28% |

### Arquitetura atualizada dos guardrails

```
Camada 1 (prompt):    Instrucoes de tom, fluxo, formato
Camada 2 (context):   alertas[] avisam sobre dados ja registrados
Camada 3 (orquest):   Fallback extrai forma_pagamento/tipo_entrega se IA esqueceu
Camada 4 (validador): Rejeita fechamento sem tipo_entrega + forma_pagamento
Camada 5 (orquest):   Auto-enriquece pneu_id se IA nao passou UUID
Camada 6 (orquest):   Auto-promove em fechamento
Camada 7 (validador): Rejeita status=promovido via atualizar
Camada 8 (banco):     Constraints PostgreSQL como ultima linha de defesa
```

### Teste E2E automatizado (29/03/2026)

Conversa simulada via `processar_turno()` diretamente (sessao `78e4da93-...`):

- 6 turnos: identificacao → busca → oferta → confirmacao_item → entrega_pagamento → fechamento
- `pneu_id` auto-enriquecido dos resultados de tool (modelo nao precisou repassar)
- Pedido `84132af0-...` criado automaticamente no turno 6 via auto-promocao
- `item_pedido` com pneu_id, quantidade, preco e subtotal corretos
- `sessao_chat.status_sessao = fechada` ao final

Bateria `teste_integrado_f1_f5.py`: **126/126 PASS** — incluindo correcao do teste INT.3/INT.4 para desempacotar a tupla retornada por `chamar_agente`.

---

## Fase 23 — Structured Outputs: Schema Estrito no EnvelopeIA (2026-04-02)

O modelo retornava tipos errados ocasionalmente (ex: `bloqueios_identificados` como string em vez de array). Substituiu `response_format: json_object` por `json_schema` com `strict: True` e schema completo `_ENVELOPE_IA_SCHEMA` em `ia/agente.py`.

Restrições aplicadas:
- Todos os campos `required` — opcionais usam `["type", "null"]`
- `additionalProperties: False` em todos os objetos aninhados
- `parallel_tool_calls: False` obrigatório junto com structured outputs (limitação da API)

Resultado: eliminou `ParseError` de tipo e tornou o envelope 100% previsível pelo orquestrador.

---

## Fase 24 — Web Search: Fallback de Compatibilidade de Motos (2026-04-03)

Quando `buscar_pneus_por_moto` retorna 0 resultados (moto não cadastrada no catálogo), o agente agora busca a medida na internet via Responses API.

**Novo arquivo:** `tools/busca_web.py`
```python
def buscar_medida_por_moto_web(moto: str, posicao: str, sessao_id=None) -> dict:
    # Usa openai.responses.create com tool web_search_preview
    # Retorna: {"encontrado": bool, "moto": str, "posicao": str, "info": str, "fonte": "web"}
```

**Cascata completa:**
1. `buscar_pneus_por_moto("Triumph Tiger 900")` → 0 resultados
2. `buscar_medida_por_moto_web("Triumph Tiger 900", "traseiro")` → "150/70 R17"
3. `buscar_pneus(medida_texto="150/70 R17")` → pneus disponíveis no estoque

**Schema da tool** em `TOOLS_SCHEMA`: instrução explícita "usar SOMENTE quando buscar_pneus_por_moto retornar 0 resultados".

---

## Fase 25 — Auditoria de Busca Web + Filtro de Posição (2026-04-04)

### Tabela `log_busca_web`

Toda busca web é auditada: moto, posição, se encontrou, texto completo da resposta, sessao_id (→ JOIN com cliente).

**Novo arquivo:** `db/log_busca_web_repo.py` — `registrar()` fail-safe (nunca levanta exceção).

`sessao_id` injetado via wrapper no dispatch de `chamar_agente()`:
```python
dispatch = {
    **_TOOL_DISPATCH,
    "buscar_medida_por_moto_web": lambda moto, posicao: buscar_medida_por_moto_web(
        moto=moto, posicao=posicao, sessao_id=sessao_id
    ),
}
```

### Filtro de posição em `buscar_pneus_por_moto`

`buscar_pneus_por_moto(termo_moto, posicao=None)` — quando `posicao` informado, filtra os resultados antes de retornar. Evita o agente misturar dianteiro e traseiro numa mesma listagem de preços.

### Apresentação direta com 1 resultado

Quando há apenas 1 opção disponível, o agente apresenta direto sem perguntar preferência de marca.

---

## Fase 26 — Rede de Segurança 9b + Ajuste de Tom (2026-04-04)

### Rede de segurança 9b (`engine/orquestrador.py`)

**Problema:** Retry de validação (`busca → confirmacao_item` bloqueado → retry para `oferta` → próximo turno `confirmacao_item`) fazia o modelo pular a criação do item em `mudancas_itens`.

**Solução:** Entre o step 9 (aplicar mudancas_itens) e step 10 (despachar ações), o orquestrador verifica se entrou em `confirmacao_item` sem nenhum item com `pneu_id`. Se sim e houver `pneus_encontrados`, cria o item automaticamente.

Segue o mesmo padrão dos outros guardrails: usa dados já existentes na sessão sem alterar a decisão da IA. Camada 9 da arquitetura de defesa em profundidade.

### Ajuste de tom em `confirmacao_item` (`ia/prompt_sistema.py`)

- **Antes:** `"Tem mais algum pneu ou pode seguir pro pagamento?"` — mencionava pagamento prematuramente
- **Depois:** `"Tem mais algum pneu ou é só esse?"` + regra: nunca mencionar "pagamento" nessa etapa

A etapa `entrega_pagamento` já tratava entrega e pagamento na ordem correta — o problema era só a frase de transição.

---

## Fase 27 — Suporte a Imagem e Áudio (2026-04-04)

### Visão geral

O agente passa a aceitar imagens e áudios enviados pelo cliente no WhatsApp, sem alterar nenhuma lógica do orquestrador ou do banco de dados.

### Imagem

`chamar_agente()` em `ia/agente.py` aceita novo parâmetro `imagens: list[str] | None`. Quando presente, o `content` da mensagem do usuário muda de string para array multimodal:

```python
# Antes
{"role": "user", "content": "mensagem do cliente"}

# Depois (com imagem)
{"role": "user", "content": [
    {"type": "text", "text": "mensagem do cliente"},
    {"type": "image_url", "image_url": {"url": "https://...", "detail": "auto"}}
]}
```

No retry de validação o parâmetro `imagens` não é reenviado — só o texto de correção.

### Áudio

O gpt-5.4 não aceita áudio nativo via Chat Completions. Solução: o webhook transcreve com Whisper antes de passar ao agente.

```
Chatwoot → webhook recebe URL do OGG
         → _transcrever_audio() baixa + envia ao Whisper (whisper-1, language=pt)
         → texto transcrito vira content da mensagem
         → processar_turno() chamado normalmente
```

O agente nunca sabe que era áudio — recebe texto puro.

### Fluxo no webhook

```
_extrair_anexos(data)
  ├─ file_type=audio/voice → _transcrever_audio(url) → texto
  └─ file_type=image/sticker → coleta URL

content final:
  ├─ só texto → string normal
  ├─ áudio transcrito → substitui/complementa content
  ├─ imagem sem texto → "(sem texto)" + array multimodal
  └─ vazio sem imagem → ignored (comportamento anterior)
```

### Cadeia de parâmetros

```
webhook._extrair_anexos()
  └─ _processar_mensagem_sync(telefone, texto, msg_id, imagens)
      └─ processar_turno(sessao_id, texto, ..., imagens)
          └─ _chamar_e_validar(contexto, texto, imagens)
              └─ chamar_agente(contexto, texto, imagens)
                  └─ content multimodal para a OpenAI
```

### Arquivos alterados

| Arquivo | Mudança |
|---------|---------|
| `ia/agente.py` | `chamar_agente(imagens=None)` — monta content multimodal |
| `engine/orquestrador.py` | `processar_turno(imagens=None)` e `_chamar_e_validar(imagens=None)` |
| `webhook.py` | `_transcrever_audio()`, `_extrair_anexos()`, endpoint atualizado |
| `ia/prompt_sistema.py` | Regras 4a (foto) e 4b (áudio) |

---

## Fase 28 — Fix: Auto-enriquecimento de Preco

### Contexto

O teste E2E com Hornet revelou que o agente entrava em loop no fechamento: o promotor
rejeitava a conversao porque o item provisorio nao tinha `preco_unitario_sugerido`.

### Bug

Em `_aplicar_mudancas_itens()` (`orquestrador.py`), o auto-enriquecimento de preco
estava **dentro** do bloco que so executa quando `pneu_uuid is None`:

```python
# ANTES (bugado) — preco so era preenchido se pneu_uuid fosse None
if pneu_uuid is None and pneus_encontrados:
    # ... match por posicao ...
    if match:
        pneu_uuid = UUID(str(match["pneu_id"]))
        if not dados.get("preco_unitario_sugerido") and match.get("preco_venda"):
            dados["preco_unitario_sugerido"] = float(match["preco_venda"])
```

Quando o modelo ja fornecia `pneu_id` valido mas omitia o preco, o bloco inteiro
era pulado e o item era criado sem preco.

### Correcao

Bloco de preco extraido e tornado independente, executando apos ambos os caminhos
(auto-enriquecimento de UUID ou UUID vindo do modelo):

```python
# DEPOIS — preco preenchido independente da origem do pneu_uuid
if pneu_uuid and not dados.get("preco_unitario_sugerido") and pneus_encontrados:
    preco_match = next(
        (p for p in pneus_encontrados
         if p.get("pneu_id") and str(p["pneu_id"]) == str(pneu_uuid)
         and p.get("preco_venda")),
        None,
    )
    if preco_match:
        dados["preco_unitario_sugerido"] = float(preco_match["preco_venda"])
```

### Efeito cascata

| Componente | Antes | Depois |
|-----------|-------|--------|
| `_aplicar_mudancas_itens` | item criado sem preco | preco auto-enriquecido |
| `promotor.py` | rejeitava: "sem preco definido" | aceita e converte |
| `fechamento` | loop infinito pedindo confirmacao | pedido criado na primeira confirmacao |

### Padrao reafirmado

Mais uma aplicacao do principio **"IA interpreta, backend garante"**: se o modelo esquece
um campo, o orquestrador preenche defensivamente antes de persistir.

---

## O que nao esta implementado no V1

Por decisao de escopo, ficaram fora do primeiro ciclo:

- RLS (Row Level Security) no Supabase
- Financeiro, comissoes, devolucoes
- Roteirizacao de entrega
- Analytics e dashboards
- Automacoes paralelas
- Testes unitarios e de integracao automatizados (apenas scripts manuais)
- `__main__.py` para `python -m agente_2w`
- Tratamento de falha de conexao Supabase (excecoes brutas propagam)

**Implementado fora do pacote `agente_2w`:**

- Webhook FastAPI (`C:\sistema\Openai\webhook.py`) — recebe mensagens do Chatwoot, despacha para `processar_turno()` e responde ao cliente. Inclui fila por cliente (`asyncio.Lock` por telefone) para evitar processamento concorrente de mensagens do mesmo contato.

---

## Fase 29 — Sistema de Handoff para Atendimento Humano

### Motivacao

Antes desta fase, o bot respondia 100% das mensagens — nao havia como pausar e transferir para um atendente humano. Situacoes como clientes frustrados, atacadistas querendo revender, ou emergencias na estrada ficavam sem atendimento adequado.

### Arquitetura do handoff

O sistema segue o mesmo padrao de fatos do cancelamento de pedido: **IA emite fato → `_nucleo.py` reage → executa logica backend → sincroniza Chatwoot**.

**Fluxo completo:**
1. IA detecta situacao de escalacao e emite fato (`escalar_para_humano`, `cliente_atacado`, `emergencia_pneu`)
2. Orquestrador desativa o fato e chama `_processar_escalacao()`
3. Classificador de prioridade (codigo puro) define `urgent`, `high` ou `medium`
4. INSERT na tabela `escalacao` + status da sessao muda para `escalada`
5. Chatwoot: label `escalado_vendas`, prioridade, time Vendas assignado, nota privada
6. Bot silenciado — guard no webhook impede respostas automaticas
7. Humano resolve e devolve ao bot ou encerra a conversa

### Tabela `escalacao`

```sql
CREATE TABLE escalacao (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sessao_chat_id   UUID NOT NULL REFERENCES sessao_chat(id),
  chatwoot_conv_id INT NOT NULL,
  motivo           TEXT NOT NULL,
  origem           TEXT NOT NULL CHECK (origem IN ('codigo','ia')),
  status           TEXT NOT NULL DEFAULT 'aguardando'
                   CHECK (status IN ('aguardando','em_atendimento','resolvida','devolvida_bot')),
  chatwoot_team_id INT,
  notas            TEXT,
  criado_em        TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_em    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Indices parciais para busca rapida de escalacoes ativas (filtra por status != resolvida/devolvida_bot).

### Classificacao de prioridade

| Prioridade | Condicao | Quem decide |
|---|---|---|
| **URGENT** | Atacado, emergencia, VIP, pedido > R$800 | Codigo |
| **HIGH** | Pediu humano, frete fora de area, estoque zerado, cliente recorrente (2+ pedidos) | Codigo |
| **MEDIUM** | Default | Codigo |

A IA **nunca** decide a prioridade — so emite o fato. O codigo em `escalacao_repo.classificar_prioridade()` classifica baseado em dados concretos do cliente e pedido.

### Gatilhos de escalacao

**Via IA (fatos):**
- `escalar_para_humano` — cliente pediu humano ("quero falar com alguem")
- `cliente_atacado` — atacadista/revendedor ("quero revender", "tenho oficina")
- `emergencia_pneu` — emergencia na estrada ("pneu furou", "moto parada")

**Via codigo:**
- `frete_nao_coberto` — municipio fora da area de entrega e cliente nao quer retirar
- Cliente VIP — `segmento == "vip"` (notificacao background, nao silencia bot)

### Novos endpoints

- `POST /internal/devolver-ao-bot` — devolve conversa ao bot (`escalacao → devolvida_bot`, `sessao → ativa`)
- `POST /internal/resolver-escalacao` — encerra escalacao (`escalacao → resolvida`, `sessao → fechada`, conversa resolvida no Chatwoot)

### Arquivos modificados/criados

| Arquivo | Mudanca |
|---|---|
| `agente_2w/config.py` | `CHATWOOT_TEAM_VENDAS_ID` |
| `agente_2w/enums/enums.py` | `StatusSessao.escalada` |
| `agente_2w/constantes.py` | 3 novas chaves de escalacao |
| `agente_2w/schemas/escalacao.py` | **Novo** — EscalacaoCreate, Escalacao |
| `agente_2w/db/escalacao_repo.py` | **Novo** — CRUD + classificador de prioridade |
| `agente_2w/chatwoot_sync.py` | `definir_prioridade()`, `assignar_time()`, `escalar_para_humano()` |
| `agente_2w/engine/orquestrador/_nucleo.py` | `_processar_escalacao()`, blocos 7d/7e, guard timeout |
| `webhook_server.py` | Guard escalacao, endpoints devolver/resolver |
| `agente_2w/ia/prompt_sistema.py` | Secao de escalacao com 3 fatos e regras |

### Padrao reafirmado

Mais uma aplicacao do principio **"IA interpreta, backend garante"**: a IA detecta a situacao e emite um fato; o codigo classifica a prioridade, cria o registro, silencia o bot e notifica o time humano — sem alucinacao possivel.
