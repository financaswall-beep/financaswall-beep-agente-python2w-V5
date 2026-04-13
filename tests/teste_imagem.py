"""Teste rápido de visão (imagem) e áudio no agente 2W Pneus.

Uso:
    python teste_imagem.py imagem
    python teste_imagem.py audio
    python teste_imagem.py url https://sua-url-aqui.jpg
"""

import sys
from agente_2w.db import sessao_repo
from agente_2w.enums.enums import EtapaFluxo, StatusSessao
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.engine.orquestrador import processar_turno

# ---------------------------------------------------------------------------
# URLs de exemplo — troque pela URL real que quiser testar
# ---------------------------------------------------------------------------

URL_IMAGEM_PNEU = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/"
    "Michelin_Pilot_Road_4_rear.jpg/320px-Michelin_Pilot_Road_4_rear.jpg"
)

# ---------------------------------------------------------------------------

def criar_sessao_teste() -> object:
    return sessao_repo.criar_sessao(SessaoChatCreate(
        canal="teste_cli",
        contato_externo="5521000000001",
        etapa_atual=EtapaFluxo.identificacao,
        status_sessao=StatusSessao.ativa,
    ))


def testar_imagem(url: str):
    print(f"\n[TESTE IMAGEM]")
    print(f"URL: {url}")
    print("-" * 60)
    sessao = criar_sessao_teste()
    resposta = processar_turno(
        sessao.id,
        mensagem_texto="qual pneu é esse? tem pra vender?",
        imagens=[url],
    )
    print(f"Agente: {resposta}")


def testar_audio_transcrito():
    """Simula o que acontece depois do Whisper transcrever o áudio."""
    print(f"\n[TESTE ÁUDIO TRANSCRITO]")
    print("Simulando: cliente mandou áudio dizendo 'quero um pneu traseiro pra minha CG 160'")
    print("-" * 60)
    sessao = criar_sessao_teste()
    # O webhook transcreveria o áudio e passaria o texto abaixo
    resposta = processar_turno(
        sessao.id,
        mensagem_texto="quero um pneu traseiro pra minha CG 160",
    )
    print(f"Agente: {resposta}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "imagem"

    if modo == "imagem":
        testar_imagem(URL_IMAGEM_PNEU)

    elif modo == "audio":
        testar_audio_transcrito()

    elif modo == "url" and len(sys.argv) > 2:
        testar_imagem(sys.argv[2])

    else:
        print("Uso: python teste_imagem.py [imagem|audio|url <URL>]")
