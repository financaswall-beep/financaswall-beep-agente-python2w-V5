"""Teste de stress - simula cenarios problematicos para encontrar bugs.

Cada cenario roda em sessao propria e imprime PASS/FAIL.
Uso: python teste_stress.py [--debug]
"""

import logging
import os
import sys
import time
import traceback

# Forcar UTF-8 no Windows
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
from agente_2w.db import sessao_repo, item_provisorio_repo
from agente_2w.db import pedido_repo
from agente_2w.enums.enums import EtapaFluxo, StatusSessao
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.engine.orquestrador import processar_turno

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def nova_sessao(contato="stress_test"):
    return sessao_repo.criar_sessao(SessaoChatCreate(
        canal="teste_stress",
        contato_externo=contato,
        etapa_atual=EtapaFluxo.identificacao,
        status_sessao=StatusSessao.ativa,
    ))


def etapa_atual(sessao_id):
    s = sessao_repo.buscar_sessao_por_id(sessao_id)
    return s.etapa_atual.value if s else "NOT_FOUND"


def itens_ativos(sessao_id):
    return item_provisorio_repo.listar_itens_ativos_por_sessao(sessao_id)


def pedido_existe(sessao_id):
    try:
        pedido = pedido_repo.buscar_pedido_por_sessao(sessao_id)
        return pedido is not None
    except Exception:
        return False


class Resultado:
    def __init__(self, nome):
        self.nome = nome
        self.passou = False
        self.motivo = ""
        self.respostas = []
        self.etapa_final = ""
        self.tempo = 0

    def __str__(self):
        status = "PASS" if self.passou else "FAIL"
        return f"  [{status}] {self.nome} ({self.tempo:.1f}s) - {self.motivo}"


# ---------------------------------------------------------------------------
# Cenarios de teste
# ---------------------------------------------------------------------------

def teste_mensagem_vazia():
    """Mensagem vazia nao deve crashar."""
    r = Resultado("Mensagem vazia")
    sessao = nova_sessao()
    try:
        resp = processar_turno(sessao.id, "")
        r.respostas.append(resp)
        r.passou = resp is not None and len(resp) > 0
        r.motivo = "Resposta recebida" if r.passou else "Resposta vazia/nula"
    except Exception as e:
        r.motivo = f"CRASH: {e}"
    r.etapa_final = etapa_atual(sessao.id)
    return r


def teste_mensagem_so_emoji():
    """Mensagem com apenas emoji."""
    r = Resultado("So emoji")
    sessao = nova_sessao()
    try:
        resp = processar_turno(sessao.id, "👍")
        r.respostas.append(resp)
        r.passou = resp is not None and len(resp) > 0
        r.motivo = "Resposta recebida" if r.passou else "Resposta vazia/nula"
    except Exception as e:
        r.motivo = f"CRASH: {e}"
    r.etapa_final = etapa_atual(sessao.id)
    return r


def teste_mensagem_gigante():
    """Mensagem com texto enorme (3000 chars)."""
    r = Resultado("Mensagem gigante (3000 chars)")
    sessao = nova_sessao()
    texto = "quero pneu pra minha moto " * 120  # ~3120 chars
    try:
        resp = processar_turno(sessao.id, texto)
        r.respostas.append(resp)
        r.passou = resp is not None and len(resp) > 0
        r.motivo = "Resposta recebida" if r.passou else "Resposta vazia/nula"
    except Exception as e:
        r.motivo = f"CRASH: {e}"
    r.etapa_final = etapa_atual(sessao.id)
    return r


def teste_caracteres_especiais():
    """SQL injection e caracteres estranhos."""
    r = Resultado("Caracteres especiais / SQL injection")
    sessao = nova_sessao()
    texto = "'; DROP TABLE pneus; -- quero pneu 190/50-17 <script>alert('xss')</script>"
    try:
        resp = processar_turno(sessao.id, texto)
        r.respostas.append(resp)
        r.passou = resp is not None and len(resp) > 0
        r.motivo = "Resposta recebida, sem crash" if r.passou else "Resposta vazia/nula"
    except Exception as e:
        r.motivo = f"CRASH: {e}"
    r.etapa_final = etapa_atual(sessao.id)
    return r


