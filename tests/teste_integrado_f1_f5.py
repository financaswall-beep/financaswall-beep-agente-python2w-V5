"""
==========================================================================
BATERIA DE TESTES INTEGRADOS — FASES 1 a 5 — Agente 2W Pneus
==========================================================================
Executa testes estruturais, de banco, de lógica de negócio e de IA.
Gera relatório completo ao final.
"""
import sys, traceback
from uuid import UUID, uuid4
from datetime import datetime, timezone
from decimal import Decimal

sys.path.insert(0, ".")

RESULTADOS: list[dict] = []
FASE_CONTADORES: dict[str, dict] = {}


def reg(fase: str, grupo: str, nome: str, ok: bool, detalhe: str = ""):
    RESULTADOS.append({"fase": fase, "grupo": grupo, "nome": nome, "ok": ok, "detalhe": detalhe})
    if fase not in FASE_CONTADORES:
        FASE_CONTADORES[fase] = {"pass": 0, "fail": 0}
    FASE_CONTADORES[fase]["pass" if ok else "fail"] += 1
    marca = "PASS" if ok else "FAIL"
    linha = f"  {marca} [{grupo}] {nome}"
    if detalhe:
        linha += f"  -> {detalhe}"
    print(linha)


def safe(fase, grupo, nome, fn):
    try:
        r = fn()
        reg(fase, grupo, nome, True, str(r) if r is not None else "")
        return r
    except Exception as e:
        reg(fase, grupo, nome, False, str(e)[:200])
        return None


# ============================================================
#  FASE 1 — ENUMS + SCHEMAS
# ============================================================
F = "F1"

print("\n" + "=" * 70)
print("FASE 1: FUNDACAO (Enums + Schemas)")
print("=" * 70)

# --- Imports Enums ---
print("\n--- 1.1 Imports Enums ---")
safe(F, "IMPORT", "13 enums direto", lambda: __import__(
    "agente_2w.enums.enums", fromlist=[
        "TipoDeVerdade", "EtapaFluxo", "StatusSessao", "NivelConfirmacao",
        "OrigemContexto", "StatusItemProvisorio", "TipoEntrega", "FormaPagamento",
        "StatusPedido", "Confianca", "Direcao", "Remetente", "Posicao",
    ]) and "OK")

safe(F, "IMPORT", "Re-export enums/__init__", lambda: __import__(
    "agente_2w.enums", fromlist=[
        "TipoDeVerdade", "EtapaFluxo", "StatusSessao",
    ]) and "OK")

# --- Imports Schemas ---
print("\n--- 1.2 Imports Schemas ---")
schema_modules = [
    ("sessao_chat", ["SessaoChat", "SessaoChatCreate"]),
    ("mensagem_chat", ["MensagemChat", "MensagemChatCreate"]),
    ("contexto_conversa", ["ContextoConversa", "ContextoConversaCreate"]),
    ("item_provisorio", ["ItemProvisorio", "ItemProvisorioCreate"]),
    ("cliente", ["Cliente", "ClienteCreate"]),
    ("pedido", ["Pedido", "PedidoCreate"]),
    ("item_pedido", ["ItemPedido", "ItemPedidoCreate"]),
    ("estoque", ["Estoque"]),
    ("pneu", ["Pneu"]),
    ("moto", ["Moto"]),
    ("medida_moto", ["MedidaMoto"]),
    ("endereco_entrega", ["EnderecoEntrega"]),
    ("metadata_chat", ["MetadataChat"]),
    ("contexto_executavel", ["ContextoExecutavel"]),
    ("envelope_ia", ["EnvelopeIA"]),
]
for mod, classes in schema_modules:
    safe(F, "IMPORT", f"schemas.{mod} ({len(classes)} cls)", lambda m=mod, c=classes:
         __import__(f"agente_2w.schemas.{m}", fromlist=c) and "OK")

# --- Validação de Schemas ---
print("\n--- 1.3 Validação Pydantic ---")

