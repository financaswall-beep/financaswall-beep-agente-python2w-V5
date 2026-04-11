"""Webhook server — ponte entre Chatwoot/WhatsApp e o agente 2W Pneus.

Endpoints:
    GET  /health          -> health check para Coolify (valida Supabase)
    POST /webhook/chatwoot -> recebe eventos do Chatwoot
    POST /internal/sync-etapa  -> Supabase DB webhook: sessao_chat UPDATE
    POST /internal/sync-pedido -> Supabase DB webhook: pedido INSERT
"""

import asyncio
import hashlib
import hmac
import logging
import os
import re
from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from threading import Lock

import tempfile

import httpx
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from openai import OpenAI

from agente_2w.config import SUPABASE_URL, OPENAI_MODEL, OPENAI_API_KEY
from agente_2w.db import sessao_repo
from agente_2w.engine.orquestrador import processar_turno, MENSAGEM_FALHA_SEGURA
from agente_2w.enums.enums import EtapaFluxo, StatusSessao
from agente_2w.schemas.sessao_chat import SessaoChatCreate

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("webhook")

CHATWOOT_BASE_URL = os.environ["CHATWOOT_BASE_URL"].rstrip("/")
CHATWOOT_API_TOKEN = os.environ["CHATWOOT_API_TOKEN"]
CHATWOOT_ACCOUNT_ID = os.environ["CHATWOOT_ACCOUNT_ID"]
CHATWOOT_INBOX_ID = os.getenv("CHATWOOT_INBOX_ID")
CHATWOOT_WEBHOOK_SECRET = os.getenv("CHATWOOT_WEBHOOK_SECRET", "")

# ---------------------------------------------------------------------------
# Dedup thread-safe (LRU)
# ---------------------------------------------------------------------------

_MAX_CACHE = 5000
_cache_lock = Lock()
_mensagens_processadas: OrderedDict[str, bool] = OrderedDict()


def _mensagem_ja_processada(message_id: str) -> bool:
    """Verifica e registra message_id de forma thread-safe."""
    if not message_id:
        return False
    with _cache_lock:
        if message_id in _mensagens_processadas:
            return True
        _mensagens_processadas[message_id] = True
        while len(_mensagens_processadas) > _MAX_CACHE:
            _mensagens_processadas.popitem(last=False)
    return False


# ---------------------------------------------------------------------------
# Lock por telefone (evita sessao duplicada)
# ---------------------------------------------------------------------------

_sessao_locks: dict[str, Lock] = {}
_sessao_locks_lock = Lock()


def _lock_para_telefone(telefone: str) -> Lock:
    with _sessao_locks_lock:
        if telefone not in _sessao_locks:
            _sessao_locks[telefone] = Lock()
        return _sessao_locks[telefone]


# ---------------------------------------------------------------------------
# Lock async por telefone (evita race condition no turno completo)
# Dois webhooks do mesmo contato nao processam em paralelo.
# ---------------------------------------------------------------------------

_turno_async_locks: dict[str, asyncio.Lock] = {}


def _get_turno_lock(telefone: str) -> asyncio.Lock:
    """Retorna (ou cria) um asyncio.Lock por telefone. Thread-safe via GIL do dict."""
    if telefone not in _turno_async_locks:
        _turno_async_locks[telefone] = asyncio.Lock()
    return _turno_async_locks[telefone]


# ---------------------------------------------------------------------------
# HTTP client (ciclo de vida correto via lifespan)
# ---------------------------------------------------------------------------

_http: httpx.AsyncClient | None = None


# ---------------------------------------------------------------------------
# Auto-resolve: fecha conversas com pedido + inatividade
# ---------------------------------------------------------------------------

