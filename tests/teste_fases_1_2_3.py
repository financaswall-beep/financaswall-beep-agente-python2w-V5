"""
Teste completo das Fases 1, 2 e 3 do Agente 2W Pneus.
Executa testes estruturais (imports, schemas, logica) e testes reais (Supabase).
"""
import sys
import traceback
from uuid import UUID, uuid4
from datetime import datetime, timezone
from decimal import Decimal

RESULTADOS: list[dict] = []


def registrar(grupo: str, nome: str, ok: bool, detalhe: str = ""):
    status = "PASS" if ok else "FAIL"
    RESULTADOS.append({"grupo": grupo, "nome": nome, "ok": ok, "detalhe": detalhe})
    marca = "✓" if ok else "✗"
    print(f"  {marca} [{grupo}] {nome}" + (f"  -> {detalhe}" if detalhe else ""))


# ============================================================
# GRUPO 1: IMPORTS (Fase 1 - Enums e Schemas)
# ============================================================
print("\n" + "=" * 60)
print("GRUPO 1: IMPORTS FASE 1 (Enums + Schemas)")
print("=" * 60)

try:
    from agente_2w.enums.enums import (
        TipoDeVerdade, EtapaFluxo, StatusSessao, NivelConfirmacao,
        OrigemContexto, StatusItemProvisorio, TipoEntrega, FormaPagamento,
        StatusPedido, Confianca, Direcao, Remetente, Posicao,
    )
    registrar("IMPORT", "13 enums importados", True)
except Exception as e:
    registrar("IMPORT", "13 enums importados", False, str(e))

try:
    from agente_2w.enums import (
        TipoDeVerdade, EtapaFluxo, StatusSessao, NivelConfirmacao,
        OrigemContexto, StatusItemProvisorio, TipoEntrega, FormaPagamento,
        StatusPedido, Confianca, Direcao, Remetente, Posicao,
    )
    registrar("IMPORT", "Re-export via enums/__init__", True)
except Exception as e:
    registrar("IMPORT", "Re-export via enums/__init__", False, str(e))

schema_modules = [
    ("sessao_chat", ["SessaoChat", "SessaoChatCreate", "SessaoChatBase"]),
    ("mensagem_chat", ["MensagemChat", "MensagemChatCreate"]),
    ("contexto_conversa", ["ContextoConversa", "ContextoConversaCreate"]),
    ("item_provisorio", ["ItemProvisorio", "ItemProvisorioCreate"]),
    ("cliente", ["Cliente", "ClienteCreate"]),
    ("pedido", ["Pedido", "PedidoCreate"]),
    ("item_pedido", ["ItemPedido", "ItemPedidoCreate"]),
    ("estoque", ["Estoque"]),
    ("pneu", ["Pneu"]),
    ("moto", ["Moto"]),
    ("medida_moto", ["MedidaMoto", "MedidaMotoCreate"]),
    ("endereco_entrega", ["EnderecoEntrega"]),
    ("metadata_chat", ["MetadataChat"]),
    ("contexto_executavel", ["ContextoExecutavel", "SessaoContexto", "ClienteContexto"]),
    ("envelope_ia", ["EnvelopeIA", "FatoObservado", "FatoInferido"]),
]

for modname, classes in schema_modules:
    try:
        mod = __import__(f"agente_2w.schemas.{modname}", fromlist=classes)
        for cls_name in classes:
            getattr(mod, cls_name)
        registrar("IMPORT", f"schemas.{modname} ({', '.join(classes)})", True)
    except Exception as e:
        registrar("IMPORT", f"schemas.{modname}", False, str(e))

# ============================================================
# GRUPO 2: IMPORTS FASE 2 (Repos)
# ============================================================
print("\n" + "=" * 60)
print("GRUPO 2: IMPORTS FASE 2 (Repos)")
print("=" * 60)

