"""
Teste: auto-enriquecimento de pneu_id NAO mistura UUIDs de turnos diferentes.

Cenário:
  Turno 1: busca pneu A → pneu_id: uuid-A
  Turno 2: busca pneu B → pneu_id: uuid-B, cliente confirma pneu B
  Verificar: item criado tem uuid-B, não uuid-A

Execute: python -m pytest tests/test_enriquecimento_cross_turn.py -v
     ou: python tests/test_enriquecimento_cross_turn.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timezone
from uuid import uuid4, UUID
from unittest.mock import patch, MagicMock

from agente_2w.schemas.envelope_ia import MudancaItem
from agente_2w.enums.enums import StatusItemProvisorio


UUID_A = str(uuid4())
UUID_B = str(uuid4())
SESSAO_ID = uuid4()


def _pneus_turno_1():
    return [{"pneu_id": UUID_A, "medida": "110/70-17", "preco_venda": 200.0, "posicao": "dianteiro"}]


def _pneus_turno_2():
    return [{"pneu_id": UUID_B, "medida": "140/70-17", "preco_venda": 280.0, "posicao": "traseiro"}]


@patch("agente_2w.engine.orquestrador.enriquecimento_itens.item_provisorio_repo")
def test_item_usa_uuid_do_turno_atual_nao_anterior(mock_repo):
    """IA manda pneu_id inválido — enriquecimento deve pegar do turno atual (B), não do anterior (A)."""
    from agente_2w.engine.orquestrador.enriquecimento_itens import _aplicar_mudancas_itens

    mock_repo.listar_itens_ativos_por_sessao.return_value = []

    # Turno 2: pneus_encontrados tem só uuid-B
    mudanca = MudancaItem(acao="criar", dados={"pneu_id": "invalido", "posicao": "traseiro"})
    _aplicar_mudancas_itens(SESSAO_ID, [mudanca], pneus_encontrados=_pneus_turno_2())

    # Verificar que criar_item foi chamado com uuid-B
    assert mock_repo.criar_item.call_count == 1
    item_criado = mock_repo.criar_item.call_args[0][0]
    assert str(item_criado.pneu_id) == UUID_B, (
        f"Item deveria ter uuid-B ({UUID_B}), mas tem {item_criado.pneu_id}"
    )


@patch("agente_2w.engine.orquestrador.enriquecimento_itens.item_provisorio_repo")
def test_uuid_valido_do_turno_atual_passa_direto(mock_repo):
    """IA manda UUID válido que está nos resultados do turno — deve usar direto."""
    from agente_2w.engine.orquestrador.enriquecimento_itens import _aplicar_mudancas_itens

    mock_repo.listar_itens_ativos_por_sessao.return_value = []

    mudanca = MudancaItem(acao="criar", dados={"pneu_id": UUID_B, "posicao": "traseiro"})
    _aplicar_mudancas_itens(SESSAO_ID, [mudanca], pneus_encontrados=_pneus_turno_2())

    assert mock_repo.criar_item.call_count == 1
    item_criado = mock_repo.criar_item.call_args[0][0]
    assert str(item_criado.pneu_id) == UUID_B


@patch("agente_2w.engine.orquestrador.enriquecimento_itens.item_provisorio_repo")
@patch("agente_2w.db.catalogo_repo.buscar_estoque_por_pneu", return_value=None)
def test_uuid_antigo_valido_rejeitado_por_c8(mock_catalogo, mock_repo):
    """IA manda UUID do turno anterior (A) mas pneus_encontrados tem só turno atual (B).
    C8 deve rejeitar porque uuid-A não está nos resultados nem no catálogo."""
    from agente_2w.engine.orquestrador.enriquecimento_itens import _aplicar_mudancas_itens

    mock_repo.listar_itens_ativos_por_sessao.return_value = []

    mudanca = MudancaItem(acao="criar", dados={"pneu_id": UUID_A, "posicao": "traseiro"})
    _aplicar_mudancas_itens(SESSAO_ID, [mudanca], pneus_encontrados=_pneus_turno_2())

    # C8 deve ter rejeitado — nenhum item criado
    assert mock_repo.criar_item.call_count == 0, (
        "UUID do turno anterior deveria ser rejeitado pelo C8 (não está nos resultados nem no catálogo)"
    )


@patch("agente_2w.engine.orquestrador.enriquecimento_itens.item_provisorio_repo")
def test_sem_pneu_id_com_2_resultados_nao_cria_errado(mock_repo):
    """IA não manda pneu_id e há 2 pneus nos resultados sem match de posição.
    Não deve criar item vinculado ao pneu errado."""
    from agente_2w.engine.orquestrador.enriquecimento_itens import _aplicar_mudancas_itens

    mock_repo.listar_itens_ativos_por_sessao.return_value = []

    dois_pneus = [
        {"pneu_id": UUID_A, "medida": "110/70-17", "preco_venda": 200.0},
        {"pneu_id": UUID_B, "medida": "140/70-17", "preco_venda": 280.0},
    ]

    mudanca = MudancaItem(acao="criar", dados={})
    _aplicar_mudancas_itens(SESSAO_ID, [mudanca], pneus_encontrados=dois_pneus)

    # Deve criar item SEM pneu_id (status: sugerido), ou não criar
    if mock_repo.criar_item.call_count == 1:
        item_criado = mock_repo.criar_item.call_args[0][0]
        assert item_criado.pneu_id is None, (
            "Com 2 pneus e sem posição, não deveria vincular a nenhum pneu específico"
        )
        assert item_criado.status_item == StatusItemProvisorio.sugerido


@patch("agente_2w.engine.orquestrador.enriquecimento_itens.item_provisorio_repo")
def test_posicao_correta_match_turno_atual(mock_repo):
    """IA manda posição 'traseiro' e turno atual tem pneu traseiro → match correto."""
    from agente_2w.engine.orquestrador.enriquecimento_itens import _aplicar_mudancas_itens

    mock_repo.listar_itens_ativos_por_sessao.return_value = []

    dois_pneus = [
        {"pneu_id": UUID_A, "medida": "110/70-17", "preco_venda": 200.0, "posicao": "dianteiro"},
        {"pneu_id": UUID_B, "medida": "140/70-17", "preco_venda": 280.0, "posicao": "traseiro"},
    ]

    mudanca = MudancaItem(acao="criar", dados={"posicao": "traseiro"})
    _aplicar_mudancas_itens(SESSAO_ID, [mudanca], pneus_encontrados=dois_pneus)

    assert mock_repo.criar_item.call_count == 1
    item_criado = mock_repo.criar_item.call_args[0][0]
    assert str(item_criado.pneu_id) == UUID_B, (
        f"Posição 'traseiro' deveria casar com uuid-B ({UUID_B}), mas casou com {item_criado.pneu_id}"
    )


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
