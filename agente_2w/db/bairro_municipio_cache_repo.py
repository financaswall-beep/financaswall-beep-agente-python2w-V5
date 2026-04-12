"""Repositório de cache bairro→município.

Redesign 12/04/2026:
- PK agora é UUID (id), não mais termo_normalizado
- Um bairro pode existir em múltiplos municípios (ex: Centro → RJ, Niterói)
- buscar() retorna lista de resultados (1=único, 2+=ambíguo, 0=miss)
- Acessos contados a cada consulta (BI)
- sessao_id indica qual atendimento descobriu o bairro
"""
import logging
import unicodedata
from datetime import datetime, timezone
from uuid import UUID

from agente_2w.db.client import supabase

logger = logging.getLogger(__name__)

_TABELA = "bairro_municipio_cache"


def _normalizar(texto: str) -> str:
    """Lowercase + remove acentos para chave de cache."""
    sem_acento = unicodedata.normalize("NFD", texto)
    sem_acento = sem_acento.encode("ascii", "ignore").decode("ascii")
    return sem_acento.strip().lower()


def buscar(termo: str) -> list[dict]:
    """Busca no cache pelo termo normalizado.

    Retorna lista de dicts com chaves 'bairro' e 'municipio':
    - [] (vazio)     → cache miss
    - [1 item]       → bairro único, municipio pode ser None (fora de cobertura)
    - [2+ itens]     → bairro ambíguo (existe em múltiplos municípios)

    Incrementa acessos em todas as linhas encontradas.
    """
    if not termo:
        return []

    chave = _normalizar(termo)
    try:
        res = (
            supabase.table(_TABELA)
            .select("id, bairro, municipio, acessos")
            .eq("termo_normalizado", chave)
            .execute()
        )
        if not res.data:
            return []

        # Incrementa acessos (fire-and-forget para cada linha)
        agora = datetime.now(timezone.utc).isoformat()
        for row in res.data:
            try:
                supabase.table(_TABELA).update(
                    {"acessos": (row.get("acessos") or 0) + 1,
                     "atualizado_em": agora}
                ).eq("id", row["id"]).execute()
            except Exception:
                pass  # não quebra o fluxo principal

        return [{"bairro": r["bairro"], "municipio": r["municipio"]} for r in res.data]

    except Exception:
        logger.exception("Erro ao buscar cache para termo '%s'", termo)
        return []


def salvar(
    termo_original: str,
    bairro: str | None,
    municipio: str | None,
    fonte: str = "informado_cliente",
    sessao_id: UUID | None = None,
) -> None:
    """Salva (ou atualiza) entrada no cache.

    municipio=None indica área fora de cobertura — também é salvo para
    evitar nova consulta para o mesmo termo.

    Usa UPSERT no unique index (termo_normalizado, municipio) para evitar
    duplicatas. Se o par (termo, municipio) já existe, atualiza acessos.
    """
    if not termo_original:
        return

    chave = _normalizar(termo_original)
    try:
        payload = {
            "termo_normalizado": chave,
            "termo_original": termo_original,
            "bairro": bairro,
            "municipio": municipio,
            "fonte": fonte,
            "acessos": 1,
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }
        if sessao_id:
            payload["sessao_id"] = str(sessao_id)

        supabase.table(_TABELA).upsert(
            payload,
            on_conflict="termo_normalizado,municipio",
        ).execute()

        logger.info(
            "Cache salvo: '%s' → bairro=%s, municipio=%s [%s]",
            termo_original, bairro, municipio, fonte,
        )
    except Exception:
        logger.exception("Erro ao salvar cache para termo '%s'", termo_original)