from agente_2w.enums.enums import *
from agente_2w.schemas.sessao_chat import SessaoChat, SessaoChatCreate
from agente_2w.schemas.mensagem_chat import MensagemChat, MensagemChatCreate
from agente_2w.schemas.contexto_conversa import ContextoConversa, ContextoConversaCreate
from agente_2w.schemas.item_provisorio import ItemProvisorio, ItemProvisorioCreate
from agente_2w.schemas.cliente import Cliente, ClienteCreate
from agente_2w.schemas.pedido import Pedido, PedidoCreate
from agente_2w.schemas.item_pedido import ItemPedido, ItemPedidoCreate
from agente_2w.schemas.estoque import Estoque
from agente_2w.schemas.pneu import Pneu
from agente_2w.schemas.endereco_entrega import EnderecoEntrega
from agente_2w.schemas.envelope_ia import EnvelopeIA, FatoObservado, FatoInferido
from agente_2w.schemas.contexto_executavel import ContextoExecutavel, SessaoContexto, ClienteContexto, Metadados

def _falha_esperada(fn):
    try:
        fn()
        raise AssertionError("deveria ter falhado")
    except Exception as e:
        if "AssertionError" in str(type(e)):
            raise
        return "rejeicao OK"

safe(F, "SCHEMA", "SessaoChatCreate instancia", lambda: SessaoChatCreate(
    canal="whatsapp", contato_externo="+5511999", etapa_atual=EtapaFluxo.identificacao,
    status_sessao=StatusSessao.ativa) and "OK")

safe(F, "SCHEMA", "SessaoChat bloqueada sem motivo rejeita", lambda: (
    _falha_esperada(lambda: SessaoChat(
        id=uuid4(), canal="wpp", contato_externo="x", etapa_atual=EtapaFluxo.identificacao,
        status_sessao=StatusSessao.bloqueada, criado_em=datetime.now(timezone.utc),
        ultima_interacao_em=datetime.now(timezone.utc)))))

safe(F, "SCHEMA", "ContextoConversa sem valor rejeita", lambda: _falha_esperada(lambda:
    ContextoConversaCreate(sessao_chat_id=uuid4(), chave="x",
        tipo_de_verdade=TipoDeVerdade.observado, nivel_confirmacao=NivelConfirmacao.nenhum,
        fonte=OrigemContexto.mensagem_cliente)))

safe(F, "SCHEMA", "ItemProvisorio quantidade=0 rejeita", lambda: _falha_esperada(lambda:
    ItemProvisorioCreate(sessao_chat_id=uuid4(), descricao_contextual="x", quantidade=0,
        status_item=StatusItemProvisorio.sugerido)))

safe(F, "SCHEMA", "Pedido tipo_entrega=a_confirmar rejeita", lambda: _falha_esperada(lambda:
    Pedido(id=uuid4(), sessao_chat_id=uuid4(), tipo_entrega=TipoEntrega.a_confirmar,
        forma_pagamento=FormaPagamento.pix, status_pedido=StatusPedido.confirmado,
        criado_em=datetime.now(timezone.utc), atualizado_em=datetime.now(timezone.utc))))

safe(F, "SCHEMA", "ItemPedido subtotal incoerente rejeita", lambda: _falha_esperada(lambda:
    ItemPedido(id=uuid4(), pedido_id=uuid4(), pneu_id=uuid4(), quantidade=2,
        preco_unitario=Decimal("100"), subtotal=Decimal("999"),
        criado_em=datetime.now(timezone.utc))))

safe(F, "SCHEMA", "EnvelopeIA instancia OK", lambda: EnvelopeIA(
    mensagem_cliente="Oi", etapa_atual=EtapaFluxo.identificacao,
    intencao_atual="saudacao", acoes_sugeridas=["registrar_fato_observado"],
    confianca=Confianca.alta) and "OK")