repo_modules = {
    "sessao_repo": ["criar_sessao", "buscar_sessao_por_id", "atualizar_etapa", "atualizar_status"],
    "mensagem_repo": ["criar_mensagem", "listar_mensagens_por_sessao"],
    "contexto_repo": ["criar_fato", "registrar_fato", "listar_fatos_ativos", "buscar_fato_ativo"],
    "item_provisorio_repo": ["criar_item", "listar_itens_ativos_por_sessao", "atualizar_status_item"],
    "cliente_repo": ["criar_cliente", "buscar_cliente_por_id", "resolver_ou_criar_cliente"],
    "catalogo_repo": ["buscar_pneu_por_id", "buscar_pneus_por_dimensoes", "buscar_estoque_por_pneu"],
    "pedido_repo": ["criar_pedido", "criar_item_pedido", "listar_itens_pedido"],
    "queries": ["contar_registros", "existe_registro", "buscar_por_id"],
}

for repo_name, funcs in repo_modules.items():
    try:
        mod = __import__(f"agente_2w.db.{repo_name}", fromlist=funcs)
        for fn in funcs:
            getattr(mod, fn)
        registrar("IMPORT", f"db.{repo_name} ({len(funcs)} funcs)", True)
    except Exception as e:
        registrar("IMPORT", f"db.{repo_name}", False, str(e))

# ============================================================
# GRUPO 3: IMPORTS FASE 3 (Engine)
# ============================================================
print("\n" + "=" * 60)
print("GRUPO 3: IMPORTS FASE 3 (Engine)")
print("=" * 60)

engine_imports = {
    "maquina_estados": ["transicao_permitida", "motivo_bloqueio", "proximas_etapas", "e_etapa_terminal", "TRANSICOES_PERMITIDAS"],
    "pendencias": ["acoes_permitidas", "pendencias_da_etapa", "ACOES_POR_ETAPA", "PENDENCIAS_POR_ETAPA"],
    "montador_contexto": ["montar_contexto"],
    "validador_envelope": ["validar_envelope"],
    "promotor": ["validar_pre_condicoes", "promover_para_pedido"],
}

for mod_name, items in engine_imports.items():
    try:
        mod = __import__(f"agente_2w.engine.{mod_name}", fromlist=items)
        for item in items:
            getattr(mod, item)
        registrar("IMPORT", f"engine.{mod_name} ({len(items)} items)", True)
    except Exception as e:
        registrar("IMPORT", f"engine.{mod_name}", False, str(e))

# ============================================================
# GRUPO 4: SCHEMAS - INSTANCIACAO
# ============================================================
print("\n" + "=" * 60)
print("GRUPO 4: SCHEMAS INSTANCIACAO")
print("=" * 60)

from agente_2w.schemas.sessao_chat import SessaoChat, SessaoChatCreate
from agente_2w.schemas.mensagem_chat import MensagemChat, MensagemChatCreate
from agente_2w.schemas.contexto_conversa import ContextoConversa, ContextoConversaCreate
from agente_2w.schemas.item_provisorio import ItemProvisorio, ItemProvisorioCreate
from agente_2w.schemas.cliente import Cliente, ClienteCreate
from agente_2w.schemas.pedido import Pedido, PedidoCreate
from agente_2w.schemas.item_pedido import ItemPedido, ItemPedidoCreate
from agente_2w.schemas.estoque import Estoque
from agente_2w.schemas.pneu import Pneu
from agente_2w.schemas.moto import Moto
from agente_2w.schemas.medida_moto import MedidaMoto
from agente_2w.schemas.endereco_entrega import EnderecoEntrega
from agente_2w.schemas.metadata_chat import MetadataChat
from agente_2w.schemas.contexto_executavel import ContextoExecutavel, SessaoContexto, ClienteContexto, Metadados, ResumoOperacional
from agente_2w.schemas.envelope_ia import EnvelopeIA, FatoObservado, FatoInferido

