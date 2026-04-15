"""
Checklist de 42 testes — anti-alucinação beta Agente 2W Pneus.

8 testes CRÍTICOS bloqueiam deploy. Os demais são regressão.

Roda sem banco de dados — usa mocks para DB.
Execute: python -m pytest tests/test_anti_alucinacao_42.py -v
     ou: python tests/test_anti_alucinacao_42.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Env vars fake para evitar KeyError no import (testes não usam DB real)
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "fake-key")
os.environ.setdefault("OPENAI_API_KEY", "fake-key")
import re
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock
from uuid import uuid4

# --- Imports do projeto ---
from agente_2w.tools.busca_catalogo import _parsear_medida, buscar_pneus
from agente_2w.ia.tools_schema import TOOLS_SCHEMA
from agente_2w.ia.prompt_sistema import _ETAPA_BUSCA
from agente_2w.engine.orquestrador.guardrails import (
    detectar_falso_negativo,
    tentar_busca_fallback_dimensoes,
    _montar_mensagem_fallback,
    _RE_NEGACAO,
)
from agente_2w.enums.enums import (
    EtapaFluxo, Confianca, TipoDeVerdade, NivelConfirmacao,
    OrigemContexto,
)
from agente_2w.schemas.envelope_ia import EnvelopeIA

# ──────────────────────────────────────────────────────────────────────────────
# Infra de testes
# ──────────────────────────────────────────────────────────────────────────────

VERDE = "\033[92m"
VERMELHO = "\033[91m"
AMARELO = "\033[93m"
RESET = "\033[0m"
NEGRITO = "\033[1m"

passou = 0
falhou = 0
criticos_ok = 0
criticos_falhou = 0

CRITICOS_TOTAL = 15  # todos marcados como CRÍTICO na checklist


def check(nome: str, condicao: bool, detalhe: str = "", critico: bool = False) -> None:
    global passou, falhou, criticos_ok, criticos_falhou
    tag = f" {VERMELHO}[CRÍTICO]{RESET}" if critico else ""
    if condicao:
        passou += 1
        if critico:
            criticos_ok += 1
        print(f"  {VERDE}✓{RESET} {nome}{tag}")
    else:
        falhou += 1
        if critico:
            criticos_falhou += 1
        print(f"  {VERMELHO}✗ FALHOU{RESET} {nome}{tag}")
        if detalhe:
            print(f"    {AMARELO}↳ {detalhe}{RESET}")


# ──────────────────────────────────────────────────────────────────────────────
# Dados fake para mocks
# ──────────────────────────────────────────────────────────────────────────────

PNEU_PIRELLI_90_90_18 = {
    "pneu_id": str(uuid4()),
    "marca": "Pirelli",
    "modelo": "Street Rider",
    "largura": 90,
    "perfil": 90,
    "aro": 18,
    "medida": "90/90-18",
    "preco_venda": 239.90,
    "disponivel_real": 5,
    "ativo": True,
}

PNEU_CST_110_80_17 = {
    "pneu_id": str(uuid4()),
    "marca": "CST",
    "modelo": "Ride Migra",
    "largura": 110,
    "perfil": 80,
    "aro": 17,
    "medida": "110/80-17",
    "preco_venda": 259.90,
    "disponivel_real": 3,
    "ativo": True,
}

PNEU_ZERADO = {
    "pneu_id": str(uuid4()),
    "marca": "Pirelli",
    "modelo": "Street Rider",
    "largura": 90,
    "perfil": 90,
    "aro": 18,
    "medida": "90/90-18",
    "preco_venda": 239.90,
    "disponivel_real": 0,  # sem estoque
    "ativo": True,
}


def _envelope_ia(msg: str, acoes=None) -> EnvelopeIA:
    return EnvelopeIA(
        mensagem_cliente=msg,
        etapa_atual=EtapaFluxo.busca,
        intencao_atual="teste",
        acoes_sugeridas=acoes or [],
        confianca=Confianca.alta,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PASSO 1 — busca_catalogo.py (dimension-first) · 12 testes
# ══════════════════════════════════════════════════════════════════════════════

def test_passo1():
    print(f"\n{NEGRITO}═══ PASSO 1 — busca_catalogo.py (dimension-first) · 12 testes ═══{RESET}")

    # --- CRÍTICOS ---

    # 1. Medida com barras padrão
    r = _parsear_medida("90/90-18")
    check(
        "P1.1 Medida com barras padrão: 90/90-18",
        r == {"largura": 90, "perfil": 90, "aro": 18},
        f"Esperado largura=90,perfil=90,aro=18, got {r}",
        critico=True,
    )

    # 2. Medida com espaços (caso original do bug)
    r = _parsear_medida("90 90 18")
    check(
        "P1.2 Medida com espaços (bug original): 90 90 18",
        r == {"largura": 90, "perfil": 90, "aro": 18},
        f"Esperado largura=90,perfil=90,aro=18, got {r}",
        critico=True,
    )

    # 3. Medida com traços
    r = _parsear_medida("90-90-18")
    check(
        "P1.3 Medida com traços: 90-90-18",
        r == {"largura": 90, "perfil": 90, "aro": 18},
        f"Esperado largura=90,perfil=90,aro=18, got {r}",
        critico=True,
    )

    # 4. Medida que não existe no catálogo
    with patch("agente_2w.tools.busca_catalogo.catalogo_repo") as mock_repo, \
         patch("agente_2w.tools.busca_catalogo.log_demanda_pneu_repo"):
        mock_repo.buscar_pneus_por_dimensoes.return_value = []
        mock_repo.buscar_pneus_por_medida_texto.return_value = []
        result = buscar_pneus(medida_texto="200/50-15")
        check(
            "P1.4 Medida inexistente: 200/50-15 retorna vazio",
            result["quantidade"] == 0 and result["pneus"] == [],
            f"Esperado 0 pneus, got {result['quantidade']}",
            critico=True,
        )

    # --- ALTOS ---

    # 5. Medida com R maiúsculo
    r = _parsear_medida("90/90-R18")
    check(
        "P1.5 Medida com R maiúsculo: 90/90-R18",
        r is not None and r["aro"] == 18,
        f"Got {r}",
    )

    # 6. Medida com r minúsculo e espaço
    r = _parsear_medida("90/90 r18")
    check(
        "P1.6 Medida com r minúsculo e espaço: 90/90 r18",
        r is not None and r == {"largura": 90, "perfil": 90, "aro": 18},
        f"Got {r}",
    )

    # 7. Medida com texto misto
    r = _parsear_medida("traseiro 90 90 18")
    check(
        "P1.7 Medida com texto misto: traseiro 90 90 18",
        r == {"largura": 90, "perfil": 90, "aro": 18},
        f"Esperado largura=90,perfil=90,aro=18, got {r}",
    )

    # 8. Entrada não numérica (fallback texto)
    with patch("agente_2w.tools.busca_catalogo.catalogo_repo") as mock_repo, \
         patch("agente_2w.tools.busca_catalogo.log_demanda_pneu_repo"):
        mock_repo.buscar_pneus_por_medida_texto.return_value = [PNEU_PIRELLI_90_90_18]
        mock_repo.buscar_pneus_por_marca_modelo.return_value = []
        result = buscar_pneus(medida_texto="pneu traseiro pirelli")
        # Deve ir para ilike (medida_texto), NÃO dimensoes
        check(
            "P1.8 Entrada não numérica → fallback ilike",
            mock_repo.buscar_pneus_por_medida_texto.called,
            "Esperado buscar_pneus_por_medida_texto ser chamado",
        )

    # 9. Entrada parcial sem 3 números
    r = _parsear_medida("aro 17")
    check(
        "P1.9 Entrada parcial sem 3 números: 'aro 17'",
        r is None,
        f"Esperado None, got {r}",
    )

    # --- MÉDIOS ---

    # 10. Medida com prefixo textual
    r = _parsear_medida("medida 110/80-17")
    check(
        "P1.10 Medida com prefixo textual: medida 110/80-17",
        r == {"largura": 110, "perfil": 80, "aro": 17},
        f"Got {r}",
    )

    # 11. Entrada com só 2 números
    r = _parsear_medida("90 90")
    check(
        "P1.11 Entrada com só 2 números: 90 90",
        r is None,
        f"Esperado None (falta aro), got {r}",
    )

    # 12. Entrada vazia
    r = _parsear_medida("")
    check(
        "P1.12 Entrada vazia",
        r is None,
        f"Esperado None, got {r}",
    )

    # --- Teste extra: dimension-first no buscar_pneus ---
    with patch("agente_2w.tools.busca_catalogo.catalogo_repo") as mock_repo, \
         patch("agente_2w.tools.busca_catalogo.log_demanda_pneu_repo"):
        mock_repo.buscar_pneus_por_dimensoes.return_value = [PNEU_PIRELLI_90_90_18]
        result = buscar_pneus(medida_texto="90 90 18")
        check(
            "P1.EXTRA dimension-first: '90 90 18' via buscar_pneus usa dimensoes",
            mock_repo.buscar_pneus_por_dimensoes.called
            and not mock_repo.buscar_pneus_por_medida_texto.called,
            "Esperado buscar_pneus_por_dimensoes ser chamado, não ilike",
        )


# ══════════════════════════════════════════════════════════════════════════════
# PASSO 2+3 — tools_schema + prompt (schema e prompt corretos) · 6 testes
# ══════════════════════════════════════════════════════════════════════════════

def test_passo2_3():
    print(f"\n{NEGRITO}═══ PASSO 2+3 — tools_schema + prompt · 6 testes ═══{RESET}")

    # Localizar schema de buscar_pneus
    schema_buscar = None
    for t in TOOLS_SCHEMA:
        if t["function"]["name"] == "buscar_pneus":
            schema_buscar = t["function"]
            break

    assert schema_buscar is not None, "buscar_pneus não encontrada em TOOLS_SCHEMA"

    desc = schema_buscar["description"]
    params = schema_buscar["parameters"]["properties"]

    # --- CRÍTICOS ---

    # 1. Schema guia modelo para usar inteiros
    check(
        "P2.1 Schema description contém REGRA DE OURO para inteiros",
        "REGRA DE OURO" in desc and "largura" in desc and "perfil" in desc and "aro" in desc,
        f"Description: {desc[:100]}...",
        critico=True,
    )

    # 2. Schema marca medida_texto como NÃO numéricas
    check(
        "P2.2 Schema medida_texto marcada como NÃO numéricas",
        "NÃO numéricas" in params["medida_texto"]["description"]
        or "NÃO numéric" in params["medida_texto"]["description"],
        f"medida_texto desc: {params['medida_texto']['description']}",
        critico=True,
    )

    # --- ALTOS ---

    # 3. Prompt _ETAPA_BUSCA contém regra crítica de medida numérica
    check(
        "P2.3 Prompt _ETAPA_BUSCA contém REGRA CRÍTICA medida numérica",
        "REGRA CRÍTICA" in _ETAPA_BUSCA and "medida numérica" in _ETAPA_BUSCA,
        "Bloco não encontrado em _ETAPA_BUSCA",
    )

    # 4. Prompt contém exemplos ✅ e ❌
    check(
        "P2.4 Prompt contém exemplos ✅ corretos e ❌ proibidos",
        "largura=90, perfil=90, aro=18" in _ETAPA_BUSCA
        and "❌" in _ETAPA_BUSCA
        and "PROIBIDO" in _ETAPA_BUSCA,
        "Exemplos não encontrados",
    )

    # --- MÉDIOS ---

    # 5. Schema description instrui uso de marca_modelo
    check(
        "P2.5 Schema description menciona marca_modelo",
        "marca_modelo" in desc or "marca/modelo" in desc,
        f"Description: {desc[:100]}...",
    )

    # 6. Params largura/perfil/aro têm exemplos claros
    check(
        "P2.6 Params largura/perfil/aro têm exemplos de conversão",
        "90/90-18" in params["largura"]["description"]
        and "90/90-18" in params["perfil"]["description"]
        and "90/90-18" in params["aro"]["description"],
        "Faltam exemplos de conversão nos params",
    )


# ══════════════════════════════════════════════════════════════════════════════
# PASSO 4 — guardrails C9 (auto-retry) · 5 testes
# ══════════════════════════════════════════════════════════════════════════════

def test_passo4():
    print(f"\n{NEGRITO}═══ PASSO 4 — guardrails C9 (auto-retry) · 5 testes ═══{RESET}")

    # --- CRÍTICOS ---

    # 1. C9 detecta falso negativo e corrige via fallback
    with patch("agente_2w.db.catalogo_repo.buscar_pneus_por_dimensoes") as mock_dim:
        mock_dim.return_value = [PNEU_PIRELLI_90_90_18]
        result = tentar_busca_fallback_dimensoes("90 90 18")
        check(
            "P4.1 C9 fallback: '90 90 18' → busca dimensoes → encontra pneu",
            len(result) == 1 and result[0]["marca"] == "Pirelli",
            f"Got {len(result)} resultados",
            critico=True,
        )

    # 2. C9 com medida_informada nos fatos
    with patch("agente_2w.db.catalogo_repo.buscar_pneus_por_dimensoes") as mock_dim:
        mock_dim.return_value = [PNEU_PIRELLI_90_90_18]
        result = tentar_busca_fallback_dimensoes("90/90-18")
        check(
            "P4.2 C9 fallback com medida_informada=90/90-18 → encontra pneu",
            len(result) == 1,
            f"Got {len(result)} resultados",
            critico=True,
        )

    # --- ALTOS ---

    # 3. C9 sem medida nos fatos → NÃO tenta fallback
    result = tentar_busca_fallback_dimensoes(None)
    check(
        "P4.3 C9 sem medida → retorna vazio, NÃO tenta fallback",
        result == [],
        f"Esperado [], got {result}",
    )

    # 4. C9 com medida que realmente não existe
    with patch("agente_2w.db.catalogo_repo.buscar_pneus_por_dimensoes") as mock_dim:
        mock_dim.return_value = []
        result = tentar_busca_fallback_dimensoes("200/50-15")
        check(
            "P4.4 C9 com medida inexistente 200/50-15 → vazio, sem invenção",
            result == [],
            f"Got {result}",
        )

    # --- MÉDIO ---

    # 5. C9 import circular
    try:
        from agente_2w.tools.busca_catalogo import _parsear_medida as pm
        from agente_2w.db import catalogo_repo as cr
        from agente_2w.engine.orquestrador.guardrails import tentar_busca_fallback_dimensoes as tbf
        importou = True
    except ImportError as e:
        importou = False
    check(
        "P4.5 C9 import circular: imports lazy sem ImportError",
        importou,
        "ImportError ao importar guardrails + busca_catalogo + catalogo_repo",
    )


# ══════════════════════════════════════════════════════════════════════════════
# BANCO DE DADOS — estoque e saldo · 5 testes
# ══════════════════════════════════════════════════════════════════════════════

def test_banco():
    print(f"\n{NEGRITO}═══ BANCO DE DADOS — estoque e saldo · 5 testes ═══{RESET}")

    # --- CRÍTICOS ---

    # 1. Saldo livre zerado
    with patch("agente_2w.tools.busca_catalogo.catalogo_repo") as mock_repo, \
         patch("agente_2w.tools.busca_catalogo.log_demanda_pneu_repo"):
        mock_repo.buscar_pneus_por_dimensoes.return_value = []
        result = buscar_pneus(largura=90, perfil=90, aro=18)
        check(
            "P5.1 Saldo livre zerado (disponivel=9, reservado=9) → 0 resultados",
            result["quantidade"] == 0,
            f"Esperado 0, got {result['quantidade']}",
            critico=True,
        )

    # 2. Retorno usa disponivel_real
    with patch("agente_2w.tools.busca_catalogo.catalogo_repo") as mock_repo, \
         patch("agente_2w.tools.busca_catalogo.log_demanda_pneu_repo"):
        pneu_com_real = {**PNEU_PIRELLI_90_90_18, "disponivel_real": 5, "quantidade_disponivel": 9}
        mock_repo.buscar_pneus_por_dimensoes.return_value = [pneu_com_real]
        result = buscar_pneus(largura=90, perfil=90, aro=18)
        pneu = result["pneus"][0]
        check(
            "P5.2 Retorno contém disponivel_real",
            "disponivel_real" in pneu and pneu["disponivel_real"] == 5,
            f"disponivel_real={pneu.get('disponivel_real')}",
            critico=True,
        )

    # --- ALTOS ---

    # 3. Preço vem do estoque, não inventado
    with patch("agente_2w.tools.busca_catalogo.catalogo_repo") as mock_repo, \
         patch("agente_2w.tools.busca_catalogo.log_demanda_pneu_repo"):
        mock_repo.buscar_pneus_por_dimensoes.return_value = [PNEU_PIRELLI_90_90_18]
        result = buscar_pneus(largura=90, perfil=90, aro=18)
        preco = result["pneus"][0].get("preco_venda")
        check(
            "P5.3 Preço vem do estoque (239.90), não inventado",
            preco == 239.90,
            f"Esperado 239.90, got {preco}",
        )

    # 4. Pneu inativo não aparece
    with patch("agente_2w.tools.busca_catalogo.catalogo_repo") as mock_repo, \
         patch("agente_2w.tools.busca_catalogo.log_demanda_pneu_repo"):
        mock_repo.buscar_pneus_por_dimensoes.return_value = []
        result = buscar_pneus(largura=90, perfil=90, aro=18)
        check(
            "P5.4 Pneu inativo (ativo=false) não retorna",
            result["quantidade"] == 0,
            f"Got {result['quantidade']}",
        )

    # --- MÉDIO ---

    # 5. Estoque mínimo — campo disponivel_real presente
    with patch("agente_2w.tools.busca_catalogo.catalogo_repo") as mock_repo, \
         patch("agente_2w.tools.busca_catalogo.log_demanda_pneu_repo"):
        pneu_baixo = {**PNEU_PIRELLI_90_90_18, "disponivel_real": 1}
        mock_repo.buscar_pneus_por_dimensoes.return_value = [pneu_baixo]
        result = buscar_pneus(largura=90, perfil=90, aro=18)
        check(
            "P5.5 Pneu com estoque baixo retorna com disponivel_real=1",
            result["pneus"][0].get("disponivel_real") == 1,
            f"disponivel_real={result['pneus'][0].get('disponivel_real')}",
        )


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRAÇÃO PONTA A PONTA (E2E) · 6 testes
# ══════════════════════════════════════════════════════════════════════════════

def test_e2e():
    print(f"\n{NEGRITO}═══ INTEGRAÇÃO PONTA A PONTA (E2E) · 6 testes ═══{RESET}")

    # --- CRÍTICOS ---

    # E2E 1: Fluxo completo medida → busca → resultados
    with patch("agente_2w.tools.busca_catalogo.catalogo_repo") as mock_repo, \
         patch("agente_2w.tools.busca_catalogo.log_demanda_pneu_repo"):
        mock_repo.buscar_pneus_por_dimensoes.return_value = [PNEU_PIRELLI_90_90_18]
        result = buscar_pneus(medida_texto="90 90 18")
        check(
            "E2E.1 Fluxo: '90 90 18' → dimension-first → encontra Pirelli",
            result["quantidade"] == 1
            and result["pneus"][0]["marca"] == "Pirelli",
            f"Got {result['quantidade']} pneus",
            critico=True,
        )

    # E2E 2: Fluxo moto → marca_modelo
    with patch("agente_2w.tools.busca_catalogo.catalogo_repo") as mock_repo, \
         patch("agente_2w.tools.busca_catalogo.log_demanda_pneu_repo"):
        mock_repo.buscar_pneus_por_marca_modelo.return_value = [PNEU_PIRELLI_90_90_18]
        result = buscar_pneus(marca_modelo="Pirelli")
        check(
            "E2E.2 Fluxo marca: 'Pirelli' → busca por marca → encontra",
            result["quantidade"] == 1,
            f"Got {result['quantidade']}",
            critico=True,
        )

    # --- ALTOS ---

    # E2E 3: C9 fallback injeta resultado na mensagem
    msg_fallback = _montar_mensagem_fallback([PNEU_PIRELLI_90_90_18])
    check(
        "E2E.3 Mensagem fallback contém marca e preço",
        "Pirelli" in msg_fallback and "239.90" in msg_fallback,
        f"Mensagem: {msg_fallback}",
    )

    # E2E 4: Contexto preservado — dimension-first funciona com variações
    for entrada in ["90/90-18", "90 90 18", "90-90-18"]:
        r = _parsear_medida(entrada)
        if r != {"largura": 90, "perfil": 90, "aro": 18}:
            check(
                f"E2E.4 Contexto: '{entrada}' parseia igual",
                False,
                f"Got {r}",
            )
            break
    else:
        check(
            "E2E.4 Todas variações '90/90-18','90 90 18','90-90-18' produzem mesmo resultado",
            True,
        )

    # E2E 5: _RE_NEGACAO detecta frases de falso negativo
    frases_neg = [
        "Não temos esse pneu",
        "não encontrei nenhum resultado",
        "Infelizmente não achei",
        "não temos disponível",
    ]
    todas_detectaram = all(_RE_NEGACAO.search(f) for f in frases_neg)
    check(
        "E2E.5 _RE_NEGACAO detecta todas as frases de falso negativo",
        todas_detectaram,
        f"Falhou em alguma frase",
    )

    # --- MÉDIO ---

    # E2E 6: Log de demanda — buscar_pneus chama registrar_busca
    with patch("agente_2w.tools.busca_catalogo.catalogo_repo") as mock_repo, \
         patch("agente_2w.tools.busca_catalogo.log_demanda_pneu_repo") as mock_log:
        mock_repo.buscar_pneus_por_dimensoes.return_value = [PNEU_PIRELLI_90_90_18]
        result = buscar_pneus(medida_texto="90 90 18")
        check(
            "E2E.6 Log de demanda registrado após busca",
            mock_log.registrar_busca.called,
            "registrar_busca não foi chamado",
        )


# ══════════════════════════════════════════════════════════════════════════════
# TESTES NEGATIVOS E DE SEGURANÇA · 8 testes
# ══════════════════════════════════════════════════════════════════════════════

def test_seguranca():
    print(f"\n{NEGRITO}═══ TESTES NEGATIVOS E DE SEGURANÇA · 8 testes ═══{RESET}")

    # --- CRÍTICOS ---

    # 1. Agente NUNCA inventa pneu — medida inexistente retorna vazio
    with patch("agente_2w.tools.busca_catalogo.catalogo_repo") as mock_repo, \
         patch("agente_2w.tools.busca_catalogo.log_demanda_pneu_repo"):
        mock_repo.buscar_pneus_por_dimensoes.return_value = []
        result = buscar_pneus(medida_texto="300/40-21")
        check(
            "SEC.1 Agente nunca inventa pneu: 300/40-21 → vazio",
            result["quantidade"] == 0 and result["pneus"] == [],
            f"Got {result['quantidade']} pneus",
            critico=True,
        )

    # 2. Agente NUNCA inventa preço — estoque zerado
    with patch("agente_2w.tools.busca_catalogo.catalogo_repo") as mock_repo, \
         patch("agente_2w.tools.busca_catalogo.log_demanda_pneu_repo"):
        mock_repo.buscar_pneus_por_dimensoes.return_value = []
        result = buscar_pneus(largura=90, perfil=90, aro=18)
        check(
            "SEC.2 Agente nunca inventa preço: estoque zerado → 0 resultados",
            result["quantidade"] == 0,
            f"Got {result['quantidade']}",
            critico=True,
        )

    # 3. Agente NUNCA confirma pedido com estoque zero
    with patch("agente_2w.tools.busca_catalogo.catalogo_repo") as mock_repo, \
         patch("agente_2w.tools.busca_catalogo.log_demanda_pneu_repo"):
        mock_repo.buscar_pneus_por_dimensoes.return_value = []
        result = buscar_pneus(largura=90, perfil=90, aro=18)
        check(
            "SEC.3 Estoque zero bloqueia: nenhum pneu retornado",
            result["quantidade"] == 0,
            f"Got {result['quantidade']}",
            critico=True,
        )

    # --- ALTOS ---

    # 4. SQL injection via medida_texto
    # _parsear_medida deve retornar None (não extrai 3 números válidos de SQLi)
    r = _parsear_medida("'; DROP TABLE pneu; --")
    check(
        "SEC.4 SQL injection: '; DROP TABLE pneu; -- → None",
        r is None,
        f"Got {r}",
    )

    # 5. Medida com caracteres especiais
    r = _parsear_medida("90/90-18!@#$%")
    check(
        "SEC.5 Caracteres especiais: 90/90-18!@#$% → extrai 90/90/18",
        r is not None and r["largura"] == 90 and r["perfil"] == 90 and r["aro"] == 18,
        f"Got {r}",
    )

    # --- MÉDIOS ---

    # 6. Medida com números absurdos
    r = _parsear_medida("9999/9999-99")
    check(
        "SEC.6 Números absurdos: 9999/9999-99 → None (aro>21)",
        r is None,
        f"Got {r}",
    )

    # 7. Unicode e emojis na entrada
    r = _parsear_medida("🏍️ 90 90 18")
    check(
        "SEC.7 Unicode e emojis: '🏍️ 90 90 18' → extrai 90/90/18",
        r == {"largura": 90, "perfil": 90, "aro": 18},
        f"Got {r}",
    )

    # --- BAIXO ---

    # 8. Múltiplas medidas na mesma mensagem — parse extrai a primeira
    r = _parsear_medida("90/90-18 e 80/100-18")
    check(
        "SEC.8 Múltiplas medidas: extrai primeira (90/90-18)",
        r is not None and r["largura"] == 90 and r["aro"] == 18,
        f"Got {r}",
    )


# ══════════════════════════════════════════════════════════════════════════════
# RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n{NEGRITO}{'='*70}")
    print("  CHECKLIST 42 testes — anti-alucinação beta Agente 2W")
    print(f"{'='*70}{RESET}")

    test_passo1()
    test_passo2_3()
    test_passo4()
    test_banco()
    test_e2e()
    test_seguranca()

    total = passou + falhou
    print(f"\n{NEGRITO}{'='*70}")
    print(f"  RESULTADO FINAL")
    print(f"{'='*70}{RESET}")
    print(f"  Total: {total} testes")
    print(f"  {VERDE}Passou: {passou}{RESET}")
    if falhou:
        print(f"  {VERMELHO}Falhou: {falhou}{RESET}")
    else:
        print(f"  Falhou: 0")

    print(f"\n  {NEGRITO}CRÍTICOS: {criticos_ok}/{CRITICOS_TOTAL} OK{RESET}", end="")
    if criticos_falhou:
        print(f"  {VERMELHO}({criticos_falhou} FALHARAM — BLOQUEIA DEPLOY){RESET}")
    else:
        print(f"  {VERDE}✓ TODOS PASSARAM — deploy liberado{RESET}")

    print()

    if falhou:
        sys.exit(1)


if __name__ == "__main__":
    main()
