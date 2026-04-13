# Projeto: Envio de Fotos de Pneus pelo Agente

**Data:** 2026-04-06
**Autor:** Claude Opus (análise arquitetural profunda)
**Status:** Planejamento (V2 — corrigido após análise minuciosa do código)

---

## 1. Situação Atual (Verificada no Código)

### 1.1 Arquitetura real do sistema

O agente **NÃO** é um webhook/Chatwoot. É uma **biblioteca Python síncrona** com CLI:

```
main.py (CLI)                          webhook externo (fora deste repo)
      │                                        │
      └──── processar_turno(sessao_id, texto, imagens?) ────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   _nucleo.py        │ ← 14 passos orquestrados
              │   (orquestrador)    │
              └────────┬────────────┘
                       │
                       ▼
              ┌─────────────────────┐
              │   agente.py (IA)    │ ← OpenAI gpt-4o + 5 tools
              │   + tool calling    │
              └────────┬────────────┘
                       │
                       ▼
              ┌─────────────────────┐
              │   Supabase (DB)     │ ← 13 tabelas + views
              └─────────────────────┘
```

**Contrato público atual:**
```python
def processar_turno(
    sessao_id: UUID,
    mensagem_texto: str,
    criado_em: datetime | None = None,
    message_id_externo: str | None = None,
    imagens: list[str] | None = None,
) -> str:  # ← retorna APENAS texto
```

### 1.2 O que existe hoje (confirmado no código)

| Componente | Estado Real | Arquivo / Localização |
|------------|------------|----------------------|
| Tabela `pneu` | 16 produtos, **sem campo de foto** | DB Supabase (betaAgente) |
| View `catalogo_agente` | Retorna: pneu_id, pneu_marca, pneu_modelo, medida, preco_venda, disponivel_real — **sem foto** | Consultada por `catalogo_repo.py` |
| `processar_turno()` | Retorna `str` (texto puro) | `_nucleo.py:437-737` |
| `chamar_agente()` | Retorna `tuple[str, list[dict]]` (texto_bruto, pneus_encontrados) | `agente.py:86-163` |
| `_extrair_pneus_de_resultado()` | Extrai `pneu_id`, `posicao`, `preco_venda` dos resultados de tools | `agente.py:161+` |
| `_persistir_pneus_encontrados()` | Salva pneus no contexto como fato `ultimos_pneus_encontrados` | `_nucleo.py:187-228` |
| `_persistir_saida()` | Grava `MensagemChat` com `conteudo_texto` (só texto) | `_nucleo.py:245-256` |
| `MensagemChat` schema | Campos: `conteudo_texto: str`, `metadata_json: Optional[dict]` | `schemas/mensagem_chat.py` |
| Supabase Storage | **Não configurado** | Nenhum bucket existe |
| Recebimento de imagem (cliente→agente) | **Funciona** — URLs passadas para GPT-4o via multimodal | `agente.py:104-111` |
| Envio de imagem (agente→cliente) | **NÃO existe** | — |
| webhook.py / Chatwoot | **NÃO existe neste repositório** | Integração externa |

### 1.3 Fluxo de dados dos pneus encontrados (crítico para fotos)

```
1. IA chama tool (ex: buscar_pneus_por_moto)
       ↓
2. Tool retorna JSON com lista de pneus (inclui pneu_id, preco_venda, etc)
       ↓
3. agente.py: _extrair_pneus_de_resultado() coleta {pneu_id, posicao, preco_venda}
       ↓
4. agente.py: retorna (texto_bruto, pneus_encontrados[])
       ↓
5. _nucleo.py: _persistir_pneus_encontrados() salva no contexto
       ↓
6. _nucleo.py: pneus usados para auto-enriquecimento de itens provisórios
       ↓
7. mensagem_final extraída de envelope.mensagem_cliente
       ↓
8. return mensagem_final (str) — pneus_encontrados NÃO são retornados ao caller
```

**Ponto-chave:** Os `pneu_id`s JÁ são coletados internamente. Falta apenas:
- Adicionar `foto_url` ao fluxo de dados
- Expor as URLs de fotos no retorno de `processar_turno()`