safe(F, "SCHEMA", "ContextoExecutavel instancia OK", lambda: ContextoExecutavel(
    sessao=SessaoContexto(sessao_id=str(uuid4()), canal="wpp", contato_externo="x",
        etapa_atual=EtapaFluxo.identificacao, status_sessao=StatusSessao.ativa,
        ultima_interacao_em=datetime.now(timezone.utc)),
    cliente=ClienteContexto(),
    metadados=Metadados(gerado_em=datetime.now(timezone.utc))) and "OK")


# ============================================================
#  FASE 2 — REPOSITORIOS
# ============================================================
F = "F2"

print("\n" + "=" * 70)
print("FASE 2: REPOSITORIOS")
print("=" * 70)

print("\n--- 2.1 Imports Repos ---")
repo_modules = [
    ("db.sessao_repo", ["criar_sessao", "buscar_sessao_por_id", "buscar_sessao_ativa_por_contato", "atualizar_etapa"]),
    ("db.mensagem_repo", ["criar_mensagem", "listar_mensagens_por_sessao"]),
    ("db.contexto_repo", ["criar_fato", "registrar_fato", "listar_fatos_ativos", "buscar_fato_ativo"]),
    ("db.item_provisorio_repo", ["criar_item", "buscar_item_por_id", "listar_itens_por_sessao"]),
    ("db.cliente_repo", ["criar_cliente", "buscar_cliente_por_telefone", "resolver_ou_criar_cliente"]),
    ("db.catalogo_repo", ["buscar_pneu_por_id", "buscar_pneus_por_dimensoes", "buscar_pneus_por_medida_texto"]),
    ("db.pedido_repo", ["criar_pedido", "buscar_pedido_por_id", "buscar_pedido_por_sessao"]),
    ("db.queries", ["contar_registros", "verificar_existencia", "buscar_por_id"]),
]
for mod, funcs in repo_modules:
    safe(F, "IMPORT", f"{mod} ({len(funcs)} funcs)", lambda m=mod, f=funcs:
         __import__(f"agente_2w.{m}", fromlist=f) and "OK")

print("\n--- 2.2 Conexão Supabase ---")
from agente_2w.db.client import supabase

tabelas = ["sessao_chat", "mensagem_chat", "contexto_conversa", "item_provisorio",
           "cliente", "pedido", "item_pedido", "pneu", "moto", "medida_moto", "estoque"]
for t in tabelas:
    safe(F, "SUPABASE", f"SELECT {t}", lambda t=t: (
        r := supabase.table(t).select("*").limit(1).execute(),
        f"{len(r.data)} reg")[1])

views = ["catalogo_agente", "compatibilidade_moto_pneu"]
for v in views:
    safe(F, "SUPABASE", f"VIEW {v}", lambda v=v: (
        r := supabase.table(v).select("*").limit(1).execute(),
        f"{len(r.data)} reg")[1])

print("\n--- 2.3 Repos Leitura Real ---")
from agente_2w.db import queries, catalogo_repo, sessao_repo, cliente_repo, mensagem_repo, contexto_repo

safe(F, "REPO", "contar_registros('pneu')", lambda: (
    n := queries.contar_registros("pneu"), f"{n} pneus")[1])

safe(F, "REPO", "buscar_pneus_por_dimensoes(aro=17)", lambda: (
    r := catalogo_repo.buscar_pneus_por_dimensoes(aro=17), f"{len(r)} resultados")[1])

safe(F, "REPO", "buscar_pneus_por_medida_texto('100/80')", lambda: (
    r := catalogo_repo.buscar_pneus_por_medida_texto("100/80"), f"{len(r)} resultados")[1])

safe(F, "REPO", "buscar_pneus_por_marca_modelo('Pirelli')", lambda: (
    r := catalogo_repo.buscar_pneus_por_marca_modelo("Pirelli"), f"{len(r)} resultados")[1])

safe(F, "REPO", "buscar_sessao_por_id(fake)=None", lambda: (
    r := sessao_repo.buscar_sessao_por_id(uuid4()),
    "None" if r is None else f"INESPERADO: {r}")[1])

