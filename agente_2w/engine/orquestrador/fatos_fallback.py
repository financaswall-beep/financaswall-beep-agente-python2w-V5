"""Extracao fallback de fatos estruturados a partir do texto livre.

Quando a IA esquece de registrar forma_pagamento/tipo_entrega via
fatos_observados, este modulo varre a mensagem do cliente atras de keywords
conhecidas e registra o fato — evitando loops onde a IA repergunta algo que
o cliente ja respondeu.

A funcao _tem_negacao_antes impede falsos positivos (ex.: 'nao quero pix').
"""
import logging
import re
import unicodedata
from uuid import UUID

from agente_2w.db import contexto_repo, bairro_municipio_cache_repo
from agente_2w.db.client import supabase
from agente_2w.constantes import ChaveContexto
from agente_2w.enums.enums import TipoDeVerdade, NivelConfirmacao, OrigemContexto
from agente_2w.schemas.contexto_conversa import ContextoConversaCreate

logger = logging.getLogger(__name__)


_KEYWORDS_FORMA_PAGAMENTO = [
    ("pix", "pix"),
    ("dinheiro", "dinheiro"),
    ("cartão", "cartao"),
    ("cartao", "cartao"),
    ("transferência", "transferencia"),
    ("transferencia", "transferencia"),
]

_KEYWORDS_TIPO_ENTREGA = [
    ("retirada", "retirada"),
    ("retiro", "retirada"),
    ("busco", "retirada"),
    ("entrega", "entrega"),
    ("entregar", "entrega"),
    ("delivery", "entrega"),
]


def _tem_negacao_antes(texto: str, keyword: str) -> bool:
    """Verifica se ha negacao proxima antes da keyword — evita falso positivo.

    Ex: 'nao quero pix' nao deve registrar pix como forma de pagamento.
    """
    pattern = rf"\b(n[aã]o|sem|nunca|n[aã]o\s+quero)\b.{{0,25}}{re.escape(keyword)}"
    return bool(re.search(pattern, texto, re.IGNORECASE))


def _extrair_fatos_estruturados_fallback(
    sessao_id: UUID, mensagem: str, mensagem_id
) -> None:
    """Fallback: registra forma_pagamento e tipo_entrega se a IA nao registrou.

    Roda APOS a IA aplicar fatos_observados. So ativa se o fato ainda nao
    existe na sessao. Previne o loop classico onde o cliente diz 'pix' e a IA
    esquece de registrar, fazendo a mesma pergunta no proximo turno.
    """
    try:
        texto = mensagem.lower()

        # forma_pagamento — so registra se ainda nao existe
        if not contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.FORMA_PAGAMENTO):
            for kw, valor in _KEYWORDS_FORMA_PAGAMENTO:
                if kw in texto and not _tem_negacao_antes(texto, kw):
                    contexto_repo.registrar_fato(ContextoConversaCreate(
                        sessao_chat_id=sessao_id,
                        chave=ChaveContexto.FORMA_PAGAMENTO,
                        valor_texto=valor,
                        valor_json=None,
                        tipo_de_verdade=TipoDeVerdade.observado,
                        nivel_confirmacao=NivelConfirmacao.nenhum,
                        fonte=OrigemContexto.backend,
                        mensagem_chat_id=mensagem_id,
                    ))
                    logger.info(
                        "Fallback: forma_pagamento extraida da mensagem — '%s'", valor
                    )
                    break

        # tipo_entrega — so registra se ainda nao existe
        if not contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.TIPO_ENTREGA):
            for kw, valor in _KEYWORDS_TIPO_ENTREGA:
                if kw in texto and not _tem_negacao_antes(texto, kw):
                    contexto_repo.registrar_fato(ContextoConversaCreate(
                        sessao_chat_id=sessao_id,
                        chave=ChaveContexto.TIPO_ENTREGA,
                        valor_texto=valor,
                        valor_json=None,
                        tipo_de_verdade=TipoDeVerdade.observado,
                        nivel_confirmacao=NivelConfirmacao.nenhum,
                        fonte=OrigemContexto.backend,
                        mensagem_chat_id=mensagem_id,
                    ))
                    logger.info(
                        "Fallback: tipo_entrega extraido da mensagem — '%s'", valor
                    )
                    break

        # bairro / municipio — resolve via cache bairro_municipio_cache
        _resolver_bairro_fallback(sessao_id, mensagem, mensagem_id)

    except Exception:
        logger.exception("Falha no fallback de extracao de fatos estruturados")


