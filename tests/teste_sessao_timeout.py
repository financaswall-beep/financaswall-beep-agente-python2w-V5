"""Testes de timeout de sessao — Fase 16.

Cobertura:
  Grupo 1 — Unitarios (sem banco): avaliar_sessao() com todos os cenarios
  Grupo 2 — Integracao (banco real): _resolver_timeout() via supabase
  Grupo 3 — Simulacao de comportamento: processar_turno() com sessoes envelhecidas

Execucao:
  cd "C:\\Agente 2w Pneus"
  python teste_sessao_timeout.py
"""

import logging
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

PASS = 0
FAIL = 0


def ok(descricao: str):
    global PASS
    PASS += 1
    print(f"  [PASS] {descricao}")


def falhou(descricao: str, detalhe: str = ""):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {descricao}" + (f" — {detalhe}" if detalhe else ""))


def secao(titulo: str):
    print(f"\n{'=' * 60}")
    print(f"  {titulo}")
    print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# Helpers para montar SessaoChat mock sem banco
# ---------------------------------------------------------------------------

def _mock_sessao(
    status: str = "ativa",
    etapa: str = "identificacao",
    dias_atras: int = 0,
    horas_atras: int = 0,
    id_: str | None = None,
):
    """Cria um objeto SessaoChat fake para testes unitarios."""
    from agente_2w.enums.enums import EtapaFluxo, StatusSessao

    ultima = datetime.now(timezone.utc) - timedelta(days=dias_atras, hours=horas_atras)

    sessao = MagicMock()
    sessao.id = id_ or uuid4()
    sessao.canal = "cli"
    sessao.contato_externo = "5521999990000"
    sessao.status_sessao = StatusSessao(status)
    sessao.etapa_atual = EtapaFluxo(etapa)
    sessao.ultima_interacao_em = ultima
    return sessao


# ---------------------------------------------------------------------------
# GRUPO 1 — Unitarios: avaliar_sessao()
# ---------------------------------------------------------------------------