# SessaoChat
try:
    s = SessaoChatCreate(
        canal="whatsapp", contato_externo="5511999990000",
        etapa_atual=EtapaFluxo.identificacao, status_sessao=StatusSessao.ativa,
    )
    registrar("SCHEMA", "SessaoChatCreate instancia OK", True)
except Exception as e:
    registrar("SCHEMA", "SessaoChatCreate", False, str(e))

# SessaoChat bloqueada sem motivo = erro
try:
    SessaoChatCreate(
        canal="whatsapp", contato_externo="5511999990000",
        etapa_atual=EtapaFluxo.identificacao, status_sessao=StatusSessao.bloqueada,
    )
    registrar("SCHEMA", "SessaoChat bloqueada sem motivo rejeita", False, "deveria ter dado erro")
except ValueError:
    registrar("SCHEMA", "SessaoChat bloqueada sem motivo rejeita", True)

# MensagemChat
try:
    MensagemChatCreate(
        sessao_chat_id=uuid4(), direcao=Direcao.entrada, remetente=Remetente.cliente,
        conteudo_texto="oi", criado_em=datetime.now(timezone.utc),
    )
    registrar("SCHEMA", "MensagemChatCreate instancia OK", True)
except Exception as e:
    registrar("SCHEMA", "MensagemChatCreate", False, str(e))

# ContextoConversa - com valor_texto
try:
    ContextoConversaCreate(
        sessao_chat_id=uuid4(), chave="moto_modelo_informado",
        tipo_de_verdade=TipoDeVerdade.observado, nivel_confirmacao=NivelConfirmacao.nenhum,
        fonte=OrigemContexto.mensagem_cliente, valor_texto="CG 160",
        mensagem_chat_id=uuid4(),
    )
    registrar("SCHEMA", "ContextoConversaCreate com valor_texto OK", True)
except Exception as e:
    registrar("SCHEMA", "ContextoConversaCreate com valor_texto", False, str(e))

# ContextoConversa - sem valor = erro
try:
    ContextoConversaCreate(
        sessao_chat_id=uuid4(), chave="test",
        tipo_de_verdade=TipoDeVerdade.observado, nivel_confirmacao=NivelConfirmacao.nenhum,
        fonte=OrigemContexto.backend,
    )
    registrar("SCHEMA", "ContextoConversa sem valor rejeita", False, "deveria ter dado erro")
except ValueError:
    registrar("SCHEMA", "ContextoConversa sem valor rejeita", True)

# ContextoConversa - fonte mensagem_cliente sem mensagem_chat_id = erro
try:
    ContextoConversaCreate(
        sessao_chat_id=uuid4(), chave="test",
        tipo_de_verdade=TipoDeVerdade.observado, nivel_confirmacao=NivelConfirmacao.nenhum,
        fonte=OrigemContexto.mensagem_cliente, valor_texto="x",
    )
    registrar("SCHEMA", "ContextoConversa mensagem_cliente sem msg_id rejeita", False, "deveria dar erro")
except ValueError:
    registrar("SCHEMA", "ContextoConversa mensagem_cliente sem msg_id rejeita", True)

# ItemProvisorio
try:
    ItemProvisorioCreate(
        sessao_chat_id=uuid4(), status_item=StatusItemProvisorio.sugerido,
    )
    registrar("SCHEMA", "ItemProvisorioCreate instancia OK", True)
except Exception as e:
    registrar("SCHEMA", "ItemProvisorioCreate", False, str(e))

# ItemProvisorio - promovido sem pneu = erro
try:
    ItemProvisorioCreate(
        sessao_chat_id=uuid4(), status_item=StatusItemProvisorio.promovido,
    )
    registrar("SCHEMA", "ItemProvisorio promovido sem pneu rejeita", False, "deveria dar erro")
except ValueError:
    registrar("SCHEMA", "ItemProvisorio promovido sem pneu rejeita", True)

