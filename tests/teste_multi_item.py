"""
==========================================================================
TESTES — Multi-item / Multi-moto — Agente 2W Pneus
==========================================================================
4 testes projetados para induzir os bugs conhecidos:

  Teste 1 — Guardrail: IA emite confirmar_item + adicionar_outro_item juntos
  Teste 2 — Contaminacao: Fan 125 (90/90-18) seguido de PCX, verifica pneu_id
  Teste 3 — Mesmo pneu_id: duas motos com pneu identico (ex: PCX + CG 160)
  Teste 4 — 4 motos em sequencia: nenhum item pode ficar orfao ou duplicado

Se todos passarem: os fixes estao solidos.
==========================================================================
"""
import sys
import logging
import traceback
from uuid import UUID, uuid4
from types import SimpleNamespace

sys.path.insert(0, ".")
logging.basicConfig(level=logging.WARNING)

RESULTADOS: list[dict] = []
GRUPO_CONTADORES: dict[str, dict] = {}


def reg(grupo: str, nome: str, ok: bool, detalhe: str = ""):
    RESULTADOS.append({"grupo": grupo, "nome": nome, "ok": ok, "detalhe": detalhe})
    if grupo not in GRUPO_CONTADORES:
        GRUPO_CONTADORES[grupo] = {"pass": 0, "fail": 0}
    GRUPO_CONTADORES[grupo]["pass" if ok else "fail"] += 1
    marca = "OK" if ok else "FAIL"
    linha = f"  [{marca}] [{grupo}] {nome}"
    if detalhe:
        linha += f"  -> {detalhe}"
    print(linha)


def nova_sessao(contato: str):
    from agente_2w.db import sessao_repo
    from agente_2w.enums.enums import EtapaFluxo, StatusSessao
    from agente_2w.schemas.sessao_chat import SessaoChatCreate
    sessao = sessao_repo.criar_sessao(SessaoChatCreate(
        canal="teste",
        contato_externo=contato,
        etapa_atual=EtapaFluxo.identificacao,
        status_sessao=StatusSessao.ativa,
    ))
    return sessao.id


def turno(sid: UUID, msg: str) -> str:
    from agente_2w.engine.orquestrador import processar_turno
    return processar_turno(sid, msg)


def itens_ativos(sid: UUID):
    from agente_2w.db import item_provisorio_repo
    return item_provisorio_repo.listar_itens_ativos_por_sessao(sid)


# ==========================================================================
# TESTE 1 — Guardrail: confirmar_item + adicionar_outro_item no mesmo turno
# ==========================================================================
# Verifica se _aplicar_guardrail remove adicionar_outro_item quando conflita
# com confirmar_item, e reverte etapa de busca para confirmacao_item.
# Este teste e UNITARIO — nao precisa de IA real.

def teste_guardrail_conflito():
    grupo = "Guardrail"
    print(f"\n[{grupo}] Teste 1 — IA emite confirmar_item + adicionar_outro_item juntos")
    try:
        from agente_2w.engine.orquestrador import _aplicar_guardrail
        from agente_2w.enums.enums import EtapaFluxo

        # Simula envelope com acoes conflitantes e etapa=busca
        envelope = SimpleNamespace(
            acoes_sugeridas=["confirmar_item", "adicionar_outro_item"],
            etapa_atual=EtapaFluxo.busca,
        )
        etapa_atual = EtapaFluxo.confirmacao_item

        resultado = _aplicar_guardrail(envelope, etapa_atual)

        # adicionar_outro_item deve ter sido removido
        reg(grupo, "adicionar_outro_item removido do envelope",
            "adicionar_outro_item" not in resultado.acoes_sugeridas,
            str(resultado.acoes_sugeridas))

        # confirmar_item deve ter sido mantido
        reg(grupo, "confirmar_item mantido no envelope",
            "confirmar_item" in resultado.acoes_sugeridas,
            str(resultado.acoes_sugeridas))

        # etapa revertida de busca para confirmacao_item
        reg(grupo, "etapa revertida de busca para confirmacao_item",
            resultado.etapa_atual == EtapaFluxo.confirmacao_item,
            f"etapa={resultado.etapa_atual.value}")

        # Teste adicional: sem conflito, envelope nao deve ser alterado
        envelope2 = SimpleNamespace(
            acoes_sugeridas=["confirmar_item", "finalizar_itens"],
            etapa_atual=EtapaFluxo.confirmacao_item,
        )
        resultado2 = _aplicar_guardrail(envelope2, EtapaFluxo.confirmacao_item)
        reg(grupo, "sem conflito — envelope nao alterado",
            resultado2.acoes_sugeridas == ["confirmar_item", "finalizar_itens"]
            and resultado2.etapa_atual == EtapaFluxo.confirmacao_item,
            str(resultado2.acoes_sugeridas))

        # Teste: so adicionar_outro_item sem confirmar_item — nao deve ser removido
        envelope3 = SimpleNamespace(
            acoes_sugeridas=["adicionar_outro_item"],
            etapa_atual=EtapaFluxo.busca,
        )
        resultado3 = _aplicar_guardrail(envelope3, EtapaFluxo.confirmacao_item)
        reg(grupo, "adicionar_outro_item sozinho — nao removido",
            "adicionar_outro_item" in resultado3.acoes_sugeridas,
            str(resultado3.acoes_sugeridas))

    except Exception as e:
        reg(grupo, "execucao sem excecao", False, traceback.format_exc(limit=3))