### 1.4 Problema

O cliente compra "no escuro". Não vê o pneu. Em pneu usado (nicho da 2W Pneus), a condição visual é decisiva.

---

## 2. Armazenamento: Supabase Storage (decisão mantida)

| Critério | Avaliação |
|----------|-----------|
| **Integração** | Nativa. `supabase-py` já tem `.storage` client. Zero dependência nova. |
| **Setup** | Criar 1 bucket público. 2 minutos no dashboard. |
| **URL de acesso** | URL pública direta com CDN |
| **Custo** | 1GB grátis. 16 pneus x 3 fotos x 500KB = ~24MB (2.4% do limite) |
| **Compatibilidade** | URL pública funciona em qualquer plataforma (WhatsApp, Telegram, web) |

---

## 3. Arquitetura Proposta (Corrigida)

### 3.1 Visão geral

```
                    ┌──────────────────┐
                    │  Supabase Storage │
                    │  bucket: "fotos"  │
                    │  (público)        │
                    └────────┬─────────┘
                             │ URL pública
                             ▼
┌──────────┐    ┌──────────────────┐    ┌──────────────┐
│  pneu    │───>│  foto_pneu       │    │ catalogo_    │
│  (16 reg)│    │  (nova tabela)   │───>│ agente (view)│
└──────────┘    │  pneu_id (FK)    │    │ + foto_url   │
                │  url              │    └──────┬───────┘
                │  tipo             │           │
                │  ordem            │           ▼
                └──────────────────┘    ┌──────────────────────┐
                                        │  Tools retornam      │
                                        │  foto_url nos dicts  │
                                        └──────┬───────────────┘
                                               │
                                               ▼
                                        ┌──────────────────────┐
                                        │  _extrair_pneus_de_  │
                                        │  resultado() coleta  │
                                        │  foto_url            │
                                        └──────┬───────────────┘
                                               │
                                               ▼
                                        ┌──────────────────────┐
                                        │  processar_turno()   │
                                        │  retorna             │
                                        │  RespostaTurno       │
                                        │  (texto + fotos[])   │
                                        └──────┬───────────────┘
                                               │
                                    ┌──────────┴──────────┐
                                    ▼                     ▼
                             ┌────────────┐       ┌─────────────┐
                             │  main.py   │       │  webhook    │
                             │  (CLI)     │       │  externo    │
                             │  ignora    │       │  envia foto │
                             │  fotos     │       │  + texto    │
                             └────────────┘       └─────────────┘
```

### 3.2 Componentes a criar/alterar

| # | Componente | Tipo | Arquivo | Risco |
|---|-----------|------|---------|-------|
| 1 | Bucket `fotos` no Storage | Novo | Dashboard Supabase | Nenhum |
| 2 | Tabela `foto_pneu` | Nova | Migration SQL | Nenhum |
| 3 | View `catalogo_agente` | Alterar | Migration SQL | **Baixo** — adiciona LEFT JOIN |
| 4 | Schema `RespostaTurno` | Novo | `schemas/resposta_turno.py` | Nenhum |
| 5 | Schema `FotoPneu` | Novo | `schemas/foto_pneu.py` | Nenhum |
| 6 | Repo `foto_pneu_repo.py` | Novo | `db/foto_pneu_repo.py` | Nenhum |
| 7 | `_extrair_pneus_de_resultado()` | Alterar | `ia/agente.py` | **Baixo** — adiciona campo |
| 8 | `processar_turno()` retorno | Alterar | `_nucleo.py` | **MEDIO** — muda tipo de retorno |
| 9 | `main.py` (CLI) | Alterar | `main.py` | **Baixo** — adaptar ao novo retorno |
| 10 | `buscar_detalhes_pneu()` | Alterar | `tools/busca_catalogo.py` | **Baixo** — adiciona fotos |
| 11 | System prompt | Alterar | `ia/prompt_sistema.py` | **Baixo** — adiciona seção |

---

## 4. Projeto de Banco de Dados (mantido, validado)