# ItemProvisorio - quantidade < 1 = erro
try:
    ItemProvisorioCreate(
        sessao_chat_id=uuid4(), status_item=StatusItemProvisorio.sugerido, quantidade=0,
    )
    registrar("SCHEMA", "ItemProvisorio quantidade=0 rejeita", False, "deveria dar erro")
except ValueError:
    registrar("SCHEMA", "ItemProvisorio quantidade=0 rejeita", True)

# Pedido
try:
    PedidoCreate(
        sessao_chat_id=uuid4(), cliente_id=uuid4(),
        tipo_entrega=TipoEntrega.retirada, forma_pagamento=FormaPagamento.pix,
        valor_total=Decimal("350.00"), status_pedido=StatusPedido.confirmado,
    )
    registrar("SCHEMA", "PedidoCreate instancia OK", True)
except Exception as e:
    registrar("SCHEMA", "PedidoCreate", False, str(e))

# Pedido - tipo_entrega a_confirmar = erro
try:
    PedidoCreate(
        sessao_chat_id=uuid4(), cliente_id=uuid4(),
        tipo_entrega=TipoEntrega.a_confirmar, forma_pagamento=FormaPagamento.pix,
        valor_total=Decimal("350.00"), status_pedido=StatusPedido.confirmado,
    )
    registrar("SCHEMA", "Pedido tipo_entrega=a_confirmar rejeita", False, "deveria dar erro")
except ValueError:
    registrar("SCHEMA", "Pedido tipo_entrega=a_confirmar rejeita", True)

# Pedido - entrega sem endereco = erro
try:
    PedidoCreate(
        sessao_chat_id=uuid4(), cliente_id=uuid4(),
        tipo_entrega=TipoEntrega.entrega, forma_pagamento=FormaPagamento.pix,
        valor_total=Decimal("350.00"), status_pedido=StatusPedido.confirmado,
    )
    registrar("SCHEMA", "Pedido entrega sem endereco rejeita", False, "deveria dar erro")
except ValueError:
    registrar("SCHEMA", "Pedido entrega sem endereco rejeita", True)

# ItemPedido
try:
    ItemPedidoCreate(
        pedido_id=uuid4(), pneu_id=uuid4(), quantidade=2,
        preco_unitario=Decimal("175.00"), subtotal=Decimal("350.00"),
    )
    registrar("SCHEMA", "ItemPedidoCreate instancia OK", True)
except Exception as e:
    registrar("SCHEMA", "ItemPedidoCreate", False, str(e))

# ItemPedido - subtotal incoerente = erro
try:
    ItemPedidoCreate(
        pedido_id=uuid4(), pneu_id=uuid4(), quantidade=2,
        preco_unitario=Decimal("175.00"), subtotal=Decimal("999.00"),
    )
    registrar("SCHEMA", "ItemPedido subtotal incoerente rejeita", False, "deveria dar erro")
except ValueError:
    registrar("SCHEMA", "ItemPedido subtotal incoerente rejeita", True)

# EnderecoEntrega
try:
    EnderecoEntrega(
        logradouro="Rua A", numero="10", bairro="Centro",
        cidade="SP", estado="SP", cep="01000-000",
    )
    registrar("SCHEMA", "EnderecoEntrega instancia OK", True)
except Exception as e:
    registrar("SCHEMA", "EnderecoEntrega", False, str(e))

# EnvelopeIA
try:
    env = EnvelopeIA(
        mensagem_cliente="Oi, quero um pneu para CG 160",
        etapa_atual=EtapaFluxo.identificacao,
        intencao_atual="compra_pneu",
        acoes_sugeridas=["pedir_clarificacao_moto"],
        confianca=Confianca.alta,
    )
    registrar("SCHEMA", "EnvelopeIA instancia OK", True)
except Exception as e:
    registrar("SCHEMA", "EnvelopeIA", False, str(e))

