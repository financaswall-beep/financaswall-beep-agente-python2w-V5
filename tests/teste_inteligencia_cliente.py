"""
Teste das novas features de inteligencia de negocio do cliente.
Nao chama a IA — testa schema, banco e logica de segmento diretamente.
"""

import sys
from decimal import Decimal
from uuid import uuid4

sys.path.insert(0, ".")

PASS = 0
FAIL = 0


def ok(nome, detalhe=""):
    global PASS
    PASS += 1
    print(f"  [OK] {nome}" + (f"  -> {detalhe}" if detalhe else ""))


def fail(nome, detalhe=""):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {nome}" + (f"  -> {detalhe}" if detalhe else ""))


def safe(nome, fn):
    try:
        r = fn()
        ok(nome, str(r) if r is not None else "")
        return r
    except Exception as e:
        fail(nome, f"{type(e).__name__}: {e}")
        return None


SEP = "=" * 60

# ────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  INTELIGENCIA DE NEGOCIO - CLIENTE")
print(SEP)

# ──── 1. Imports ────────────────────────────────────────────────
print("\n--- 1. Imports ---")

safe("constantes MUNICIPIO/BAIRRO", lambda: (
    __import__("agente_2w.constantes", fromlist=["ChaveContexto"]).ChaveContexto.MUNICIPIO
))
safe("schema Cliente novos campos", lambda: (
    __import__("agente_2w.schemas.cliente", fromlist=["Cliente"]).Cliente
))
safe("ClienteContexto novos campos", lambda: (
    __import__("agente_2w.schemas.contexto_executavel", fromlist=["ClienteContexto"]).ClienteContexto
))
safe("_calcular_segmento import", lambda: (
    __import__("agente_2w.engine.promotor", fromlist=["_calcular_segmento"])._calcular_segmento
))
safe("_atualizar_stats_cliente import", lambda: (
    __import__("agente_2w.engine.promotor", fromlist=["_atualizar_stats_cliente"])._atualizar_stats_cliente
))
safe("_atualizar_localidade_cliente import", lambda: (
    __import__("agente_2w.engine.orquestrador", fromlist=["_atualizar_localidade_cliente"])._atualizar_localidade_cliente
))

# ──── 2. Logica de segmento ──────────────────────────────────────
print("\n--- 2. Logica de segmento ---")

from agente_2w.engine.promotor import _calcular_segmento

testes_segmento = [
    (0,  Decimal("0"),   "novo"),
    (1,  Decimal("100"), "recorrente"),
    (4,  Decimal("499"), "recorrente"),
    (5,  Decimal("100"), "vip"),
    (2,  Decimal("500"), "vip"),
    (10, Decimal("999"), "vip"),
]

for pedidos, valor, esperado in testes_segmento:
    resultado = _calcular_segmento(pedidos, valor)
    if resultado == esperado:
        ok(f"segmento({pedidos} pedidos, R${valor})", f"= {resultado}")
    else:
        fail(f"segmento({pedidos} pedidos, R${valor})", f"esperado={esperado} obtido={resultado}")

# ──── 3. Schema — novos campos ───────────────────────────────────
print("\n--- 3. Schema Cliente ---")

from agente_2w.schemas.cliente import ClienteCreate, Cliente
from datetime import datetime, timezone

def testar_schema_create():
    c = ClienteCreate(
        telefone="21999990000",
        nome="Teste",
        municipio="Duque de Caxias",
        bairro="Centro",
    )
    assert c.municipio == "Duque de Caxias"
    assert c.bairro == "Centro"
    return "municipio e bairro OK"

safe("ClienteCreate com municipio/bairro", testar_schema_create)

def testar_schema_cliente():
    from agente_2w.schemas.cliente import Cliente
    import uuid
    agora = datetime.now(timezone.utc)
    c = Cliente(
        id=uuid.uuid4(),
        telefone="21999990000",
        segmento="recorrente",
        total_pedidos=2,
        valor_total_gasto=Decimal("499.80"),
        ultima_compra_em=agora,
        municipio="Niteroi",
        bairro="Icarai",
        criado_em=agora,
        atualizado_em=agora,
    )
    assert c.segmento == "recorrente"
    assert c.total_pedidos == 2
    assert c.municipio == "Niteroi"
    return f"segmento={c.segmento}, total={c.total_pedidos}, municipio={c.municipio}"

safe("Cliente com todos os novos campos", testar_schema_cliente)

# ──── 4. ClienteContexto ────────────────────────────────────────
print("\n--- 4. ClienteContexto ---")

from agente_2w.schemas.contexto_executavel import ClienteContexto

def testar_ctx_novo():
    ctx = ClienteContexto()
    assert ctx.segmento is None
    assert ctx.total_pedidos == 0
    assert ctx.municipio is None
    return "defaults OK"