### 4.1. Bucket Supabase Storage

```
Nome: fotos
Tipo: PÚBLICO (sem autenticação para leitura)
```

Convenção de nomes:
```
fotos/{pneu_id}/principal.jpg
fotos/{pneu_id}/detalhe_1.jpg
fotos/{pneu_id}/detalhe_2.jpg
```

### 4.2. Tabela `foto_pneu`

```sql
CREATE TABLE foto_pneu (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pneu_id     uuid NOT NULL REFERENCES pneu(id) ON DELETE CASCADE,
    url         text NOT NULL,
    tipo        text NOT NULL DEFAULT 'principal'
                CHECK (tipo IN ('principal', 'detalhe', 'sulco', 'lateral')),
    ordem       smallint NOT NULL DEFAULT 1,
    descricao   text,
    ativo       boolean NOT NULL DEFAULT true,
    criado_em   timestamptz NOT NULL DEFAULT now(),

    UNIQUE (pneu_id, tipo, ordem)
);

CREATE INDEX idx_foto_pneu_pneu_id ON foto_pneu(pneu_id) WHERE ativo = true;
```

### 4.3. Atualizar View `catalogo_agente`

```sql
CREATE OR REPLACE VIEW catalogo_agente AS
SELECT
    p.id          AS pneu_id,
    p.marca       AS pneu_marca,
    p.modelo      AS pneu_modelo,
    p.medida,
    p.largura,
    p.perfil,
    p.aro,
    p.tipo        AS pneu_tipo,
    p.descricao_comercial,
    e.preco_venda,
    e.quantidade_disponivel,
    e.reservado,
    (e.quantidade_disponivel - e.reservado) AS disponivel_real,
    p.ativo,
    -- NOVO: foto principal
    fp.url        AS foto_url
FROM pneu p
JOIN estoque e ON e.pneu_id = p.id
LEFT JOIN foto_pneu fp
    ON fp.pneu_id = p.id
    AND fp.tipo = 'principal'
    AND fp.ordem = 1
    AND fp.ativo = true
WHERE p.ativo = true;
```

**Impacto analisado:**
- LEFT JOIN garante que pneus SEM foto continuam aparecendo (`foto_url = null`)
- Filtro `tipo='principal' AND ordem=1` garante no máximo 1 linha por pneu (sem duplicação)
- Constraint UNIQUE `(pneu_id, tipo, ordem)` garante isso no banco
- Performance: índice parcial `idx_foto_pneu_pneu_id WHERE ativo = true` cobre a busca
- **ZERO impacto** nas queries existentes — campos anteriores ficam iguais

---

## 5. Projeto de Código Python (Corrigido)

### 5.1 Mudança central: tipo de retorno de `processar_turno()`

**Este é o ponto mais delicado.** Hoje todos os callers esperam `str`:

```python
# main.py
resposta = processar_turno(sessao_id, mensagem)
print(f"\n2W Pneus: {resposta}\n")

# testes
r = processar_turno(sessao.id, "Oi, quero um pneu")
assert "pneu" in r.lower()

# webhook externo (fora do repo)
resposta = processar_turno(sessao_id, texto, imagens=urls)
# envia resposta para Chatwoot/WhatsApp
```

**Solução: `RespostaTurno` — dataclass que se comporta como string**

```python
# schemas/resposta_turno.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class RespostaTurno:
    """Resposta de um turno do agente.

    Comporta-se como string para retrocompatibilidade:
    - print(resposta) → imprime o texto
    - "pneu" in resposta → funciona
    - f"2W: {resposta}" → funciona
    - str(resposta) → retorna o texto

    Mas também carrega metadados opcionais como fotos.
    """
    texto: str
    fotos: list[str] = field(default_factory=list)  # URLs das fotos para enviar

    def __str__(self) -> str:
        return self.texto

    def __contains__(self, item: str) -> bool:
        return item in self.texto

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.texto == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.texto)
```

**Por que essa abordagem:**