# ContextoExecutavel
try:
    ctx = ContextoExecutavel(
        sessao=SessaoContexto(
            sessao_id=str(uuid4()), canal="whatsapp", contato_externo="5511999990000",
            etapa_atual=EtapaFluxo.identificacao, status_sessao=StatusSessao.ativa,
            ultima_interacao_em=datetime.now(timezone.utc),
        ),
        cliente=ClienteContexto(),
        metadados=Metadados(gerado_em=datetime.now(timezone.utc)),
    )
    registrar("SCHEMA", "ContextoExecutavel instancia OK", True)
except Exception as e:
    registrar("SCHEMA", "ContextoExecutavel", False, str(e))

# ============================================================
# GRUPO 5: MAQUINA DE ESTADOS
# ============================================================
print("\n" + "=" * 60)
print("GRUPO 5: MAQUINA DE ESTADOS")
print("=" * 60)

from agente_2w.engine.maquina_estados import (
    transicao_permitida, motivo_bloqueio,
    proximas_etapas, e_etapa_terminal, TRANSICOES_PERMITIDAS,
)

# Todas as etapas tem entrada no dicionario
for etapa in EtapaFluxo:
    ok = etapa in TRANSICOES_PERMITIDAS
    registrar("ESTADO", f"{etapa.value} existe em TRANSICOES", ok)

# Transicoes validas
testes_transicao = [
    (EtapaFluxo.identificacao, EtapaFluxo.busca, True),
    (EtapaFluxo.busca, EtapaFluxo.oferta, True),
    (EtapaFluxo.oferta, EtapaFluxo.confirmacao_item, True),
    (EtapaFluxo.confirmacao_item, EtapaFluxo.entrega_pagamento, True),
    (EtapaFluxo.entrega_pagamento, EtapaFluxo.fechamento, True),
    # Retornos permitidos
    (EtapaFluxo.busca, EtapaFluxo.identificacao, True),
    (EtapaFluxo.oferta, EtapaFluxo.busca, True),
    # Transicoes proibidas
    (EtapaFluxo.identificacao, EtapaFluxo.fechamento, False),
    (EtapaFluxo.busca, EtapaFluxo.fechamento, False),
    (EtapaFluxo.fechamento, EtapaFluxo.identificacao, False),
]
for atual, destino, esperado in testes_transicao:
    resultado = transicao_permitida(atual, destino)
    ok = resultado == esperado
    registrar("ESTADO", f"{atual.value}->{destino.value} = {esperado}", ok)

# Etapa terminal
registrar("ESTADO", "fechamento e terminal", e_etapa_terminal(EtapaFluxo.fechamento))
registrar("ESTADO", "identificacao NAO e terminal", not e_etapa_terminal(EtapaFluxo.identificacao))

# Proximas etapas
prox = proximas_etapas(EtapaFluxo.identificacao)
registrar("ESTADO", "proximas(identificacao) = [busca]", prox == [EtapaFluxo.busca])

# ============================================================
# GRUPO 6: PENDENCIAS
# ============================================================
print("\n" + "=" * 60)
print("GRUPO 6: PENDENCIAS")
print("=" * 60)

from agente_2w.engine.pendencias import acoes_permitidas, pendencias_da_etapa, ACOES_POR_ETAPA

# Todas as etapas tem acoes
for etapa in EtapaFluxo:
    acoes = acoes_permitidas(etapa)
    ok = len(acoes) > 0
    registrar("PENDENCIA", f"{etapa.value} tem {len(acoes)} acoes", ok)

# responder_incerteza_segura esta em todas
for etapa in EtapaFluxo:
    acoes = acoes_permitidas(etapa)
    ok = "responder_incerteza_segura" in acoes
    registrar("PENDENCIA", f"{etapa.value} tem responder_incerteza_segura", ok)

# Pendencias existem para todas as etapas
for etapa in EtapaFluxo:
    pends = pendencias_da_etapa(etapa)
    registrar("PENDENCIA", f"{etapa.value} tem {len(pends)} pendencia(s)", len(pends) >= 1)

