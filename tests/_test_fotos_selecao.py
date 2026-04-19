"""
Testa o cenário exato do bug: cliente selecionou pneu e pede foto.
Antes da correção: foto não era enviada (pneus_encontrados stale).
Após a correção: vai direto ao banco por pneu_id selecionado.
"""
import os, sys, uuid
from uuid import UUID

_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(_env):
    with open(_env) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agente_2w.db import sessao_repo
from agente_2w.db import item_provisorio_repo
from agente_2w.enums.enums import EtapaFluxo, StatusSessao
from agente_2w.schemas.item_provisorio import ItemProvisorioCreate
from agente_2w.enums.enums import StatusItemProvisorio
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.engine.orquestrador._nucleo import processar_turno

# pneu_id real do bug report (Pirelli Diablo Rosso dianteiro)
PNEU_ID_BUG = UUID("1423239d-4bb7-4afe-b466-b2d164d7f5ea")

CONTATO = f"5521SEL{uuid.uuid4().hex[:6]}"

print("=" * 60)
print("TESTE: foto com item selecionado (cenário do bug)")
print("=" * 60)

sessao = sessao_repo.criar_sessao(SessaoChatCreate(
    canal="teste_selecao",
    contato_externo=CONTATO,
    etapa_atual=EtapaFluxo.oferta,
    status_sessao=StatusSessao.ativa,
))

try:
    # Inserir item selecionado diretamente (simula cliente já ter escolhido)
    item_provisorio_repo.criar_item(ItemProvisorioCreate(
        sessao_chat_id=sessao.id,
        pneu_id=PNEU_ID_BUG,
        posicao="dianteiro",
        quantidade=1,
        preco_unitario=299.90,
        status_item=StatusItemProvisorio.selecionado_cliente,
    ))
    print(f"  Item selecionado criado: pneu_id={PNEU_ID_BUG}")
    print(f"  Sessao: {sessao.id}")
    print()

    # Cenário 1: pede foto SEM pneus_encontrados no contexto (bug original)
    print("[Turno 1] Cliente pede foto — contexto SEM pneus_encontrados")
    print("  Você: Tem foto dele aí?")
    r = processar_turno(sessao.id, "Tem foto dele aí?")
    print(f"  Agente: {r.texto}")
    if r.fotos:
        print(f"  >>> FOTOS ({len(r.fotos)}) — CORREÇÃO FUNCIONOU:")
        for u in r.fotos:
            print(f"        {u}")
        resultado1 = "PASS"
    else:
        print("  >>> SEM FOTOS — bug ainda presente!")
        resultado1 = "FAIL"

    print()

    # Cenário 2: pede vídeo
    print("[Turno 2] Cliente pede vídeo")
    print("  Você: Tem vídeo?")
    r2 = processar_turno(sessao.id, "Tem vídeo?")
    print(f"  Agente: {r2.texto}")
    if r2.videos:
        print(f"  >>> VÍDEOS ({len(r2.videos)}):")
        for u in r2.videos:
            print(f"        {u}")
        resultado2 = "PASS (tem vídeo)"
    else:
        print("  >>> Sem vídeo cadastrado para este pneu (pode ser normal)")
        resultado2 = "OK (sem vídeo no banco)"

    print()
    print("=" * 60)
    print(f"  Fotos com seleção : {resultado1}")
    print(f"  Vídeo com seleção : {resultado2}")
    print("=" * 60)

finally:
    sessao_repo.fechar_sessao(sessao.id)
    print(f"\nSessao {sessao.id} encerrada.")