def teste_unitarios():
    secao("GRUPO 1 — Unitarios: avaliar_sessao()")

    from agente_2w.engine.sessao_timeout import avaliar_sessao, SituacaoSessao

    # 1.1 Sessao normal recente — ok
    s = _mock_sessao(status="ativa", etapa="identificacao", dias_atras=1)
    resultado = avaliar_sessao(s)
    if resultado == SituacaoSessao.ok:
        ok("1.1 Sessao ativa recente (1 dia) -> ok")
    else:
        falhou("1.1 Sessao ativa recente (1 dia)", f"esperado=ok, obtido={resultado}")

    # 1.2 Sessao ativa antiga em identificacao — expirada_sem_contexto
    s = _mock_sessao(status="ativa", etapa="identificacao", dias_atras=8)
    resultado = avaliar_sessao(s)
    if resultado == SituacaoSessao.expirada_sem_contexto:
        ok("1.2 Sessao ativa 8 dias em identificacao -> expirada_sem_contexto")
    else:
        falhou("1.2 Sessao ativa 8 dias em identificacao", f"esperado=expirada_sem_contexto, obtido={resultado}")

    # 1.3 Sessao ativa antiga em busca — expirada_sem_contexto
    s = _mock_sessao(status="ativa", etapa="busca", dias_atras=10)
    resultado = avaliar_sessao(s)
    if resultado == SituacaoSessao.expirada_sem_contexto:
        ok("1.3 Sessao ativa 10 dias em busca -> expirada_sem_contexto")
    else:
        falhou("1.3 Sessao ativa 10 dias em busca", f"esperado=expirada_sem_contexto, obtido={resultado}")

    # 1.4 Sessao ativa antiga em oferta — expirada_com_contexto
    s = _mock_sessao(status="ativa", etapa="oferta", dias_atras=8)
    resultado = avaliar_sessao(s)
    if resultado == SituacaoSessao.expirada_com_contexto:
        ok("1.4 Sessao ativa 8 dias em oferta -> expirada_com_contexto")
    else:
        falhou("1.4 Sessao ativa 8 dias em oferta", f"esperado=expirada_com_contexto, obtido={resultado}")

    # 1.5 Sessao ativa antiga em confirmacao_item — expirada_com_contexto
    s = _mock_sessao(status="ativa", etapa="confirmacao_item", dias_atras=9)
    resultado = avaliar_sessao(s)
    if resultado == SituacaoSessao.expirada_com_contexto:
        ok("1.5 Sessao ativa 9 dias em confirmacao_item -> expirada_com_contexto")
    else:
        falhou("1.5 Sessao ativa 9 dias em confirmacao_item", f"esperado=expirada_com_contexto, obtido={resultado}")

    # 1.6 Sessao ativa antiga em entrega_pagamento — expirada_com_contexto
    s = _mock_sessao(status="ativa", etapa="entrega_pagamento", dias_atras=15)
    resultado = avaliar_sessao(s)
    if resultado == SituacaoSessao.expirada_com_contexto:
        ok("1.6 Sessao ativa 15 dias em entrega_pagamento -> expirada_com_contexto")
    else:
        falhou("1.6 Sessao ativa 15 dias em entrega_pagamento", f"esperado=expirada_com_contexto, obtido={resultado}")

    # 1.7 Sessao ativa antiga em fechamento — expirada_com_contexto
    s = _mock_sessao(status="ativa", etapa="fechamento", dias_atras=8)
    resultado = avaliar_sessao(s)
    if resultado == SituacaoSessao.expirada_com_contexto:
        ok("1.7 Sessao ativa 8 dias em fechamento -> expirada_com_contexto")
    else:
        falhou("1.7 Sessao ativa 8 dias em fechamento", f"esperado=expirada_com_contexto, obtido={resultado}")

    # 1.8 Sessao fechada — ok (nao interferir)
    s = _mock_sessao(status="fechada", etapa="fechamento", dias_atras=30)
    resultado = avaliar_sessao(s)
    if resultado == SituacaoSessao.ok:
        ok("1.8 Sessao fechada 30 dias -> ok (nao interferir)")
    else:
        falhou("1.8 Sessao fechada 30 dias", f"esperado=ok, obtido={resultado}")

    # 1.9 Sessao bloqueada recente — ok (respeitar bloqueio)
    s = _mock_sessao(status="bloqueada", etapa="identificacao", horas_atras=1)
    resultado = avaliar_sessao(s)
    if resultado == SituacaoSessao.ok:
        ok("1.9 Sessao bloqueada ha 1h -> ok (respeitar bloqueio recente)")
    else:
        falhou("1.9 Sessao bloqueada ha 1h", f"esperado=ok, obtido={resultado}")

    # 1.10 Sessao bloqueada antiga — bloqueada_antiga
    s = _mock_sessao(status="bloqueada", etapa="identificacao", horas_atras=3)
    resultado = avaliar_sessao(s)
    if resultado == SituacaoSessao.bloqueada_antiga:
        ok("1.10 Sessao bloqueada ha 3h -> bloqueada_antiga")
    else:
        falhou("1.10 Sessao bloqueada ha 3h", f"esperado=bloqueada_antiga, obtido={resultado}")

    # 1.11 Limite exato: 7 dias menos 1 minuto — ainda ok
    s = _mock_sessao(
        status="ativa", etapa="confirmacao_item",
        horas_atras=7 * 24 - 1  # 6 dias e 23 horas
    )
    resultado = avaliar_sessao(s)
    if resultado == SituacaoSessao.ok:
        ok("1.11 Sessao ativa 6d23h em confirmacao_item -> ok (ainda dentro do prazo)")
    else:
        falhou("1.11 Sessao ativa 6d23h", f"esperado=ok, obtido={resultado}")

    # 1.12 Limite exato: 7 dias mais 1 hora — expirada
    s = _mock_sessao(
        status="ativa", etapa="confirmacao_item",
        horas_atras=7 * 24 + 1  # 7 dias e 1 hora
    )
    resultado = avaliar_sessao(s)
    if resultado == SituacaoSessao.expirada_com_contexto:
        ok("1.12 Sessao ativa 7d1h em confirmacao_item -> expirada_com_contexto")
    else:
        falhou("1.12 Sessao ativa 7d1h", f"esperado=expirada_com_contexto, obtido={resultado}")