# ---------------------------------------------------------------------------
# Helpers para fallback de bairro
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset(
    "a o e de do da em no na os as dos das um uma uns umas pra pro para "
    "eu vc vcs voce voces me mim te nos la aqui ai ja nao sim que com por "
    "oi ola bom boa dia tarde noite tudo bem obrigado obrigada blz beleza "
    "entrega entregam entregar delivery retirada busco retiro quero preciso "
    "pneu pneus moto carro valor preco frete quanto custa tem have ok".split()
)


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFD", texto)
    sem_acento = sem_acento.encode("ascii", "ignore").decode("ascii")
    return sem_acento.strip().lower()


def _gerar_candidatos(texto: str) -> list[str]:
    """Gera n-grams (1 a 3 palavras) normalizados, filtrando stop words."""
    limpo = re.sub(r"[^\w\s]", " ", texto)
    palavras = [_normalizar(p) for p in limpo.split() if p.strip()]
    palavras = [p for p in palavras if p and p not in _STOP_WORDS and len(p) > 2]

    candidatos = []
    for n in (3, 2, 1):
        for i in range(len(palavras) - n + 1):
            candidatos.append(" ".join(palavras[i : i + n]))
    return candidatos


def _resolver_bairro_fallback(
    sessao_id: UUID, mensagem: str, mensagem_id
) -> None:
    """Fallback: se a IA nao registrou bairro/municipio, tenta extrair da mensagem via cache."""
    if contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.MUNICIPIO):
        return
    if contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.BAIRRO):
        return

    candidatos = _gerar_candidatos(mensagem)
    if not candidatos:
        return

    # Query unica: busca todos os candidatos no cache de uma vez
    try:
        res = (
            supabase.table("bairro_municipio_cache")
            .select("termo_normalizado, bairro, municipio")
            .in_("termo_normalizado", candidatos)
            .execute()
        )
    except Exception:
        logger.exception("Fallback bairro: erro ao consultar cache")
        return

    if not res.data:
        return

    # Priorizar n-gram mais longo (ja vem nessa ordem em candidatos)
    encontrados = {r["termo_normalizado"]: r for r in res.data}
    for cand in candidatos:
        if cand in encontrados:
            hit = encontrados[cand]
            break
    else:
        return

    bairro = hit.get("bairro")
    municipio = hit.get("municipio")

    if bairro:
        contexto_repo.registrar_fato(ContextoConversaCreate(
            sessao_chat_id=sessao_id,
            chave=ChaveContexto.BAIRRO,
            valor_texto=bairro,
            tipo_de_verdade=TipoDeVerdade.observado,
            nivel_confirmacao=NivelConfirmacao.nenhum,
            fonte=OrigemContexto.backend,
            mensagem_chat_id=mensagem_id,
        ))
        logger.info("Fallback: bairro extraido da mensagem via cache — '%s'", bairro)

    if municipio:
        contexto_repo.registrar_fato(ContextoConversaCreate(
            sessao_chat_id=sessao_id,
            chave=ChaveContexto.MUNICIPIO,
            valor_texto=municipio,
            tipo_de_verdade=TipoDeVerdade.validado_tool,
            nivel_confirmacao=NivelConfirmacao.confirmado_cliente,
            fonte=OrigemContexto.backend,
            mensagem_chat_id=mensagem_id,
        ))
        logger.info("Fallback: municipio resolvido via cache — '%s'", municipio)