# ============================================================
# GRUPO 7: VALIDADOR DE ENVELOPE (unitario)
# ============================================================
print("\n" + "=" * 60)
print("GRUPO 7: VALIDADOR DE ENVELOPE")
print("=" * 60)

from agente_2w.engine.validador_envelope import validar_envelope

ctx_teste = ContextoExecutavel(
    sessao=SessaoContexto(
        sessao_id=str(uuid4()), canal="whatsapp", contato_externo="5511999990000",
        etapa_atual=EtapaFluxo.identificacao, status_sessao=StatusSessao.ativa,
        ultima_interacao_em=datetime.now(timezone.utc),
    ),
    cliente=ClienteContexto(),
    metadados=Metadados(gerado_em=datetime.now(timezone.utc)),
)

# Envelope valido
env_ok = EnvelopeIA(
    mensagem_cliente="Oi, quero pneu para CG 160",
    etapa_atual=EtapaFluxo.identificacao,
    intencao_atual="compra_pneu",
    acoes_sugeridas=["pedir_clarificacao_moto"],
    confianca=Confianca.alta,
)
erros = validar_envelope(env_ok, ctx_teste)
registrar("VALIDADOR", "envelope valido = 0 erros", len(erros) == 0, f"erros: {erros}" if erros else "")

# Acao invalida
env_acao_ruim = EnvelopeIA(
    mensagem_cliente="Vou converter",
    etapa_atual=EtapaFluxo.identificacao,
    intencao_atual="compra_pneu",
    acoes_sugeridas=["converter_em_pedido"],  # so na etapa fechamento
    confianca=Confianca.alta,
)
erros = validar_envelope(env_acao_ruim, ctx_teste)
registrar("VALIDADOR", "acao converter_em_pedido na identificacao = erro", len(erros) > 0)

# Transicao invalida
env_transicao_ruim = EnvelopeIA(
    mensagem_cliente="Pulando para fechamento",
    etapa_atual=EtapaFluxo.fechamento,  # pula de identificacao -> fechamento
    intencao_atual="compra_pneu",
    acoes_sugeridas=["pedir_clarificacao_moto"],
    confianca=Confianca.alta,
)
erros = validar_envelope(env_transicao_ruim, ctx_teste)
registrar("VALIDADOR", "transicao identificacao->fechamento = erro", len(erros) > 0)

# Fato inferido sem justificativa
env_sem_justif = EnvelopeIA(
    mensagem_cliente="Teste",
    etapa_atual=EtapaFluxo.identificacao,
    intencao_atual="test",
    acoes_sugeridas=["registrar_fato_observado"],
    confianca=Confianca.media,
    fatos_inferidos=[FatoInferido(chave="teste", valor="x", justificativa="")],
)
erros = validar_envelope(env_sem_justif, ctx_teste)
registrar("VALIDADOR", "fato inferido sem justificativa = erro", len(erros) > 0)

# Mensagem vazia
env_msg_vazia = EnvelopeIA(
    mensagem_cliente="",
    etapa_atual=EtapaFluxo.identificacao,
    intencao_atual="test",
    acoes_sugeridas=["registrar_fato_observado"],
    confianca=Confianca.media,
)
erros = validar_envelope(env_msg_vazia, ctx_teste)
registrar("VALIDADOR", "mensagem_cliente vazia = erro", len(erros) > 0)

# ============================================================
# GRUPO 8: CONEXAO SUPABASE
# ============================================================
print("\n" + "=" * 60)
print("GRUPO 8: CONEXAO SUPABASE")
print("=" * 60)

try:
    from agente_2w.db.client import supabase
    registrar("SUPABASE", "Client criado com sucesso", True)
except Exception as e:
    registrar("SUPABASE", "Client criado", False, str(e))