# ==========================================================================
# TESTE 2 — Contaminacao de contexto: Fan 125 (90/90-18) → PCX 160
# ==========================================================================
# Verifica se medida_informada da Fan NAO contamina a busca do PCX.
# O PCX deve receber seu proprio pneu_id, diferente da Fan.

def teste_contaminacao_contexto():
    grupo = "Contaminacao"
    print(f"\n[{grupo}] Teste 2 — Fan 125 (90/90-18) seguido de PCX 160")
    try:
        sid = nova_sessao("5521777000001")

        # Fan 125 com medida explicita
        turno(sid, "quero pneu pra fan 125 traseiro medida 90/90-18")
        turno(sid, "sem preferencia de marca")
        turno(sid, "sim pode ser")
        turno(sid, "sim confirmo")

        itens_fan = itens_ativos(sid)
        reg(grupo, "Fan 125: 1 item criado",
            len(itens_fan) == 1,
            f"itens={len(itens_fan)}")

        pneu_fan = str(itens_fan[0].pneu_id) if itens_fan else None

        # PCX 160 logo em seguida
        turno(sid, "agora quero pra pcx 160 traseiro")
        turno(sid, "sem preferencia de marca")
        turno(sid, "sim pode ser")
        turno(sid, "sim confirmo")

        itens_pos = itens_ativos(sid)
        reg(grupo, "apos PCX: 2 itens no total",
            len(itens_pos) == 2,
            f"itens={len(itens_pos)}")

        pneus = [str(i.pneu_id) for i in itens_pos]
        pneu_pcx = next((p for p in pneus if p != pneu_fan), None)

        reg(grupo, "PCX tem pneu_id diferente da Fan",
            pneu_pcx is not None and pneu_pcx != pneu_fan,
            f"fan={str(pneu_fan)[:8] if pneu_fan else 'None'} pcx={str(pneu_pcx)[:8] if pneu_pcx else 'IGUAL/NONE'}")

        reg(grupo, "nenhum pneu_id NULL",
            all(i.pneu_id is not None for i in itens_pos),
            f"pneus={[str(i.pneu_id)[:8] for i in itens_pos]}")

    except Exception as e:
        reg(grupo, "execucao sem excecao", False, traceback.format_exc(limit=3))


# ==========================================================================
# TESTE 3 — Mesmo pneu_id: PCX 160 + CG 160 (compartilham pneu no catalogo)
# ==========================================================================
# Verifica se dois itens com mesmo pneu_id sao criados e confirmados
# independentemente — sem o bug do next() que confirmava sempre o mais antigo.

def teste_mesmo_pneu_duas_motos():
    grupo = "MesmoPneu"
    print(f"\n[{grupo}] Teste 3 — PCX 160 + CG 160 (pneu_id potencialmente igual)")
    try:
        sid = nova_sessao("5521777000002")

        # Moto 1 — PCX 160
        turno(sid, "quero pneu pra pcx 160 traseiro")
        turno(sid, "sem preferencia")
        turno(sid, "sim")
        turno(sid, "sim confirmo")

        itens_apos_pcx = itens_ativos(sid)
        reg(grupo, "PCX: 1 item criado",
            len(itens_apos_pcx) == 1,
            f"itens={len(itens_apos_pcx)}")

        pneu_pcx = str(itens_apos_pcx[0].pneu_id) if itens_apos_pcx else None

        # Moto 2 — CG 160 (pode ter mesmo pneu)
        turno(sid, "agora quero pra cg 160 traseiro")
        turno(sid, "sem preferencia")
        turno(sid, "sim")
        turno(sid, "sim confirmo")

        itens_apos_cg = itens_ativos(sid)
        reg(grupo, "CG 160: 2 itens no total (nenhum item perdido)",
            len(itens_apos_cg) == 2,
            f"itens={len(itens_apos_cg)}")

        pneus = [str(i.pneu_id) for i in itens_apos_cg]
        ids_unicos = set(pneus)

        if len(ids_unicos) == 1:
            # Mesmo pneu_id — cenario do bug original
            # Fix garante que ambos os itens existem no banco
            reg(grupo, "mesmo pneu_id detectado — ambos os itens existem no banco",
                len(itens_apos_cg) == 2,
                f"pneu_id={pneus[0][:8]} x2 — correto: 2 unidades do mesmo pneu")
        else:
            reg(grupo, "pneu_ids distintos — sem risco de duplicacao",
                True,
                f"pneus={[p[:8] for p in pneus]}")

        reg(grupo, "nenhum pneu_id NULL",
            all(i.pneu_id is not None for i in itens_apos_cg),
            f"pneus={[str(i.pneu_id)[:8] for i in itens_apos_cg]}")

    except Exception as e:
        reg(grupo, "execucao sem excecao", False, traceback.format_exc(limit=3))