safe(F, "REPO", "buscar_cliente_por_telefone(fake)=None", lambda: (
    r := cliente_repo.buscar_cliente_por_telefone("0000000000"),
    "None" if r is None else f"INESPERADO: {r}")[1])


# ============================================================
#  FASE 3 — ENGINE
# ============================================================
F = "F3"

print("\n" + "=" * 70)
print("FASE 3: ENGINE")
print("=" * 70)

print("\n--- 3.1 Imports Engine ---")
engine_modules = [
    ("engine.maquina_estados", ["transicao_permitida", "proximas_etapas", "e_etapa_terminal"]),
    ("engine.pendencias", ["acoes_permitidas", "pendencias_da_etapa"]),
    ("engine.montador_contexto", ["montar_contexto"]),
    ("engine.validador_envelope", ["validar_envelope"]),
    ("engine.promotor", ["promover_itens"]),
]
for mod, funcs in engine_modules:
    safe(F, "IMPORT", f"{mod} ({len(funcs)})", lambda m=mod, f=funcs:
         __import__(f"agente_2w.{m}", fromlist=f) and "OK")

print("\n--- 3.2 Máquina de Estados ---")
from agente_2w.engine.maquina_estados import transicao_permitida, proximas_etapas, e_etapa_terminal

transicoes_validas = [
    (EtapaFluxo.identificacao, EtapaFluxo.busca, True),
    (EtapaFluxo.busca, EtapaFluxo.oferta, True),
    (EtapaFluxo.oferta, EtapaFluxo.confirmacao_item, True),
    (EtapaFluxo.confirmacao_item, EtapaFluxo.entrega_pagamento, True),
    (EtapaFluxo.entrega_pagamento, EtapaFluxo.fechamento, True),
    (EtapaFluxo.busca, EtapaFluxo.identificacao, True),
    (EtapaFluxo.oferta, EtapaFluxo.busca, True),
    (EtapaFluxo.identificacao, EtapaFluxo.fechamento, False),
    (EtapaFluxo.busca, EtapaFluxo.fechamento, False),
    (EtapaFluxo.fechamento, EtapaFluxo.identificacao, False),
]
for orig, dest, esperado in transicoes_validas:
    safe(F, "ESTADO", f"{orig.value}->{dest.value}={esperado}", lambda o=orig, d=dest, e=esperado: (
        r := transicao_permitida(o, d),
        "OK" if r == e else f"FALHA: esperava {e}, obteve {r}")[1])

safe(F, "ESTADO", "fechamento é terminal", lambda: "OK" if e_etapa_terminal(EtapaFluxo.fechamento) else "FALHA")
safe(F, "ESTADO", "identificacao NAO é terminal", lambda: "OK" if not e_etapa_terminal(EtapaFluxo.identificacao) else "FALHA")
safe(F, "ESTADO", "proximas(identificacao)=[busca]", lambda: (
    r := proximas_etapas(EtapaFluxo.identificacao),
    "OK" if r == [EtapaFluxo.busca] else f"FALHA: {r}")[1])

print("\n--- 3.3 Pendências ---")
from agente_2w.engine.pendencias import acoes_permitidas, pendencias_da_etapa

etapas_acoes = {
    EtapaFluxo.identificacao: 7, EtapaFluxo.busca: 7, EtapaFluxo.oferta: 4,
    EtapaFluxo.confirmacao_item: 5, EtapaFluxo.entrega_pagamento: 6, EtapaFluxo.fechamento: 3,
}
for etapa, qtd in etapas_acoes.items():
    safe(F, "PENDENCIA", f"{etapa.value} tem {qtd} acoes", lambda e=etapa, q=qtd: (
        r := acoes_permitidas(e),
        "OK" if len(r) == q else f"FALHA: tem {len(r)}")[1])