# Teste de leitura em cada tabela
tabelas = [
    "sessao_chat", "mensagem_chat", "contexto_conversa",
    "item_provisorio", "cliente", "pedido", "item_pedido",
    "pneu", "moto", "medida_moto", "estoque",
]
for tabela in tabelas:
    try:
        resultado = supabase.table(tabela).select("id", count="exact").limit(1).execute()
        count = resultado.count if resultado.count is not None else 0
        registrar("SUPABASE", f"SELECT {tabela} ({count} registros)", True)
    except Exception as e:
        registrar("SUPABASE", f"SELECT {tabela}", False, str(e))

# Teste das views
views = ["catalogo_agente", "compatibilidade_moto_pneu"]
for view in views:
    try:
        resultado = supabase.table(view).select("*").limit(1).execute()
        registrar("SUPABASE", f"VIEW {view} acessivel ({len(resultado.data)} rows)", True)
    except Exception as e:
        registrar("SUPABASE", f"VIEW {view}", False, str(e))

# ============================================================
# GRUPO 9: REPOS LEITURA REAL (Fase 2 com Supabase)
# ============================================================
print("\n" + "=" * 60)
print("GRUPO 9: REPOS LEITURA REAL")
print("=" * 60)

from agente_2w.db import queries, catalogo_repo, cliente_repo, sessao_repo

# queries.contar_registros
try:
    n = queries.contar_registros("pneu")
    registrar("REPO", f"queries.contar_registros('pneu') = {n}", n >= 0)
except Exception as e:
    registrar("REPO", "queries.contar_registros", False, str(e))

# catalogo_repo.buscar_pneus_por_dimensoes
try:
    res = catalogo_repo.buscar_pneus_por_dimensoes(aro=17)
    registrar("REPO", f"catalogo_repo.buscar_pneus_por_dimensoes(aro=17) = {len(res)} resultados", True)
except Exception as e:
    registrar("REPO", "catalogo_repo.buscar_pneus_por_dimensoes", False, str(e))

# catalogo_repo.buscar_pneus_por_medida_texto
try:
    res = catalogo_repo.buscar_pneus_por_medida_texto("100/80")
    registrar("REPO", f"catalogo_repo.buscar_pneus_por_medida_texto('100/80') = {len(res)} resultados", True)
except Exception as e:
    registrar("REPO", "catalogo_repo.buscar_pneus_por_medida_texto", False, str(e))

# sessao_repo.buscar_sessao_por_id (dummy)
try:
    fake_id = uuid4()
    res = sessao_repo.buscar_sessao_por_id(fake_id)
    registrar("REPO", "sessao_repo.buscar_sessao_por_id(fake) = None", res is None)
except Exception as e:
    registrar("REPO", "sessao_repo.buscar_sessao_por_id(fake)", False, str(e))

# cliente_repo.buscar_cliente_por_telefone
try:
    res = cliente_repo.buscar_cliente_por_telefone("0000000000")
    registrar("REPO", "cliente_repo.buscar_cliente_por_telefone('0000') = None", res is None)
except Exception as e:
    registrar("REPO", "cliente_repo.buscar_cliente_por_telefone", False, str(e))

# ============================================================
# GRUPO 10: TESTE DE INTEGRACAO (criar sessao -> montar contexto)
# ============================================================
print("\n" + "=" * 60)
print("GRUPO 10: INTEGRACAO (Sessao + Contexto)")
print("=" * 60)

from agente_2w.db import sessao_repo, mensagem_repo, contexto_repo
from agente_2w.engine.montador_contexto import montar_contexto

sessao_teste = None
try:
    # Criar sessao
    sessao_teste = sessao_repo.criar_sessao(SessaoChatCreate(
        canal="whatsapp_teste",
        contato_externo="5511999999999",
        etapa_atual=EtapaFluxo.identificacao,
        status_sessao=StatusSessao.ativa,
    ))
    registrar("INTEGRACAO", f"Sessao criada id={sessao_teste.id}", True)