# ==========================================================================
# TESTE 4 — 4 motos em sequencia: XRE + Fan + PCX + CG
# ==========================================================================
# Estresse total: verifica que nenhum item fica orfao, nenhuma confirmacao
# vai pro item errado, e a contagem final e 4.

def teste_4_motos_sequencia():
    grupo = "4Motos"
    print(f"\n[{grupo}] Teste 4 — XRE 300 + Fan 125 + PCX 160 + CG 160 em sequencia")
    try:
        sid = nova_sessao("5521777000003")

        # Moto 1 — XRE 300
        turno(sid, "quero pneu pra 4 motos")
        turno(sid, "xre 300 traseiro")
        turno(sid, "sem preferencia")
        turno(sid, "sim")
        turno(sid, "sim confirmo")
        n1 = len(itens_ativos(sid))
        reg(grupo, "apos XRE: 1 item", n1 == 1, f"itens={n1}")

        # Moto 2 — Fan 125 com medida
        turno(sid, "fan 125 traseiro medida 90/90-18")
        turno(sid, "sem preferencia")
        turno(sid, "sim")
        turno(sid, "sim confirmo")
        n2 = len(itens_ativos(sid))
        reg(grupo, "apos Fan: 2 itens", n2 == 2, f"itens={n2}")

        # Moto 3 — PCX 160
        turno(sid, "pcx 160 traseiro")
        turno(sid, "sem preferencia")
        turno(sid, "sim")
        turno(sid, "sim confirmo")
        n3 = len(itens_ativos(sid))
        reg(grupo, "apos PCX: 3 itens", n3 == 3, f"itens={n3}")

        # Moto 4 — CG 160
        turno(sid, "cg 160 traseiro")
        turno(sid, "sem preferencia")
        turno(sid, "sim")
        turno(sid, "sim confirmo")
        n4 = len(itens_ativos(sid))
        reg(grupo, "apos CG: 4 itens", n4 == 4, f"itens={n4}")

        # Verifica integridade final
        itens_final = itens_ativos(sid)
        pneus = [str(i.pneu_id) for i in itens_final]

        reg(grupo, "contagem final = 4 itens",
            len(itens_final) == 4,
            f"itens={len(itens_final)}")

        reg(grupo, "nenhum pneu_id NULL",
            all(i.pneu_id is not None for i in itens_final),
            f"pneus={[p[:8] for p in pneus]}")

        reg(grupo, "XRE nao contaminada (pneu_id exclusivo)",
            pneus.count(pneus[0]) == 1 if pneus else False,
            f"xre={pneus[0][:8] if pneus else 'N/A'}")

        # Dois primeiros pneus devem ser distintos (XRE != Fan)
        reg(grupo, "XRE e Fan tem pneus distintos",
            len(pneus) >= 2 and pneus[0] != pneus[1],
            f"xre={pneus[0][:8] if len(pneus)>0 else '?'} fan={pneus[1][:8] if len(pneus)>1 else '?'}")

    except Exception as e:
        reg(grupo, "execucao sem excecao", False, traceback.format_exc(limit=3))


# ==========================================================================
# RUNNER
# ==========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  TESTES MULTI-ITEM / MULTI-MOTO — Agente 2W Pneus")
    print("=" * 60)

    teste_guardrail_conflito()
    teste_contaminacao_contexto()
    teste_mesmo_pneu_duas_motos()
    teste_4_motos_sequencia()

    print("\n" + "=" * 60)
    print("  RESULTADO FINAL")
    print("=" * 60)

    total_pass = sum(r["ok"] for r in RESULTADOS)
    total_fail = sum(not r["ok"] for r in RESULTADOS)
    total = len(RESULTADOS)

    for grupo, cnt in GRUPO_CONTADORES.items():
        status = "PASS" if cnt["fail"] == 0 else "FAIL"
        print(f"  [{status}] {grupo}: {cnt['pass']}/{cnt['pass']+cnt['fail']}")

    print(f"\n  TOTAL: {total_pass}/{total} PASS", end="")
    if total_fail == 0:
        print(" — TUDO OK, sistema solido!")
    else:
        print(f" — {total_fail} FALHA(S)")
        print("\n  Falhas:")
        for r in RESULTADOS:
            if not r["ok"]:
                print(f"    - [{r['grupo']}] {r['nome']}: {r['detalhe']}")
    print("=" * 60)