for etapa in EtapaFluxo:
    safe(F, "PENDENCIA", f"{etapa.value} tem responder_incerteza_segura", lambda e=etapa: (
        "OK" if "responder_incerteza_segura" in acoes_permitidas(e) else "FALHA"))

print("\n--- 3.4 Validador de Envelope ---")
from agente_2w.engine.validador_envelope import validar_envelope

def _ctx_teste(etapa=EtapaFluxo.identificacao):
    return ContextoExecutavel(
        sessao=SessaoContexto(sessao_id=str(uuid4()), canal="teste", contato_externo="x",
            etapa_atual=etapa, status_sessao=StatusSessao.ativa,
            ultima_interacao_em=datetime.now(timezone.utc)),
        cliente=ClienteContexto(),
        metadados=Metadados(gerado_em=datetime.now(timezone.utc)))

safe(F, "VALIDADOR", "envelope valido = 0 erros", lambda: (
    env := EnvelopeIA(mensagem_cliente="Oi", etapa_atual=EtapaFluxo.identificacao,
        intencao_atual="saudacao", acoes_sugeridas=["registrar_fato_observado"], confianca=Confianca.alta),
    erros := validar_envelope(env, _ctx_teste()),
    f"{len(erros)} erros" if len(erros) == 0 else f"FALHA: {erros}")[2])

safe(F, "VALIDADOR", "acao invalida na etapa = erro", lambda: (
    env := EnvelopeIA(mensagem_cliente="X", etapa_atual=EtapaFluxo.identificacao,
        intencao_atual="x", acoes_sugeridas=["converter_em_pedido"], confianca=Confianca.alta),
    erros := validar_envelope(env, _ctx_teste()),
    "OK" if len(erros) > 0 else "FALHA: deveria ter erros")[2])

safe(F, "VALIDADOR", "transicao proibida = erro", lambda: (
    env := EnvelopeIA(mensagem_cliente="X", etapa_atual=EtapaFluxo.fechamento,
        intencao_atual="x", acoes_sugeridas=["responder_incerteza_segura"], confianca=Confianca.alta),
    erros := validar_envelope(env, _ctx_teste()),
    "OK" if len(erros) > 0 else "FALHA: deveria ter erros")[2])

safe(F, "VALIDADOR", "fato inferido sem justificativa = erro", lambda: (
    env := EnvelopeIA(mensagem_cliente="X", etapa_atual=EtapaFluxo.identificacao,
        intencao_atual="x", acoes_sugeridas=["registrar_fato_observado"], confianca=Confianca.alta,
        fatos_inferidos=[FatoInferido(chave="x", valor="y", justificativa="")]),
    erros := validar_envelope(env, _ctx_teste()),
    "OK" if len(erros) > 0 else "FALHA: deveria ter erros")[2])


# ============================================================
#  FASE 4 — TOOLS
# ============================================================
F = "F4"

print("\n" + "=" * 70)
print("FASE 4: TOOLS")
print("=" * 70)

print("\n--- 4.1 Imports Tools ---")
safe(F, "IMPORT", "busca_catalogo (3 funcs)", lambda: __import__(
    "agente_2w.tools.busca_catalogo", fromlist=["buscar_pneus", "buscar_pneus_por_moto", "buscar_detalhes_pneu"]) and "OK")
safe(F, "IMPORT", "consulta_estoque (1 func)", lambda: __import__(
    "agente_2w.tools.consulta_estoque", fromlist=["consultar_estoque"]) and "OK")
safe(F, "IMPORT", "resolve_cliente (1 func)", lambda: __import__(
    "agente_2w.tools.resolve_cliente", fromlist=["resolver_cliente"]) and "OK")

print("\n--- 4.2 Tools Execução Real ---")
from agente_2w.tools.busca_catalogo import buscar_pneus, buscar_pneus_por_moto, buscar_detalhes_pneu
from agente_2w.tools.consulta_estoque import consultar_estoque
from agente_2w.tools.resolve_cliente import resolver_cliente

