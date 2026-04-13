"""
Testes da normalização de termos de busca de moto (Fase 21).

Testa as 4 regras universais: fabricante, hífen/ponto, espaço letra→número, acento.
Roda sem banco de dados — testa apenas a função de normalização.

Execute: python -m pytest tests/test_normalizacao_moto.py -v
     ou: python tests/test_normalizacao_moto.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agente_2w.tools.busca_catalogo import _normalizar_termo_moto

VERDE   = "\033[92m"
VERMELHO = "\033[91m"
RESET   = "\033[0m"
NEGRITO = "\033[1m"

passou = 0
falhou = 0


def check(nome: str, termo_entrada: str, esperado_conter: str) -> None:
    global passou, falhou
    variacoes = _normalizar_termo_moto(termo_entrada)
    if esperado_conter in variacoes:
        passou += 1
        print(f"  {VERDE}✓{RESET} {nome}")
        print(f"      '{termo_entrada}' → variações: {variacoes}")
    else:
        falhou += 1
        print(f"  {VERMELHO}✗ FALHOU{RESET} {nome}")
        print(f"      '{termo_entrada}' → variações: {variacoes}")
        print(f"      esperava encontrar: '{esperado_conter}'")


# ──────────────────────────────────────────────────────────────────────────────
# REGRA 1 — Remove fabricante
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}REGRA 1 — Remove fabricante{RESET}")
print("─" * 60)

check("honda cb300",        "honda cb300",        "cb 300")
check("honda cg 160",       "honda cg 160",       "cg 160")
check("yamaha fazer 250",   "yamaha fazer 250",   "fazer 250")
check("yamaha xre300",      "yamaha xre300",      "xre 300")
check("kawasaki z400",      "kawasaki z400",      "z 400")
check("kawasaki ninja 300", "kawasaki ninja 300", "ninja 300")
check("suzuki yes",         "suzuki yes",         "yes")
check("bmw g310",           "bmw g310",           "g 310")
check("royal enfield",      "royal enfield himalayan", "himalayan")

# ──────────────────────────────────────────────────────────────────────────────
# REGRA 2 — Hífen e ponto viram espaço
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}REGRA 2 — Hífen/ponto → espaço{RESET}")
print("─" * 60)

check("cb-300",    "cb-300",    "cb 300")
check("xre-300",   "xre-300",   "xre 300")
check("mt-07",     "mt-07",     "mt 07")
check("cb.300",    "cb.300",    "cb 300")
check("cg.160",    "cg.160",    "cg 160")
check("nxr-bros",  "nxr-bros",  "nxr bros")

# ──────────────────────────────────────────────────────────────────────────────
# REGRA 3 — Espaço entre letra e número
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}REGRA 3 — Espaço letra→número{RESET}")
print("─" * 60)

check("cb300",    "cb300",    "cb 300")
check("cg160",    "cg160",    "cg 160")
check("xre300",   "xre300",   "xre 300")
check("pcx150",   "pcx150",   "pcx 150")
check("fan125",   "fan125",   "fan 125")
check("cbr600",   "cbr600",   "cbr 600")
check("z400",     "z400",     "z 400")
check("g310",     "g310",     "g 310")
check("nxr160",   "nxr160",   "nxr 160")

# ──────────────────────────────────────────────────────────────────────────────
# REGRA 4 — Remove acentos
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}REGRA 4 — Remove acentos{RESET}")
print("─" * 60)

check("ténéré",         "ténéré",         "tenere")
check("ténéré 250",     "ténéré 250",     "tenere 250")
check("láguna",         "láguna",         "laguna")

# ──────────────────────────────────────────────────────────────────────────────
# COMBINAÇÕES — Múltiplas regras juntas
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}COMBINAÇÕES — Múltiplas regras juntas{RESET}")
print("─" * 60)

check("honda cb-300",        "honda cb-300",        "cb 300")
check("yamaha xre300",       "yamaha xre300",       "xre 300")
check("kawasaki z-400",      "kawasaki z-400",      "z 400")
check("honda nxr160 bros",   "honda nxr160 bros",   "nxr 160 bros")
check("yamaha ténéré 250",   "yamaha ténéré 250",   "tenere 250")
check("honda cb300 twister", "honda cb300 twister", "cb 300 twister")

# ──────────────────────────────────────────────────────────────────────────────
# PROTEÇÕES — Não deve quebrar casos normais
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}PROTEÇÕES — Casos normais não devem quebrar{RESET}")
print("─" * 60)

check("CG 160",     "CG 160",     "cg 160")
check("CB 300",     "CB 300",     "cb 300")
check("XRE 300",    "XRE 300",    "xre 300")
check("Biz 125",    "Biz 125",    "biz 125")
check("Factor 150", "Factor 150", "factor 150")
check("Lander 250", "Lander 250", "lander 250")

# ──────────────────────────────────────────────────────────────────────────────
# RESULTADO
# ──────────────────────────────────────────────────────────────────────────────

total = passou + falhou
print(f"\n{'─' * 60}")
print(f"{NEGRITO}RESULTADO: {passou}/{total} testes passaram{RESET}")

if falhou == 0:
    print(f"{VERDE}{NEGRITO}✓ Normalização funcionando para todos os casos.{RESET}")
else:
    print(f"{VERMELHO}{NEGRITO}✗ {falhou} teste(s) falharam.{RESET}")
    sys.exit(1)