# ---------------------------------------------------------------------------
# GRUPO 2 — Integracao: _resolver_timeout() com banco real
# ---------------------------------------------------------------------------

def _backdatar_sessao(sessao_id, dias: int):
    """Atualiza ultima_interacao_em no banco para X dias atras (uso em testes)."""
    from agente_2w.db.client import supabase
    data_antiga = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    supabase.table("sessao_chat").update({"ultima_interacao_em": data_antiga}).eq("id", str(sessao_id)).execute()


def teste_integracao():
    secao("GRUPO 2 — Integracao: _resolver_timeout() com banco real")

    from agente_2w.db import sessao_repo
    from agente_2w.engine.orquestrador import _resolver_timeout
    from agente_2w.enums.enums import EtapaFluxo, StatusSessao
    from agente_2w.schemas.sessao_chat import SessaoChatCreate

    CONTATO_TESTE = "5521000000099"  # contato ficticio exclusivo para estes testes
    sessoes_criadas = []

    try:
        # --- 2.1 Sessao normal recente — deve retornar o mesmo ID ---
        s = sessao_repo.criar_sessao(SessaoChatCreate(
            canal="teste", contato_externo=CONTATO_TESTE,
            etapa_atual=EtapaFluxo.identificacao, status_sessao=StatusSessao.ativa,
        ))
        sessoes_criadas.append(s.id)
        resultado_id = _resolver_timeout(s)
        if resultado_id == s.id:
            ok("2.1 Sessao ativa recente -> retorna mesmo ID")
        else:
            falhou("2.1 Sessao ativa recente", f"esperado={s.id}, obtido={resultado_id}")
        sessao_repo.fechar_sessao(s.id)

        # --- 2.2 Sessao em identificacao com 8 dias -> deve criar nova sessao ---
        s = sessao_repo.criar_sessao(SessaoChatCreate(
            canal="teste", contato_externo=CONTATO_TESTE,
            etapa_atual=EtapaFluxo.identificacao, status_sessao=StatusSessao.ativa,
        ))
        sessoes_criadas.append(s.id)
        _backdatar_sessao(s.id, dias=8)
        s_recarregada = sessao_repo.buscar_sessao_por_id(s.id)
        novo_id = _resolver_timeout(s_recarregada)
        sessoes_criadas.append(novo_id)

        if novo_id != s.id:
            ok("2.2 Sessao identificacao 8 dias -> nova sessao criada")
        else:
            falhou("2.2 Sessao identificacao 8 dias", "retornou o mesmo ID, deveria criar nova")

        # Verificar que a antiga foi fechada
        antiga = sessao_repo.buscar_sessao_por_id(s.id)
        if antiga and antiga.status_sessao == StatusSessao.fechada:
            ok("2.2b Sessao antiga foi fechada no banco")
        else:
            falhou("2.2b Sessao antiga deveria estar fechada", f"status={antiga.status_sessao if antiga else 'nao encontrada'}")

        # Verificar que a nova esta ativa em identificacao
        nova = sessao_repo.buscar_sessao_por_id(novo_id)
        if nova and nova.status_sessao == StatusSessao.ativa and nova.etapa_atual == EtapaFluxo.identificacao:
            ok("2.2c Nova sessao criada em identificacao/ativa")
        else:
            falhou("2.2c Nova sessao", f"status={nova.status_sessao if nova else '?'}, etapa={nova.etapa_atual if nova else '?'}")
        sessao_repo.fechar_sessao(novo_id)

        # --- 2.3 Sessao em confirmacao_item com 9 dias -> deve criar nova sessao ---
        s = sessao_repo.criar_sessao(SessaoChatCreate(
            canal="teste", contato_externo=CONTATO_TESTE,
            etapa_atual=EtapaFluxo.confirmacao_item, status_sessao=StatusSessao.ativa,
        ))
        sessoes_criadas.append(s.id)
        _backdatar_sessao(s.id, dias=9)
        s_recarregada = sessao_repo.buscar_sessao_por_id(s.id)
        novo_id = _resolver_timeout(s_recarregada)
        sessoes_criadas.append(novo_id)

        if novo_id != s.id:
            ok("2.3 Sessao confirmacao_item 9 dias -> nova sessao criada")
        else:
            falhou("2.3 Sessao confirmacao_item 9 dias", "retornou o mesmo ID")

        # Nova sessao deve comecar do zero (identificacao)
        nova = sessao_repo.buscar_sessao_por_id(novo_id)
        if nova and nova.etapa_atual == EtapaFluxo.identificacao:
            ok("2.3b Nova sessao inicia em identificacao (sem herdar etapa anterior)")
        else:
            falhou("2.3b Nova sessao etapa", f"etapa={nova.etapa_atual if nova else '?'}")
        sessao_repo.fechar_sessao(novo_id)

        # --- 2.4 Sessao bloqueada ha 3 horas -> deve desbloquear ---
        s = sessao_repo.criar_sessao(SessaoChatCreate(
            canal="teste", contato_externo=CONTATO_TESTE,
            etapa_atual=EtapaFluxo.identificacao, status_sessao=StatusSessao.ativa,
        ))
        sessoes_criadas.append(s.id)
        # Bloquear manualmente
        sessao_repo.atualizar_status(
            s.id, StatusSessao.bloqueada,
            codigo_motivo="transicao_invalida",
            mensagem_motivo="Teste de bloqueio antigo",
            campo_relacionado="etapa_atual",
            acao_bloqueada="teste",
        )
        # Retroagir para 3 horas atras
        from agente_2w.db.client import supabase
        data_3h = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        supabase.table("sessao_chat").update({"ultima_interacao_em": data_3h}).eq("id", str(s.id)).execute()

        s_bloqueada = sessao_repo.buscar_sessao_por_id(s.id)
        resultado_id = _resolver_timeout(s_bloqueada)

        if resultado_id == s.id:
            ok("2.4 Sessao bloqueada 3h -> retorna mesmo ID (desbloqueada)")
        else:
            falhou("2.4 Sessao bloqueada 3h", "retornou ID diferente")

        desbloqueada = sessao_repo.buscar_sessao_por_id(s.id)
        if desbloqueada and desbloqueada.status_sessao == StatusSessao.ativa:
            ok("2.4b Sessao foi desbloqueada (status=ativa)")
        else:
            falhou("2.4b Desbloqueio", f"status={desbloqueada.status_sessao if desbloqueada else '?'}")
        sessao_repo.fechar_sessao(s.id)

        # --- 2.5 Sessao bloqueada recente (1h) -> nao deve desbloquear ---
        s = sessao_repo.criar_sessao(SessaoChatCreate(
            canal="teste", contato_externo=CONTATO_TESTE,
            etapa_atual=EtapaFluxo.identificacao, status_sessao=StatusSessao.ativa,
        ))
        sessoes_criadas.append(s.id)
        sessao_repo.atualizar_status(
            s.id, StatusSessao.bloqueada,
            codigo_motivo="transicao_invalida",
            mensagem_motivo="Bloqueio recente de teste",
            campo_relacionado="etapa_atual",
            acao_bloqueada="teste",
        )
        s_bloqueada_recente = sessao_repo.buscar_sessao_por_id(s.id)
        resultado_id = _resolver_timeout(s_bloqueada_recente)

        if resultado_id == s.id:
            ok("2.5 Sessao bloqueada recente (< 2h) -> retorna mesmo ID (bloqueio preservado)")
        else:
            falhou("2.5 Sessao bloqueada recente", "retornou ID diferente, nao deveria")

        ainda_bloqueada = sessao_repo.buscar_sessao_por_id(s.id)
        if ainda_bloqueada and ainda_bloqueada.status_sessao == StatusSessao.bloqueada:
            ok("2.5b Sessao permanece bloqueada")
        else:
            falhou("2.5b Status preservado", f"status={ainda_bloqueada.status_sessao if ainda_bloqueada else '?'}")
        sessao_repo.fechar_sessao(s.id)

    except Exception as e:
        falhou(f"Erro inesperado no grupo 2: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Limpeza: fechar qualquer sessao de teste que nao foi fechada
        for sid in sessoes_criadas:
            try:
                s_check = sessao_repo.buscar_sessao_por_id(sid)
                if s_check and s_check.status_sessao != StatusSessao.fechada:
                    sessao_repo.fechar_sessao(sid)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# GRUPO 3 — Simulacao: comportamento end-to-end sem chamar a IA
# ---------------------------------------------------------------------------

def teste_simulacao():
    secao("GRUPO 3 — Simulacao de comportamento (banco real, sem IA)")

    from agente_2w.db import sessao_repo
    from agente_2w.engine.sessao_timeout import avaliar_sessao, SituacaoSessao
    from agente_2w.enums.enums import EtapaFluxo, StatusSessao
    from agente_2w.schemas.sessao_chat import SessaoChatCreate

    CONTATO_TESTE = "5521000000088"
    sessoes_criadas = []

    try:
        # --- 3.1 Simula: cliente voltou depois de 8 dias em identificacao ---
        # Esperado: nova sessao criada, cliente nao percebe diferenca
        s = sessao_repo.criar_sessao(SessaoChatCreate(
            canal="teste", contato_externo=CONTATO_TESTE,
            etapa_atual=EtapaFluxo.identificacao, status_sessao=StatusSessao.ativa,
        ))
        sessoes_criadas.append(s.id)
        _backdatar_sessao(s.id, dias=8)

        s_reload = sessao_repo.buscar_sessao_por_id(s.id)
        situacao = avaliar_sessao(s_reload)

        if situacao == SituacaoSessao.expirada_sem_contexto:
            ok("3.1 Cliente voltou 8 dias depois (identificacao) -> sera atendido em sessao nova sem interrupcao")
        else:
            falhou("3.1", f"situacao={situacao}")
        sessao_repo.fechar_sessao(s.id)

        # --- 3.2 Simula: cliente voltou depois de 8 dias com pneu no carrinho ---
        # Esperado: expirada_com_contexto — contexto era valioso
        s = sessao_repo.criar_sessao(SessaoChatCreate(
            canal="teste", contato_externo=CONTATO_TESTE,
            etapa_atual=EtapaFluxo.confirmacao_item, status_sessao=StatusSessao.ativa,
        ))
        sessoes_criadas.append(s.id)
        _backdatar_sessao(s.id, dias=8)

        s_reload = sessao_repo.buscar_sessao_por_id(s.id)
        situacao = avaliar_sessao(s_reload)

        if situacao == SituacaoSessao.expirada_com_contexto:
            ok("3.2 Cliente voltou 8 dias depois com pneu no carrinho -> expirada_com_contexto (nova sessao, historico preservado no cadastro)")
        else:
            falhou("3.2", f"situacao={situacao}")
        sessao_repo.fechar_sessao(s.id)

        # --- 3.3 Simula: mesmo cliente, duas mensagens rapidas (concorrencia) ---
        # O segundo _resolver_timeout deve encontrar a sessao ja fechada (criada pelo primeiro)
        s = sessao_repo.criar_sessao(SessaoChatCreate(
            canal="teste", contato_externo=CONTATO_TESTE,
            etapa_atual=EtapaFluxo.identificacao, status_sessao=StatusSessao.ativa,
        ))
        sessoes_criadas.append(s.id)
        _backdatar_sessao(s.id, dias=8)

        from agente_2w.engine.orquestrador import _resolver_timeout

        s_reload = sessao_repo.buscar_sessao_por_id(s.id)
        id_1 = _resolver_timeout(s_reload)
        sessoes_criadas.append(id_1)

        # Segunda chamada com a sessao ja fechada — deve retornar ok (sessao fechada nao e tratada)
        s_fechada = sessao_repo.buscar_sessao_por_id(s.id)
        situacao_2a_chamada = avaliar_sessao(s_fechada)

        if situacao_2a_chamada == SituacaoSessao.ok:
            ok("3.3 Segunda avaliacao da sessao ja fechada -> ok (nao cria segunda nova sessao)")
        else:
            falhou("3.3 Segunda avaliacao", f"situacao={situacao_2a_chamada}")

        sessao_repo.fechar_sessao(id_1)

        # --- 3.4 Simula: cliente VIP com historico voltando apos 10 dias ---
        # Nao deve perder o cadastro — apenas a sessao e renovada
        from agente_2w.db import cliente_repo
        cliente = cliente_repo.resolver_ou_criar_cliente(CONTATO_TESTE)
        # Simular cliente vip
        cliente_repo.atualizar_cliente(cliente.id, {"segmento": "vip", "total_pedidos": 6})

        s = sessao_repo.criar_sessao(SessaoChatCreate(
            canal="teste", contato_externo=CONTATO_TESTE,
            etapa_atual=EtapaFluxo.oferta, status_sessao=StatusSessao.ativa,
        ))
        sessoes_criadas.append(s.id)
        _backdatar_sessao(s.id, dias=10)

        s_reload = sessao_repo.buscar_sessao_por_id(s.id)
        novo_id = _resolver_timeout(s_reload)
        sessoes_criadas.append(novo_id)

        # Verificar que o cliente ainda e vip
        cliente_apos = cliente_repo.resolver_ou_criar_cliente(CONTATO_TESTE)
        if cliente_apos.segmento == "vip" and cliente_apos.total_pedidos == 6:
            ok("3.4 Cliente VIP voltou apos 10 dias -> cadastro preservado intacto (segmento=vip, pedidos=6)")
        else:
            falhou("3.4 Cadastro cliente", f"segmento={cliente_apos.segmento}, pedidos={cliente_apos.total_pedidos}")

        sessao_repo.fechar_sessao(novo_id)

    except Exception as e:
        falhou(f"Erro inesperado no grupo 3: {e}")
        import traceback
        traceback.print_exc()
    finally:
        for sid in sessoes_criadas:
            try:
                s_check = sessao_repo.buscar_sessao_por_id(sid)
                if s_check and s_check.status_sessao.value != "fechada":
                    sessao_repo.fechar_sessao(sid)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\nTeste de Timeout de Sessao — Agente 2W Pneus")
    print("=" * 60)

    try:
        teste_unitarios()
    except Exception as e:
        print(f"\n[ERRO CRITICO] Grupo 1 falhou com excecao: {e}")
        import traceback
        traceback.print_exc()

    try:
        teste_integracao()
    except Exception as e:
        print(f"\n[ERRO CRITICO] Grupo 2 falhou com excecao: {e}")
        import traceback
        traceback.print_exc()

    try:
        teste_simulacao()
    except Exception as e:
        print(f"\n[ERRO CRITICO] Grupo 3 falhou com excecao: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    print(f"  Resultado: {PASS}/{total} PASS")
    if FAIL > 0:
        print(f"  FALHAS:    {FAIL}")
    print(f"{'=' * 60}\n")

    sys.exit(0 if FAIL == 0 else 1)