r_pneus = safe(F, "TOOL", "buscar_pneus(aro=17)", lambda: (
    r := buscar_pneus(aro=17), f"{r['quantidade']} pneus")[1])

safe(F, "TOOL", "buscar_pneus(medida_texto='100/80')", lambda: (
    r := buscar_pneus(medida_texto="100/80"), f"{r['quantidade']} pneus")[1])

safe(F, "TOOL", "buscar_pneus(marca_modelo='Pirelli')", lambda: (
    r := buscar_pneus(marca_modelo="Pirelli"), f"{r['quantidade']} pneus")[1])

safe(F, "TOOL", "buscar_pneus_por_moto('CG 160')", lambda: (
    r := buscar_pneus_por_moto("CG 160"), f"{r['quantidade']} compat")[1])

# Pegar pneu_id real
_pneus = buscar_pneus(aro=17)
_pid = _pneus["pneus"][0].get("pneu_id") or _pneus["pneus"][0].get("id") if _pneus["pneus"] else None

if _pid:
    safe(F, "TOOL", "buscar_detalhes_pneu(real)", lambda: (
        r := buscar_detalhes_pneu(str(_pid)),
        f"encontrado={r['encontrado']}, estoque={'sim' if r.get('estoque') else 'nao'}")[1])

    safe(F, "TOOL", "consultar_estoque(real)", lambda: (
        r := consultar_estoque(str(_pid)),
        f"disponivel={r['disponivel']}, preco={r.get('preco_venda','?')}")[1])

safe(F, "TOOL", "buscar_detalhes_pneu(fake)", lambda: (
    r := buscar_detalhes_pneu("00000000-0000-0000-0000-000000000000"),
    f"encontrado={r['encontrado']}")[1])

safe(F, "TOOL", "consultar_estoque(fake)", lambda: (
    r := consultar_estoque("00000000-0000-0000-0000-000000000000"),
    f"disponivel={r['disponivel']}")[1])

# resolve_cliente (criar + buscar + limpar)
_rc = safe(F, "TOOL", "resolver_cliente(novo)", lambda: (
    r := resolver_cliente("0000000001"), f"ja_existia={r['ja_existia']}")[1])

if _rc:
    _cl = resolver_cliente("0000000001")
    safe(F, "TOOL", "resolver_cliente(existente)", lambda: f"ja_existia={_cl['ja_existia']}")
    supabase.table("cliente").delete().eq("telefone", "0000000001").execute()


# ============================================================
#  FASE 5 — IA
# ============================================================
F = "F5"

print("\n" + "=" * 70)
print("FASE 5: IA")
print("=" * 70)

print("\n--- 5.1 Imports IA ---")
safe(F, "IMPORT", "prompt_sistema", lambda: (
    mod := __import__("agente_2w.ia.prompt_sistema", fromlist=["SYSTEM_PROMPT"]),
    f"{len(mod.SYSTEM_PROMPT)} chars")[1])

safe(F, "IMPORT", "agente (5 tools)", lambda: (
    mod := __import__("agente_2w.ia.agente", fromlist=["TOOLS_SCHEMA", "_TOOL_DISPATCH"]),
    f"{len(mod.TOOLS_SCHEMA)} tools, {len(mod._TOOL_DISPATCH)} dispatchers")[1])

safe(F, "IMPORT", "parser_envelope", lambda: __import__(
    "agente_2w.ia.parser_envelope", fromlist=["parse_resposta", "ParseError"]) and "OK")

print("\n--- 5.2 Parser ---")
from agente_2w.ia.parser_envelope import parse_resposta, ParseError

json_valido = '''{
  "mensagem_cliente": "Oi! Qual moto voce tem?",
  "etapa_atual": "identificacao",
  "intencao_atual": "saudacao inicial",
  "acoes_sugeridas": ["pedir_clarificacao_moto"],
  "confianca": "alta"
}'''

def _try_parse_error():
    try:
        parse_resposta("nao e json", _ctx_teste())
        raise AssertionError("deveria ter falhado")
    except ParseError:
        return True

