"""Agente IA — chamada ao OpenAI com function calling e contexto.

MIGRAÇÃO: Chat Completions → Responses API para família gpt-5.x
=====================================================================
Baseado na documentação oficial:
- https://developers.openai.com/api/docs/guides/function-calling
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/guides/migrate-to-responses
- https://developers.openai.com/api/reference/resources/responses/methods/create

MUDANÇAS CHAVE (da documentação):
1. Responses API usa `input` (items) em vez de `messages`
2. Tools: {type:"function", name:"X", parameters:{...}} — sem wrapper "function"
3. Tool calls: items `function_call` no output (com call_id)
4. Tool results: items `function_call_output` (referenciando call_id)
5. System prompt vai em `instructions`
6. Structured Outputs usa `text.format` em vez de `response_format`
7. Reasoning items devem ser passados de volta com `reasoning.encrypted_content`

COMPATIBILIDADE:
- gpt-4o e anteriores: Chat Completions (sem mudança)
- gpt-5.x (flagship, mini, nano): Responses API
"""

import json
import logging

from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from agente_2w.config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MODEL_MINI, OPENAI_MODEL_FLAGSHIP, MAX_TOOL_ROUNDS

logger = logging.getLogger(__name__)

OPENAI_TIMEOUT = 30  # segundos
from agente_2w.ia.prompt_sistema import construir_prompt
from agente_2w.schemas.contexto_executavel import ContextoExecutavel
from agente_2w.tools.busca_catalogo import (
    buscar_pneus,
    buscar_pneus_por_moto,
    buscar_detalhes_pneu,
    buscar_motos_por_medida,
    consultar_catalogo_resumo,
    consultar_motos_atendidas,
    consultar_historico_cliente,
)
from agente_2w.tools.consulta_estoque import consultar_estoque
from agente_2w.tools.resolve_cliente import resolver_cliente

_client = OpenAI(api_key=OPENAI_API_KEY, timeout=OPENAI_TIMEOUT)

from agente_2w.ia.schemas_envelope import ENVELOPE_IA_SCHEMA as _ENVELOPE_IA_SCHEMA
from agente_2w.ia.tools_schema import TOOLS_SCHEMA, TOOLS_COM_PNEU as _TOOLS_COM_PNEU
from agente_2w.ia.extracao_pneus import extrair_pneus_de_resultado as _extrair_pneus_de_resultado

# ---------- Mapa de dispatch das tools ----------

_TOOL_DISPATCH: dict = {
    "buscar_pneus": buscar_pneus,
    "buscar_pneus_por_moto": buscar_pneus_por_moto,
    "buscar_detalhes_pneu": buscar_detalhes_pneu,
    "buscar_motos_por_medida": buscar_motos_por_medida,
    "consultar_catalogo_resumo": consultar_catalogo_resumo,
    "consultar_motos_atendidas": consultar_motos_atendidas,
    "consultar_historico_cliente": consultar_historico_cliente,
    "consultar_estoque": consultar_estoque,
    "resolver_cliente": resolver_cliente,
}

_RETRY_EXCEPTIONS = (RateLimitError, APITimeoutError, APIConnectionError)


# ==========================================================================
# CONVERSÃO DE TOOLS: Chat Completions → Responses API
# ==========================================================================
# Doc: https://developers.openai.com/api/docs/guides/function-calling
#
# Chat Completions:  {"type":"function", "function": {"name":"X", ...}}
# Responses API:     {"type":"function", "name":"X", ...}
# ==========================================================================

def _converter_tools_para_responses(tools_completions: list[dict]) -> list[dict]:
    """Converte TOOLS_SCHEMA do formato Chat Completions para Responses API."""
    tools_responses = []
    for tool in tools_completions:
        if tool.get("type") != "function":
            tools_responses.append(tool)
            continue
        fn = tool["function"]
        tools_responses.append({
            "type": "function",
            "name": fn["name"],
            "description": fn.get("description", ""),
            "parameters": fn.get("parameters", {}),
            # IMPORTANTE: strict=False porque varias tools tem "required": []
            # (params opcionais). Com strict=True a Responses API forca todos
            # os campos como required e rejeita o schema.
            # Doc: "To opt out of strict mode... explicitly set strict: false"
            "strict": False,
        })
    return tools_responses


_TOOLS_SCHEMA_RESPONSES: list[dict] | None = None


