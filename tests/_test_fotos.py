"""Testa se o agente retorna fotos/videos ao ser perguntado."""
import os, sys, uuid

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
from agente_2w.enums.enums import EtapaFluxo, StatusSessao
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.engine.orquestrador._nucleo import processar_turno

CONTATO = f"5521FOTO{uuid.uuid4().hex[:6]}"

sessao = sessao_repo.criar_sessao(SessaoChatCreate(
    canal="teste_foto",
    contato_externo=CONTATO,
    etapa_atual=EtapaFluxo.identificacao,
    status_sessao=StatusSessao.ativa,
))

TURNOS = [
    "Oi",
    "Quero ver foto do Pirelli Diablo Rosso 120/70-17",
]

print("=" * 60)
print(f"TESTE FOTOS — sessao: {sessao.id}")
print("=" * 60)

try:
    for msg in TURNOS:
        print(f"\nVoce: {msg}")
        r = processar_turno(sessao.id, msg)
        print(f"Agente: {r.texto}")
        if r.fotos:
            print(f"  >>> FOTOS ({len(r.fotos)}):")
            for u in r.fotos:
                print(f"      {u}")
        if r.videos:
            print(f"  >>> VIDEOS ({len(r.videos)}):")
            for u in r.videos:
                print(f"      {u}")
        print("-" * 40)
finally:
    sessao_repo.fechar_sessao(sessao.id)
    print(f"\nSessao {sessao.id} encerrada.")