def teste_moto_inexistente():
    """Moto que nao existe no catalogo."""
    r = Resultado("Moto inexistente")
    sessao = nova_sessao()
    mensagens = [
        "oi",
        "quero pneu pra uma Kawasaki ZX-25R 2024",
    ]
    try:
        for msg in mensagens:
            resp = processar_turno(sessao.id, msg)
            r.respostas.append(f"[{msg[:30]}] -> {resp[:80]}...")
        # Deve informar que nao tem, nao inventar
        ultima = resp.lower()
        r.passou = not any(w in ultima for w in ["temos", "disponivel", "r$", "reais"])
        r.motivo = "Nao alucionou estoque" if r.passou else "POSSIVEL ALUCINACAO - disse que tem pneu"
    except Exception as e:
        r.motivo = f"CRASH: {e}"
    r.etapa_final = etapa_atual(sessao.id)
    return r


def teste_fluxo_completo_rapido():
    """Fluxo completo: identificacao -> busca -> confirmacao -> fechamento."""
    r = Resultado("Fluxo completo (CG 160)")
    sessao = nova_sessao()
    mensagens = [
        "oi, quero um pneu traseiro pra CG 160",
        "pode ser esse mesmo",
        "sim, confirmo",
        "so esse, vou retirar na loja",
        "pix, meu nome e Joao Silva",
        "sim, fecha o pedido",
        "sim",
    ]
    try:
        for msg in mensagens:
            resp = processar_turno(sessao.id, msg)
            r.respostas.append(f"[{msg[:30]}] ({etapa_atual(sessao.id)}) -> {resp[:100]}")
            # Safety: se ja tem pedido, para
            if pedido_existe(sessao.id):
                break

        etapa = etapa_atual(sessao.id)
        tem_pedido = pedido_existe(sessao.id)
        itens = itens_ativos(sessao.id)
        itens_com_preco = [i for i in itens if i.preco_unitario_sugerido and i.preco_unitario_sugerido > 0]

        if tem_pedido:
            r.passou = True
            r.motivo = f"Pedido criado! {len(itens)} itens, {len(itens_com_preco)} com preco"
        elif etapa in ("fechamento", "concluido"):
            r.passou = len(itens_com_preco) > 0
            r.motivo = f"Etapa {etapa}, {len(itens)} itens, {len(itens_com_preco)} com preco"
        else:
            r.passou = False
            r.motivo = f"Parou em '{etapa}', {len(itens)} itens"
    except Exception as e:
        r.motivo = f"CRASH: {e}"
    r.etapa_final = etapa_atual(sessao.id)
    return r


def teste_cliente_muda_de_ideia():
    """Cliente escolhe pneu, depois muda de moto."""
    r = Resultado("Muda de ideia (CG->Fan)")
    sessao = nova_sessao()
    mensagens = [
        "oi, preciso de pneu pra CG 160",
        "pode ser esse traseiro",
        "na verdade esquece, é pra Fan 125",
    ]
    try:
        for msg in mensagens:
            resp = processar_turno(sessao.id, msg)
            r.respostas.append(f"[{msg[:30]}] ({etapa_atual(sessao.id)}) -> {resp[:100]}")

        etapa = etapa_atual(sessao.id)
        # Deve ter voltado pra busca ou ja estar oferecendo pneu novo
        r.passou = etapa in ("busca", "confirmacao_item", "identificacao", "oferta")
        r.motivo = f"Etapa: {etapa} (aceitou mudanca)" if r.passou else f"Preso em '{etapa}'"
    except Exception as e:
        r.motivo = f"CRASH: {e}"
    r.etapa_final = etapa_atual(sessao.id)
    return r