def _get_tools_responses() -> list[dict]:
    """Retorna TOOLS_SCHEMA convertido para formato Responses API (com cache)."""
    global _TOOLS_SCHEMA_RESPONSES
    if _TOOLS_SCHEMA_RESPONSES is None:
        _TOOLS_SCHEMA_RESPONSES = _converter_tools_para_responses(TOOLS_SCHEMA)
        logger.info("[MIGRATION] Convertidos %d tools para Responses API", len(_TOOLS_SCHEMA_RESPONSES))
    return _TOOLS_SCHEMA_RESPONSES


def _familia_gpt5(modelo: str) -> bool:
    """True para qualquer modelo da familia gpt-5.x (flagship, mini, nano)."""
    return "gpt-5." in modelo.lower()


def _escolher_modelo(tentativa: int, tem_imagem: bool) -> str:
    """Roteia para FLAGSHIP em retries/imagens, MINI no resto."""
    if tentativa > 1 or tem_imagem:
        return OPENAI_MODEL_FLAGSHIP
    return OPENAI_MODEL_MINI


# ==========================================================================
# CHAT COMPLETIONS (gpt-4o e anteriores — sem mudança)
# ==========================================================================

@retry(
    retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    before_sleep=lambda retry_state: logger.warning(
        "OpenAI retry %d apos %s: %s",
        retry_state.attempt_number,
        type(retry_state.outcome.exception()).__name__,
        retry_state.outcome.exception(),
    ),
    reraise=True,
)
def _chamar_openai_completions(messages: list, tools=None, model: str | None = None) -> object:
    """Chamada via Chat Completions — para gpt-4o e anteriores."""
    modelo = model or OPENAI_MODEL
    kwargs = {
        "model": modelo,
        "messages": messages,
        "temperature": 0.3,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "EnvelopeIA",
                "strict": True,
                "schema": _ENVELOPE_IA_SCHEMA,
            },
        },
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
        kwargs["parallel_tool_calls"] = False
    return _client.chat.completions.create(**kwargs)


# ==========================================================================
# RESPONSES API (gpt-5.x — mini, nano, flagship)
# ==========================================================================
# Doc: https://developers.openai.com/api/docs/guides/migrate-to-responses
#
# 1. instructions em vez de system messages
# 2. text.format em vez de response_format
# 3. function_call items no output (com call_id)
# 4. function_call_output items como resposta (referenciando call_id)
# 5. reasoning.encrypted_content obrigatorio com store=False para multi-turn
# 6. reasoning.effort controla nivel de raciocinio
# ==========================================================================