| Alternativa | Problema |
|-------------|----------|
| Retornar `tuple[str, list]` | **Quebra TODOS os callers** — `print(resposta)` imprimiria a tuple inteira |
| Retornar `dict` | Quebra callers. `"pneu" in resposta` falha |
| Criar parâmetro de callback | Invasivo, muda a assinatura |
| **`RespostaTurno` (dataclass)** | **Retrocompatível.** `print()`, `in`, `f-string` funcionam como antes. Callers novos acessam `.fotos` |

**Callers existentes — impacto ZERO:**
```python
# main.py (FUNCIONA SEM MUDAR)
resposta = processar_turno(sessao_id, mensagem)
print(f"\n2W Pneus: {resposta}\n")  # __str__ retorna texto

# testes (FUNCIONA SEM MUDAR)
r = processar_turno(sessao.id, "Oi")
assert "pneu" in r  # __contains__ delega para texto

# webhook externo (PODE EVOLUIR)
resposta = processar_turno(sessao_id, texto)
texto = str(resposta)           # retrocompatível
fotos = resposta.fotos          # NOVO — lista de URLs
```

### 5.2 Schema `FotoPneu`

**Novo arquivo:** `agente_2w/schemas/foto_pneu.py`

```python
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional


class FotoPneuBase(BaseModel):
    pneu_id: UUID
    url: str
    tipo: str = "principal"
    ordem: int = 1
    descricao: Optional[str] = None
    ativo: bool = True


class FotoPneu(FotoPneuBase):
    id: UUID
    criado_em: datetime

    model_config = {"from_attributes": True}
```

### 5.3 Repositório `foto_pneu_repo.py`

**Novo arquivo:** `agente_2w/db/foto_pneu_repo.py`

```python
"""Repositório de fotos de pneus."""

import logging
from uuid import UUID
from agente_2w.db.client import supabase

logger = logging.getLogger(__name__)

_TABELA = "foto_pneu"


def buscar_foto_principal(pneu_id: UUID) -> str | None:
    """Retorna URL da foto principal do pneu, ou None."""
    try:
        res = (
            supabase.table(_TABELA)
            .select("url")
            .eq("pneu_id", str(pneu_id))
            .eq("tipo", "principal")
            .eq("ativo", True)
            .order("ordem")
            .limit(1)
            .execute()
        )
        return res.data[0]["url"] if res.data else None
    except Exception:
        logger.exception("Erro ao buscar foto principal pneu %s", pneu_id)
        return None


def listar_fotos(pneu_id: UUID) -> list[dict]:
    """Retorna todas as fotos ativas de um pneu, ordenadas."""
    try:
        res = (
            supabase.table(_TABELA)
            .select("url, tipo, ordem, descricao")
            .eq("pneu_id", str(pneu_id))
            .eq("ativo", True)
            .order("ordem")
            .execute()
        )
        return res.data or []
    except Exception:
        logger.exception("Erro ao listar fotos pneu %s", pneu_id)
        return []
```

### 5.4 Alteração em `_extrair_pneus_de_resultado()` — `ia/agente.py`

**Mudança:** Adicionar `foto_url` à extração. O campo já virá nos dicts da view `catalogo_agente`.

```python
# Dentro de _extrair_item():
def _extrair_item(item: dict, preco_contexto=None) -> None:
    pid = item.get("pneu_id")
    if pid:
        _adicionar(
            str(pid),
            posicao=item.get("posicao") or item.get("pneu_tipo"),
            preco=item.get("preco_venda") or preco_contexto,
            foto_url=item.get("foto_url"),  # NOVO
        )

def _adicionar(pid: str, posicao=None, preco=None, foto_url=None) -> None:
    if pid and pid not in vistos:
        vistos.add(pid)
        pneus.append({
            "pneu_id": pid,
            "posicao": posicao,
            "preco_venda": preco,
            "foto_url": foto_url,  # NOVO — pode ser None
        })
```

**Impacto:** Baixo. Adiciona campo opcional ao dict. Todos os consumidores usam `.get()` e ignoram campos desconhecidos.

### 5.5 Alteração em `_persistir_pneus_encontrados()` — `_nucleo.py`

