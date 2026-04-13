"""
Testes do validador de envelope da IA (engine/validador_envelope.py).

Cobre as 9 regras de validacao do envelope (1,2,3,4,5,6,7,8,10 no codigo).
Complementa test_guardrails.py — aqui focamos nas regras 1,2,3,4,5,6,10.

Roda sem banco de dados e sem IA. Puramente logico.

Execute: python -X utf8 tests/test_validador_envelope.py
     ou: python -m pytest tests/test_validador_envelope.py -v
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
from agente_2w.schemas.envelope_ia import (
    EnvelopeIA, FatoObservado, FatoInferido, MudancaContexto,
    MudancaItem, BloqueioIdentificado,
)
from agente_2w.schemas.contexto_executavel import (
    ContextoExecutavel, SessaoContexto, ClienteContexto,
    FatoAtivo, ItemProvisorioContexto, ResumoOperacional, Metadados,
)
from agente_2w.engine.validador_envelope import validar_envelope
from agente_2w.engine.pendencias import acoes_permitidas

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
# Helpers (mesmo padrao de test_guardrails.py)
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


def _item_provisorio(item_id: str, pneu_id: str | None = None) -> ItemProvisorioContexto:
    return ItemProvisorioContexto(
        item_provisorio_id=item_id,
        pneu_id=pneu_id,
        descricao_contextual="item teste",
        quantidade=1,
        status_item=StatusItemProvisorio.sugerido,
    )


def _contexto(
    etapa: EtapaFluxo,
    fatos: list[FatoAtivo] | None = None,
    itens: list[ItemProvisorioContexto] | None = None,
    com_acoes: bool = True,
) -> ContextoExecutavel:
    return ContextoExecutavel(
        sessao=_sessao(etapa),
        cliente=ClienteContexto(),
        fatos_ativos=fatos or [],
        itens_provisorios=itens or [],
        acoes_permitidas=acoes_permitidas(etapa) if com_acoes else [],
        resumo_operacional=ResumoOperacional(),
        metadados=Metadados(gerado_em=datetime.now(timezone.utc)),
    )


def _envelope(
    etapa: EtapaFluxo,
    acoes: list[str] | None = None,
    mensagem: str = "Resposta valida.",
    fatos_obs: list[FatoObservado] | None = None,
    fatos_inf: list[FatoInferido] | None = None,
    mudancas_itens: list[MudancaItem] | None = None,
    confianca: Confianca = Confianca.alta,
) -> EnvelopeIA:
    return EnvelopeIA(
        mensagem_cliente=mensagem,
        etapa_atual=etapa,
        intencao_atual="teste",
        acoes_sugeridas=acoes or [],
        confianca=confianca,
        fatos_observados=fatos_obs or [],
        fatos_inferidos=fatos_inf or [],
        mudancas_itens=mudancas_itens or [],
    )


# ──────────────────────────────────────────────────────────────────────────────
# REGRA 1 — Acoes sugeridas devem estar dentro das permitidas
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}REGRA 1 — Acoes sugeridas devem estar nas permitidas{RESET}")
print("─" * 60)

# Caso OK: acao permitida na etapa atual
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(EtapaFluxo.busca, acoes=["buscar_por_moto"])
erros = validar_envelope(env, ctx)
erros_acoes = [e for e in erros if "nao e permitida" in e]
check(
    "Acao valida na etapa atual (busca/buscar_por_moto) passa",
    len(erros_acoes) == 0,
    f"erros: {erros}",
)

# Caso ERRO: acao nao existe
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(EtapaFluxo.busca, acoes=["converter_em_pedido"])
erros = validar_envelope(env, ctx)
erros_acoes = [e for e in erros if "converter_em_pedido" in e and "nao e permitida" in e]
check(
    "Acao de outra etapa (converter_em_pedido em busca) e rejeitada",
    len(erros_acoes) == 1,
    f"erros: {erros}",
)

# Caso OK: acao da etapa proposta e permitida se transicao e valida
# Ex: em busca -> oferta, apresentar_opcoes (da oferta) e permitida
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(EtapaFluxo.oferta, acoes=["apresentar_opcoes"])
erros = validar_envelope(env, ctx)
erros_acoes = [e for e in erros if "apresentar_opcoes" in e and "nao e permitida" in e]
check(
    "Acao da etapa proposta (oferta/apresentar_opcoes) e aceita em transicao valida",
    len(erros_acoes) == 0,
    f"erros: {erros}",
)

# Caso ERRO: acao de etapa nao-adjacente nao e aceita
ctx = _contexto(EtapaFluxo.identificacao)
env = _envelope(EtapaFluxo.busca, acoes=["converter_em_pedido"])  # fechamento!
erros = validar_envelope(env, ctx)
erros_acoes = [e for e in erros if "converter_em_pedido" in e]
check(
    "Acao de etapa distante (converter_em_pedido com etapa=busca) e rejeitada",
    len(erros_acoes) == 1,
    f"erros: {erros}",
)

# Caso: multiplas acoes misturadas (valida + invalida)
ctx = _contexto(EtapaFluxo.oferta)
env = _envelope(EtapaFluxo.oferta, acoes=["apresentar_opcoes", "buscar_por_moto"])
# buscar_por_moto nao e da oferta e nao ha transicao em jogo
erros = validar_envelope(env, ctx)
erros_acoes = [e for e in erros if "buscar_por_moto" in e and "nao e permitida" in e]
check(
    "Mistura de acoes: invalida (buscar_por_moto em oferta) e flagrada",
    len(erros_acoes) == 1,
    f"erros: {erros}",
)

# Caso: multiplas acoes todas invalidas geram multiplos erros
ctx = _contexto(EtapaFluxo.identificacao)
env = _envelope(EtapaFluxo.identificacao, acoes=["converter_em_pedido", "apresentar_opcoes"])
erros = validar_envelope(env, ctx)
erros_acoes = [e for e in erros if "nao e permitida" in e]
check(
    "Duas acoes invalidas geram 2 erros distintos",
    len(erros_acoes) == 2,
    f"erros: {erros}",
)


# ──────────────────────────────────────────────────────────────────────────────
# REGRA 2 — Etapa do envelope deve ser igual ou transicao valida
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}REGRA 2 — Transicao de etapa deve ser valida{RESET}")
print("─" * 60)

# Caso OK: mesma etapa
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(EtapaFluxo.busca, acoes=["buscar_por_moto"])
erros = validar_envelope(env, ctx)
erros_trans = [e for e in erros if "transicao de" in e and "nao e permitida" in e]
check(
    "Mesma etapa (busca->busca) nao gera erro de transicao",
    len(erros_trans) == 0,
    f"erros: {erros}",
)

# Caso OK: transicao valida (busca -> oferta)
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(EtapaFluxo.oferta, acoes=["apresentar_opcoes"])
erros = validar_envelope(env, ctx)
erros_trans = [e for e in erros if "transicao de" in e and "nao e permitida" in e]
check(
    "Transicao valida (busca->oferta) nao gera erro",
    len(erros_trans) == 0,
    f"erros: {erros}",
)

# Caso ERRO: salto proibido (identificacao -> fechamento)
ctx = _contexto(EtapaFluxo.identificacao)
env = _envelope(EtapaFluxo.fechamento, acoes=["converter_em_pedido"])
erros = validar_envelope(env, ctx)
erros_trans = [e for e in erros if "transicao de" in e and "nao e permitida" in e]
check(
    "Salto proibido (identificacao->fechamento) e rejeitado",
    len(erros_trans) == 1,
    f"erros: {erros}",
)

# Caso ERRO: voltar de fechamento (terminal)
ctx = _contexto(EtapaFluxo.fechamento)
env = _envelope(EtapaFluxo.busca, acoes=["buscar_por_moto"])
erros = validar_envelope(env, ctx)
erros_trans = [e for e in erros if "transicao de fechamento" in e]
check(
    "Sair de fechamento (terminal) e rejeitado",
    len(erros_trans) == 1,
    f"erros: {erros}",
)


# ──────────────────────────────────────────────────────────────────────────────
# REGRA 3 — Fatos observados nao podem ter chave vazia ou valor nulo
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}REGRA 3 — Fatos observados: chave nao vazia, valor nao nulo{RESET}")
print("─" * 60)

# Caso OK: fato bem formado
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(
    EtapaFluxo.busca,
    acoes=["buscar_por_moto"],
    fatos_obs=[FatoObservado(chave="moto_modelo", valor="CG 160")],
)
erros = validar_envelope(env, ctx)
erros_fatos = [e for e in erros if "fato observado" in e]
check(
    "Fato observado bem formado nao gera erro",
    len(erros_fatos) == 0,
    f"erros: {erros}",
)

# Caso ERRO: chave vazia string
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(
    EtapaFluxo.busca,
    acoes=["buscar_por_moto"],
    fatos_obs=[FatoObservado(chave="", valor="CG 160")],
)
erros = validar_envelope(env, ctx)
erros_fatos = [e for e in erros if "chave vazia" in e]
check(
    "Fato observado com chave vazia e rejeitado",
    len(erros_fatos) == 1,
    f"erros: {erros}",
)

# Caso ERRO: chave so espacos
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(
    EtapaFluxo.busca,
    acoes=["buscar_por_moto"],
    fatos_obs=[FatoObservado(chave="   ", valor="CG 160")],
)
erros = validar_envelope(env, ctx)
erros_fatos = [e for e in erros if "chave vazia" in e]
check(
    "Fato observado com chave so-espacos e rejeitado",
    len(erros_fatos) == 1,
    f"erros: {erros}",
)

# Caso ERRO: valor nulo
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(
    EtapaFluxo.busca,
    acoes=["buscar_por_moto"],
    fatos_obs=[FatoObservado(chave="moto_modelo", valor=None)],
)
erros = validar_envelope(env, ctx)
erros_fatos = [e for e in erros if "valor nulo" in e]
check(
    "Fato observado com valor nulo e rejeitado",
    len(erros_fatos) == 1,
    f"erros: {erros}",
)

# Caso: sem fatos = sem erros
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(EtapaFluxo.busca, acoes=["buscar_por_moto"], fatos_obs=[])
erros = validar_envelope(env, ctx)
erros_fatos = [e for e in erros if "fato observado" in e]
check(
    "Sem fatos observados, sem erros da regra 3",
    len(erros_fatos) == 0,
)


# ──────────────────────────────────────────────────────────────────────────────
# REGRA 4 — Fatos inferidos devem ter justificativa
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}REGRA 4 — Fatos inferidos exigem justificativa{RESET}")
print("─" * 60)

# Caso OK: fato inferido com justificativa
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(
    EtapaFluxo.busca,
    acoes=["buscar_por_moto"],
    fatos_inf=[FatoInferido(
        chave="posicao_pneu",
        valor="traseiro",
        justificativa="cliente mencionou pneu de tras",
    )],
)
erros = validar_envelope(env, ctx)
erros_inf = [e for e in erros if "fato inferido" in e]
check(
    "Fato inferido com justificativa nao gera erro",
    len(erros_inf) == 0,
    f"erros: {erros}",
)

# Caso ERRO: justificativa vazia
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(
    EtapaFluxo.busca,
    acoes=["buscar_por_moto"],
    fatos_inf=[FatoInferido(chave="posicao_pneu", valor="traseiro", justificativa="")],
)
erros = validar_envelope(env, ctx)
erros_inf = [e for e in erros if "sem justificativa" in e]
check(
    "Fato inferido com justificativa vazia e rejeitado",
    len(erros_inf) == 1,
    f"erros: {erros}",
)

# Caso ERRO: justificativa so espacos
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(
    EtapaFluxo.busca,
    acoes=["buscar_por_moto"],
    fatos_inf=[FatoInferido(chave="x", valor="y", justificativa="   ")],
)
erros = validar_envelope(env, ctx)
erros_inf = [e for e in erros if "sem justificativa" in e]
check(
    "Fato inferido com justificativa so-espacos e rejeitado",
    len(erros_inf) == 1,
    f"erros: {erros}",
)


# ──────────────────────────────────────────────────────────────────────────────
# REGRA 5 — Mudancas de itens: item_provisorio_id deve existir, status=promovido proibido
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}REGRA 5 — Mudancas de itens: validacao de ID e bloqueio de promovido{RESET}")
print("─" * 60)

# Caso OK: item_provisorio_id existe no contexto
item_id = str(uuid4())
ctx = _contexto(
    EtapaFluxo.confirmacao_item,
    itens=[_item_provisorio(item_id)],
)
env = _envelope(
    EtapaFluxo.confirmacao_item,
    acoes=["confirmar_item"],
    mudancas_itens=[MudancaItem(item_provisorio_id=item_id, acao="confirmar")],
)
erros = validar_envelope(env, ctx)
erros_mud = [e for e in erros if "mudanca referencia" in e]
check(
    "Mudanca com item_provisorio_id existente e aceita",
    len(erros_mud) == 0,
    f"erros: {erros}",
)

# Caso ERRO: item_provisorio_id nao existe
ctx = _contexto(
    EtapaFluxo.confirmacao_item,
    itens=[_item_provisorio(str(uuid4()))],  # outro id
)
env = _envelope(
    EtapaFluxo.confirmacao_item,
    acoes=["confirmar_item"],
    mudancas_itens=[MudancaItem(item_provisorio_id=str(uuid4()), acao="confirmar")],
)
erros = validar_envelope(env, ctx)
erros_mud = [e for e in erros if "nao existe no contexto" in e]
check(
    "Mudanca com item_provisorio_id inexistente e rejeitada",
    len(erros_mud) == 1,
    f"erros: {erros}",
)

# Caso TOLERANCIA: IA passou pneu_id ao inves de item_provisorio_id
# (backend auto-corrige, validador nao deve reclamar)
pneu_id = str(uuid4())
item_id = str(uuid4())
ctx = _contexto(
    EtapaFluxo.confirmacao_item,
    itens=[_item_provisorio(item_id, pneu_id=pneu_id)],
)
env = _envelope(
    EtapaFluxo.confirmacao_item,
    acoes=["confirmar_item"],
    mudancas_itens=[MudancaItem(item_provisorio_id=pneu_id, acao="confirmar")],
)
erros = validar_envelope(env, ctx)
erros_mud = [e for e in erros if "nao existe no contexto" in e]
check(
    "Tolerancia: pneu_id no lugar de item_provisorio_id nao e flagrado (auto-corrige)",
    len(erros_mud) == 0,
    f"erros: {erros}",
)

# Caso ERRO: IA tenta setar status_item=promovido (exclusivo do promotor)
item_id = str(uuid4())
ctx = _contexto(
    EtapaFluxo.confirmacao_item,
    itens=[_item_provisorio(item_id)],
)
env = _envelope(
    EtapaFluxo.confirmacao_item,
    acoes=["confirmar_item"],
    mudancas_itens=[MudancaItem(
        item_provisorio_id=item_id,
        acao="atualizar",
        dados={"status_item": "promovido"},
    )],
)
erros = validar_envelope(env, ctx)
erros_prom = [e for e in erros if "promovido" in e and "exclusivo do promotor" in e]
check(
    "IA tentando setar status=promovido e bloqueada",
    len(erros_prom) == 1,
    f"erros: {erros}",
)

# Caso OK: status_item=selecionado_cliente (permitido)
item_id = str(uuid4())
ctx = _contexto(
    EtapaFluxo.confirmacao_item,
    itens=[_item_provisorio(item_id)],
)
env = _envelope(
    EtapaFluxo.confirmacao_item,
    acoes=["confirmar_item"],
    mudancas_itens=[MudancaItem(
        item_provisorio_id=item_id,
        acao="atualizar",
        dados={"status_item": "selecionado_cliente"},
    )],
)
erros = validar_envelope(env, ctx)
erros_prom = [e for e in erros if "promovido" in e]
check(
    "status_item=selecionado_cliente nao e bloqueado",
    len(erros_prom) == 0,
    f"erros: {erros}",
)

# Caso: mudanca sem item_provisorio_id (acao=criar) nao deve gerar erro de ID
ctx = _contexto(EtapaFluxo.oferta)
env = _envelope(
    EtapaFluxo.oferta,
    acoes=["apresentar_opcoes"],
    mudancas_itens=[MudancaItem(
        item_provisorio_id=None,
        acao="criar",
        dados={"pneu_id": str(uuid4()), "quantidade": 1},
    )],
)
erros = validar_envelope(env, ctx)
erros_mud = [e for e in erros if "mudanca referencia" in e]
check(
    "Acao 'criar' sem item_provisorio_id nao gera erro de ID",
    len(erros_mud) == 0,
    f"erros: {erros}",
)


# ──────────────────────────────────────────────────────────────────────────────
# REGRA 6 — Confianca deve ser enum valido (Pydantic ja garante)
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}REGRA 6 — Confianca valida (alta/media/baixa){RESET}")
print("─" * 60)

# Pydantic ja valida no parse, entao aqui testamos apenas que valores validos passam
for conf in [Confianca.alta, Confianca.media, Confianca.baixa]:
    ctx = _contexto(EtapaFluxo.busca)
    env = _envelope(EtapaFluxo.busca, acoes=["buscar_por_moto"], confianca=conf)
    erros = validar_envelope(env, ctx)
    erros_conf = [e for e in erros if "confianca" in e]
    check(
        f"Confianca={conf.value} e aceita",
        len(erros_conf) == 0,
        f"erros: {erros}",
    )


# ──────────────────────────────────────────────────────────────────────────────
# REGRA 10 — Mensagem para o cliente nao pode ser vazia
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}REGRA 10 — mensagem_cliente nao pode ser vazia{RESET}")
print("─" * 60)

# Caso OK: mensagem com texto
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(EtapaFluxo.busca, acoes=["buscar_por_moto"], mensagem="Oi, tudo bem?")
erros = validar_envelope(env, ctx)
erros_msg = [e for e in erros if "mensagem_cliente vazia" in e]
check(
    "mensagem_cliente com texto nao gera erro",
    len(erros_msg) == 0,
    f"erros: {erros}",
)

# Caso ERRO: mensagem string vazia
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(EtapaFluxo.busca, acoes=["buscar_por_moto"], mensagem="")
erros = validar_envelope(env, ctx)
erros_msg = [e for e in erros if "mensagem_cliente vazia" in e]
check(
    "mensagem_cliente string vazia e rejeitada",
    len(erros_msg) == 1,
    f"erros: {erros}",
)

# Caso ERRO: mensagem so espacos/whitespace
ctx = _contexto(EtapaFluxo.busca)
env = _envelope(EtapaFluxo.busca, acoes=["buscar_por_moto"], mensagem="   \n\t  ")
erros = validar_envelope(env, ctx)
erros_msg = [e for e in erros if "mensagem_cliente vazia" in e]
check(
    "mensagem_cliente so whitespace e rejeitada",
    len(erros_msg) == 1,
    f"erros: {erros}",
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO EXTRA — Envelope bem formado completo nao gera erros
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}EXTRA — Envelope 100% valido nao gera nenhum erro{RESET}")
print("─" * 60)

item_id = str(uuid4())
ctx = _contexto(
    EtapaFluxo.confirmacao_item,
    itens=[_item_provisorio(item_id)],
)
env = _envelope(
    EtapaFluxo.confirmacao_item,
    acoes=["confirmar_item"],
    mensagem="Otimo! Confirmando o pneu.",
    fatos_obs=[FatoObservado(chave="pneu_escolhido", valor="Pirelli 100/80-17")],
    fatos_inf=[FatoInferido(
        chave="posicao_pneu",
        valor="traseiro",
        justificativa="cliente falou 'de tras'",
    )],
    mudancas_itens=[MudancaItem(item_provisorio_id=item_id, acao="confirmar")],
    confianca=Confianca.alta,
)
erros = validar_envelope(env, ctx)
check(
    "Envelope 100% valido gera lista vazia de erros",
    erros == [],
    f"erros inesperados: {erros}",
)


# ──────────────────────────────────────────────────────────────────────────────
# GRUPO EXTRA 2 — Multiplos erros aparecem todos juntos
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{NEGRITO}EXTRA 2 — Multiplos erros no mesmo envelope{RESET}")
print("─" * 60)

# Envelope com varios problemas simultaneos:
# - acao invalida
# - transicao invalida
# - fato observado com chave vazia
# - fato inferido sem justificativa
# - mensagem vazia
ctx = _contexto(EtapaFluxo.identificacao)
env = _envelope(
    EtapaFluxo.fechamento,  # transicao invalida
    acoes=["converter_em_pedido"],  # acao invalida na etapa identificacao
    mensagem="",  # vazia
    fatos_obs=[FatoObservado(chave="", valor="x")],  # chave vazia
    fatos_inf=[FatoInferido(chave="x", valor="y", justificativa="")],  # sem justificativa
)
erros = validar_envelope(env, ctx)

check(
    "Envelope com 5 problemas gera pelo menos 5 erros",
    len(erros) >= 5,
    f"erros ({len(erros)}): {erros}",
)
check(
    "Erro de acao invalida aparece",
    any("nao e permitida" in e for e in erros),
    f"erros: {erros}",
)
check(
    "Erro de transicao aparece",
    any("transicao de" in e for e in erros),
    f"erros: {erros}",
)
check(
    "Erro de chave vazia aparece",
    any("chave vazia" in e for e in erros),
    f"erros: {erros}",
)
check(
    "Erro de justificativa aparece",
    any("sem justificativa" in e for e in erros),
    f"erros: {erros}",
)
check(
    "Erro de mensagem vazia aparece",
    any("mensagem_cliente vazia" in e for e in erros),
    f"erros: {erros}",
)


# ──────────────────────────────────────────────────────────────────────────────
# RESULTADO FINAL
# ──────────────────────────────────────────────────────────────────────────────

total = passou + falhou
print(f"\n{'─' * 60}")
print(f"{NEGRITO}RESULTADO: {passou}/{total} testes passaram{RESET}")

if falhou == 0:
    print(f"{VERDE}{NEGRITO}✓ Validador de envelope 100% correto.{RESET}")
else:
    print(f"{VERMELHO}{NEGRITO}✗ {falhou} teste(s) falharam — revisar validador_envelope.py{RESET}")
    sys.exit(1)
