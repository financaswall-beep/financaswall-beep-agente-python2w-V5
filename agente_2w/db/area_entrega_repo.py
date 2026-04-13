"""Repositorio de areas de entrega e fretes.

Redesign 12/04/2026 — query SQL filtrada por municipio em vez de SELECT *
Fix 12/04/2026b — cache local com TTL 1h; match por normalização em Python
(sem acentos, case-insensitive) para nunca depender do ilike do PostgreSQL.
"""

import logging
import time
import unicodedata
from decimal import Decimal

from agente_2w.db.client import supabase

logger = logging.getLogger(__name__)

_TABELA = "area_entrega"
_TTL_SEGUNDOS = 3600  # 1 hora

# Cache: dict{municipio_normalizado -> (municipio_oficial, valor_frete)}
_cache_fretes: dict[str, tuple[str, Decimal]] | None = None
_cache_carregado_em: float = 0.0


def _normalizar(texto: str) -> str:
    """Remove acentos e converte para minusculo para comparacao."""
    sem_acento = unicodedata.normalize("NFD", texto)
    sem_acento = sem_acento.encode("ascii", "ignore").decode("ascii")
    return sem_acento.strip().lower()


def _carregar_cache() -> dict[str, tuple[str, Decimal]]:
    """Carrega tabela de fretes do banco e indexa por municipio normalizado."""
    resultado = (
        supabase.table(_TABELA)
        .select("municipio, valor_frete")
        .eq("ativo", True)
        .is_("bairro", "null")
        .execute()
    )
    index: dict[str, tuple[str, Decimal]] = {}
    for r in resultado.data:
        nome = r["municipio"]
        index[_normalizar(nome)] = (nome, Decimal(str(r["valor_frete"])))
    logger.info("Cache area_entrega carregado: %d municipios", len(index))
    return index


def _obter_cache() -> dict[str, tuple[str, Decimal]]:
    """Retorna cache com TTL de 1h. Recarrega se expirou."""
    global _cache_fretes, _cache_carregado_em
    agora = time.monotonic()
    if _cache_fretes is None or (agora - _cache_carregado_em) > _TTL_SEGUNDOS:
        try:
            _cache_fretes = _carregar_cache()
            _cache_carregado_em = agora
        except Exception:
            logger.exception("Falha ao carregar cache area_entrega")
            if _cache_fretes is None:
                _cache_fretes = {}
    return _cache_fretes


def consultar_frete(municipio: str) -> Decimal | None:
    """Retorna o valor do frete para o municipio informado.

    Match por normalização em Python: remove acentos e compara em minúsculas.
    Isso garante que 'Sao Goncalo', 'são gonçalo', 'SAO GONCALO' — todos
    batem com 'São Gonçalo' sem depender de collation ou ilike do PostgreSQL.
    Retorna None se o municipio nao for coberto.
    """
    if not municipio:
        return None
    try:
        cache = _obter_cache()
        chave = _normalizar(municipio)
        if chave in cache:
            nome_oficial, valor = cache[chave]
            logger.info("Frete encontrado: %s = R$%s", nome_oficial, valor)
            return valor
        logger.info("Municipio '%s' nao coberto para entrega", municipio)
        return None
    except Exception:
        logger.exception("Erro ao consultar frete para '%s'", municipio)
        return None


def listar_municipios_ativos() -> list[str]:
    """Retorna lista de municipios cobertos (para referencia no prompt)."""
    try:
        cache = _obter_cache()
        return sorted(nome for nome, _ in cache.values())
    except Exception:
        logger.exception("Erro ao listar municipios")
        return []


def buscar_tabela_fretes() -> list[dict]:
    """Retorna tabela de fretes por municipio.

    Formato: [{"municipio": "Niterói", "valor_frete": "9.90"}, ...]
    Usado para expor a tabela completa no contexto da IA.
    """
    try:
        cache = _obter_cache()
        return sorted(
            [{"municipio": nome, "valor_frete": str(valor)} for nome, valor in cache.values()],
            key=lambda x: x["municipio"],
        )
    except Exception:
        logger.exception("Erro ao buscar tabela de fretes")
        return []

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
    """Retorna tabela de fretes por municipio.

    Formato: [{"municipio": "Niteroi", "valor_frete": "9.90"}, ...]
    Usado para expor a tabela completa no contexto da IA.
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