async def _auto_resolver_conversas(horas: int = 72) -> int:
    """Resolve conversas no Chatwoot com pedido criado e sem atividade por `horas` horas.

    Apenas sessoes fechadas (pedido confirmado) com chatwoot_conv_id definido.
    Retorna numero de conversas resolvidas.
    """
    from agente_2w import chatwoot_sync
    from agente_2w.db.client import supabase

    try:
        corte = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
        res = (
            supabase.table("sessao_chat")
            .select("id, chatwoot_conv_id")
            .not_.is_("chatwoot_conv_id", "null")
            .lt("ultima_interacao_em", corte)
            .execute()
        )
        sessoes = res.data or []
    except Exception:
        logger.exception("Erro ao buscar sessoes para auto-resolve")
        return 0

    resolvidas = 0
    for s in sessoes:
        try:
            pedidos = (
                supabase.table("pedido")
                .select("id")
                .eq("sessao_chat_id", s["id"])
                .limit(1)
                .execute()
            )
            if not pedidos.data:
                continue
            await asyncio.to_thread(chatwoot_sync.resolver_conversa, s["chatwoot_conv_id"])
            logger.info("Auto-resolve: conv=%s sessao=%s", s["chatwoot_conv_id"], s["id"])
            resolvidas += 1
        except Exception:
            logger.warning("Falha ao auto-resolver conv=%s", s.get("chatwoot_conv_id"), exc_info=True)

    return resolvidas


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http
    _http = httpx.AsyncClient(timeout=30.0)
    logger.info("Agente 2W Pneus webhook iniciado")
    logger.info("  Chatwoot:    %s", CHATWOOT_BASE_URL)
    logger.info("  Account ID:  %s", CHATWOOT_ACCOUNT_ID)
    logger.info("  Supabase:    %s...", SUPABASE_URL[:40])
    logger.info("  Modelo:      %s", OPENAI_MODEL)

    # Inicia scheduler de auto-resolve (roda a cada 6 horas)
    async def _scheduler():
        await asyncio.sleep(300)  # aguarda 5min após startup antes do primeiro check
        while True:
            try:
                n = await _auto_resolver_conversas(horas=72)
                if n:
                    logger.info("Auto-resolve: %d conversa(s) resolvida(s)", n)
            except Exception:
                logger.exception("Erro no scheduler de auto-resolve")
            await asyncio.sleep(6 * 3600)

    task = asyncio.create_task(_scheduler())
    yield
    task.cancel()
    await _http.aclose()
    logger.info("Webhook encerrado")