**Nenhuma mudança necessária.** A função já faz merge genérico por campo:
```python
for k, v in p.items():
    if v is not None and not existente.get(k):
        existente[k] = v
```
O campo `foto_url` será preservado automaticamente no merge.

### 5.6 Alteração em `processar_turno()` — `_nucleo.py`

**Mudança no retorno (linhas 725-737):**

```python
# ANTES:
mensagem_final = (
    _montar_confirmacao_pedido(pedido_criado)
    if pedido_criado
    else (envelope_pos_frete.mensagem_cliente if envelope_pos_frete else envelope.mensagem_cliente)
)
_persistir_saida(sessao_id, mensagem_final)
return mensagem_final

# DEPOIS:
mensagem_final = (
    _montar_confirmacao_pedido(pedido_criado)
    if pedido_criado
    else (envelope_pos_frete.mensagem_cliente if envelope_pos_frete else envelope.mensagem_cliente)
)
_persistir_saida(sessao_id, mensagem_final)

# Coletar fotos dos pneus encontrados neste turno
fotos_para_enviar = [
    p["foto_url"]
    for p in pneus_encontrados
    if p.get("foto_url")
]

return RespostaTurno(texto=mensagem_final, fotos=fotos_para_enviar)
```

**Onde `pneus_encontrados` vem:** Já existe como variável local na linha 494:
```python
envelope, pneus_encontrados = _chamar_e_validar(contexto, mensagem_texto, imagens=imagens)
```

**Pontos de atenção (todos os caminhos de retorno):**

| Linha | Retorno | Mudança |
|-------|---------|---------|
| 454 | Mensagem vazia → fallback genérico | `return RespostaTurno(texto=resposta_padrao)` |
| 491 | Erro montando contexto → FALHA_SEGURA | `return RespostaTurno(texto=MENSAGEM_FALHA_SEGURA)` |
| 497 | Envelope None → FALHA_SEGURA | `return RespostaTurno(texto=MENSAGEM_FALHA_SEGURA)` |
| 737 | Fluxo normal → mensagem_final | `return RespostaTurno(texto=mensagem_final, fotos=fotos)` |

**Total: 4 pontos de retorno.** Todos precisam ser atualizados para `RespostaTurno`.

### 5.7 Alteração em `buscar_detalhes_pneu()` — `tools/busca_catalogo.py`

```python
# ANTES (linha 438-442):
return {
    "encontrado": True,
    "pneu": pneu.model_dump(mode="json"),
    "estoque": estoque.model_dump(mode="json") if estoque else None,
}

# DEPOIS:
fotos = foto_pneu_repo.listar_fotos(UUID(pneu_id))
return {
    "encontrado": True,
    "pneu": pneu.model_dump(mode="json"),
    "estoque": estoque.model_dump(mode="json") if estoque else None,
    "fotos": fotos,  # NOVO
}
```

**Impacto:** Nenhum nos consumidores existentes. A IA já recebe o dict completo como JSON no tool result.

### 5.8 Nota sobre `buscar_pneus_por_moto()` e `buscar_pneus()`

Estas tools consultam `catalogo_agente` que JÁ terá `foto_url` após a alteração da view. Nenhuma mudança no código Python necessária — o campo `foto_url` aparecerá automaticamente nos dicts retornados.

### 5.9 Alteração no System Prompt — `ia/prompt_sistema.py`

Adicionar após a seção de imagens (linha 39):

```
# FOTOS DE PRODUTOS

Quando os resultados de busca incluírem `foto_url`, o sistema enviará a foto automaticamente junto com sua mensagem no WhatsApp.

Regras:
- NÃO mencione a foto no texto ("segue a foto", "vou te mandar a foto", "olha a foto"). A foto aparece automaticamente.
- Apresente o pneu normalmente com os dados textuais (marca, modelo, medida, preço).
- Se `foto_url` for null ou ausente, o pneu não tem foto. Continue normalmente sem mencionar.
- NUNCA invente ou sugira que existe foto quando `foto_url` é null.
```

### 5.10 `main.py` — Atualização opcional (mas recomendada)

