"""
Testes da maquina de estados do fluxo conversacional (engine/maquina_estados.py).

Valida TODAS as transicoes permitidas e bloqueadas entre as 6 etapas do V1:
identificacao -> busca -> oferta -> confirmacao_item -> entrega_pagamento -> fechamento

Roda sem banco de dados e sem IA. Puramente logico.

Execute: python -m pytest tests/test_maquina_estados.py -v
     ou: python tests/test_maquina_estados.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agente_2w.enums.enums import EtapaFluxo
from agente_2w.engine.maquina_estados import (
    TRANSICOES_PERMITIDAS,
    transicao_permitida,
    motivo_bloqueio,
    proximas_etapas,
    e_etapa_terminal,
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


# Fonte de verdade do fluxo V1 — replicada aqui para catar qualquer regressao
# que altere TRANSICOES_PERMITIDAS sem atualizar este teste de proposito.
TRANSICOES_ESPERADAS: set[tuple[EtapaFluxo, EtapaFluxo]] = {
    (EtapaFluxo.identificacao, EtapaFluxo.busca),
    (EtapaFluxo.busca, EtapaFluxo.oferta),
    (EtapaFluxo.busca, EtapaFluxo.identificacao),
    (EtapaFluxo.oferta, EtapaFluxo.confirmacao_item),
    (EtapaFluxo.oferta, EtapaFluxo.busca),
    (EtapaFluxo.confirmacao_item, EtapaFluxo.entrega_pagamento),
    (EtapaFluxo.confirmacao_item, EtapaFluxo.oferta),
    (EtapaFluxo.confirmacao_item, EtapaFluxo.busca),
    (EtapaFluxo.entrega_pagamento, EtapaFluxo.fechamento),
    (EtapaFluxo.entrega_pagamento, EtapaFluxo.confirmacao_item),
    (EtapaFluxo.entrega_pagamento, EtapaFluxo.busca),
}

TODAS_ETAPAS = list(EtapaFluxo)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 1 — Integridade da tabela TRANSICOES_PERMITIDAS
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 1 — Integridade da tabela de transicoes{RESET}")
print("─" * 60)

check(
    "TRANSICOES_PERMITIDAS cobre todas as 6 etapas como chave",
    set(TRANSICOES_PERMITIDAS.keys()) == set(TODAS_ETAPAS),
    f"chaves: {list(TRANSICOES_PERMITIDAS.keys())}",
)

check(
    "fechamento e etapa terminal (lista vazia de destinos)",
    TRANSICOES_PERMITIDAS[EtapaFluxo.fechamento] == [],
)

# Nenhuma etapa tem self-transition (nao faz sentido voltar pra si mesmo)
for etapa in TODAS_ETAPAS:
    check(
        f"{etapa.value} nao contem self-transition",
        etapa not in TRANSICOES_PERMITIDAS[etapa],
        f"destinos de {etapa.value}: {TRANSICOES_PERMITIDAS[etapa]}",
    )


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 2 — transicao_permitida() — todas as transicoes VALIDAS retornam True
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 2 — Transicoes validas retornam True{RESET}")
print("─" * 60)

for atual, destino in TRANSICOES_ESPERADAS:
    check(
        f"{atual.value} -> {destino.value} (VALIDA)",
        transicao_permitida(atual, destino) is True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 3 — transicao_permitida() — transicoes INVALIDAS retornam False
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 3 — Transicoes invalidas retornam False{RESET}")
print("─" * 60)

# Gera todos os pares (atual, destino) possiveis e compara com as esperadas
pares_invalidos: list[tuple[EtapaFluxo, EtapaFluxo]] = []
for atual in TODAS_ETAPAS:
    for destino in TODAS_ETAPAS:
        if atual == destino:
            continue  # self-transition tratada no grupo 1
        if (atual, destino) not in TRANSICOES_ESPERADAS:
            pares_invalidos.append((atual, destino))

check(
    f"Existem {len(pares_invalidos)} pares invalidos para testar",
    len(pares_invalidos) > 0,
)

for atual, destino in pares_invalidos:
    check(
        f"{atual.value} -> {destino.value} (INVALIDA)",
        transicao_permitida(atual, destino) is False,
    )


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 4 — transicao_permitida() — self-transitions bloqueadas
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 4 — Self-transitions retornam False{RESET}")
print("─" * 60)

for etapa in TODAS_ETAPAS:
    check(
        f"{etapa.value} -> {etapa.value} e bloqueada",
        transicao_permitida(etapa, etapa) is False,
    )


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 5 — motivo_bloqueio() sempre menciona as duas etapas
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 5 — motivo_bloqueio() retorna mensagem informativa{RESET}")
print("─" * 60)

# Testamos com pares invalidos reais
casos_motivo = [
    (EtapaFluxo.identificacao, EtapaFluxo.fechamento),
    (EtapaFluxo.busca, EtapaFluxo.fechamento),
    (EtapaFluxo.fechamento, EtapaFluxo.busca),
]

for atual, destino in casos_motivo:
    motivo = motivo_bloqueio(atual, destino)
    check(
        f"motivo({atual.value}->{destino.value}) menciona etapa atual",
        atual.value in motivo,
        f"motivo: {motivo!r}",
    )
    check(
        f"motivo({atual.value}->{destino.value}) menciona etapa destino",
        destino.value in motivo,
        f"motivo: {motivo!r}",
    )
    check(
        f"motivo({atual.value}->{destino.value}) e string nao vazia",
        isinstance(motivo, str) and len(motivo.strip()) > 0,
    )


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 6 — proximas_etapas() retorna a lista correta
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 6 — proximas_etapas() retorna lista correta{RESET}")
print("─" * 60)

for etapa in TODAS_ETAPAS:
    esperado = TRANSICOES_PERMITIDAS[etapa]
    obtido = proximas_etapas(etapa)
    check(
        f"proximas_etapas({etapa.value}) == {[e.value for e in esperado]}",
        obtido == esperado,
        f"obtido: {[e.value for e in obtido]}",
    )

# proximas_etapas deve retornar lista (nao None, nao set, nao tupla)
check(
    "proximas_etapas sempre retorna list",
    all(isinstance(proximas_etapas(e), list) for e in TODAS_ETAPAS),
)

# fechamento retorna lista vazia
check(
    "proximas_etapas(fechamento) == [] (vazia)",
    proximas_etapas(EtapaFluxo.fechamento) == [],
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 7 — e_etapa_terminal() identifica fechamento como terminal
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 7 — e_etapa_terminal(){RESET}")
print("─" * 60)

check(
    "fechamento e terminal",
    e_etapa_terminal(EtapaFluxo.fechamento) is True,
)

# Todas as outras etapas NAO sao terminais
nao_terminais = [e for e in TODAS_ETAPAS if e != EtapaFluxo.fechamento]
for etapa in nao_terminais:
    check(
        f"{etapa.value} NAO e terminal",
        e_etapa_terminal(etapa) is False,
    )

# Exatamente 1 etapa terminal no fluxo V1
qtd_terminais = sum(1 for e in TODAS_ETAPAS if e_etapa_terminal(e))
check(
    "Fluxo V1 tem exatamente 1 etapa terminal",
    qtd_terminais == 1,
    f"terminais encontradas: {qtd_terminais}",
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 8 — Propriedades do fluxo V1 (regras de negocio)
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 8 — Propriedades do fluxo V1{RESET}")
print("─" * 60)

# Propriedade: toda etapa (exceto fechamento) tem pelo menos 1 destino
# Garante que nao existe "dead end" no meio do fluxo
for etapa in nao_terminais:
    check(
        f"{etapa.value} tem pelo menos 1 destino (nao e dead-end)",
        len(proximas_etapas(etapa)) >= 1,
    )

# Propriedade: identificacao -> busca e o unico caminho de saida da identificacao
check(
    "identificacao tem apenas 1 destino permitido",
    len(proximas_etapas(EtapaFluxo.identificacao)) == 1,
)
check(
    "identificacao so pode ir para busca",
    proximas_etapas(EtapaFluxo.identificacao) == [EtapaFluxo.busca],
)

# Propriedade: fechamento so pode ser atingido via entrega_pagamento
etapas_que_vao_para_fechamento = [
    e for e in TODAS_ETAPAS
    if EtapaFluxo.fechamento in proximas_etapas(e)
]
check(
    "Apenas entrega_pagamento pode transicionar para fechamento",
    etapas_que_vao_para_fechamento == [EtapaFluxo.entrega_pagamento],
    f"etapas que vao para fechamento: {[e.value for e in etapas_que_vao_para_fechamento]}",
)

# Propriedade Fase 14 — multi-pneu/multi-moto: confirmacao_item e entrega_pagamento
# podem voltar para busca (adicionar_outro_item)
check(
    "Fase 14: confirmacao_item -> busca e permitida (adicionar_outro_item)",
    transicao_permitida(EtapaFluxo.confirmacao_item, EtapaFluxo.busca) is True,
)
check(
    "Fase 14: entrega_pagamento -> busca e permitida (adicionar_outro_item)",
    transicao_permitida(EtapaFluxo.entrega_pagamento, EtapaFluxo.busca) is True,
)

# Propriedade: cliente pode voltar para etapa anterior em varios pontos (correcao)
check(
    "oferta -> busca e permitida (refinar busca)",
    transicao_permitida(EtapaFluxo.oferta, EtapaFluxo.busca) is True,
)
check(
    "confirmacao_item -> oferta e permitida (ver outras opcoes)",
    transicao_permitida(EtapaFluxo.confirmacao_item, EtapaFluxo.oferta) is True,
)
check(
    "entrega_pagamento -> confirmacao_item e permitida (revisar itens)",
    transicao_permitida(EtapaFluxo.entrega_pagamento, EtapaFluxo.confirmacao_item) is True,
)

# Propriedade: fluxo feliz completo (identificacao -> ... -> fechamento) e possivel
caminho_feliz = [
    (EtapaFluxo.identificacao, EtapaFluxo.busca),
    (EtapaFluxo.busca, EtapaFluxo.oferta),
    (EtapaFluxo.oferta, EtapaFluxo.confirmacao_item),
    (EtapaFluxo.confirmacao_item, EtapaFluxo.entrega_pagamento),
    (EtapaFluxo.entrega_pagamento, EtapaFluxo.fechamento),
]
for atual, destino in caminho_feliz:
    check(
        f"Caminho feliz: {atual.value} -> {destino.value}",
        transicao_permitida(atual, destino) is True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 9 — Transicoes que NUNCA podem ocorrer (saltos proibidos)
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GRUPO 9 — Saltos proibidos do fluxo V1{RESET}")
print("─" * 60)

saltos_proibidos = [
    # Nao pode pular etapas
    (EtapaFluxo.identificacao, EtapaFluxo.oferta),
    (EtapaFluxo.identificacao, EtapaFluxo.confirmacao_item),
    (EtapaFluxo.identificacao, EtapaFluxo.entrega_pagamento),
    (EtapaFluxo.identificacao, EtapaFluxo.fechamento),
    (EtapaFluxo.busca, EtapaFluxo.confirmacao_item),
    (EtapaFluxo.busca, EtapaFluxo.entrega_pagamento),
    (EtapaFluxo.busca, EtapaFluxo.fechamento),
    (EtapaFluxo.oferta, EtapaFluxo.entrega_pagamento),
    (EtapaFluxo.oferta, EtapaFluxo.fechamento),
    (EtapaFluxo.confirmacao_item, EtapaFluxo.fechamento),
    # Fechamento e terminal — nao sai dele
    (EtapaFluxo.fechamento, EtapaFluxo.identificacao),
    (EtapaFluxo.fechamento, EtapaFluxo.busca),
    (EtapaFluxo.fechamento, EtapaFluxo.oferta),
    (EtapaFluxo.fechamento, EtapaFluxo.confirmacao_item),
    (EtapaFluxo.fechamento, EtapaFluxo.entrega_pagamento),
]

for atual, destino in saltos_proibidos:
    check(
        f"PROIBIDO: {atual.value} -> {destino.value}",
        transicao_permitida(atual, destino) is False,
    )


# ──────────────────────────────────────────────────────────────────────────────
# RESULTADO FINAL
# ──────────────────────────────────────────────────────────────────────────────

total = passou + falhou
print(f"\n{'─' * 60}")
print(f"{NEGRITO}RESULTADO: {passou}/{total} testes passaram{RESET}")

if falhou == 0:
    print(f"{VERDE}{NEGRITO}✓ Maquina de estados 100% correta.{RESET}")
else:
    print(f"{VERMELHO}{NEGRITO}✗ {falhou} teste(s) falharam — revisar maquina_estados.py{RESET}")
    sys.exit(1)
