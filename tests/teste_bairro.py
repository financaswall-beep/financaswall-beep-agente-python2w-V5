"""Teste: cliente fala só o bairro, sem o município.

Sub-cenários:
  A) Bairro único/coberto:  "entrega em bangu" → resolve Rio de Janeiro → frete
  B) Bairro ambíguo:       "entrega em santa isabel" → Magé ou São Gonçalo → agent pergunta cidade
  C) Bairro não coberto:   "entrega em petrópolis" → fora da área → agent informa que não cobre

Executa um cenário por vez (arg: A, B ou C). Default: A
"""

import logging
import sys
from uuid import UUID

from agente_2w.db import sessao_repo, contexto_repo, item_provisorio_repo, pedido_repo
from agente_2w.enums.enums import (
    EtapaFluxo, StatusSessao, StatusItemProvisorio,
    TipoDeVerdade, NivelConfirmacao, OrigemContexto,
)
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.schemas.contexto_conversa import ContextoConversaCreate
from agente_2w.schemas.item_provisorio import ItemProvisorioCreate
from agente_2w.constantes import ChaveContexto
from agente_2w.engine.orquestrador import processar_turno

# Mostrar apenas logs relevantes
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("agente_2w.engine.orquestrador.localidade_frete").setLevel(logging.INFO)
logging.getLogger("agente_2w.tools.resolver_bairro").setLevel(logging.INFO)
logging.getLogger("agente_2w.db.area_entrega_repo").setLevel(logging.INFO)

# pneu_id real (Michelin traseiro Fazer — confirmado nos logs anteriores)
PNEU_ID_TRASEIRO = UUID("4a9d3ece-18fd-42aa-98e9-55a7a1d0da0a")

CENARIO = sys.argv[1].upper() if len(sys.argv) > 1 else "A"

MENSAGENS_BAIRRO = {
    "A": ("bangu",          "Bairro único coberto (Rio de Janeiro)"),
    "B": ("santa isabel",   "Bairro ambíguo (Magé ou São Gonçalo)"),
    "C": ("petrópolis",     "Fora da área de cobertura"),
}

if CENARIO not in MENSAGENS_BAIRRO:
    print(f"Cenário inválido. Use A, B ou C.")
    sys.exit(1)

bairro_msg, descricao = MENSAGENS_BAIRRO[CENARIO]
print(f"\n=== CENÁRIO {CENARIO}: {descricao} ===")
print(f"    Bairro testado: '{bairro_msg}'\n")


def fato(sid, chave, valor):
    contexto_repo.registrar_fato(ContextoConversaCreate(
        sessao_chat_id=sid,
        chave=chave,
        valor_texto=valor,
        tipo_de_verdade=TipoDeVerdade.confirmado_cliente,
        nivel_confirmacao=NivelConfirmacao.confirmado_cliente,
        fonte=OrigemContexto.backend,
    ))


def turno(sid, msg, label=""):
    tag = f" [{label}]" if label else ""
    print(f">>> Cliente{tag}: {msg}")
    resp = processar_turno(sid, msg)
    sessao = sessao_repo.buscar_sessao_por_id(sid)
    frete_fato = contexto_repo.buscar_fato_ativo(sid, ChaveContexto.FRETE_VALOR)
    nao_coberto = contexto_repo.buscar_fato_ativo(sid, ChaveContexto.FRETE_NAO_COBERTO)
    ambiguo = contexto_repo.buscar_fato_ativo(sid, ChaveContexto.MUNICIPIO_AMBIGUO)
    frete_info = (
        f"frete=R${frete_fato.valor_texto}" if frete_fato else
        f"nao_coberto={nao_coberto.valor_texto}" if nao_coberto else
        f"ambiguo={ambiguo.valor_texto}" if ambiguo else
        "frete=pendente"
    )
    print(f"<<< Agente:   {resp}")
    print(f"    [etapa={sessao.etapa_atual.value} | {frete_info}]\n")
    return resp


# ── 1. Criar sessão já em entrega_pagamento com um item confirmado ──────────
sessao = sessao_repo.criar_sessao(SessaoChatCreate(
    canal="cli_teste",
    contato_externo=f"5521900000{CENARIO}",
    etapa_atual=EtapaFluxo.entrega_pagamento,
    status_sessao=StatusSessao.ativa,
))
sid = sessao.id
print(f"Sessão: {sid}\n")

# Item provisório já confirmado (simula confirmacao_item completa)
item_provisorio_repo.criar_item(ItemProvisorioCreate(
    sessao_chat_id=sid,
    status_item=StatusItemProvisorio.selecionado_cliente,
    pneu_id=PNEU_ID_TRASEIRO,
    posicao="traseiro",
    quantidade=1,
    preco_unitario_sugerido=469.90,
))

# Fatos já coletados (moto confirmada)
fato(sid, ChaveContexto.MOTO_MODELO, "Fazer 150")
fato(sid, ChaveContexto.POSICAO_PNEU, "traseiro")
fato(sid, ChaveContexto.ITENS_FINALIZADOS, "true")

print("── Setup completo. Iniciando conversa na etapa entrega_pagamento ──\n")

# ── 2. Agente pergunta entrega/pagamento ─────────────────────────────────────
turno(sid, "oi, pode continuar", "warmup")

# ── 3. Cliente fala SÓ o bairro ──────────────────────────────────────────────
turno(sid, f"entrega em {bairro_msg}", "BAIRRO SEM MUNICÍPIO")

# ── 4. Se ambíguo: cliente esclarece cidade ───────────────────────────────────
ambiguo = contexto_repo.buscar_fato_ativo(sid, ChaveContexto.MUNICIPIO_AMBIGUO)
if ambiguo:
    print(">>> [Backend detectou ambiguidade — agent deve perguntar a cidade]")
    turno(sid, "magé", "esclarecimento cidade")

# ── 5. Pagamento ──────────────────────────────────────────────────────────────
frete_ok = contexto_repo.buscar_fato_ativo(sid, ChaveContexto.FRETE_VALOR)
nao_coberto = contexto_repo.buscar_fato_ativo(sid, ChaveContexto.FRETE_NAO_COBERTO)

if frete_ok:
    turno(sid, "rua das acácias 55 apto 201, pix", "endereço + pagamento")
    turno(sid, "sim", "confirma pedido")

# ── 6. Resultado ──────────────────────────────────────────────────────────────
print("="*60)
frete_fato = contexto_repo.buscar_fato_ativo(sid, ChaveContexto.FRETE_VALOR)
nao_coberto = contexto_repo.buscar_fato_ativo(sid, ChaveContexto.FRETE_NAO_COBERTO)
pedido = pedido_repo.buscar_pedido_por_sessao(sid)

print(f"CENÁRIO {CENARIO} — {descricao}")
if frete_fato:
    print(f"  Frete resolvido: R${frete_fato.valor_texto} ✓")
elif nao_coberto:
    print(f"  Não coberto: {nao_coberto.valor_texto} ✓")
else:
    print(f"  Frete ainda pendente (ambiguidade não resolvida)")
print(f"  Pedido: {'#'+str(pedido.numero_pedido) if pedido else 'não criado'}")