app = FastAPI(title="Agente 2W Pneus - Webhook", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalizar_telefone(raw: str) -> str:
    """Extrai apenas digitos do telefone. Garante formato 55XXXXXXXXXXX."""
    digitos = re.sub(r"\D", "", raw or "")
    if digitos and not digitos.startswith("55"):
        digitos = "55" + digitos
    return digitos


def _extrair_telefone_do_identifier(identifier: str) -> str:
    """Extrai telefone do identifier do Baileys.

    Baileys envia '5534999999999@s.whatsapp.net' — extrai so o numero.
    """
    if not identifier:
        return ""
    return identifier.split("@")[0]


def _verificar_assinatura(body: bytes, timestamp: str, signature: str) -> bool:
    """Valida HMAC-SHA256 do webhook no formato do Chatwoot."""
    if not CHATWOOT_WEBHOOK_SECRET:
        return True
    if not timestamp or not signature:
        return False
    message = f"{timestamp}.".encode() + body
    expected = "sha256=" + hmac.new(
        CHATWOOT_WEBHOOK_SECRET.encode(), message, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _obter_ou_criar_sessao(telefone: str) -> object:
    """Busca sessao ativa pelo telefone ou cria nova (thread-safe).

    Retorna o objeto SessaoChat completo para acesso a .id e outros campos.
    """
    lock = _lock_para_telefone(telefone)
    with lock:
        sessao = sessao_repo.buscar_sessao_ativa_por_contato(telefone)
        if sessao:
            logger.debug(
                "Sessao existente: %s (etapa=%s)",
                sessao.id, sessao.etapa_atual.value,
            )
            return sessao

        sessao = sessao_repo.criar_sessao(SessaoChatCreate(
            canal="whatsapp",
            contato_externo=telefone,
            etapa_atual=EtapaFluxo.identificacao,
            status_sessao=StatusSessao.ativa,
        ))
        logger.info("Nova sessao criada: %s para %s", sessao.id, telefone)
        return sessao


async def _enviar_mensagem_chatwoot(conversation_id: int, texto: str) -> None:
    """Envia mensagem de resposta via API do Chatwoot."""
    url = (
        f"{CHATWOOT_BASE_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}"
        f"/conversations/{conversation_id}/messages"
    )
    headers = {"api_access_token": CHATWOOT_API_TOKEN}
    payload = {
        "content": texto,
        "message_type": "outgoing",
        "private": False,
    }
    try:
        resp = await _http.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        logger.info(
            "Resposta enviada: conv=%s (%d chars)", conversation_id, len(texto),
        )
    except httpx.HTTPStatusError as e:
        logger.error(
            "Erro ao enviar para Chatwoot: %s - %s",
            e.response.status_code, e.response.text,
        )
    except Exception as e:
        logger.error("Erro de conexao com Chatwoot: %s", e)


async def _enviar_foto_chatwoot(conversation_id: int, foto_url: str) -> None:
    """Baixa imagem e envia como anexo real no Chatwoot via multipart.

    Fallback: se o download ou upload falhar, envia a URL como texto.
    """
    try:
        img_resp = await _http.get(foto_url, timeout=15.0)
        img_resp.raise_for_status()
        content_type = img_resp.headers.get("content-type", "image/webp")
        filename = foto_url.split("/")[-1].split("?")[0] or "pneu.jpg"
        url = (
            f"{CHATWOOT_BASE_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}"
            f"/conversations/{conversation_id}/messages"
        )
        headers = {"api_access_token": CHATWOOT_API_TOKEN}
        files = {"attachments[]": (filename, img_resp.content, content_type)}
        data = {"message_type": "outgoing", "private": "false"}
        resp = await _http.post(url, headers=headers, files=files, data=data)
        resp.raise_for_status()
        logger.info("Foto enviada como anexo: conv=%s filename=%s", conversation_id, filename)
    except Exception as e:
        logger.error("Falha ao enviar foto como anexo, enviando URL: %s", e)
        await _enviar_mensagem_chatwoot(conversation_id, foto_url)


# ---------------------------------------------------------------------------
# Transcricao de audio (Whisper / OpenAI)
# ---------------------------------------------------------------------------

_openai_client = OpenAI(api_key=OPENAI_API_KEY, timeout=60)


async def _transcrever_audio(audio_url: str) -> str:
    """Baixa audio pela URL e transcreve via Whisper da OpenAI.

    Retorna o texto transcrito ou string vazia se falhar.
    """
    try:
        resp = await _http.get(audio_url, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        logger.error("Falha ao baixar audio: %s", e)
        return ""

    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            transcricao = await asyncio.to_thread(
                lambda: _openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="pt",
                )
            )

        os.unlink(tmp_path)
        texto = transcricao.text.strip()
        logger.info("Audio transcrito (%d chars): '%s'", len(texto), texto[:80])
        return texto

    except Exception as e:
        logger.error("Falha ao transcrever audio: %s", e)
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    """Health check com validacao de conectividade Supabase."""
    try:
        from agente_2w.db.client import supabase
        supabase.table("sessao_chat").select("id").limit(1).execute()
        return {"status": "ok", "service": "agente-2w-pneus"}
    except Exception as e:
        logger.error("Health check falhou: %s", e)
        raise HTTPException(status_code=503, detail="Supabase indisponivel")


@app.get("/version")
async def version():
    """Retorna versao do codigo deployado."""
    return {"version": "2026-04-11b", "chatwoot_conv_id_fix": True}


@app.post("/webhook/chatwoot")
async def chatwoot_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recebe webhooks do Chatwoot para mensagens recebidas."""

    # 1. Validar assinatura HMAC
    body = await request.body()
    signature = request.headers.get("x-chatwoot-signature", "")
    timestamp = request.headers.get("x-chatwoot-timestamp", "")
    if CHATWOOT_WEBHOOK_SECRET and not _verificar_assinatura(body, timestamp, signature):
        logger.warning("Assinatura invalida no webhook")
        raise HTTPException(status_code=401, detail="Assinatura invalida")

    data = await request.json()

    # 2. Filtrar: processar eventos de mensagem recebida do Chatwoot
    event = data.get("event")
    if event not in {"message_created", "message_incoming"}:
        logger.info("Webhook ignorado: event=%s", event)
        return {"status": "ignored", "event": event}

    # 3. Filtrar: so processar mensagens incoming (do cliente)
    message_type = data.get("message_type")
    if message_type not in (0, "incoming"):
        logger.info("Webhook ignorado: message_type=%s", message_type)
        return {"status": "ignored", "reason": "not_incoming"}

    # 4. Ignorar mensagens privadas (notas internas)
    if data.get("private", False):
        logger.info("Webhook ignorado: mensagem privada")
        return {"status": "ignored", "reason": "private"}

    # 5. Extrair dados basicos
    content = (data.get("content") or "").strip()
    conversation = data.get("conversation", {})
    conversation_id = conversation.get("id")
    inbox_id = conversation.get("inbox_id") or data.get("inbox", {}).get("id")
    sender = data.get("sender", {})
    sender_meta = conversation.get("meta", {}).get("sender", {})
    chatwoot_contact_id = sender.get("id") or sender_meta.get("id")

    # 6. Gerar message_id robusto
    raw_id = data.get("id")
    message_id = (
        str(raw_id) if raw_id
        else f"cw_{conversation_id}_{datetime.now(timezone.utc).timestamp()}"
    )

    # 7. Filtrar por inbox (opcional)
    if CHATWOOT_INBOX_ID and str(inbox_id) != str(CHATWOOT_INBOX_ID):
        logger.info(
            "Webhook ignorado: inbox_id=%s esperado=%s",
            inbox_id,
            CHATWOOT_INBOX_ID,
        )
        return {"status": "ignored", "reason": "wrong_inbox"}

    # 8. Extrair telefone — varios locais possiveis
    telefone_raw = (
        sender.get("phone_number")
        or sender_meta.get("phone_number")
        or _extrair_telefone_do_identifier(sender.get("identifier", ""))
        or _extrair_telefone_do_identifier(sender_meta.get("identifier", ""))
        or conversation.get("contact", {}).get("phone_number")
        or ""
    )
    telefone = _normalizar_telefone(telefone_raw)

    if not telefone:
        telefone = f"chatwoot_{conversation_id}"
        logger.warning("Telefone nao encontrado, usando fallback: %s", telefone)

    # 9. Dedup
    if _mensagem_ja_processada(message_id):
        return {"status": "ignored", "reason": "duplicate"}

    # 10. Extrair imagens e audios dos attachments
    # Chatwoot pode mandar attachments em dois lugares diferentes:
    # - data["attachments"] → formato padrao
    # - data["content_attributes"]["attachments"] → formato Baileys/WhatsApp (audio, video)
    attachments = data.get("attachments") or []
    content_attributes = data.get("content_attributes") or {}
    attachments_ca = content_attributes.get("attachments") or []
    if attachments_ca and not attachments:
        attachments = attachments_ca
        logger.warning("Attachments vindos de content_attributes (Baileys): %d item(s)", len(attachments))

    # Log de diagnostico em WARNING para garantir visibilidade independente do log level
    if attachments:
        for idx, a in enumerate(attachments):
            logger.warning("DIAG Attachment[%d]: %s", idx, {k: str(v)[:200] for k, v in a.items()})
    else:
        # Sem attachments em nenhum lugar — logar payload completo para depuracao
        _diag = {k: str(v)[:300] for k, v in data.items() if k not in ("conversation",)}
        logger.warning("DIAG sem-attachment: content=%r content_attributes=%r payload_keys=%s",
                       content, content_attributes, list(data.keys()))

    imagens = [
        a.get("data_url") or a.get("url", "")
        for a in attachments
        if str(a.get("file_type", "")).lower() in ("image", "image_file")
    ]
    imagens = [u for u in imagens if u]

    _AUDIO_FILE_TYPES = {"audio", "audio_file", "audio/ogg", "audio/mpeg", "audio/mp4", "voice"}
    audios = [
        a.get("data_url") or a.get("url", "")
        for a in attachments
        if str(a.get("file_type", "")).lower() in _AUDIO_FILE_TYPES
        or str(a.get("file_type", "")).lower().startswith("audio")
    ]
    audios = [u for u in audios if u]

    # Fallback agressivo: qualquer attachment com URL que nao seja imagem → tenta como audio
    if not audios and not content and attachments:
        fallback_urls = [
            a.get("data_url") or a.get("url", "")
            for a in attachments
            if (a.get("data_url") or a.get("url", ""))
            and str(a.get("file_type", "")).lower() not in ("image", "image_file")
        ]
        if fallback_urls:
            logger.warning(
                "DIAG Fallback audio: transcrevendo %d attachment(s) com file_type nao reconhecido",
                len(fallback_urls),
            )
            audios = fallback_urls

    # 11. Texto vazio sem imagens e sem audios — pedir descricao
    if not content and not imagens and not audios:
        content = "Recebi seu arquivo! Pode descrever o que precisa?"

    logger.info(
        "Mensagem recebida: conv=%s tel=%s msg_id=%s texto='%s' imagens=%d audios=%d",
        conversation_id, telefone, message_id, content[:80], len(imagens), len(audios),
    )

    # 12. Processar em background — retorna 200 imediato pro Chatwoot
    async def _processar_e_responder():
        nonlocal content
        # Lock por telefone: garante que dois webhooks do mesmo contato
        # nao processam em paralelo (evita race condition de contexto).
        async with _get_turno_lock(telefone):
            try:
                # 12a. Transcrever audios (se houver)
                for audio_url in audios:
                    texto_audio = await _transcrever_audio(audio_url)
                    if texto_audio:
                        content = f"{content} {texto_audio}".strip() if content else texto_audio

                sessao = await asyncio.to_thread(_obter_ou_criar_sessao, telefone)

                # Persistir IDs do Chatwoot na sessao (idempotente, fail-safe)
                if conversation_id and not sessao.chatwoot_conv_id:
                    await asyncio.to_thread(
                        sessao_repo.salvar_chatwoot_ids,
                        sessao.id, conversation_id, chatwoot_contact_id,
                    )

                # Typing indicator — mostra "digitando..." enquanto IA processa
                from agente_2w import chatwoot_sync
                await asyncio.to_thread(chatwoot_sync.ativar_typing, conversation_id)

                resposta = await asyncio.to_thread(
                    processar_turno,
                    sessao.id,
                    content,
                    message_id_externo=message_id,
                    imagens=imagens or None,
                    chatwoot_conv_id=conversation_id,
                    chatwoot_contact_id=chatwoot_contact_id,
                )

                # Enviar texto
                if resposta.texto:
                    await _enviar_mensagem_chatwoot(conversation_id, resposta.texto)

                # Enviar fotos
                for foto_url in resposta.fotos or []:
                    await _enviar_foto_chatwoot(conversation_id, foto_url)

            except Exception as e:
                logger.error("Erro ao processar mensagem: %s", e, exc_info=True)
                await _enviar_mensagem_chatwoot(conversation_id, MENSAGEM_FALHA_SEGURA)

    background_tasks.add_task(_processar_e_responder)

    return {"status": "processing", "message_id": message_id}


# ---------------------------------------------------------------------------
# Endpoints internos — Supabase Database Webhooks
# ---------------------------------------------------------------------------

@app.post("/internal/sync-etapa")
async def sync_etapa(request: Request):
    """Chamado pelo Supabase quando sessao_chat.etapa_atual muda.

    Payload Supabase webhook (format: pg_net):
    {
      "type": "UPDATE",
      "table": "sessao_chat",
      "record": { ...row atual... },
      "old_record": { ...row anterior... }
    }
    """
    from agente_2w import chatwoot_sync

    body = await request.json()
    record = body.get("record") or {}
    conv_id = record.get("chatwoot_conv_id")
    etapa = record.get("etapa_atual")

    if not conv_id or not etapa:
        return {"status": "skipped", "reason": "sem conv_id ou etapa"}

    chatwoot_sync.sincronizar_etapa(conv_id, etapa)
    logger.info("sync-etapa: conv=%s etapa=%s", conv_id, etapa)
    return {"status": "ok"}


@app.post("/internal/sync-pedido")
async def sync_pedido(request: Request):
    """Chamado pelo Supabase quando um pedido é inserido.

    Payload Supabase webhook:
    {
      "type": "INSERT",
      "table": "pedido",
      "record": { ...row do pedido... }
    }
    """
    from agente_2w import chatwoot_sync
    from agente_2w.db import sessao_repo

    body = await request.json()
    record = body.get("record") or {}
    sessao_id = record.get("sessao_chat_id")
    numero_pedido = record.get("numero_pedido")
    valor_total = record.get("valor_total")

    if not sessao_id or not numero_pedido:
        return {"status": "skipped", "reason": "sem sessao_id ou numero_pedido"}

    sessao = sessao_repo.buscar_sessao_por_id(sessao_id)
    if not sessao or not sessao.chatwoot_conv_id:
        return {"status": "skipped", "reason": "sessao sem chatwoot_conv_id"}

    chatwoot_sync.sincronizar_pedido_criado(
        sessao.chatwoot_conv_id, numero_pedido, valor_total or 0,
    )
    logger.info("sync-pedido: conv=%s pedido=#%s", sessao.chatwoot_conv_id, numero_pedido)
    return {"status": "ok"}


@app.post("/internal/auto-resolve")
async def auto_resolve(request: Request):
    """Dispara manualmente o auto-resolve de conversas antigas.

    Query param opcional: horas (default=72). Use horas=0 para testar (resolve tudo).
    Exemplo: POST /internal/auto-resolve?horas=0
    """
    horas_str = request.query_params.get("horas", "72")
    try:
        horas = int(horas_str)
    except ValueError:
        horas = 72

    n = await _auto_resolver_conversas(horas=horas)
    logger.info("auto-resolve manual: %d conversa(s) resolvida(s) (horas=%d)", n, horas)
    return {"status": "ok", "resolvidas": n, "horas": horas}
