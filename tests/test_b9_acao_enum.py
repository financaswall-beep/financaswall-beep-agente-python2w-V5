"""
Teste B9 — enum no campo acao de mudancas_itens.

Verifica que o schema ENVELOPE_IA_SCHEMA aceita os valores validos
e rejeita valores invÃ¡lidos usando jsonschema.validate.

Valores validos: "criar", "confirmar", "atualizar", "cancelar", "rejeitar"
"""
import json
import pytest
from jsonschema import validate, ValidationError

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agente_2w.ia.schemas_envelope import ENVELOPE_IA_SCHEMA


def _envelope_base(**kwargs) -> dict:
    """Monta envelope minimo valido."""
    return {
        "mensagem_cliente": "ok",
        "etapa_atual": "busca",
        "intencao_atual": "busca_pneu",
        "acoes_sugeridas": [],
        "pendencias": [],
        "confianca": "alta",
        "fatos_observados": [],
        "fatos_inferidos": [],
        "mudancas_contexto": [],
        "mudancas_itens": kwargs.get("mudancas_itens", []),
        "bloqueios_identificados": [],
    }


def _mudanca(acao: str) -> dict:
    return {
        "item_provisorio_id": None,
        "acao": acao,
        "dados": None,
    }


ACOES_VALIDAS = ["criar", "confirmar", "atualizar", "cancelar", "rejeitar"]
ACOES_INVALIDAS = ["deletar", "adicionar", "remover", "update", "create", "", "CRIAR"]


@pytest.mark.parametrize("acao", ACOES_VALIDAS)
def test_acao_valida_aceita(acao):
    envelope = _envelope_base(mudancas_itens=[_mudanca(acao)])
    validate(instance=envelope, schema=ENVELOPE_IA_SCHEMA)
    print(f"  [OK] acao='{acao}' aceita pelo schema")


@pytest.mark.parametrize("acao", ACOES_INVALIDAS)
def test_acao_invalida_rejeitada(acao):
    envelope = _envelope_base(mudancas_itens=[_mudanca(acao)])
    with pytest.raises(ValidationError):
        validate(instance=envelope, schema=ENVELOPE_IA_SCHEMA)
    print(f"  [OK] acao='{acao}' rejeitada pelo schema")


def test_lista_mudancas_vazia_valida():
    envelope = _envelope_base(mudancas_itens=[])
    validate(instance=envelope, schema=ENVELOPE_IA_SCHEMA)
    print("  [OK] mudancas_itens vazio é valido")


def test_multiplas_acoes_validas():
    mudancas = [_mudanca(a) for a in ACOES_VALIDAS]
    envelope = _envelope_base(mudancas_itens=mudancas)
    validate(instance=envelope, schema=ENVELOPE_IA_SCHEMA)
    print("  [OK] todas as 5 acoes validas em uma lista aceita")


if __name__ == "__main__":
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    sys.exit(result.returncode)
