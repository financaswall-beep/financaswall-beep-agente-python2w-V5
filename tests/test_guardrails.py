"""
Testes dos 3 guardrails implementados na Fase 20.

Roda sem banco de dados — usa objetos Pydantic mockados.
Execute: python -m pytest tests/test_guardrails.py -v
     ou: python tests/test_guardrails.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timezone
from uuid import uuid4

from agente_2w.enums.enums import (
    EtapaFluxo, Confianca, TipoDeVerdade, NivelConfirmacao,
    OrigemContexto, StatusSessao, StatusItemProvisorio,
)
from agente_2w.schemas.envelope_ia import EnvelopeIA
from agente_2w.schemas.contexto_executavel import (
    ContextoExecutavel, SessaoContexto, ClienteContexto,
    FatoAtivo, ResumoOperacional, Metadados,
)
from agente_2w.schemas.envelope_ia import FatoObservado
from agente_2w.engine.validador_envelope import validar_envelope
from agente_2w.engine.orquestrador import _tem_negacao_antes

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _sessao(etapa: EtapaFluxo) -> SessaoContexto:
    return SessaoContexto(
        sessao_id=str(uuid4()),
        canal="whatsapp",
        contato_externo="21999990000",
        etapa_atual=etapa,
        status_sessao=StatusSessao.ativa,
        ultima_interacao_em=datetime.now(timezone.utc),
    )


def _fato(chave: str, valor: str) -> FatoAtivo:
    return FatoAtivo(
        chave=chave,
        valor=valor,
        tipo_de_verdade=TipoDeVerdade.observado,
        nivel_confirmacao=NivelConfirmacao.nenhum,
        fonte=OrigemContexto.mensagem_cliente,
        coletado_em=datetime.now(timezone.utc),
    )


def _contexto(etapa: EtapaFluxo, fatos: list[FatoAtivo] | None = None) -> ContextoExecutavel:
    return ContextoExecutavel(
        sessao=_sessao(etapa),
        cliente=ClienteContexto(),
        fatos_ativos=fatos or [],
        acoes_permitidas=[],
        resumo_operacional=ResumoOperacional(),
        metadados=Metadados(gerado_em=datetime.now(timezone.utc)),
    )


def _fato_obs(chave: str, valor: str) -> FatoObservado:
    return FatoObservado(chave=chave, valor=valor)


def _envelope(
    etapa: EtapaFluxo,
    acoes: list[str] | None = None,
    fatos_obs: list[FatoObservado] | None = None,
) -> EnvelopeIA:
    return EnvelopeIA(
        mensagem_cliente="Confirmado!",
        etapa_atual=etapa,
        intencao_atual="teste",
        acoes_sugeridas=acoes or [],
        confianca=Confianca.alta,
        fatos_observados=fatos_obs or [],
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
# GRUPO 1 — _tem_negacao_antes()
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GUARDRAIL 1 — Detecção de negação (anti falso-positivo){RESET}")
print("─" * 60)

# Casos que DEVEM detectar negação (retornar True)
check(
    "não quero pix → detecta negação",
    _tem_negacao_antes("não quero pix", "pix") is True,
)
check(
    "nao quero pix (sem acento) → detecta negação",
    _tem_negacao_antes("nao quero pix", "pix") is True,
)
check(
    "sem pix → detecta negação",
    _tem_negacao_antes("sem pix por favor", "pix") is True,
)
check(
    "não quero entrega, prefiro retirar → detecta negação em entrega",
    _tem_negacao_antes("não quero entrega, prefiro retirar", "entrega") is True,
)
check(
    "não aceito cartão → detecta negação em cartão",
    _tem_negacao_antes("não aceito cartao", "cartao") is True,
)

# Casos que NÃO devem detectar negação (retornar False)
check(
    "quero pix → NÃO detecta negação",
    _tem_negacao_antes("quero pagar no pix", "pix") is False,
)
check(
    "retirada → NÃO detecta negação",
    _tem_negacao_antes("prefiro retirada na loja", "retirada") is False,
)
check(
    "entrega em casa → NÃO detecta negação",
    _tem_negacao_antes("quero entrega em casa", "entrega") is False,
)
check(
    "dinheiro → NÃO detecta negação",
    _tem_negacao_antes("pago em dinheiro", "dinheiro") is False,
)
check(
    "string vazia → NÃO detecta negação",
    _tem_negacao_antes("", "pix") is False,
)

# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 2 — Validador: fechamento prematuro (Proposta 2)
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GUARDRAIL 2 — Validador bloqueia fechamento prematuro{RESET}")
print("─" * 60)

# Cenário A: tenta ir pra fechamento SEM nenhum dado → deve bloquear
ctx_vazio = _contexto(EtapaFluxo.entrega_pagamento, fatos=[])
env_fechamento = _envelope(EtapaFluxo.fechamento, acoes=["revisar_pedido"])
erros_a = validar_envelope(env_fechamento, ctx_vazio)

check(
    "SEM tipo_entrega e forma_pagamento → 2 erros gerados",
    len(erros_a) == 2,
    f"erros encontrados: {erros_a}",
)
check(
    "Erro menciona tipo_entrega",
    any("tipo_entrega" in e for e in erros_a),
    f"erros: {erros_a}",
)
check(
    "Erro menciona forma_pagamento",
    any("forma_pagamento" in e for e in erros_a),
    f"erros: {erros_a}",
)

# Cenário B: tem tipo_entrega mas não tem forma_pagamento → 1 erro
ctx_parcial = _contexto(
    EtapaFluxo.entrega_pagamento,
    fatos=[_fato("tipo_entrega", "retirada")],
)
erros_b = validar_envelope(env_fechamento, ctx_parcial)

check(
    "COM tipo_entrega, SEM forma_pagamento → 1 erro apenas",
    len(erros_b) == 1,
    f"erros encontrados: {erros_b}",
)
check(
    "Erro é sobre forma_pagamento (não tipo_entrega)",
    all("forma_pagamento" in e for e in erros_b),
    f"erros: {erros_b}",
)

# Cenário C: tem os dois → NÃO deve bloquear fechamento
ctx_completo = _contexto(
    EtapaFluxo.entrega_pagamento,
    fatos=[
        _fato("tipo_entrega", "retirada"),
        _fato("forma_pagamento", "pix"),
    ],
)
erros_c = validar_envelope(env_fechamento, ctx_completo)
erros_c_relevantes = [e for e in erros_c if "fechamento" in e or "tipo_entrega" in e or "forma_pagamento" in e]

check(
    "COM tipo_entrega e forma_pagamento → SEM erros de fechamento",
    len(erros_c_relevantes) == 0,
    f"erros inesperados: {erros_c_relevantes}",
)

# Cenário D: em outra etapa (busca → oferta) → regra 7 NÃO se aplica
ctx_busca = _contexto(EtapaFluxo.busca, fatos=[])
env_oferta = _envelope(EtapaFluxo.oferta, acoes=["apresentar_opcoes"])
erros_d = validar_envelope(env_oferta, ctx_busca)
erros_d_fechamento = [e for e in erros_d if "tipo_entrega" in e or "forma_pagamento" in e]

check(
    "Em etapa busca → oferta → regra 7 não interfere",
    len(erros_d_fechamento) == 0,
    f"erros inesperados: {erros_d_fechamento}",
)

# Cenário E (Regra 8): tipo_entrega=entrega SEM endereco → deve bloquear fechamento
ctx_entrega_sem_end = _contexto(
    EtapaFluxo.entrega_pagamento,
    fatos=[
        _fato("tipo_entrega", "entrega"),
        _fato("forma_pagamento", "pix"),
    ],
)
erros_e = validar_envelope(env_fechamento, ctx_entrega_sem_end)
erros_e_end = [e for e in erros_e if "endereco_entrega" in e]

check(
    "tipo_entrega=entrega SEM endereco_entrega → erro gerado",
    len(erros_e_end) == 1,
    f"erros: {erros_e}",
)
check(
    "Erro menciona endereco_entrega",
    any("endereco_entrega" in e for e in erros_e),
    f"erros: {erros_e}",
)

# Cenário F: tipo_entrega=entrega COM endereco → NÃO deve bloquear
ctx_entrega_com_end = _contexto(
    EtapaFluxo.entrega_pagamento,
    fatos=[
        _fato("tipo_entrega", "entrega"),
        _fato("forma_pagamento", "pix"),
        _fato("endereco_entrega", "Rua das Flores, 100, Centro, Nova Iguaçu"),
    ],
)
erros_f = validar_envelope(env_fechamento, ctx_entrega_com_end)
erros_f_end = [e for e in erros_f if "endereco_entrega" in e]

check(
    "tipo_entrega=entrega COM endereco_entrega → SEM erro de endereço",
    len(erros_f_end) == 0,
    f"erros inesperados: {erros_f_end}",
)

# Cenário G: tipo_entrega=retirada SEM endereco → NÃO deve bloquear (retirada não precisa)
ctx_retirada = _contexto(
    EtapaFluxo.entrega_pagamento,
    fatos=[
        _fato("tipo_entrega", "retirada"),
        _fato("forma_pagamento", "dinheiro"),
    ],
)
erros_g = validar_envelope(env_fechamento, ctx_retirada)
erros_g_end = [e for e in erros_g if "endereco_entrega" in e]

check(
    "tipo_entrega=retirada SEM endereco_entrega → regra 8 não interfere",
    len(erros_g_end) == 0,
    f"erros inesperados: {erros_g_end}",
)

# Cenário H (bug real "pix"): tipo_entrega no banco, forma_pagamento no envelope atual → deve passar
# Reproduz exatamente o que falhou no log: cliente diz "pix" e IA registra + avança no mesmo turno
ctx_tipo_no_banco = _contexto(
    EtapaFluxo.entrega_pagamento,
    fatos=[_fato("tipo_entrega", "entrega"), _fato("endereco_entrega", "Rua X, 10, Centro")],
)
env_pix_no_envelope = _envelope(
    EtapaFluxo.fechamento,
    acoes=["revisar_pedido"],
    fatos_obs=[_fato_obs("forma_pagamento", "pix")],
)
erros_h = validar_envelope(env_pix_no_envelope, ctx_tipo_no_banco)
erros_h_rel = [e for e in erros_h if "forma_pagamento" in e or "tipo_entrega" in e]

check(
    "forma_pagamento no envelope do turno atual (não no banco) → deve passar (bug fix)",
    len(erros_h_rel) == 0,
    f"erros inesperados: {erros_h_rel}",
)

# Cenário I: tudo no envelope (nenhum fato no banco ainda) → deve passar
ctx_sem_fatos = _contexto(EtapaFluxo.entrega_pagamento, fatos=[])
env_tudo_no_envelope = _envelope(
    EtapaFluxo.fechamento,
    acoes=["revisar_pedido"],
    fatos_obs=[
        _fato_obs("tipo_entrega", "retirada"),
        _fato_obs("forma_pagamento", "dinheiro"),
    ],
)
erros_i = validar_envelope(env_tudo_no_envelope, ctx_sem_fatos)
erros_i_rel = [e for e in erros_i if "forma_pagamento" in e or "tipo_entrega" in e]

check(
    "tipo_entrega e forma_pagamento ambos no envelope → deve passar",
    len(erros_i_rel) == 0,
    f"erros inesperados: {erros_i_rel}",
)

# ──────────────────────────────────────────────────────────────────────────────
# GRUPO 3 — Alertas no contexto (Proposta 3)
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}GUARDRAIL 3 — Alertas contextuais no ContextoExecutavel{RESET}")
print("─" * 60)

# Simula o que montador_contexto faz com fatos registrados
def _simular_alertas(fatos: list[FatoAtivo]) -> list[str]:
    alertas = []
    chaves_ativas = {f.chave for f in fatos}
    if "nome_cliente" in chaves_ativas:
        fato = next(f for f in fatos if f.chave == "nome_cliente")
        alertas.append(f"nome_cliente ja registrado como '{fato.valor}' — NAO pergunte o nome de novo")
    if "tipo_entrega" in chaves_ativas:
        fato = next(f for f in fatos if f.chave == "tipo_entrega")
        alertas.append(f"tipo_entrega ja registrado como '{fato.valor}' — NAO pergunte de novo")
    if "forma_pagamento" in chaves_ativas:
        fato = next(f for f in fatos if f.chave == "forma_pagamento")
        alertas.append(f"forma_pagamento ja registrado como '{fato.valor}' — NAO pergunte de novo")
    if "municipio" in chaves_ativas:
        fato = next(f for f in fatos if f.chave == "municipio")
        alertas.append(f"municipio ja registrado como '{fato.valor}' — NAO pergunte o municipio de novo")
    if "endereco_entrega" in chaves_ativas:
        fato = next(f for f in fatos if f.chave == "endereco_entrega")
        alertas.append(f"endereco_entrega ja registrado como '{fato.valor}' — NAO peca o endereco de novo")
    return alertas


# Sem fatos → sem alertas
alertas_vazios = _simular_alertas([])
check(
    "Sem fatos → sem alertas",
    len(alertas_vazios) == 0,
)

# Com nome_cliente → alerta de nome
alertas_nome = _simular_alertas([_fato("nome_cliente", "João Silva")])
check(
    "Com nome_cliente → alerta gerado",
    len(alertas_nome) == 1,
)
check(
    "Alerta de nome contém o valor registrado",
    "João Silva" in alertas_nome[0],
    f"alerta: {alertas_nome}",
)

# Com pagamento e entrega → 2 alertas
alertas_2 = _simular_alertas([
    _fato("forma_pagamento", "pix"),
    _fato("tipo_entrega", "retirada"),
])
check(
    "Com forma_pagamento e tipo_entrega → 2 alertas",
    len(alertas_2) == 2,
    f"alertas: {alertas_2}",
)
check(
    "Alerta de pagamento menciona 'pix'",
    any("pix" in a for a in alertas_2),
    f"alertas: {alertas_2}",
)
check(
    "Alerta de entrega menciona 'retirada'",
    any("retirada" in a for a in alertas_2),
    f"alertas: {alertas_2}",
)

# Com endereco_entrega → alerta de endereço (bug fix Fase 22)
alertas_end = _simular_alertas([_fato("endereco_entrega", "Rua Gago Tarado, 879, Bom Jardim, Nova Iguaçu")])
check(
    "Com endereco_entrega → alerta gerado",
    len(alertas_end) == 1,
    f"alertas: {alertas_end}",
)
check(
    "Alerta de endereço contém o valor registrado",
    "Rua Gago Tarado" in alertas_end[0],
    f"alerta: {alertas_end}",
)
check(
    "Alerta de endereço menciona NAO peca",
    "NAO peca" in alertas_end[0],
    f"alerta: {alertas_end}",
)

# Contexto com alertas é serializável (não quebra o JSON para a IA)
ctx_com_alertas = _contexto(
    EtapaFluxo.entrega_pagamento,
    fatos=[_fato("forma_pagamento", "pix"), _fato("tipo_entrega", "entrega")],
)
ctx_com_alertas.alertas = _simular_alertas(ctx_com_alertas.fatos_ativos)
json_gerado = ctx_com_alertas.model_dump_json(indent=None)
check(
    "Contexto com alertas serializa para JSON sem erro",
    '"alertas"' in json_gerado,
    "campo alertas ausente no JSON gerado",
)
check(
    "Alertas aparecem no JSON enviado à IA",
    "NAO pergunte" in json_gerado,
    f"JSON (trecho): {json_gerado[:200]}",
)

# ──────────────────────────────────────────────────────────────────────────────
# RESULTADO FINAL
# ──────────────────────────────────────────────────────────────────────────────

total = passou + falhou
print(f"\n{'─' * 60}")
print(f"{NEGRITO}RESULTADO: {passou}/{total} testes passaram{RESET}")

if falhou == 0:
    print(f"{VERDE}{NEGRITO}✓ Todos os guardrails funcionando corretamente.{RESET}")
else:
    print(f"{VERMELHO}{NEGRITO}✗ {falhou} teste(s) falharam — revisar implementação.{RESET}")
    sys.exit(1)
