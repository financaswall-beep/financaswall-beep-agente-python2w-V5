"""Teste completo: conversa com agente pedindo fotos de vários pneus."""
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

TESTES = [
    ("Pirelli Diablo Rosso 180/55-17", "tem foto do pirelli diablo rosso 180/55-17?"),
    ("Michelin Anakee 170/60-17", "manda foto do michelin anakee 170/60-17"),
    ("Levorin Matrix 90/90-18", "quero ver o levorin matrix 90/90-18"),
    ("Bridgestone Battlax 180/55-17", "tem imagem do bridgestone battlax 180/55-17?"),
    ("Maggion Winner 100/80-18", "mostra o maggion winner 100/80-18"),
]

total_ok = 0
total_fail = 0

for nome, msg in TESTES:
    contato = f"5521T{uuid.uuid4().hex[:8]}"
    sessao = sessao_repo.criar_sessao(SessaoChatCreate(
        canal="teste_foto",
        contato_externo=contato,
        etapa_atual=EtapaFluxo.identificacao,
        status_sessao=StatusSessao.ativa,
    ))
    try:
        # turno 1: saudacao
        processar_turno(sessao.id, "oi")
        # turno 2: pedir foto
        r = processar_turno(sessao.id, msg)

        fotos = r.fotos or []
        videos = r.videos or []
        total_midia = len(fotos) + len(videos)

        if total_midia > 0:
            status = "OK"
            total_ok += 1
        else:
            status = "SEM MIDIA"
            total_fail += 1

        print(f"[{status:8}] {nome}")
        print(f"         Texto: {r.texto[:100]}...")
        if fotos:
            print(f"         Fotos ({len(fotos)}):")
            for u in fotos:
                print(f"           {u.split('/fotos/')[1] if '/fotos/' in u else u}")
        if videos:
            print(f"         Videos ({len(videos)}):")
            for u in videos:
                print(f"           {u.split('/fotos/')[1] if '/fotos/' in u else u}")
        print()
    except Exception as e:
        print(f"[ERRO    ] {nome}: {e}\n")
        total_fail += 1
    finally:
        sessao_repo.fechar_sessao(sessao.id)

print("=" * 55)
print(f"Resultado: {total_ok} OK / {total_fail} falhas / {len(TESTES)} total")