except Exception as e:
    registrar("INTEGRACAO", "Criar sessao", False, traceback.format_exc())

if sessao_teste:
    # Criar mensagem
    try:
        msg = mensagem_repo.criar_mensagem(MensagemChatCreate(
            sessao_chat_id=sessao_teste.id,
            direcao=Direcao.entrada,
            remetente=Remetente.cliente,
            conteudo_texto="Oi, quero um pneu para CG 160",
            criado_em=datetime.now(timezone.utc),
        ))
        registrar("INTEGRACAO", f"Mensagem criada id={msg.id}", True)
    except Exception as e:
        registrar("INTEGRACAO", "Criar mensagem", False, traceback.format_exc())
        msg = None

    # Criar fato
    try:
        fato = contexto_repo.registrar_fato(ContextoConversaCreate(
            sessao_chat_id=sessao_teste.id,
            chave="moto_modelo_informado",
            tipo_de_verdade=TipoDeVerdade.observado,
            nivel_confirmacao=NivelConfirmacao.nenhum,
            fonte=OrigemContexto.mensagem_cliente,
            valor_texto="CG 160",
            mensagem_chat_id=msg.id if msg else uuid4(),
        ))
        registrar("INTEGRACAO", f"Fato criado id={fato.id}", True)
    except Exception as e:
        registrar("INTEGRACAO", "Criar fato", False, traceback.format_exc())

    # Montar contexto
    try:
        ctx = montar_contexto(sessao_teste.id)
        registrar("INTEGRACAO", "montar_contexto executou OK", True)
        registrar("INTEGRACAO", f"  sessao.etapa_atual = {ctx.sessao.etapa_atual.value}", ctx.sessao.etapa_atual == EtapaFluxo.identificacao)
        registrar("INTEGRACAO", f"  mensagens_recentes = {len(ctx.mensagens_recentes)}", len(ctx.mensagens_recentes) >= 1)
        registrar("INTEGRACAO", f"  fatos_ativos = {len(ctx.fatos_ativos)}", len(ctx.fatos_ativos) >= 1)
        registrar("INTEGRACAO", f"  acoes_permitidas = {len(ctx.acoes_permitidas)} acoes", len(ctx.acoes_permitidas) > 0)
        registrar("INTEGRACAO", f"  pendencias = {len(ctx.pendencias)}", len(ctx.pendencias) >= 1)
    except Exception as e:
        registrar("INTEGRACAO", "montar_contexto", False, traceback.format_exc())

    # Limpar dados de teste
    try:
        supabase.table("contexto_conversa").delete().eq("sessao_chat_id", str(sessao_teste.id)).execute()
        supabase.table("mensagem_chat").delete().eq("sessao_chat_id", str(sessao_teste.id)).execute()
        supabase.table("sessao_chat").delete().eq("id", str(sessao_teste.id)).execute()
        registrar("INTEGRACAO", "Dados de teste limpos", True)
    except Exception as e:
        registrar("INTEGRACAO", "Limpeza dados teste", False, str(e))


# ============================================================
# RELATORIO FINAL
# ============================================================
print("\n" + "=" * 60)
print("RELATORIO FINAL")
print("=" * 60)

total = len(RESULTADOS)
passed = sum(1 for r in RESULTADOS if r["ok"])
failed = sum(1 for r in RESULTADOS if not r["ok"])

print(f"\nTotal: {total} testes")
print(f"  PASS: {passed}")
print(f"  FAIL: {failed}")

if failed > 0:
    print("\n--- FALHAS ---")
    for r in RESULTADOS:
        if not r["ok"]:
            print(f"  ✗ [{r['grupo']}] {r['nome']}")
            if r["detalhe"]:
                print(f"    Detalhe: {r['detalhe']}")

print(f"\nResultado: {'TODOS OS TESTES PASSARAM' if failed == 0 else f'{failed} FALHA(S) ENCONTRADA(S)'}")