def testar_ctx_preenchido():
    ctx = ClienteContexto(
        cliente_id="abc-123",
        nome="João Silva",
        resolvido=True,
        segmento="vip",
        total_pedidos=7,
        valor_total_gasto=Decimal("1299.50"),
        municipio="Rio de Janeiro",
        bairro="Tijuca",
    )
    assert ctx.segmento == "vip"
    assert ctx.total_pedidos == 7
    assert ctx.bairro == "Tijuca"
    return f"segmento={ctx.segmento}, pedidos={ctx.total_pedidos}, bairro={ctx.bairro}"

safe("ClienteContexto defaults", testar_ctx_novo)
safe("ClienteContexto preenchido", testar_ctx_preenchido)

# ──── 5. Banco — criar/atualizar/ler cliente com novos campos ───
print("\n--- 5. Banco (Supabase) ---")

from agente_2w.db import cliente_repo
from agente_2w.schemas.cliente import ClienteCreate

TELEFONE_TESTE = f"test_{uuid4().hex[:8]}"

def criar_cliente_teste():
    c = cliente_repo.criar_cliente(ClienteCreate(
        telefone=TELEFONE_TESTE,
        nome="Cliente Teste BI",
        municipio="Petrópolis",
        bairro="Quitandinha",
    ))
    assert c.municipio == "Petrópolis"
    assert c.bairro == "Quitandinha"
    assert c.segmento == "novo"
    assert c.total_pedidos == 0
    assert c.valor_total_gasto == Decimal("0")
    assert c.ultima_compra_em is None
    return f"id={c.id}, segmento={c.segmento}"

cliente_criado = safe("criar cliente com municipio/bairro", criar_cliente_teste)

# Buscar o cliente criado para usar nos proximos testes
_cliente_db = cliente_repo.buscar_cliente_por_telefone(TELEFONE_TESTE)

def atualizar_stats_direto():
    assert _cliente_db is not None, "cliente nao encontrado"
    from agente_2w.engine.promotor import _atualizar_stats_cliente
    _atualizar_stats_cliente(_cliente_db.id, Decimal("259.90"))
    # Re-buscar e verificar
    atualizado = cliente_repo.buscar_cliente_por_id(_cliente_db.id)
    assert atualizado.total_pedidos == 1
    assert atualizado.valor_total_gasto == Decimal("259.90")
    assert atualizado.segmento == "recorrente"
    assert atualizado.ultima_compra_em is not None
    return f"total_pedidos={atualizado.total_pedidos}, segmento={atualizado.segmento}, valor={atualizado.valor_total_gasto}"

safe("_atualizar_stats_cliente (1o pedido -> recorrente)", atualizar_stats_direto)

def segundo_pedido_vip():
    c = cliente_repo.buscar_cliente_por_id(_cliente_db.id)
    from agente_2w.engine.promotor import _atualizar_stats_cliente
    # Simula mais 4 pedidos para chegar a vip
    for _ in range(4):
        _atualizar_stats_cliente(c.id, Decimal("100"))
    final = cliente_repo.buscar_cliente_por_id(c.id)
    assert final.total_pedidos == 5
    assert final.segmento == "vip"
    return f"total_pedidos={final.total_pedidos}, segmento={final.segmento}, valor_total=R${final.valor_total_gasto}"

safe("apos 5 pedidos → segmento vip", segundo_pedido_vip)

def ler_localidade():
    c = cliente_repo.buscar_cliente_por_id(_cliente_db.id)
    assert c.municipio == "Petrópolis"
    assert c.bairro == "Quitandinha"
    return f"municipio={c.municipio}, bairro={c.bairro}"

safe("localidade persiste apos updates de stats", ler_localidade)

# ──── 6. montador_contexto carrega novos campos ─────────────────
print("\n--- 6. Contexto executavel com dados de cliente ---")

from agente_2w.db import sessao_repo
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.enums.enums import EtapaFluxo, StatusSessao
from agente_2w.engine.montador_contexto import montar_contexto

def testar_montador():
    assert _cliente_db is not None
    # Criar sessao e vincular ao cliente
    sessao = sessao_repo.criar_sessao(SessaoChatCreate(
        canal="test",
        contato_externo=TELEFONE_TESTE,
        etapa_atual=EtapaFluxo.identificacao,
        status_sessao=StatusSessao.ativa,
    ))
    sessao_repo.vincular_cliente(sessao.id, _cliente_db.id)

    ctx = montar_contexto(sessao.id)
    assert ctx.cliente.resolvido is True
    assert ctx.cliente.segmento == "vip"
    assert ctx.cliente.total_pedidos == 5
    assert ctx.cliente.municipio == "Petrópolis"
    assert ctx.cliente.bairro == "Quitandinha"
    return (
        f"segmento={ctx.cliente.segmento}, "
        f"pedidos={ctx.cliente.total_pedidos}, "
        f"municipio={ctx.cliente.municipio}"
    )

safe("montador_contexto carrega campos de BI no ClienteContexto", testar_montador)

# ──── Resultado final ────────────────────────────────────────────
print(f"\n{SEP}")
total = PASS + FAIL
print(f"  RESULTADO: {PASS}/{total} PASS")
if FAIL:
    print(f"  FALHAS: {FAIL}")
    sys.exit(1)
else:
    print("  Inteligencia de negocio do cliente funcionando!")
    sys.exit(0)
