"""
Testa o cenario do dialogo real: cliente escolheu Michelin (selecionado),
depois pede 'foto do pirelli' — bot deve mandar foto do Pirelli, nao do Michelin.
Tambem valida Fix B: 1 pneu alvo devolve todas as fotos cadastradas.
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

from agente_2w.db import sessao_repo, item_provisorio_repo, contexto_repo
from agente_2w.enums.enums import (
    EtapaFluxo, StatusSessao, StatusItemProvisorio,
    TipoDeVerdade, NivelConfirmacao, OrigemContexto,
)
from agente_2w.constantes import ChaveContexto
from agente_2w.schemas.item_provisorio import ItemProvisorioCreate
from agente_2w.schemas.contexto_conversa import ContextoConversaCreate
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.engine.orquestrador._nucleo import processar_turno
from agente_2w.db.client import supabase

# Buscar os pneu_ids reais do catalogo (Michelin Pilot + Pirelli City Dragon 80/100-18)
_res = (
    supabase.table("pneu")
    .select("id, marca, modelo")
    .eq("ativo", True)
    .eq("largura", 80).eq("perfil", 100).eq("aro", 18)
    .execute()
)
pneus = {row["marca"].lower() + " " + row["modelo"].lower(): row["id"] for row in _res.data or []}
print("Pneus 80/100-18 no catalogo:")
for k, v in pneus.items():
    print(f"  {k} -> {v}")

michelin_id = next((v for k, v in pneus.items() if "michelin" in k and "pilot" in k), None)
pirelli_id = next((v for k, v in pneus.items() if "pirelli" in k and "city dragon" in k), None)
assert michelin_id and pirelli_id, f"Precisa dos dois pneus no banco. michelin={michelin_id}, pirelli={pirelli_id}"

CONTATO = f"5521MEN{uuid.uuid4().hex[:6]}"
sessao = sessao_repo.criar_sessao(SessaoChatCreate(
    canal="teste_menciona",
    contato_externo=CONTATO,
    etapa_atual=EtapaFluxo.oferta,
    status_sessao=StatusSessao.ativa,
))

try:
    # Simular o estado: pneus encontrados na busca + Michelin selecionado
    contexto_repo.registrar_fato(ContextoConversaCreate(
        sessao_chat_id=sessao.id,
        chave=ChaveContexto.ULTIMOS_PNEUS_ENCONTRADOS,
        tipo_de_verdade=TipoDeVerdade.validado_tool,
        nivel_confirmacao=NivelConfirmacao.validado_tool,
        fonte=OrigemContexto.tool,
        valor_json=[
            {"pneu_id": pirelli_id, "marca": "Pirelli", "modelo": "City Dragon", "medida": "80/100-18", "preco": 79.90},
            {"pneu_id": michelin_id, "marca": "Michelin", "modelo": "Pilot", "medida": "80/100-18", "preco": 79.90},
        ],
    ))
    item_provisorio_repo.criar_item(ItemProvisorioCreate(
        sessao_chat_id=sessao.id,
        pneu_id=UUID(michelin_id),
        posicao="dianteiro",
        quantidade=1,
        preco_unitario=79.90,
        status_item=StatusItemProvisorio.selecionado_cliente,
    ))
    print(f"\nSessao: {sessao.id}")
    print(f"Selecionado: Michelin Pilot ({michelin_id})")
    print(f"Na lista: Pirelli City Dragon ({pirelli_id}) + Michelin Pilot")
    print()

    # TESTE 1: cliente pede foto do pneu selecionado (generico) -> deve mandar TODAS as fotos do Michelin (Fix B)
    print("=" * 60)
    print("[TESTE 1] 'tem foto dele?' (sem marca) -> Michelin (selecionado)")
    print("  Espera: MULTIPLAS fotos do Michelin")
    print("=" * 60)
    r1 = processar_turno(sessao.id, "tem foto dele?")
    print(f"Agente: {r1.texto}")
    print(f"Fotos enviadas: {len(r1.fotos)}")
    for u in r1.fotos:
        print(f"  - {u}")
    teste1_ok = len(r1.fotos) >= 2 and all("michelin" in u.lower() for u in r1.fotos)
    print(f"Resultado: {'PASS' if teste1_ok else 'FAIL'}")
    print()

    # TESTE 2: cliente pede foto do Pirelli -> deve mandar do Pirelli, nao do Michelin (Fix A)
    print("=" * 60)
    print("[TESTE 2] 'manda a foto do pirelli' -> deve enviar PIRELLI (Fix A)")
    print("  Espera: MULTIPLAS fotos do Pirelli (nao Michelin)")
    print("=" * 60)
    r2 = processar_turno(sessao.id, "manda a foto do pirelli")
    print(f"Agente: {r2.texto}")
    print(f"Fotos enviadas: {len(r2.fotos)}")
    for u in r2.fotos:
        print(f"  - {u}")
    teste2_ok = len(r2.fotos) >= 2 and all("pirelli" in u.lower() for u in r2.fotos)
    print(f"Resultado: {'PASS' if teste2_ok else 'FAIL'}")
    print()

    print("=" * 60)
    print(f"  RESULTADO FINAL")
    print(f"  Teste 1 (Fix B — todas fotos 1 pneu)    : {'PASS' if teste1_ok else 'FAIL'}")
    print(f"  Teste 2 (Fix A — mudar alvo por mencao) : {'PASS' if teste2_ok else 'FAIL'}")
    print("=" * 60)

finally:
    sessao_repo.fechar_sessao(sessao.id)
    print(f"\nSessao {sessao.id} encerrada.")
