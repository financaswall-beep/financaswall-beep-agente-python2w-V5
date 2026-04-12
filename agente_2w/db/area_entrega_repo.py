"""Repositorio de areas de entrega e fretes.

Redesign 12/04/2026 — query SQL filtrada por municipio em vez de SELECT *
"""

import logging
import unicodedata
from decimal import Decimal

from agente_2w.db.client import supabase

logger = logging.getLogger(__name__)

_TABELA = "area_entrega"


def _normalizar(texto: str) -> str:
    """Remove acentos e converte para minusculo para comparacao."""
    sem_acento = unicodedata.normalize("NFD", texto)
    sem_acento = sem_acento.encode("ascii", "ignore").decode("ascii")
    return sem_acento.strip().lower()


def consultar_frete(municipio: str) -> Decimal | None:
    """Retorna o valor do frete para o municipio informado.

    Faz query SQL filtrada por municipio (case-insensitive via indice lower()).
    Retorna None se o municipio nao for coberto.
    """
    if not municipio:
        return None

    try:
        resultado = (
            supabase.table(_TABELA)
            .select("municipio, valor_frete")
            .eq("ativo", True)
            .is_("bairro", "null")
            .ilike("municipio", municipio)
            .limit(1)
            .execute()
        )

        if resultado.data:
            r = resultado.data[0]
            valor = Decimal(str(r["valor_frete"]))
            logger.info("Frete encontrado: %s = R$%s", r["municipio"], valor)
            return valor

        logger.info("Municipio '%s' nao coberto para entrega", municipio)
        return None

    except Exception:
        logger.exception("Erro ao consultar frete para '%s'", municipio)
        return None


def listar_municipios_ativos() -> list[str]:
    """Retorna lista de municipios cobertos (para referencia no prompt)."""
    try:
        resultado = (
            supabase.table(_TABELA)
            .select("municipio")
            .eq("ativo", True)
            .is_("bairro", "null")
            .order("municipio")
            .execute()
        )
        return [r["municipio"] for r in resultado.data]
    except Exception:
        logger.exception("Erro ao listar municipios")
        return []


def buscar_tabela_fretes() -> list[dict]:
    """Retorna tabela de fretes por municipio (apenas linhas sem bairro especifico).

    Formato: [{"municipio": "Niteroi", "valor_frete": "9.90"}, ...]
    Usado para expor a tabela completa no contexto da IA, permitindo
    que ela responda perguntas sobre frete proativamente sem nova consulta.
    """
    try:
        resultado = (
            supabase.table(_TABELA)
            .select("municipio, valor_frete")
            .eq("ativo", True)
            .is_("bairro", "null")
            .order("municipio")
            .execute()
        )
        return [
            {"municipio": r["municipio"], "valor_frete": str(Decimal(str(r["valor_frete"])))}
            for r in resultado.data
        ]
    except Exception:
        logger.exception("Erro ao buscar tabela de fretes")
        return []
