"""Teste do follow-up automatico de frete.

Simula o cenario: cliente informa apenas o bairro ("jardim primavera"),
o backend resolve via web_search, e o agente deve responder JA COM O FRETE
na mesma mensagem — sem o cliente precisar digitar mais nada.

Tambem testa o caso "frete nao coberto" (municipio sem cobertura).
"""
import logging
import sys
from uuid import UUID

from agente_2w.db import sessao_repo, cliente_repo, contexto_repo, item_provisorio_repo
from agente_2w.enums.enums import (
    EtapaFluxo, StatusSessao, TipoDeVerdade, NivelConfirmacao, OrigemContexto,
    StatusItemProvisorio,
)
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.schemas.contexto_conversa import ContextoConversaCreate
from agente_2w.schemas.item_provisorio import ItemProvisorioCreate
from agente_2w.constantes import ChaveContexto
from agente_2w.engine.orquestrador import processar_turno

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Silencia logs verbosos de HTTP
logging.getLogger("httpx").setLevel(logging.WARNING)

CONTATO = "5521900000099"


def _criar_sessao_em_entrega_pagamento() -> UUID:
    """Cria sessao ja em entrega_pagamento com um item validado."""
    sessao = sessao_repo.criar_sessao(SessaoChatCreate(
        canal="teste",
        contato_externo=CONTATO,
        etapa_atual=EtapaFluxo.entrega_pagamento,
        status_sessao=StatusSessao.ativa,
    ))

    # Vincular/criar cliente
    cliente = cliente_repo.resolver_ou_criar_cliente(CONTATO)
    sessao_repo.vincular_cliente(sessao.id, cliente.id)

    # Fato: tipo_entrega = entrega (para nao pular o calculo de frete)
    contexto_repo.registrar_fato(ContextoConversaCreate(
        sessao_chat_id=sessao.id,
        chave=ChaveContexto.TIPO_ENTREGA,
        valor_texto="entrega",
        valor_json=None,
        tipo_de_verdade=TipoDeVerdade.confirmado_cliente,
        nivel_confirmacao=NivelConfirmacao.confirmado_cliente,
        fonte=OrigemContexto.backend,
    ))

    # Item provisorio validado (pneu XRE traseiro — ID real do catalogo)
    try:
        item_provisorio_repo.criar_item(ItemProvisorioCreate(
            sessao_chat_id=sessao.id,
            status_item=StatusItemProvisorio.validado,
            pneu_id=UUID("78515ece-e874-434e-b615-9efd124b64f5"),
            posicao="traseiro",
            quantidade=1,
            preco_unitario_sugerido=309.90,
        ))
    except Exception as e:
        print(f"  [AVISO] Nao foi possivel criar item (pneu_id pode nao existir): {e}")

    return sessao.id


def turno(sessao_id: UUID, msg: str) -> str:
    print(f"\n>>> Cliente: {msg}")
    resp = processar_turno(sessao_id, msg)
    sessao = sessao_repo.buscar_sessao_por_id(sessao_id)
    frete_fato = contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.FRETE_VALOR)
    nao_coberto = contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.FRETE_NAO_COBERTO)
    frete_info = (
        f"frete=R${frete_fato.valor_texto}" if frete_fato
        else (f"nao_coberto={nao_coberto.valor_texto}" if nao_coberto else "frete=?")
    )
    print(f"<<< Agente:  {resp}")
    print(f"    [etapa={sessao.etapa_atual.value} | {frete_info}]")
    return resp


def avaliar(nome: str, resposta: str, deve_conter: list[str], nao_deve_conter: list[str] = None):
    ok = all(t.lower() in resposta.lower() for t in deve_conter)
    nok = nao_deve_conter and any(t.lower() in resposta.lower() for t in nao_deve_conter)
    status = "OK" if (ok and not nok) else "FALHOU"
    print(f"  [{status}] {nome}")
    if not ok:
        print(f"         Esperava conter: {deve_conter}")
    if nok:
        print(f"         Nao deveria conter: {nao_deve_conter}")
    return status == "OK"


def main():
    resultados = []

    # ----------------------------------------------------------------
    # CENARIO A: bairro que resolve via web_search (Jardim Primavera → Duque de Caxias)
    # ----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("CENARIO A: bairro resolvido via web_search (Jardim Primavera)")
    print("=" * 60)
    sid_a = _criar_sessao_em_entrega_pagamento()
    print(f"  Sessao: {sid_a}")

    r_a = turno(sid_a, "cara eu sou de jardim primavera")

    ok_a = avaliar(
        "Resposta ja com frete — sem 'verificar'",
        r_a,
        deve_conter=["24", "90"],          # valor do frete Duque de Caxias
        nao_deve_conter=["verificar", "aguarde"],
    )
    resultados.append(("A: bairro web_search", ok_a))

    # ----------------------------------------------------------------
    # CENARIO B: municipio direto na tabela (Niteroi)
    # ----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("CENARIO B: municipio direto na tabela (Niteroi)")
    print("=" * 60)
    sid_b = _criar_sessao_em_entrega_pagamento()
    print(f"  Sessao: {sid_b}")

    r_b = turno(sid_b, "entrego em niteroi")

    ok_b = avaliar(
        "Resposta imediata com frete Niteroi",
        r_b,
        deve_conter=["9", "90"],  # frete Niteroi = R$9,90
        nao_deve_conter=["verificar", "aguarde"],
    )
    resultados.append(("B: municipio na tabela", ok_b))

    # ----------------------------------------------------------------
    # CENARIO C: municipio sem cobertura
    # ----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("CENARIO C: municipio sem cobertura (Petropolis)")
    print("=" * 60)
    sid_c = _criar_sessao_em_entrega_pagamento()
    print(f"  Sessao: {sid_c}")

    r_c = turno(sid_c, "sou de petropolis")

    ok_c = avaliar(
        "Resposta informando nao cobertura",
        r_c,
        deve_conter=["retirar", "loja"],       # sugere retirada
        nao_deve_conter=["verificar", "aguarde"],
    )
    resultados.append(("C: municipio sem cobertura", ok_c))

    # ----------------------------------------------------------------
    # RESULTADO FINAL
    # ----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("RESULTADO FINAL:")
    todos_ok = True
    for nome, ok in resultados:
        print(f"  {'OK  ' if ok else 'FALH'} {nome}")
        if not ok:
            todos_ok = False
    print("=" * 60)
    sys.exit(0 if todos_ok else 1)


if __name__ == "__main__":
    main()
