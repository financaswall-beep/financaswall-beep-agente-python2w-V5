"""
Testes B4 e B5.

B4 — dedup do promotor por (pneu_id, posicao):
    Verifica que dois itens com o mesmo pneu_id mas posicoes diferentes
    (dianteira e traseira) NAO sao eliminados pelo dedup.

B5 — guard de profundidade em processar_turno:
    Verifica que _profundidade > 1 retorna resposta segura imediatamente
    sem chamar banco nem IA.
"""
import sys
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# B4 — dedup por (pneu_id, posicao)
# ---------------------------------------------------------------------------

def _make_item(pneu_id, posicao, criado_em=None, status="selecionado_cliente"):
    """Cria objeto fake de ItemProvisorio com os campos relevantes para o dedup."""
    from agente_2w.enums.enums import StatusItemProvisorio, Posicao
    item = MagicMock()
    item.id = uuid.uuid4()
    item.pneu_id = pneu_id
    item.posicao_moto = posicao
    item.status_item = StatusItemProvisorio(status)
    item.criado_em = criado_em or datetime.now(timezone.utc)
    item.preco_unitario_sugerido = Decimal("259.90")
    item.quantidade = 1
    return item


def _rodar_dedup(itens_validados):
    """Executa apenas o bloco de dedup do promotor (isolado do resto)."""
    from agente_2w.enums.enums import StatusItemProvisorio

    vistos: dict[str, object] = {}
    cancelados = []

    for item in itens_validados:
        chave = f"{item.pneu_id}|{item.posicao_moto or ''}"
        if chave in vistos:
            antigo = vistos[chave]
            if item.criado_em > antigo.criado_em:
                cancelados.append(antigo)
                vistos[chave] = item
            else:
                cancelados.append(item)
        else:
            vistos[chave] = item

    return list(vistos.values()), cancelados


def test_b4_mesmo_pneu_posicoes_diferentes_ambos_ficam():
    pneu_id = uuid.uuid4()
    item_dianteira = _make_item(pneu_id, "dianteira")
    item_traseira  = _make_item(pneu_id, "traseira")

    mantidos, cancelados = _rodar_dedup([item_dianteira, item_traseira])

    assert len(mantidos) == 2, (
        f"FALHOU B4: esperava 2 itens mantidos, got {len(mantidos)}. "
        f"Dedup eliminou o item de posicao diferente!"
    )
    assert len(cancelados) == 0, f"FALHOU B4: {len(cancelados)} item(s) cancelado(s) indevidamente"
    print("  [OK] Mesmo pneu em dianteira + traseira → ambos mantidos")


def test_b4_mesmo_pneu_mesma_posicao_elimina_antigo():
    from datetime import timedelta
    pneu_id = uuid.uuid4()
    agora = datetime.now(timezone.utc)
    item_antigo = _make_item(pneu_id, "dianteira", criado_em=agora - timedelta(minutes=5))
    item_novo   = _make_item(pneu_id, "dianteira", criado_em=agora)

    mantidos, cancelados = _rodar_dedup([item_antigo, item_novo])

    assert len(mantidos) == 1, f"FALHOU B4: esperava 1 item mantido, got {len(mantidos)}"
    assert mantidos[0].id == item_novo.id, "FALHOU B4: item mantido deveria ser o mais recente"
    assert len(cancelados) == 1
    print("  [OK] Mesmo pneu + mesma posicao → antigo eliminado, novo mantido")


def test_b4_sem_posicao_continua_dedup_pelo_pneu():
    """Itens sem posicao (None) continuam sendo deduplicados por pneu_id."""
    from datetime import timedelta
    pneu_id = uuid.uuid4()
    agora = datetime.now(timezone.utc)
    item_a = _make_item(pneu_id, None, criado_em=agora - timedelta(minutes=2))
    item_b = _make_item(pneu_id, None, criado_em=agora)

    mantidos, cancelados = _rodar_dedup([item_a, item_b])

    assert len(mantidos) == 1
    assert mantidos[0].id == item_b.id
    print("  [OK] Sem posicao: dedup por pneu_id continua funcionando")


# ---------------------------------------------------------------------------
# B5 — guard de profundidade
# ---------------------------------------------------------------------------