O CLI funcionará sem mudanças graças ao `__str__()` do `RespostaTurno`. Mas podemos melhorar:

```python
# OPCIONAL — mostrar indicador de foto no CLI
resposta = processar_turno(sessao_id, mensagem)
if resposta.fotos:
    print(f"\n2W Pneus: {resposta}\n  [📷 {len(resposta.fotos)} foto(s) disponível(is)]\n")
else:
    print(f"\n2W Pneus: {resposta}\n")
```

---

## 6. Análise de Impacto Detalhada

### 6.1 Fluxo completo COM fotos (após implementação)

```
Cliente: "quero pneu pra CG 160 traseiro"
    ↓
processar_turno(sessao_id, "quero pneu pra CG 160 traseiro")
    ↓
IA chama buscar_pneus_por_moto("CG 160", "traseiro")
    ↓
Tool consulta catalogo_agente → retorna:
  [{pneu_id: "0cce4ee0-...", pneu_marca: "Pirelli", pneu_modelo: "Street Rider",
    medida: "90/90-18", preco_venda: 279.90,
    foto_url: "https://xxx.supabase.co/.../principal.jpg"}]   ← NOVO CAMPO
    ↓
_extrair_pneus_de_resultado() coleta:
  [{pneu_id: "0cce4ee0-...", posicao: "traseiro", preco_venda: 279.90,
    foto_url: "https://xxx.supabase.co/.../principal.jpg"}]   ← FOTO CAPTURADA
    ↓
IA gera EnvelopeIA com mensagem_cliente:
  "Temos o Pirelli Street Rider 90/90-18 por R$279,90! Quer fechar?"
    ↓
_nucleo.py coleta fotos dos pneus_encontrados:
  fotos_para_enviar = ["https://xxx.supabase.co/.../principal.jpg"]
    ↓
return RespostaTurno(
    texto="Temos o Pirelli Street Rider 90/90-18 por R$279,90! Quer fechar?",
    fotos=["https://xxx.supabase.co/.../principal.jpg"]
)
    ↓
CALLER (webhook externo):
  - Envia texto + imagem via Chatwoot multipart/form-data
  - Cliente vê no WhatsApp: TEXTO + FOTO
```

### 6.2 Cenários de borda analisados

| Cenário | Comportamento | Testado? |
|---------|---------------|----------|
| Pneu sem foto cadastrada | `foto_url = null` → `fotos = []` → envia só texto | Automático (LEFT JOIN) |
| Nenhum pneu encontrado | `pneus_encontrados = []` → `fotos = []` | Automático |
| Múltiplos pneus encontrados | Coleta foto de todos → `fotos = [url1, url2, ...]` | Automático |
| Erro na IA (retry/fallback) | `pneus_encontrados` vem de `_chamar_e_validar` que acumula entre retries | OK |
| Pedido criado (confirmação) | `mensagem_final` vem de `_montar_confirmacao_pedido`, fotos vêm de `pneus_encontrados` do turno | OK — mas pode não ter pneus neste turno |
| Follow-up de frete | `pneus_encontrados` pode estar vazio (frete é pós-busca) → `fotos = []` | OK |
| Mensagem vazia | Return FALHA_SEGURA antes de chamar IA → `fotos = []` | OK |
| Caller antigo (espera str) | `print(resposta)` usa `__str__()` → funciona | OK |
| Caller antigo `"x" in resposta` | `__contains__()` delega para texto → funciona | OK |
| Caller antigo `f"2W: {resposta}"` | `__str__()` → funciona | OK |

### 6.3 O que NÃO muda

| Componente | Por que não muda |
|------------|-----------------|
| `EnvelopeIA` schema | A IA não precisa saber sobre envio de fotos — é decisão do backend |
| `MensagemChat` schema | A persistência continua sendo só texto. Foto é metadado de envio, não de conteúdo |
| `_montar_confirmacao_pedido()` | Confirmação é formatação de pedido, não tem foto |
| Guardrails | Não afetados — operam sobre envelope |
| Transição de etapas | Não afetada |
| Cálculo de frete | Não afetado |
| Item provisório | Não afetado |
| `catalogo_repo.py` | Já faz `SELECT *` na view — campo novo vem automaticamente |
| `buscar_pneus_por_moto()` | Já retorna dicts crus da view — campo novo vem automaticamente |
| `buscar_pneus()` | Idem |