@retry(
    retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    before_sleep=lambda retry_state: logger.warning(
        "OpenAI Responses retry %d apos %s: %s",
        retry_state.attempt_number,
        type(retry_state.outcome.exception()).__name__,
        retry_state.outcome.exception(),
    ),
    reraise=True,
)
def _chamar_openai_responses(
    instructions: str,
    input_items: list | str,
    tools: list | None = None,
    model: str | None = None,
) -> object:
    """Chamada via Responses API — para gpt-5.x."""
    modelo = model or OPENAI_MODEL
    kwargs = {
        "model": modelo,
        "instructions": instructions,
        "input": input_items,
        # Structured Outputs: text.format em vez de response_format
        # Doc: "Instead of response_format, use text.format in Responses"
        "text": {
            "format": {
                "type": "json_schema",
                "name": "EnvelopeIA",
                "strict": True,
                "schema": _ENVELOPE_IA_SCHEMA,
            },
        },
        "store": False,
        # CRITICO: com store=False, reasoning items precisam de encrypted_content
        # para funcionar em multi-turn (loop de tool calls).
        # Doc: "reasoning.encrypted_content: Includes an encrypted version of
        # reasoning tokens... enables reasoning items to be used in multi-turn
        # conversations when using the Responses API statelessly"
        "include": ["reasoning.encrypted_content"],
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
        kwargs["parallel_tool_calls"] = False
        kwargs["reasoning"] = {"effort": "low"}

    return _client.responses.create(**kwargs)


def _executar_tool(nome: str, argumentos: dict, dispatch: dict | None = None) -> str:
    """Executa uma tool pelo nome e retorna o resultado serializado."""
    fn = (dispatch or _TOOL_DISPATCH).get(nome)
    if fn is None:
        return json.dumps({"erro": f"Tool '{nome}' não encontrada."})
    resultado = fn(**argumentos)
    return json.dumps(resultado, ensure_ascii=False, default=str)


# ==========================================================================
# LOOP DE TOOL CALLS — RESPONSES API
# ==========================================================================
# Doc: https://developers.openai.com/api/docs/guides/function-calling
#
# 1. Enviar input → receber output com function_call items
# 2. Executar cada function_call → criar function_call_output
# 3. Reenviar: output items originais + function_call_output como novo input
#    (inclui reasoning items — obrigatorio para GPT-5)
# 4. Repetir até não ter mais function_calls
# ==========================================================================

def _extrair_function_calls(output_items: list) -> list:
    """Extrai function_call items do output da Responses API."""
    calls = []
    for item in output_items:
        item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
        if item_type == "function_call":
            calls.append(item)
    return calls


def _chamar_agente_responses(
    contexto: ContextoExecutavel,
    mensagem_usuario: str,
    imagens: list[str] | None = None,
    tentativa: int = 1,
) -> tuple[str, list[dict]]:
    """Loop de tool calls via Responses API para gpt-5.x."""
    contexto_json = contexto.model_dump_json(indent=None)

    etapa_atual = contexto.sessao.etapa_atual
    if hasattr(etapa_atual, "value"):
        etapa_atual = etapa_atual.value
    prompt_sistema = construir_prompt(etapa_atual or "identificacao")
    logger.info("[V3-RESPONSES] prompt_dinamico etapa=%s chars=%d", etapa_atual, len(prompt_sistema))

    modelo = _escolher_modelo(tentativa, bool(imagens))
    logger.info("[ROUTER-RESPONSES] modelo=%s imagem=%s tentativa=%d", modelo, bool(imagens), tentativa)

    # instructions = system prompt + contexto (mais eficiente para cache)
    instructions = f"{prompt_sistema}\n\nCONTEXTO ATUAL DA SESSÃO (JSON):\n{contexto_json}"

    # Input no formato Responses API
    # Doc: "Pass a string with input or a list of messages"
    if imagens:
        user_content = [{"type": "input_text", "text": mensagem_usuario or "(sem texto)"}]
        for url in imagens:
            user_content.append({
                "type": "input_image",
                "image_url": url,
                "detail": "auto",
            })
        input_items = [{"role": "user", "content": user_content}]
    else:
        input_items = [{"role": "user", "content": mensagem_usuario}]

    pneus_encontrados: list[dict] = []
    tools = _get_tools_responses()

    sessao_id = contexto.sessao.sessao_id
    dispatch = {
        **_TOOL_DISPATCH,
        "buscar_pneus_por_moto": lambda termo_moto, posicao=None: buscar_pneus_por_moto(
            termo_moto=termo_moto, posicao=posicao, sessao_id=sessao_id
        ),
        "buscar_pneus": lambda **kwargs: buscar_pneus(**kwargs, sessao_id=sessao_id),
    }

    for round_num in range(MAX_TOOL_ROUNDS):
        response = _chamar_openai_responses(
            instructions=instructions,
            input_items=input_items,
            tools=tools,
            model=modelo,
        )

        output_items = response.output
        function_calls = _extrair_function_calls(output_items)

        if not function_calls:
            return response.output_text or "", pneus_encontrados

        # Doc: "include the original function_call item followed by
        # its function_call_output item (same call_id)"
        # Doc: "for reasoning models like GPT-5, any reasoning items
        # returned in model responses with tool calls must also be
        # passed back with tool call outputs"
        new_input_items = list(output_items)

        for fc in function_calls:
            fc_name = getattr(fc, "name", None) or (fc.get("name") if isinstance(fc, dict) else None)
            fc_args_raw = getattr(fc, "arguments", None) or (fc.get("arguments") if isinstance(fc, dict) else None)
            fc_call_id = getattr(fc, "call_id", None) or (fc.get("call_id") if isinstance(fc, dict) else None)

            args = json.loads(fc_args_raw) if isinstance(fc_args_raw, str) else (fc_args_raw or {})
            logger.debug("[RESPONSES] Tool call: %s(%s) call_id=%s", fc_name, args, fc_call_id)
            resultado = _executar_tool(fc_name, args, dispatch=dispatch)

            if fc_name in _TOOLS_COM_PNEU:
                novos = _extrair_pneus_de_resultado(resultado)
                pneus_encontrados.extend(novos)

            new_input_items.append({
                "type": "function_call_output",
                "call_id": fc_call_id,
                "output": resultado,
            })

        input_items = new_input_items

    logger.warning("[RESPONSES] Esgotou %d rounds de tool calls, chamando sem tools", MAX_TOOL_ROUNDS)
    response = _chamar_openai_responses(
        instructions=instructions,
        input_items=input_items,
        tools=None,
        model=modelo,
    )
    return response.output_text or "", pneus_encontrados


# ==========================================================================
# FUNÇÃO PÚBLICA — ROTEIA ENTRE COMPLETIONS E RESPONSES
# ==========================================================================

def chamar_agente(
    contexto: ContextoExecutavel,
    mensagem_usuario: str,
    imagens: list[str] | None = None,
    tentativa: int = 1,
) -> tuple[str, list[dict]]:
    """Envia mensagem do usuário + contexto para o modelo e processa tool calls.

    Roteamento automático:
    - gpt-5.x → Responses API
    - gpt-4o e anteriores → Chat Completions

    Retorna tupla:
        - texto bruto da resposta final do modelo (JSON do EnvelopeIA)
        - lista de pneus encontrados pelas tools (pneu_id, posicao, preco_venda)
    """
    modelo = _escolher_modelo(tentativa, bool(imagens))

    if _familia_gpt5(modelo):
        logger.info("[AGENTE] Usando Responses API para modelo=%s", modelo)
        return _chamar_agente_responses(
            contexto=contexto,
            mensagem_usuario=mensagem_usuario,
            imagens=imagens,
            tentativa=tentativa,
        )
    else:
        logger.info("[AGENTE] Usando Chat Completions para modelo=%s", modelo)
        return _chamar_agente_completions(
            contexto=contexto,
            mensagem_usuario=mensagem_usuario,
            imagens=imagens,
            tentativa=tentativa,
        )


def _chamar_agente_completions(
    contexto: ContextoExecutavel,
    mensagem_usuario: str,
    imagens: list[str] | None = None,
    tentativa: int = 1,
) -> tuple[str, list[dict]]:
    """Loop de tool calls via Chat Completions — código original sem alteração."""
    contexto_json = contexto.model_dump_json(indent=None)

    if imagens:
        user_content: list[dict] | str = [{"type": "text", "text": mensagem_usuario or "(sem texto)"}]
        for url in imagens:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": url, "detail": "auto"},
            })
    else:
        user_content = mensagem_usuario

    etapa_atual = contexto.sessao.etapa_atual
    if hasattr(etapa_atual, "value"):
        etapa_atual = etapa_atual.value
    prompt_sistema = construir_prompt(etapa_atual or "identificacao")
    logger.info("[V3] prompt_dinamico etapa=%s chars=%d", etapa_atual, len(prompt_sistema))

    modelo = _escolher_modelo(tentativa, bool(imagens))
    logger.info("[ROUTER] modelo=%s imagem=%s tentativa=%d", modelo, bool(imagens), tentativa)

    messages = [
        {"role": "system", "content": prompt_sistema},
        {"role": "system", "content": f"CONTEXTO ATUAL DA SESSÃO (JSON):\n{contexto_json}"},
        {"role": "user", "content": user_content},
    ]

    pneus_encontrados: list[dict] = []

    sessao_id = contexto.sessao.sessao_id
    dispatch = {
        **_TOOL_DISPATCH,
        "buscar_pneus_por_moto": lambda termo_moto, posicao=None: buscar_pneus_por_moto(
            termo_moto=termo_moto, posicao=posicao, sessao_id=sessao_id
        ),
        "buscar_pneus": lambda **kwargs: buscar_pneus(**kwargs, sessao_id=sessao_id),
    }

    for round_num in range(MAX_TOOL_ROUNDS):
        response = _chamar_openai_completions(messages, tools=TOOLS_SCHEMA, model=modelo)
        choice = response.choices[0]

        if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
            return choice.message.content or "", pneus_encontrados

        messages.append(choice.message)

        for tool_call in choice.message.tool_calls:
            args = json.loads(tool_call.function.arguments)
            logger.debug("Tool call: %s(%s)", tool_call.function.name, args)
            resultado = _executar_tool(tool_call.function.name, args, dispatch=dispatch)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": resultado,
            })

            if tool_call.function.name in _TOOLS_COM_PNEU:
                novos = _extrair_pneus_de_resultado(resultado)
                pneus_encontrados.extend(novos)

    logger.warning("Esgotou %d rounds de tool calls, chamando sem tools", MAX_TOOL_ROUNDS)
    response = _chamar_openai_completions(messages, model=modelo)
    return response.choices[0].message.content or "", pneus_encontrados
