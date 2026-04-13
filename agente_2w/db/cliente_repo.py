import logging
from uuid import UUID

from agente_2w.db.client import supabase
from agente_2w.db.exceptions import RegistroNaoEncontrado, ErroDeInsercao, ErroDeAtualizacao
from agente_2w.schemas.cliente import Cliente, ClienteCreate

logger = logging.getLogger(__name__)

_TABELA = "cliente"


def criar_cliente(dados: ClienteCreate) -> Cliente:
    try:
        resultado = (
            supabase.table(_TABELA)
            .insert(dados.model_dump(mode="json"))
            .execute()
        )
        logger.debug("Cliente criado: %s", resultado.data[0].get("id"))
        return Cliente(**resultado.data[0])
    except Exception as e:
        raise ErroDeInsercao(_TABELA, str(e)) from e


def buscar_cliente_por_id(cliente_id: UUID) -> Cliente | None:
    try:
        resultado = (
            supabase.table(_TABELA)
            .select("*")
            .eq("id", str(cliente_id))
            .maybe_single()
            .execute()
        )
        if resultado is None or resultado.data is None:
            return None
        return Cliente(**resultado.data)
    except Exception as e:
        raise RegistroNaoEncontrado(_TABELA, str(cliente_id)) from e


def buscar_cliente_por_telefone(telefone: str) -> Cliente | None:
    try:
        resultado = (
            supabase.table(_TABELA)
            .select("*")
            .eq("telefone", telefone)
            .maybe_single()
            .execute()
        )
        if resultado is None or resultado.data is None:
            return None
        return Cliente(**resultado.data)
    except Exception as e:
        raise RegistroNaoEncontrado(_TABELA, telefone) from e


def resolver_ou_criar_cliente(telefone: str, nome: str | None = None) -> Cliente:
    """Busca ou cria cliente de forma atômica via RPC.

    Usa INSERT ... ON CONFLICT (telefone) DO NOTHING para garantir que
    dois workers simultâneos para o mesmo telefone nunca criem duplicatas.
    """
    try:
        resultado = supabase.rpc(
            "resolver_ou_criar_cliente_atomico",
            {"p_telefone": telefone, "p_nome": nome},
        ).execute()
        if not resultado.data:
            raise ErroDeInsercao(_TABELA, f"RPC retornou vazio para telefone={telefone}")
        return Cliente(**resultado.data[0])
    except ErroDeInsercao:
        raise
    except Exception as e:
        raise ErroDeInsercao(_TABELA, f"telefone={telefone}: {e}") from e


def atualizar_cliente(cliente_id: UUID, campos: dict) -> Cliente:
    try:
        resultado = (
            supabase.table(_TABELA)
            .update(campos)
            .eq("id", str(cliente_id))
            .execute()
        )
        logger.debug("Cliente atualizado: %s", cliente_id)
        return Cliente(**resultado.data[0])
    except Exception as e:
        raise ErroDeAtualizacao(_TABELA, f"{cliente_id}: {e}") from e