---

## 7. Plano de Implementação (Corrigido)

### Fase 1 — Infraestrutura (banco + storage)

| Passo | O que | Onde | Risco |
|-------|-------|------|-------|
| 1.1 | Criar bucket `fotos` (público) | Dashboard Supabase → Storage | Nenhum |
| 1.2 | Executar SQL: CREATE TABLE `foto_pneu` | Editor SQL Supabase | Nenhum (tabela nova) |
| 1.3 | Executar SQL: CREATE OR REPLACE VIEW `catalogo_agente` | Editor SQL Supabase | **Baixo** — testar que queries existentes continuam funcionando |
| 1.4 | Upload fotos dos pneus ativos | Dashboard Storage (manual) | Nenhum |
| 1.5 | INSERT registros na `foto_pneu` com URLs | Editor SQL | Nenhum |

**Validação Fase 1:** Executar `SELECT * FROM catalogo_agente LIMIT 5` e confirmar que `foto_url` aparece.

### Fase 2 — Backend Python (este repositório)

| Passo | O que | Arquivo | Risco |
|-------|-------|---------|-------|
| 2.1 | Criar `RespostaTurno` | `schemas/resposta_turno.py` | Nenhum (arquivo novo) |
| 2.2 | Criar `FotoPneu` schema | `schemas/foto_pneu.py` | Nenhum (arquivo novo) |
| 2.3 | Criar `foto_pneu_repo.py` | `db/foto_pneu_repo.py` | Nenhum (arquivo novo) |
| 2.4 | Alterar `_extrair_pneus_de_resultado()` | `ia/agente.py` | **Baixo** — adiciona campo ao dict |
| 2.5 | Alterar 4 retornos de `processar_turno()` | `engine/orquestrador/_nucleo.py` | **MEDIO** — tipo de retorno muda |
| 2.6 | Atualizar export em `__init__.py` | `engine/orquestrador/__init__.py` | Baixo — adiciona RespostaTurno |
| 2.7 | Alterar `buscar_detalhes_pneu()` | `tools/busca_catalogo.py` | Baixo — adiciona campo |
| 2.8 | Atualizar system prompt | `ia/prompt_sistema.py` | Baixo — adiciona parágrafo |
| 2.9 | Atualizar main.py (opcional) | `main.py` | Baixo — indicador visual no CLI |

**Validação Fase 2:** Rodar CLI, buscar pneu com foto cadastrada, confirmar que `RespostaTurno.fotos` contém URLs.

### Fase 3 — Integração externa (webhook — FORA deste repo)

| Passo | O que | Onde | Risco |
|-------|-------|------|-------|
| 3.1 | Adaptar webhook para ler `resposta.fotos` | webhook externo | Depende da arquitetura externa |
| 3.2 | Implementar envio multipart Chatwoot | webhook externo | Médio — testar API |
| 3.3 | Teste end-to-end WhatsApp | WhatsApp real | — |

---

## 8. Riscos e Mitigações

| Risco | Prob. | Impacto | Mitigação |
|-------|:---:|:---:|-----------|
| LEFT JOIN na view duplica linhas | Baixa | Alto | UNIQUE constraint `(pneu_id, tipo, ordem)` impede. Testar com `SELECT COUNT(*)` antes/depois |
| Caller antigo quebra com RespostaTurno | Baixa | Alto | `__str__`, `__contains__`, `__eq__` cobrem todos os padrões de uso encontrados (print, in, assert, f-string) |
| Testes existentes falham | Baixa | Médio | Todos usam `r = processar_turno(...)` com `print(r)` ou `"x" in r` — cobertos pelo __str__/__contains__ |
| `foto_url` aparece em contexto serializado (tokens extra) | Média | Baixo | URL é ~100 chars. Com 3 pneus = ~300 chars extras. Impacto marginal no contexto |
| Pneu sem foto — IA menciona foto inexistente | Média | Médio | Prompt explícito: "NUNCA sugira foto quando foto_url é null" |
| Storage offline → foto_url aponta para URL morta | Muito baixa | Baixo | Webhook externo deve ter fail-safe: se download falha, envia só texto |