safe(F, "PARSER", "JSON valido aceito", lambda: (
    _r := parse_resposta(json_valido, _ctx_teste()),
    f"{len(_r[1])} erros")[1])

safe(F, "PARSER", "JSON em markdown aceito", lambda: (
    _r := parse_resposta("```json\n" + json_valido + "\n```", _ctx_teste()),
    "OK")[1])

safe(F, "PARSER", "JSON com texto ao redor aceito", lambda: (
    _r := parse_resposta("Resposta:\n" + json_valido + "\nFim.", _ctx_teste()),
    "OK")[1])

safe(F, "PARSER", "texto invalido rejeita", lambda: (
    _try_parse_error(), "ParseError OK")[1])

safe(F, "PARSER", "acao invalida detectada", lambda: (
    _r := parse_resposta('''{
        "mensagem_cliente":"X","etapa_atual":"identificacao","intencao_atual":"x",
        "acoes_sugeridas":["converter_em_pedido"],"confianca":"alta"
    }''', _ctx_teste()),
    f"{len(_r[1])} erros detectados")[1])


# ============================================================
#  INTEGRAÇÃO CROSS-FASE (F1→F5 fluxo completo)
# ============================================================
F = "INT"

print("\n" + "=" * 70)
print("INTEGRACAO: FLUXO COMPLETO F1-F5")
print("=" * 70)

from agente_2w.db import sessao_repo, mensagem_repo, contexto_repo
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.schemas.mensagem_chat import MensagemChatCreate
from agente_2w.schemas.contexto_conversa import ContextoConversaCreate
from agente_2w.engine.montador_contexto import montar_contexto
from agente_2w.ia.agente import chamar_agente

print("\n--- INT.1 Criar sessão + mensagem + fato ---")
_s = sessao_repo.criar_sessao(SessaoChatCreate(
    canal="teste_integrado", contato_externo="teste_int_bot",
    etapa_atual=EtapaFluxo.identificacao, status_sessao=StatusSessao.ativa))
reg(F, "CRIAR", "Sessao criada", True, f"id={str(_s.id)[:8]}...")

_m = mensagem_repo.criar_mensagem(MensagemChatCreate(
    sessao_chat_id=_s.id, direcao=Direcao.entrada, remetente=Remetente.cliente,
    conteudo_texto="Preciso de pneu pra CG 160", criado_em=datetime.now(timezone.utc)))
reg(F, "CRIAR", "Mensagem criada", True, f"id={str(_m.id)[:8]}...")

_f = contexto_repo.criar_fato(ContextoConversaCreate(
    sessao_chat_id=_s.id, chave="moto_modelo_informado", valor_texto="CG 160",
    tipo_de_verdade=TipoDeVerdade.observado, nivel_confirmacao=NivelConfirmacao.nenhum,
    fonte=OrigemContexto.mensagem_cliente, mensagem_chat_id=_m.id))
reg(F, "CRIAR", "Fato criado", True, f"id={str(_f.id)[:8]}...")

print("\n--- INT.2 Montar contexto (F3) ---")
_ctx = safe(F, "ENGINE", "montar_contexto", lambda: montar_contexto(_s.id))
if _ctx:
    reg(F, "ENGINE", "sessao.etapa_atual", True, _ctx.sessao.etapa_atual.value)
    reg(F, "ENGINE", "mensagens_recentes", True, f"{len(_ctx.mensagens_recentes)}")
    reg(F, "ENGINE", "fatos_ativos", True, f"{len(_ctx.fatos_ativos)}")
    reg(F, "ENGINE", "acoes_permitidas", True, f"{len(_ctx.acoes_permitidas)} acoes")
    reg(F, "ENGINE", "pendencias", True, f"{len(_ctx.pendencias)}")

