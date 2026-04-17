"""Debug: testa detecção de pedido de foto + pneus encontrados."""
import os, sys, uuid, json

_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(_env):
    with open(_env) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 1) Testar regex de pediu_foto
from agente_2w.engine.orquestrador._nucleo import _cliente_pediu_foto, _cliente_pediu_video

msgs = [
    "tem foto do pirelli diablo rosso 180/55-17?",
    "manda foto do michelin anakee 170/60-17",
    "quero ver o levorin matrix 90/90-18",
    "tem imagem do bridgestone battlax 180/55-17?",
    "mostra o maggion winner 100/80-18",
]
print("=== Detecção de pedido de foto ===")
for m in msgs:
    print(f"  '{m[:50]}...' → foto={_cliente_pediu_foto(m)}, video={_cliente_pediu_video(m)}")

# 2) Testar o que o fallback retorna
print("\n=== Dados do fallback por dimensão ===")
from agente_2w.db import catalogo_repo
pneus = catalogo_repo.buscar_pneus_por_dimensoes(largura=180, perfil=55, aro=17)
for p in pneus[:2]:
    print(f"  pneu_id={p.get('pneu_id')}")
    print(f"  foto_url={p.get('foto_url')}")
    print(f"  marca={p.get('marca')} pneu_marca={p.get('pneu_marca')}")
    print()

# 3) Testar buscar_foto_frontal
print("=== buscar_foto_frontal / buscar_video ===")
from agente_2w.db.foto_pneu_repo import buscar_foto_frontal, buscar_video
pid = pneus[0]["pneu_id"] if pneus else None
if pid:
    from uuid import UUID
    print(f"  pneu_id: {pid}")
    print(f"  frontal: {buscar_foto_frontal(UUID(pid))}")
    print(f"  video:   {buscar_video(UUID(pid))}")
