"""
Testes de _parsear_localidade_endereco (orquestrador.py).

Extrai (municipio, bairro) a partir de um fato 'endereco_entrega':
- Caso 1: valor_json estruturado com chaves municipio/cidade/bairro
- Caso 2: valor_texto livre ("Rua X, 123, Bairro Centro, Caxias do Sul, RS")

Roda sem banco de dados. Usa SimpleNamespace como stub de Fato.

Execute: python -X utf8 tests/test_parsear_localidade_endereco.py
"""

import sys
import os
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agente_2w.engine.orquestrador import _parsear_localidade_endereco

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


def fato(valor_json=None, valor_texto=None):
    """Stub de um Fato com os dois campos lidos pela funcao."""
    return SimpleNamespace(valor_json=valor_json, valor_texto=valor_texto)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 1 — valor_json estruturado (caminho feliz)
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 1 — valor_json estruturado{RESET}")
print("─" * 60)

check(
    "JSON com municipio e bairro extrai ambos",
    _parsear_localidade_endereco(
        fato(valor_json={"municipio": "Caxias do Sul", "bairro": "Centro"})
    ) == ("Caxias do Sul", "Centro"),
)

check(
    "JSON com chave 'cidade' e aceito como municipio",
    _parsear_localidade_endereco(
        fato(valor_json={"cidade": "Porto Alegre", "bairro": "Menino Deus"})
    ) == ("Porto Alegre", "Menino Deus"),
)

check(
    "JSON so com municipio (bairro None)",
    _parsear_localidade_endereco(
        fato(valor_json={"municipio": "Bento Goncalves"})
    ) == ("Bento Goncalves", None),
)

check(
    "JSON so com bairro (municipio None)",
    _parsear_localidade_endereco(
        fato(valor_json={"bairro": "Sao Pelegrino"})
    ) == (None, "Sao Pelegrino"),
)

check(
    "JSON vazio retorna (None, None)",
    _parsear_localidade_endereco(fato(valor_json={})) == (None, None),
)

check(
    "JSON com strings vazias retorna (None, None)",
    _parsear_localidade_endereco(
        fato(valor_json={"municipio": "", "bairro": ""})
    ) == (None, None),
)