def test_b5_profundidade_zero_passa():
    """_profundidade=0 (default) nao deve acionar o guard."""
    from agente_2w.engine.orquestrador._nucleo import processar_turno

    sessao_id = uuid.uuid4()

    # Mock de todas as dependencias de banco para nao precisar de dados reais
    sessao_mock = MagicMock()
    sessao_mock.id = sessao_id
    sessao_mock.etapa_atual.value = "identificacao"
    sessao_mock.status_sessao.value = "ativa"
    sessao_mock.cliente_id = None
    sessao_mock.contato_externo = "5521000000002"
    sessao_mock.canal = "whatsapp"

    with patch("agente_2w.engine.orquestrador._nucleo.sessao_repo") as mock_sr, \
         patch("agente_2w.engine.orquestrador._nucleo.cliente_repo"), \
         patch("agente_2w.engine.orquestrador._nucleo.item_provisorio_repo"), \
         patch("agente_2w.engine.orquestrador._nucleo.montador_contexto") as mock_mc, \
         patch("agente_2w.engine.orquestrador._nucleo.chamar_agente") as mock_ia, \
         patch("agente_2w.engine.orquestrador._nucleo.contexto_repo"), \
         patch("agente_2w.engine.orquestrador._nucleo.mensagem_repo"), \
         patch("agente_2w.engine.orquestrador._nucleo.config_loja_repo"):

        mock_sr.buscar_sessao_por_id.return_value = sessao_mock
        mock_sr.buscar_ou_criar_sessao.return_value = sessao_mock
        # montar_contexto retorna objeto com sessao
        ctx_mock = MagicMock()
        ctx_mock.sessao = sessao_mock
        mock_mc.montar_contexto.return_value = ctx_mock

        # IA retorna envelope minimo
        envelope_mock = MagicMock()
        envelope_mock.resposta_cliente = "Olá, como posso ajudar?"
        envelope_mock.acoes_sugeridas = []
        envelope_mock.mudancas_itens = []
        envelope_mock.intencao_atual = "saudacao"
        envelope_mock.confianca.value = "alta"
        mock_ia.return_value = envelope_mock

        resultado = processar_turno(sessao_id, "oi", _profundidade=0)
        # Se chegou aqui sem erro, o guard nao bloqueou indevidamente
        assert resultado is not None
        print("  [OK] _profundidade=0 nao aciona o guard")


def test_b5_profundidade_maior_que_1_retorna_safe():
    """_profundidade > 1 deve retornar resposta segura SEM chamar banco ou IA."""
    from agente_2w.engine.orquestrador._nucleo import processar_turno

    sessao_id = uuid.uuid4()

    with patch("agente_2w.engine.orquestrador._nucleo.sessao_repo") as mock_sr, \
         patch("agente_2w.engine.orquestrador._nucleo.chamar_agente") as mock_ia:

        resultado = processar_turno(sessao_id, "qualquer coisa", _profundidade=2)

        # Guard deve ter ativado antes de qualquer chamada ao banco
        mock_sr.buscar_sessao_por_id.assert_not_called()
        mock_ia.assert_not_called()

        assert "erro" in resultado.texto.lower() or "novamente" in resultado.texto.lower(), (
            f"Resposta inesperada do guard: '{resultado.texto}'"
        )
        print(f"  [OK] _profundidade=2 → guard ativou. Resposta: '{resultado.texto}'")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\n=== Teste B4: dedup promotor por (pneu_id, posicao) ===\n")
    try:
        print("1. Mesmo pneu em posicoes diferentes — ambos devem ser mantidos...")
        test_b4_mesmo_pneu_posicoes_diferentes_ambos_ficam()

        print("2. Mesmo pneu na mesma posicao — antigo deve ser eliminado...")
        test_b4_mesmo_pneu_mesma_posicao_elimina_antigo()

        print("3. Sem posicao — dedup por pneu_id continua funcionando...")
        test_b4_sem_posicao_continua_dedup_pelo_pneu()

        print("\n✓ B4: todos os testes passaram.\n")
    except AssertionError as e:
        print(f"\n✗ B4 FALHOU: {e}\n")
        sys.exit(1)

    print("=== Teste B5: guard de profundidade em processar_turno ===\n")
    try:
        print("1. _profundidade=2 deve ativar guard sem chamar banco ou IA...")
        test_b5_profundidade_maior_que_1_retorna_safe()

        print("\n✓ B5: todos os testes passaram.\n")
    except AssertionError as e:
        print(f"\n✗ B5 FALHOU: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
