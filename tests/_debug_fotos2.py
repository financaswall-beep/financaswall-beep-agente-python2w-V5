"""Debug profundo: patcha processar_turno para logar pneus_encontrados antes de fotos."""
import os, sys, uuid, logging

_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(_env):
    with open(_env) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")

from agente_2w.db import sessao_repo
from agente_2w.enums.enums import EtapaFluxo, StatusSessao
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.engine.orquestrador._nucleo import processar_turno, _cliente_pediu_foto

contato = f"5521D{uuid.uuid4().hex[:8]}"
sessao = sessao_repo.criar_sessao(SessaoChatCreate(
    canal="teste_debug",
    contato_externo=contato,
    etapa_atual=EtapaFluxo.identificacao,
    status_sessao=StatusSessao.ativa,
))

try:
    print("=== Turno 1: Oi ===")
    r1 = processar_turno(sessao.id, "oi")
    print(f"Agente: {r1.texto[:80]}")
    
    print("\n=== Turno 2: Pedir foto Pirelli 180/55-17 ===")
    msg = "tem foto do pirelli diablo rosso 180/55-17?"
    print(f"pediu_foto={_cliente_pediu_foto(msg)}")
    r2 = processar_turno(sessao.id, msg)
    print(f"Agente: {r2.texto[:120]}")
    print(f"Fotos: {r2.fotos}")
    print(f"Videos: {r2.videos}")
finally:
    sessao_repo.fechar_sessao(sessao.id)