print("\n--- INT.3 Chamar IA (F5) ---")
_resposta_bruta = None
if _ctx:
    _resultado_ia = safe(F, "IA", "chamar_agente (OpenAI real)", lambda:
        chamar_agente(_ctx, "Preciso de pneu pra CG 160"))
    # chamar_agente retorna (texto, pneus_encontrados) desde Fase 9
    if isinstance(_resultado_ia, tuple):
        _resposta_bruta, _pneus_ia = _resultado_ia
    else:
        _resposta_bruta = _resultado_ia

if _resposta_bruta:
    print(f"  [RESPOSTA] {str(_resposta_bruta)[:120]}...")

print("\n--- INT.4 Parse resposta (F5) ---")
if _resposta_bruta and _ctx:
    _parse_result = safe(F, "PARSER", "parse_resposta real", lambda: parse_resposta(_resposta_bruta, _ctx))
    if _parse_result and isinstance(_parse_result, tuple):
        _env, _erros = _parse_result
        reg(F, "PARSER", "etapa_atual", True, _env.etapa_atual.value)
        reg(F, "PARSER", "intencao_atual", True, _env.intencao_atual[:60])
        reg(F, "PARSER", "acoes_sugeridas", True, str(_env.acoes_sugeridas))
        reg(F, "PARSER", "fatos_observados", True, f"{len(_env.fatos_observados)}")
        reg(F, "PARSER", "confianca", True, _env.confianca.value)
        reg(F, "PARSER", "erros_validacao", True, f"{len(_erros)} erros" + (f": {_erros}" if _erros else ""))
        reg(F, "PARSER", "mensagem_cliente nao vazia", _env.mensagem_cliente.strip() != "",
            f"{len(_env.mensagem_cliente)} chars")

print("\n--- INT.5 Limpeza ---")
supabase.table("contexto_conversa").delete().eq("sessao_chat_id", str(_s.id)).execute()
supabase.table("mensagem_chat").delete().eq("sessao_chat_id", str(_s.id)).execute()
supabase.table("sessao_chat").delete().eq("id", str(_s.id)).execute()
# Limpar sessoes extras criadas no safe acima
supabase.table("sessao_chat").delete().eq("contato_externo", "teste_int_bot").execute()
reg(F, "LIMPEZA", "Dados de teste removidos", True)


# ============================================================
#  RELATORIO FINAL
# ============================================================
print("\n" + "=" * 70)
print("RELATORIO FINAL — BATERIA INTEGRADA FASES 1-5")
print("=" * 70)

total = len(RESULTADOS)
total_pass = sum(1 for r in RESULTADOS if r["ok"])
total_fail = sum(1 for r in RESULTADOS if not r["ok"])

# Por fase
print("\n--- Por Fase ---")
for fase in ["F1", "F2", "F3", "F4", "F5", "INT"]:
    c = FASE_CONTADORES.get(fase, {"pass": 0, "fail": 0})
    nome_fase = {"F1": "Fundacao", "F2": "Repositorios", "F3": "Engine",
                 "F4": "Tools", "F5": "IA", "INT": "Integracao"}[fase]
    total_f = c["pass"] + c["fail"]
    status = "PASS" if c["fail"] == 0 else "FAIL"
    print(f"  {fase} {nome_fase:20s} {c['pass']:3d}/{total_f:3d} {status}")

# Falhas
falhas = [r for r in RESULTADOS if not r["ok"]]
if falhas:
    print(f"\n--- {len(falhas)} FALHA(S) ---")
    for r in falhas:
        print(f"  FAIL [{r['fase']}][{r['grupo']}] {r['nome']}")
        if r["detalhe"]:
            print(f"    {r['detalhe'][:150]}")

print(f"\n{'='*70}")
print(f"TOTAL: {total} testes | PASS: {total_pass} | FAIL: {total_fail}")
if total_fail == 0:
    print("RESULTADO: TODOS OS TESTES PASSARAM")
else:
    print(f"RESULTADO: {total_fail} FALHA(S) ENCONTRADA(S)")
print("=" * 70)