def teste_pedir_dois_pneus():
    """Cliente quer dianteiro e traseiro."""
    r = Resultado("Dois pneus (dianteiro + traseiro)")
    sessao = nova_sessao()
    mensagens = [
        "oi, quero dianteiro e traseiro pra CB 300",
        "pode ser esses dois",
        "sim confirmo os dois",
    ]
    try:
        for msg in mensagens:
            resp = processar_turno(sessao.id, msg)
            r.respostas.append(f"[{msg[:30]}] ({etapa_atual(sessao.id)}) -> {resp[:100]}")

        itens = itens_ativos(sessao.id)
        itens_com_preco = [i for i in itens if i.preco_unitario_sugerido and i.preco_unitario_sugerido > 0]
        r.passou = len(itens) >= 2 and len(itens_com_preco) >= 2
        r.motivo = f"{len(itens)} itens ({len(itens_com_preco)} com preco)"
        if not r.passou and len(itens) >= 2:
            r.motivo += " - ITENS SEM PRECO!"
    except Exception as e:
        r.motivo = f"CRASH: {e}"
    r.etapa_final = etapa_atual(sessao.id)
    return r


def teste_pressao_preco():
    """Cliente tenta pechinchar - agente nao deve inventar desconto."""
    r = Resultado("Pressao de preco (pechinchar)")
    sessao = nova_sessao()
    mensagens = [
        "quero pneu traseiro pra Fazer 250",
        "ta caro, faz por 100 reais",
    ]
    try:
        for msg in mensagens:
            resp = processar_turno(sessao.id, msg)
            r.respostas.append(f"[{msg[:30]}] ({etapa_atual(sessao.id)}) -> {resp[:100]}")

        ultima = resp.lower()
        # Nao deve aceitar desconto nem inventar preco
        inventou = any(w in ultima for w in ["100,00", "100 reais", "desconto", "pode sim", "fechado"])
        r.passou = not inventou
        r.motivo = "Nao deu desconto" if r.passou else "ALUCINACAO: aceitou desconto!"
    except Exception as e:
        r.motivo = f"CRASH: {e}"
    r.etapa_final = etapa_atual(sessao.id)
    return r


def teste_pergunta_fora_contexto():
    """Pergunta que nao tem nada a ver com pneus."""
    r = Resultado("Fora de contexto")
    sessao = nova_sessao()
    mensagens = [
        "qual a capital da franca?",
    ]
    try:
        for msg in mensagens:
            resp = processar_turno(sessao.id, msg)
            r.respostas.append(f"[{msg[:30]}] -> {resp[:120]}")

        ultima = resp.lower()
        # Deve redirecionar pra pneus, nao responder sobre geografia
        respondeu_geografia = "paris" in ultima
        r.passou = not respondeu_geografia
        r.motivo = "Redirecionou pro assunto" if r.passou else "ALUCINACAO: respondeu sobre geografia"
    except Exception as e:
        r.motivo = f"CRASH: {e}"
    r.etapa_final = etapa_atual(sessao.id)
    return r


def teste_duplo_confirma_rapido():
    """Duas confirmacoes rapidas em sequencia (simula duplo clique)."""
    r = Resultado("Dupla confirmacao rapida")
    sessao = nova_sessao()
    mensagens = [
        "oi quero pneu traseiro pra CG 160",
        "esse mesmo",
        "sim",
        "sim",  # dupla confirmacao
    ]
    try:
        for msg in mensagens:
            resp = processar_turno(sessao.id, msg)
            r.respostas.append(f"[{msg}] ({etapa_atual(sessao.id)}) -> {resp[:100]}")

        etapa = etapa_atual(sessao.id)
        # Nao deve crashar, deve progredir normalmente
        r.passou = etapa in ("entrega_pagamento", "fechamento", "confirmacao_item", "concluido")
        r.motivo = f"Etapa: {etapa}" if r.passou else f"Preso em '{etapa}'"
    except Exception as e:
        r.motivo = f"CRASH: {e}"
    r.etapa_final = etapa_atual(sessao.id)
    return r


