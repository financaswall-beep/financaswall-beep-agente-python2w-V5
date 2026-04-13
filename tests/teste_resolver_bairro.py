"""
Teste isolado do resolver_bairro + cache.
Valida que bairros do RJ são resolvidos para o município correto
sem exigir CEP, tolerando erros de grafia.
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from agente_2w.tools.resolver_bairro import resolver_bairro_municipio

SEP = "-" * 60

CASOS = [
    # (termo_digitado, municipio_esperado, ambiguo_esperado)
    # municipio_esperado = None quando ambiguo_esperado = True
    ("bangu",              "Rio de Janeiro", False),
    ("Bangu",              "Rio de Janeiro", False),  # mesma entrada, deve vir do cache
    ("campo grande",       "Rio de Janeiro", False),
    ("santa cruz",         "Rio de Janeiro", False),
    ("icarai",             "Niterói",        False),
    ("santa isabel",       None,             True),   # ambiguo: Magé e/ou São Gonçalo
    ("sao goncalo",        "São Gonçalo",    False),  # municipio coberto — resolver retorna ele
    ("petropolis",         None,             False),  # fora da area de cobertura
]

print()
print(SEP)
print("  TESTE RESOLVER BAIRRO -> MUNICIPIO")
print(SEP)
print()

erros = []

for termo, municipio_esperado, ambiguo_esperado in CASOS:
    bairro_res, municipio_res, ambiguos = resolver_bairro_municipio(termo)
    e_ambiguo = bool(ambiguos)

    if ambiguo_esperado:
        ok = e_ambiguo
    else:
        ok = municipio_res == municipio_esperado and not e_ambiguo

    status = "[OK]" if ok else "[FAIL]"
    print(f"  {status}  '{termo}'")
    if e_ambiguo:
        print(f"       -> bairro='{bairro_res}'  AMBÍGUO: {ambiguos}")
    else:
        print(f"       -> bairro='{bairro_res}'  municipio='{municipio_res}'")
    if not ok:
        if ambiguo_esperado:
            print(f"       !! esperado ambíguo=True, got municipio='{municipio_res}'")
        else:
            print(f"       !! esperado municipio='{municipio_esperado}'")
        erros.append(termo)
    print()

print(SEP)
if erros:
    print(f"  RESULTADO: FAIL — {len(erros)} caso(s) incorreto(s): {erros}")
    sys.exit(1)
else:
    print("  RESULTADO: PASS — todos os termos resolvidos corretamente!")
    sys.exit(0)