check(
    "JSON prefere 'municipio' sobre 'cidade' quando ambos existem",
    _parsear_localidade_endereco(
        fato(valor_json={"municipio": "Caxias", "cidade": "Ignorada", "bairro": "X"})
    ) == ("Caxias", "X"),
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 2 — valor_texto livre (parse com virgulas)
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 2 — valor_texto livre{RESET}")
print("─" * 60)

# Formato tipico: logradouro, numero, bairro, municipio, UF
check(
    "'Rua X, 123, Bairro Centro, Caxias do Sul, RS' extrai tudo",
    _parsear_localidade_endereco(
        fato(valor_texto="Rua X, 123, Bairro Centro, Caxias do Sul, RS")
    ) == ("Caxias do Sul", "Centro"),
)

check(
    "'Av Paulista, 1000, Bairro Bela Vista, Sao Paulo, SP' extrai tudo",
    _parsear_localidade_endereco(
        fato(valor_texto="Av Paulista, 1000, Bairro Bela Vista, Sao Paulo, SP")
    ) == ("Sao Paulo", "Bela Vista"),
)

# Sem prefixo "Bairro " — pega penultimo candidato
check(
    "'Rua X, 45, Centro, Caxias do Sul, RS' — pega penultimo como bairro",
    _parsear_localidade_endereco(
        fato(valor_texto="Rua X, 45, Centro, Caxias do Sul, RS")
    ) == ("Caxias do Sul", "Centro"),
)

# So municipio e UF
check(
    "'Caxias do Sul, RS' extrai so municipio",
    _parsear_localidade_endereco(
        fato(valor_texto="Caxias do Sul, RS")
    ) == ("Caxias do Sul", None),
)

# Com CEP
check(
    "'Rua X, 123, 95000000, Centro, Caxias do Sul, RS' remove CEP",
    _parsear_localidade_endereco(
        fato(valor_texto="Rua X, 123, 95000000, Centro, Caxias do Sul, RS")
    ) == ("Caxias do Sul", "Centro"),
)

# Com CEP com hifen
check(
    "'Rua X, 95000-000, Centro, Caxias do Sul' — CEP com hifen removido",
    _parsear_localidade_endereco(
        fato(valor_texto="Rua X, 95000-000, Centro, Caxias do Sul")
    ) == ("Caxias do Sul", "Centro"),
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 3 — Prefixos de logradouro sao filtrados
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 3 — Prefixos de logradouro filtrados{RESET}")
print("─" * 60)

prefixos_casos = [
    ("Rua dos Andradas, 100, Centro, Porto Alegre, RS", "Porto Alegre", "Centro"),
    ("Av Brasil, 500, Centro, Caxias, RS", "Caxias", "Centro"),
    ("Avenida Ipiranga, 1000, Partenon, Porto Alegre, RS", "Porto Alegre", "Partenon"),
    ("Alameda Santos, 50, Jardins, Sao Paulo, SP", "Sao Paulo", "Jardins"),
    ("Travessa Azevedo, 12, Cidade Baixa, Porto Alegre, RS", "Porto Alegre", "Cidade Baixa"),
    ("Estrada do Sol, 99, Interior, Bento, RS", "Bento", "Interior"),
    ("Rodovia BR 116, KM 10, Zona Rural, Caxias, RS", "Caxias", "Zona Rural"),
    ("Praca da Se, 1, Se, Sao Paulo, SP", "Sao Paulo", "Se"),
    ("Largo do Arouche, 5, Republica, Sao Paulo, SP", "Sao Paulo", "Republica"),
]

for texto, munic_esp, bairro_esp in prefixos_casos:
    resultado = _parsear_localidade_endereco(fato(valor_texto=texto))
    check(
        f"'{texto[:40]}...' -> ({munic_esp}, {bairro_esp})",
        resultado == (munic_esp, bairro_esp),
        f"obtido: {resultado}",
    )


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 4 — Edge cases
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 4 — Edge cases{RESET}")
print("─" * 60)

check(
    "valor_texto=None e valor_json=None retorna (None, None)",
    _parsear_localidade_endereco(fato()) == (None, None),
)

check(
    "valor_texto='' (string vazia) retorna (None, None)",
    _parsear_localidade_endereco(fato(valor_texto="")) == (None, None),
)

check(
    "valor_texto='   ' (so espacos) retorna (None, None)",
    _parsear_localidade_endereco(fato(valor_texto="   ")) == (None, None),
)

# So virgulas
check(
    "valor_texto=',,,' retorna (None, None)",
    _parsear_localidade_endereco(fato(valor_texto=",,,")) == (None, None),
)

# Texto sem virgulas
check(
    "texto sem virgulas e tratado como candidato unico (municipio)",
    _parsear_localidade_endereco(
        fato(valor_texto="Caxias do Sul")
    ) == ("Caxias do Sul", None),
)

# valor_json nao e dict (tipo inesperado) — cai no fluxo de texto
check(
    "valor_json=[] (nao-dict) cai no fluxo de texto",
    _parsear_localidade_endereco(
        fato(valor_json=[], valor_texto="Caxias do Sul, RS")
    ) == ("Caxias do Sul", None),
)

# So numeros e UF — nenhum candidato valido
check(
    "'123, 95000000, RS' retorna (None, None) — so lixo",
    _parsear_localidade_endereco(
        fato(valor_texto="123, 95000000, RS")
    ) == (None, None),
)

# Case insensitive: "BAIRRO " e "bairro " devem ambos funcionar
check(
    "'Bairro Centro' (capitalizado) e reconhecido",
    _parsear_localidade_endereco(
        fato(valor_texto="Rua X, 1, Bairro Centro, Caxias, RS")
    ) == ("Caxias", "Centro"),
)

check(
    "'bairro centro' (minusculo) e reconhecido (UF precisa ser maiuscula)",
    _parsear_localidade_endereco(
        fato(valor_texto="rua x, 1, bairro centro, caxias, RS")
    ) == ("caxias", "centro"),
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 5 — JSON tem prioridade sobre texto
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 5 — Prioridade JSON > texto{RESET}")
print("─" * 60)

check(
    "Quando valor_json E valor_texto existem, JSON ganha",
    _parsear_localidade_endereco(
        fato(
            valor_json={"municipio": "Gramado", "bairro": "Planalto"},
            valor_texto="Rua X, 1, Centro, Caxias, RS",
        )
    ) == ("Gramado", "Planalto"),
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 6 — Sigla de estado (UF) e filtrada
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 6 — Sigla UF filtrada{RESET}")
print("─" * 60)

# UF no final nao vira municipio
for uf in ["RS", "SP", "RJ", "MG", "SC", "PR", "BA", "DF"]:
    resultado = _parsear_localidade_endereco(
        fato(valor_texto=f"Rua X, 1, Centro, Canela, {uf}")
    )
    check(
        f"UF '{uf}' no final nao e tratada como municipio",
        resultado == ("Canela", "Centro"),
        f"obtido: {resultado}",
    )

# UF minuscula NAO e filtrada (regex exige maiuscula) — comportamento atual
check(
    "UF minuscula 'rs' passa pelo filtro (fica como candidato)",
    _parsear_localidade_endereco(
        fato(valor_texto="rua x, 1, centro, canela, rs")
    )[0] == "rs",  # "rs" vira o ultimo candidato (municipio)
)


# ──────────────────────────────────────────────────────────────────────────────
# RESULTADO FINAL
# ──────────────────────────────────────────────────────────────────────────────

total = passou + falhou
print(f"\n{'─' * 60}")
print(f"{NEGRITO}RESULTADO: {passou}/{total} testes passaram{RESET}")

if falhou == 0:
    print(f"{VERDE}{NEGRITO}✓ _parsear_localidade_endereco 100% correto.{RESET}")
else:
    print(f"{VERMELHO}{NEGRITO}✗ {falhou} teste(s) falharam — revisar orquestrador.py{RESET}")
    sys.exit(1)