---

## 9. Consultas Úteis (Pós-Implementação)

```sql
-- Pneus sem foto cadastrada
SELECT p.marca, p.modelo, p.medida
FROM pneu p
LEFT JOIN foto_pneu fp ON fp.pneu_id = p.id AND fp.ativo = true
WHERE p.ativo = true AND fp.id IS NULL;

-- Verificar que a view não duplica linhas
SELECT COUNT(*) AS total_view FROM catalogo_agente;
-- Deve ser igual a:
SELECT COUNT(*) FROM pneu p JOIN estoque e ON e.pneu_id = p.id WHERE p.ativo = true;

-- Contagem de fotos por pneu
SELECT p.marca, p.modelo, COUNT(fp.id) AS total_fotos
FROM pneu p
LEFT JOIN foto_pneu fp ON fp.pneu_id = p.id AND fp.ativo = true
WHERE p.ativo = true
GROUP BY p.id, p.marca, p.modelo
ORDER BY total_fotos;
```

---

## 10. Decisões Tomadas (Atualizadas)

| Decisão | Justificativa |
|---------|--------------|
| **Supabase Storage** em vez de Google Drive | Mesma infra, zero dependência, URL direta, CDN, 24MB de 1GB |
| **Tabela separada** `foto_pneu` | 1:N, tipificação, soft-delete granular |
| **Bucket público** | Fotos de produto não são sensíveis |
| **`foto_url` na view** `catalogo_agente` | IA recebe foto automaticamente. Zero tool call extra |
| **`RespostaTurno` com duck-typing** de string | Retrocompatível com TODOS os callers existentes. Callers novos acessam `.fotos` |
| **Backend decide** quais fotos enviar (não a IA) | Zero tokens extra no EnvelopeIA. Sem mudança no schema da IA |
| **Foto principal** apenas no fluxo automático | 1 foto suficiente para WhatsApp. Detalhes via `buscar_detalhes_pneu` |
| **Não alterar `MensagemChat`** | Persistência é do texto. Foto é metadado de envio para o canal |
| **Não alterar `EnvelopeIA`** | A IA não precisa "decidir" enviar foto — é automático pelo backend |

---

## 11. Diferenças em relação ao documento V1

| Item V1 | Problema | Correção V2 |
|---------|----------|-------------|
| Referência a `webhook.py` | **Não existe neste repo** | Removido. Fase 3 marcada como "integração externa" |
| `_enviar_resposta_chatwoot()` | Função inexistente | Removida. Envio é responsabilidade do caller |
| `_enviar_foto_chatwoot()` | Função inexistente | Removida. Código de exemplo movido para "Fase 3 externa" |
| `_processar_e_responder()` | Função inexistente | Substituída por `processar_turno()` |
| Retorno `tuple[str, list]` | Quebraria print/assert/f-string | `RespostaTurno` com duck-typing string |
| Alteração no `catalogo_repo.py` | Desnecessária | Removida. `SELECT *` já traz campo novo |
| Alteração no `buscar_pneus_por_moto()` | Desnecessária | Removida. View já retorna `foto_url` |
| Abordagem B (IA decide via EnvelopeIA) | Complexidade desnecessária para V1 | Removida da V1. Mantida como evolução futura |

---

## 12. Evolução Futura (V2+)

- **Múltiplas fotos:** Enviar carrossel com `fotos[0..N]` em vez de só a principal
- **Upload via WhatsApp:** Dono envia foto → agente detecta → salva no Storage
- **IA decide quando enviar:** Campo `enviar_fotos` no EnvelopeIA
- **Thumbnails automáticos:** Supabase Image Transformation
- **Metadata na mensagem:** Gravar URLs de fotos em `MensagemChat.metadata_json` para auditoria