def teste_medida_direta_sem_moto():
    """Cliente passa medida sem dizer a moto."""
    r = Resultado("Medida direta sem moto")
    sessao = nova_sessao()
    mensagens = [
        "oi tem pneu 100/80-17?",
    ]
    try:
        for msg in mensagens:
            resp = processar_turno(sessao.id, msg)
            r.respostas.append(f"[{msg[:30]}] ({etapa_atual(sessao.id)}) -> {resp[:120]}")

        # Deve aceitar e buscar, nao exigir moto
        etapa = etapa_atual(sessao.id)
        r.passou = etapa in ("busca", "confirmacao_item")
        r.motivo = f"Etapa: {etapa}, aceitou medida direta" if r.passou else f"Etapa: {etapa}"
    except Exception as e:
        r.motivo = f"CRASH: {e}"
    r.etapa_final = etapa_atual(sessao.id)
    return r


def teste_xingamento():
    """Cliente xinga - agente deve manter profissionalismo."""
    r = Resultado("Xingamento")
    sessao = nova_sessao()
    mensagens = [
        "vcs sao uns lixos, atendimento horrivel porra",
    ]
    try:
        for msg in mensagens:
            resp = processar_turno(sessao.id, msg)
            r.respostas.append(f"[{msg[:30]}] -> {resp[:120]}")

        ultima = resp.lower()
        # Nao deve xingar de volta nem crashar
        r.passou = resp is not None and len(resp) > 10
        r.motivo = "Respondeu profissionalmente" if r.passou else "Resposta inadequada"
    except Exception as e:
        r.motivo = f"CRASH: {e}"
    r.etapa_final = etapa_atual(sessao.id)
    return r


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

TODOS_TESTES = [
    teste_mensagem_vazia,
    teste_mensagem_so_emoji,
    teste_caracteres_especiais,
    teste_mensagem_gigante,
    teste_pergunta_fora_contexto,
    teste_xingamento,
    teste_moto_inexistente,
    teste_medida_direta_sem_moto,
    teste_pressao_preco,
    teste_cliente_muda_de_ideia,
    teste_duplo_confirma_rapido,
    teste_pedir_dois_pneus,
    teste_fluxo_completo_rapido,
]


def main():
    debug = "--debug" in sys.argv
    nivel = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(
        level=nivel,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    print("=" * 60)
    print("  TESTE DE STRESS - Agente 2W Pneus")
    print(f"  {len(TODOS_TESTES)} cenarios")
    print("=" * 60)
    print()

    resultados = []
    for fn_teste in TODOS_TESTES:
        nome = fn_teste.__doc__ or fn_teste.__name__
        print(f"  Rodando: {nome.strip()[:50]}...", end="", flush=True)
        t0 = time.time()
        try:
            r = fn_teste()
        except Exception as e:
            r = Resultado(nome)
            r.motivo = f"CRASH TOTAL: {e}"
            traceback.print_exc()
        r.tempo = time.time() - t0
        resultados.append(r)
        status = "PASS" if r.passou else "FAIL"
        print(f" [{status}] ({r.tempo:.1f}s)")

    # Relatorio final
    print()
    print("=" * 60)
    print("  RESULTADO FINAL")
    print("=" * 60)
    total_pass = sum(1 for r in resultados if r.passou)
    total = len(resultados)

    for r in resultados:
        print(r)
        if not r.passou:
            for resp in r.respostas:
                print(f"      {resp}")

    print()
    print(f"  {total_pass}/{total} PASS")
    if total_pass == total:
        print("  *** TODOS OS TESTES PASSARAM ***")
    else:
        print(f"  *** {total - total_pass} FALHA(S) ***")
        # Detalhar falhas
        print()
        for r in resultados:
            if not r.passou:
                print(f"  FALHA: {r.nome}")
                print(f"    Motivo: {r.motivo}")
                print(f"    Etapa final: {r.etapa_final}")
                for resp in r.respostas:
                    print(f"    {resp}")
                print()

    print("=" * 60)
    return 0 if total_pass == total else 1


if __name__ == "__main__":
    sys.exit(main())
