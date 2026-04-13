"""
Testes da extracao de fatos estruturados fallback (orquestrador.py).

Foca em:
- _tem_negacao_antes: deteccao de negacao (janela de 25 chars, 4 tipos de negacao)
- _KEYWORDS_FORMA_PAGAMENTO / _KEYWORDS_TIPO_ENTREGA: cobertura das keywords

Roda sem banco de dados. Puramente logico.

Execute: python -X utf8 tests/test_fatos_fallback.py
     ou: python -m pytest tests/test_fatos_fallback.py -v
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agente_2w.engine.orquestrador import (
    _tem_negacao_antes,
    _KEYWORDS_FORMA_PAGAMENTO,
    _KEYWORDS_TIPO_ENTREGA,
)

VERDE = "\033[92m"
VERMELHO = "\033[91m"
AMARELO = "\033[93m"
RESET = "\033[0m"
NEGRITO = "\033[1m"

passou = 0
falhou = 0


def check(nome: str, condicao: bool, detalhe: str = "") -> None:
    global passou, falhou
    if condicao:
        passou += 1
        print(f"  {VERDE}✓{RESET} {nome}")
    else:
        falhou += 1
        print(f"  {VERMELHO}✗ FALHOU{RESET} {nome}")
        if detalhe:
            print(f"    {AMARELO}↳ {detalhe}{RESET}")


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 1 — _tem_negacao_antes: 4 variacoes de negacao
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 1 — 4 tipos de negacao (nao/não/sem/nunca){RESET}")
print("─" * 60)

# "não" (com acento)
check(
    "'não quero pix' detecta negacao em 'pix'",
    _tem_negacao_antes("não quero pix", "pix") is True,
)
check(
    "'não aceito cartao' detecta negacao em 'cartao'",
    _tem_negacao_antes("não aceito cartao", "cartao") is True,
)

# "nao" (sem acento)
check(
    "'nao quero pix' detecta negacao em 'pix'",
    _tem_negacao_antes("nao quero pix", "pix") is True,
)
check(
    "'nao vou de entrega' detecta negacao em 'entrega'",
    _tem_negacao_antes("nao vou de entrega", "entrega") is True,
)

# "sem"
check(
    "'sem pix' detecta negacao em 'pix'",
    _tem_negacao_antes("sem pix por favor", "pix") is True,
)
check(
    "'sem dinheiro' detecta negacao em 'dinheiro'",
    _tem_negacao_antes("estou sem dinheiro", "dinheiro") is True,
)

# "nunca"
check(
    "'nunca uso cartao' detecta negacao em 'cartao'",
    _tem_negacao_antes("nunca uso cartao", "cartao") is True,
)
check(
    "'nunca peguei entrega' detecta negacao em 'entrega'",
    _tem_negacao_antes("nunca peguei entrega", "entrega") is True,
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 2 — Case insensitive
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 2 — Case insensitive{RESET}")
print("─" * 60)

check(
    "'NAO QUERO PIX' (maiusculo) detecta negacao",
    _tem_negacao_antes("NAO QUERO PIX", "pix") is True,
)
check(
    "'Não Quero Pix' (misto) detecta negacao",
    _tem_negacao_antes("Não Quero Pix", "pix") is True,
)
check(
    "'SEM ENTREGA' detecta negacao em 'entrega'",
    _tem_negacao_antes("SEM ENTREGA", "entrega") is True,
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 3 — Casos positivos (keyword sem negacao)
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 3 — Sem negacao (NAO deve detectar){RESET}")
print("─" * 60)

check(
    "'quero pix' NAO detecta negacao",
    _tem_negacao_antes("quero pagar no pix", "pix") is False,
)
check(
    "'pix por favor' NAO detecta negacao",
    _tem_negacao_antes("pix por favor", "pix") is False,
)
check(
    "'pago em dinheiro' NAO detecta negacao",
    _tem_negacao_antes("pago em dinheiro", "dinheiro") is False,
)
check(
    "'cartao de credito' NAO detecta negacao",
    _tem_negacao_antes("cartao de credito", "cartao") is False,
)
check(
    "'entrega em casa' NAO detecta negacao",
    _tem_negacao_antes("entrega em casa por favor", "entrega") is False,
)
check(
    "'retirada na loja' NAO detecta negacao",
    _tem_negacao_antes("prefiro retirada na loja", "retirada") is False,
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 4 — Janela de 25 caracteres (limite do regex)
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 4 — Janela de 25 caracteres{RESET}")
print("─" * 60)

# Dentro dos 25 chars: deve detectar
# "nao" + "X" * 20 + " pix" = 3 + 20 + 4 = 27 chars, mas entre "nao" e "pix" tem 21 chars
check(
    "Negacao a 20 chars de distancia DETECTA",
    _tem_negacao_antes("nao " + "x" * 20 + " pix", "pix") is True,
)

# Palavra de negacao a >25 chars de distancia: NAO deve detectar
# "nao" + (50 chars entre) + "pix"
texto_longo = "nao " + "palavra qualquer aqui escrevendo muito blablabla xyz abcde " + "pix"
check(
    "Negacao a >25 chars de distancia NAO detecta",
    _tem_negacao_antes(texto_longo, "pix") is False,
    f"texto: {texto_longo!r}",
)

# Negacao DEPOIS da keyword: NAO deve detectar (regex so procura antes)
check(
    "'pix, nao quero' — negacao DEPOIS da keyword NAO detecta",
    _tem_negacao_antes("pix, nao quero mais", "pix") is False,
)
check(
    "'entrega nunca!' — negacao DEPOIS da keyword NAO detecta",
    _tem_negacao_antes("entrega nunca!", "entrega") is False,
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 5 — Casos edge
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 5 — Casos edge{RESET}")
print("─" * 60)

# String vazia
check(
    "String vazia NAO detecta negacao",
    _tem_negacao_antes("", "pix") is False,
)

# Keyword ausente do texto
check(
    "Keyword ausente do texto NAO detecta negacao",
    _tem_negacao_antes("nao quero nada", "pix") is False,
)

# So keyword, sem nada antes
check(
    "Texto com so a keyword NAO detecta negacao",
    _tem_negacao_antes("pix", "pix") is False,
)

# Negacao como parte de outra palavra NAO deve disparar (\b garante word boundary)
# "naocentro" nao tem "nao" como palavra isolada
check(
    "'conosco pix' (sem negacao real) NAO detecta",
    _tem_negacao_antes("conosco pix", "pix") is False,
)

# "semana pix" — "sem" dentro de "semana" nao conta como negacao
# Porem o regex usa \b antes e depois, entao "semana" NAO dispara pois tem letras apos "sem"
check(
    "'semana pix' NAO detecta (sem dentro de semana nao e negacao)",
    _tem_negacao_antes("na semana faco pix", "pix") is False,
)

# "sempre pix" — "sempre" comeca com "sem" mas nao e negacao
check(
    "'sempre faco pix' NAO detecta (sempre nao e negacao)",
    _tem_negacao_antes("sempre faco pix", "pix") is False,
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 6 — Multiplas keywords no mesmo texto
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 6 — Multiplas keywords no texto{RESET}")
print("─" * 60)

# Uma negada e outra nao — dinheiro fica >25 chars apos "nao"
texto = "nao quero pix, mas tudo bem posso pagar com dinheiro agora"
check(
    "pix TEM negacao (proximo de 'nao')",
    _tem_negacao_antes(texto, "pix") is True,
)
check(
    "dinheiro NAO tem negacao (>25 chars de 'nao')",
    _tem_negacao_antes(texto, "dinheiro") is False,
    f"texto: {texto!r}",
)

# Duas negadas
texto = "nao aceito pix nem cartao"
check(
    "'nao aceito pix nem cartao' — pix TEM negacao",
    _tem_negacao_antes(texto, "pix") is True,
)
# cartao tambem deve detectar (negacao dentro de 25 chars)
check(
    "'nao aceito pix nem cartao' — cartao TEM negacao",
    _tem_negacao_antes(texto, "cartao") is True,
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 7 — _KEYWORDS_FORMA_PAGAMENTO: cobertura e mapeamento
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 7 — _KEYWORDS_FORMA_PAGAMENTO{RESET}")
print("─" * 60)

# Deve ser lista de tuplas (keyword, valor_normalizado)
check(
    "_KEYWORDS_FORMA_PAGAMENTO e uma lista nao-vazia",
    isinstance(_KEYWORDS_FORMA_PAGAMENTO, list) and len(_KEYWORDS_FORMA_PAGAMENTO) > 0,
)
check(
    "Cada item e tupla (keyword, valor)",
    all(isinstance(t, tuple) and len(t) == 2 for t in _KEYWORDS_FORMA_PAGAMENTO),
)

# Extrai valores normalizados possiveis
valores_pagamento = {v for _, v in _KEYWORDS_FORMA_PAGAMENTO}

# Os 4 tipos validos (baseado em FormaPagamento enum)
check(
    "'pix' esta nos valores normalizados",
    "pix" in valores_pagamento,
)
check(
    "'dinheiro' esta nos valores normalizados",
    "dinheiro" in valores_pagamento,
)
check(
    "'cartao' (sem acento) esta nos valores normalizados",
    "cartao" in valores_pagamento,
)
check(
    "'transferencia' (sem acento) esta nos valores normalizados",
    "transferencia" in valores_pagamento,
)

# Keywords com e sem acento devem estar cobertas
keywords_lower = {k.lower() for k, _ in _KEYWORDS_FORMA_PAGAMENTO}
check(
    "'cartão' (com acento) e reconhecido como keyword",
    "cartão" in keywords_lower,
)
check(
    "'cartao' (sem acento) e reconhecido como keyword",
    "cartao" in keywords_lower,
)
check(
    "'transferência' (com acento) e reconhecido como keyword",
    "transferência" in keywords_lower,
)
check(
    "'transferencia' (sem acento) e reconhecido como keyword",
    "transferencia" in keywords_lower,
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 8 — _KEYWORDS_TIPO_ENTREGA: cobertura e mapeamento
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 8 — _KEYWORDS_TIPO_ENTREGA{RESET}")
print("─" * 60)

check(
    "_KEYWORDS_TIPO_ENTREGA e uma lista nao-vazia",
    isinstance(_KEYWORDS_TIPO_ENTREGA, list) and len(_KEYWORDS_TIPO_ENTREGA) > 0,
)
check(
    "Cada item e tupla (keyword, valor)",
    all(isinstance(t, tuple) and len(t) == 2 for t in _KEYWORDS_TIPO_ENTREGA),
)

# Valores normalizados devem ser apenas "entrega" ou "retirada"
valores_entrega = {v for _, v in _KEYWORDS_TIPO_ENTREGA}
check(
    "Valores normalizados sao apenas {entrega, retirada}",
    valores_entrega == {"entrega", "retirada"},
    f"valores encontrados: {valores_entrega}",
)

# Keywords de retirada
keywords_retirada = [k for k, v in _KEYWORDS_TIPO_ENTREGA if v == "retirada"]
check(
    "Existem keywords mapeadas para 'retirada'",
    len(keywords_retirada) > 0,
    f"keywords: {keywords_retirada}",
)

# Keywords de entrega
keywords_entrega = [k for k, v in _KEYWORDS_TIPO_ENTREGA if v == "entrega"]
check(
    "Existem keywords mapeadas para 'entrega'",
    len(keywords_entrega) > 0,
    f"keywords: {keywords_entrega}",
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 9 — Integracao: keywords + _tem_negacao_antes
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 9 — Integracao keywords x _tem_negacao_antes{RESET}")
print("─" * 60)

# Cenario: entrega negada, retirada longe (>25 chars) do "nao"
texto = "nao quero entrega, mas tudo bem eu prefiro ir de retirada entao"
check(
    "entrega TEM negacao (proximo de 'nao')",
    _tem_negacao_antes(texto, "entrega") is True,
)
check(
    "retirada NAO tem negacao (>25 chars de 'nao')",
    _tem_negacao_antes(texto, "retirada") is False,
    f"texto: {texto!r}",
)

# Cenario: cartao negado, pix longe (>25 chars) do "nunca"
texto = "nunca uso cartao, entao eu vou pagar mesmo no pix hoje"
check(
    "cartao TEM negacao (proximo de 'nunca')",
    _tem_negacao_antes(texto, "cartao") is True,
)
check(
    "pix NAO tem negacao (>25 chars de 'nunca')",
    _tem_negacao_antes(texto, "pix") is False,
    f"texto: {texto!r}",
)


# ──────────────────────────────────────────────────────────────────────────────
# RESULTADO FINAL
# ──────────────────────────────────────────────────────────────────────────────

total = passou + falhou
print(f"\n{'─' * 60}")
print(f"{NEGRITO}RESULTADO: {passou}/{total} testes passaram{RESET}")

if falhou == 0:
    print(f"{VERDE}{NEGRITO}✓ Extracao de fatos fallback 100% correta.{RESET}")
else:
    print(f"{VERMELHO}{NEGRITO}✗ {falhou} teste(s) falharam — revisar orquestrador.py{RESET}")
    sys.exit(1)
