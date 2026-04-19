import logging
from uuid import UUID

from agente_2w.db.client import supabase
from agente_2w.db.exceptions import RegistroNaoEncontrado, ErroDeInsercao, ErroDeAtualizacao
from agente_2w.schemas.contexto_conversa import ContextoConversa, ContextoConversaCreate

logger = logging.getLogger(__name__)

_TABELA = "contexto_conversa"


def criar_fato(dados: ContextoConversaCreate) -> ContextoConversa:
    try:
        resultado = (
            supabase.table(_TABELA)
            .insert(dados.model_dump(mode="json"))
            .execute()
        )
        logger.debug("Fato criado: chave=%s", dados.chave)
        return ContextoConversa(**resultado.data[0])
    except Exception as e:
        raise ErroDeInsercao(_TABELA, f"chave={dados.chave}: {e}") from e


def desativar_fato_anterior(
    sessao_id: UUID,
    chave: str,
    item_provisorio_id: UUID | None = None,
) -> None:
    try:
        query = (
            supabase.table(_TABELA)
            .update({"ativo": False})
            .eq("sessao_chat_id", str(sessao_id))
            .eq("chave", chave)
            .eq("ativo", True)
        )
        if item_provisorio_id is not None:
            query = query.eq("item_provisorio_id", str(item_provisorio_id))
        else:
            query = query.is_("item_provisorio_id", "null")
        query.execute()
    except Exception as e:
        raise ErroDeAtualizacao(_TABELA, f"desativar chave={chave}: {e}") from e


def registrar_fato(dados: ContextoConversaCreate) -> ContextoConversa:
    """Desativa fato anterior e cria o novo em transação atômica via RPC.

    Usa registrar_fato_atomico para garantir que se o INSERT falhar,
    o UPDATE de desativação é revertido — nenhum dado de contexto é perdido.
    """
    try:
        params = {
            "p_sessao_chat_id": str(dados.sessao_chat_id),
            "p_chave": dados.chave,
            "p_item_provisorio_id": str(dados.item_provisorio_id) if dados.item_provisorio_id else None,
            "p_tipo_de_verdade": dados.tipo_de_verdade.value,
            "p_nivel_confirmacao": dados.nivel_confirmacao.value,
            "p_fonte": dados.fonte.value,
            "p_valor_texto": dados.valor_texto,
            "p_valor_json": dados.valor_json,
            "p_mensagem_chat_id": str(dados.mensagem_chat_id) if dados.mensagem_chat_id else None,
            "p_referencia_fonte": dados.referencia_fonte,
            "p_observacao": dados.observacao,
            "p_ativo": dados.ativo,
        }
        resultado = supabase.rpc("registrar_fato_atomico", params).execute()
        if not resultado.data:
            raise ErroDeInsercao(_TABELA, f"RPC retornou vazio para chave={dados.chave}")
        logger.debug("Fato registrado atomicamente: chave=%s", dados.chave)
        return ContextoConversa(**resultado.data[0])
    except (ErroDeInsercao, ErroDeAtualizacao):
        raise
    except Exception as e:
        raise ErroDeInsercao(_TABELA, f"chave={dados.chave}: {e}") from e


def listar_fatos_ativos(sessao_id: UUID) -> list[ContextoConversa]:
    try:
        resultado = (
            supabase.table(_TABELA)
            .select("*")
            .eq("sessao_chat_id", str(sessao_id))
            .eq("ativo", True)
            .order("coletado_em", desc=True)
            .limit(30)
            .execute()
        )
        return [ContextoConversa(**row) for row in resultado.data]
    except Exception as e:
        raise RegistroNaoEncontrado(_TABELA, str(sessao_id)) from e


def listar_fatos_por_chave(
    sessao_id: UUID,
    chave: str,
) -> list[ContextoConversa]:
    try:
        resultado = (
            supabase.table(_TABELA)
            .select("*")
            .eq("sessao_chat_id", str(sessao_id))
            .eq("chave", chave)
            .order("coletado_em", desc=False)
            .execute()
        )
        return [ContextoConversa(**row) for row in resultado.data]
    except Exception as e:
        raise RegistroNaoEncontrado(_TABELA, f"chave={chave}, sessao={sessao_id}") from e


def buscar_fato_ativo(
    sessao_id: UUID,
    chave: str,
    item_provisorio_id: UUID | None = None,
) -> ContextoConversa | None:
    try:
        query = (
            supabase.table(_TABELA)
            .select("*")
            .eq("sessao_chat_id", str(sessao_id))
            .eq("chave", chave)
            .eq("ativo", True)
        )
        if item_provisorio_id is not None:
            query = query.eq("item_provisorio_id", str(item_provisorio_id))
        else:
            query = query.is_("item_provisorio_id", "null")

        resultado = query.maybe_single().execute()
        if resultado is None or resultado.data is None:
            return None
        return ContextoConversa(**resultado.data)
    except Exception as e:
        raise RegistroNaoEncontrado(_TABELA, f"chave={chave}, sessao={sessao_id}") from e
