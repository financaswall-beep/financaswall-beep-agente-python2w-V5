"""Extracao de localidade + consulta de frete.

Redesign 12/04/2026 — fluxo simplificado em 4 camadas:
  1. area_entrega direto (municipio)
  2. bairro_municipio_cache (bairro→municipio, 625+ entradas)
  3. ViaCEP (se cliente informou CEP)
  4. Registrar LOCALIDADE_NAO_RESOLVIDA (IA pergunta ao cliente)

Sem web_search. Sem dependência externa obrigatória (ViaCEP é grátis e opcional).
"""
import logging
import re
from uuid import UUID

from agente_2w.db import contexto_repo, cliente_repo, area_entrega_repo, bairro_municipio_cache_repo
from agente_2w.constantes import ChaveContexto
from agente_2w.enums.enums import TipoDeVerdade, NivelConfirmacao, OrigemContexto
from agente_2w.schemas.contexto_conversa import ContextoConversaCreate

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Parse de endereco (mantido do código original — funciona bem)
# ──────────────────────────────────────────────────────────────────────────────

def _parsear_localidade_endereco(fato) -> tuple[str | None, str | None]:
    """Extrai (municipio, bairro) do fato endereco_entrega."""
    if fato.valor_json and isinstance(fato.valor_json, dict):
        d = fato.valor_json
        municipio = d.get("municipio") or d.get("cidade")
        bairro = d.get("bairro")
        return municipio or None, bairro or None

    texto = fato.valor_texto
    if not texto:
        return None, None

    partes = [p.strip() for p in texto.split(",") if p.strip()]

    def e_numero_ou_cep(s: str) -> bool:
        return bool(re.match(r'^\d[\d\-]*$', s))

    def e_sigla_estado(s: str) -> bool:
        return bool(re.match(r'^[A-Z]{2}$', s))

    bairro = None
    for parte in partes:
        if parte.lower().startswith("bairro "):
            bairro = parte[7:].strip()
            break

    _PREFIXOS_LOGRADOURO = ("rua ", "av ", "avenida ", "alameda ", "travessa ",
                             "estrada ", "rodovia ", "praca ", "largo ")
    candidatos = [
        p for p in partes
        if not e_numero_ou_cep(p)
        and not e_sigla_estado(p)
        and not any(p.lower().startswith(pref) for pref in _PREFIXOS_LOGRADOURO)
        and not p.lower().startswith("bairro ")
    ]

    municipio = candidatos[-1] if candidatos else None
    if bairro is None and len(candidatos) >= 2:
        bairro = candidatos[-2]

    return municipio or None, bairro or None


def _extrair_cep(texto: str | None) -> str | None:
    """Extrai CEP de texto livre (ex: "meu cep é 21610-210")."""
    if not texto:
        return None
    match = re.search(r'\b(\d{5})-?(\d{3})\b', texto)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Atualizar localidade no cadastro do cliente
# ──────────────────────────────────────────────────────────────────────────────

def _atualizar_localidade_cliente(sessao_id: UUID, cliente_id) -> None:
    """Persiste municipio/bairro no cliente a partir dos fatos da sessao."""
    try:
        cliente = cliente_repo.buscar_cliente_por_id(cliente_id)
        if not cliente:
            return

        campos: dict = {}

        # Sempre atualiza municipio/bairro com dados da sessao atual —
        # clientes recorrentes podem ter localidade desatualizada de sessoes anteriores.
        fato = contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.MUNICIPIO)
        if fato and fato.valor_texto:
            campos["municipio"] = fato.valor_texto

        fato = contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.BAIRRO)
        if fato and fato.valor_texto:
            campos["bairro"] = fato.valor_texto

        municipio_pendente = "municipio" not in campos
        bairro_pendente = "bairro" not in campos

        if municipio_pendente or bairro_pendente:
            fato_end = contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.ENDERECO_ENTREGA)
            if fato_end:
                municipio_parsed, bairro_parsed = _parsear_localidade_endereco(fato_end)
                if municipio_pendente and municipio_parsed:
                    campos["municipio"] = municipio_parsed
                if bairro_pendente and bairro_parsed:
                    campos["bairro"] = bairro_parsed

        if campos:
            cliente_repo.atualizar_cliente(cliente_id, campos)
            logger.info("Localidade cliente %s atualizada: %s", cliente_id, campos)
    except Exception:
        logger.exception("Falha ao atualizar localidade do cliente")


# ──────────────────────────────────────────────────────────────────────────────
# Consulta e registro de frete — fluxo redesenhado em 4 camadas
# ──────────────────────────────────────────────────────────────────────────────

def _consultar_e_registrar_frete(sessao_id: UUID) -> None:
    """Consulta frete para o municipio/bairro e registra como fato.

    Fluxo em 4 camadas (para na primeira que resolve):
      1. area_entrega direto (municipio)
      2. bairro_municipio_cache (bairro→municipio)
      3. ViaCEP (se CEP disponível)
      4. Registrar LOCALIDADE_NAO_RESOLVIDA (IA vai perguntar ao cliente)
    """
    try:
        # Skip se retirada
        fato_entrega = contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.TIPO_ENTREGA)
        if fato_entrega and fato_entrega.valor_texto == "retirada":
            for chave_frete in (ChaveContexto.FRETE_VALOR, ChaveContexto.FRETE_NAO_COBERTO):
                try:
                    contexto_repo.desativar_fato_anterior(sessao_id, chave_frete)
                except Exception:
                    pass
            return

        # Coletar municipio e bairro dos fatos da sessão
        municipio = None
        bairro = None

        for chave_mun in (ChaveContexto.MUNICIPIO, ChaveContexto.MUNICIPIO_ENTREGA):
            fato_municipio = contexto_repo.buscar_fato_ativo(sessao_id, chave_mun)
            if fato_municipio and fato_municipio.valor_texto:
                municipio = fato_municipio.valor_texto
                break

        fato_bairro = contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.BAIRRO)
        if fato_bairro and fato_bairro.valor_texto:
            bairro = fato_bairro.valor_texto

        # Também tentar extrair do endereço
        cep_texto = None
        if not municipio:
            fato_end = contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.ENDERECO_ENTREGA)
            if fato_end:
                municipio_parsed, bairro_parsed = _parsear_localidade_endereco(fato_end)
                municipio = municipio_parsed
                if bairro_parsed and not bairro:
                    bairro = bairro_parsed
                # Extrair CEP do endereço
                cep_texto = _extrair_cep(fato_end.valor_texto)

        # Sem dados de localidade → nada a fazer
        if not municipio and not bairro and not cep_texto:
            return

        # Se havia ambiguidade e agora temos municipio definido, limpar
        if municipio:
            try:
                contexto_repo.desativar_fato_anterior(sessao_id, ChaveContexto.MUNICIPIO_AMBIGUO)
            except Exception:
                pass
            try:
                contexto_repo.desativar_fato_anterior(sessao_id, ChaveContexto.LOCALIDADE_NAO_RESOLVIDA)
            except Exception:
                pass

        # Idempotencia: se frete já calculado pro mesmo município, não recalcula
        # EXCETO se resultado anterior foi frete_nao_coberto — sempre recalcular
        # para corrigir falsos negativos (ex: bug de normalização já corrigido).
        fato_frete = contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.FRETE_VALOR)
        fato_nao_coberto = contexto_repo.buscar_fato_ativo(sessao_id, ChaveContexto.FRETE_NAO_COBERTO)
        if fato_frete or fato_nao_coberto:
            municipio_anterior = None
            if fato_nao_coberto:
                municipio_anterior = fato_nao_coberto.valor_texto
            elif fato_frete and fato_frete.valor_json and isinstance(fato_frete.valor_json, dict):
                municipio_anterior = fato_frete.valor_json.get("municipio")

            # Se o resultado anterior foi frete_valor (positivo) e mesmo município, skip
            if fato_frete and not fato_nao_coberto and municipio and municipio_anterior and municipio_anterior.lower() == municipio.lower():
                return  # mesmo município, frete já calculado corretamente

            # Município mudou OU resultado anterior era frete_nao_coberto — limpar e recalcular
            for chave_frete in (ChaveContexto.FRETE_VALOR, ChaveContexto.FRETE_NAO_COBERTO):
                try:
                    contexto_repo.desativar_fato_anterior(sessao_id, chave_frete)
                except Exception:
                    pass

        # ── CAMADA 1: Lookup direto por município ──
        valor_frete = None
        municipio_resolvido = None

        if municipio:
            valor_frete = area_entrega_repo.consultar_frete(municipio)
            if valor_frete is not None:
                municipio_resolvido = municipio

        # ── CAMADA 2: Cache bairro→município ──
        if valor_frete is None:
            for termo in filter(None, [bairro, municipio]):
                resultados = bairro_municipio_cache_repo.buscar(termo)

                if len(resultados) == 1:
                    r = resultados[0]
                    if r["municipio"] is None:
                        # Cache negativo — fora de cobertura
                        _registrar_frete_nao_coberto(sessao_id, termo)
                        return
                    valor_frete = area_entrega_repo.consultar_frete(r["municipio"])
                    if valor_frete is not None:
                        municipio_resolvido = r["municipio"]
                        bairro = r["bairro"] or bairro
                        break

                elif len(resultados) > 1:
                    # Ambíguo — bairro existe em 2+ municípios
                    municipios_possiveis = [r["municipio"] for r in resultados if r["municipio"]]
                    _registrar_ambiguidade(sessao_id, termo, municipios_possiveis)
                    return  # IA vai perguntar ao cliente

        # ── CAMADA 3: ViaCEP (se CEP disponível) ──
        if valor_frete is None and cep_texto:
            try:
                from agente_2w.tools.viacep import consultar_cep
                dados_cep = consultar_cep(cep_texto)
                if dados_cep and dados_cep.get("municipio"):
                    valor_frete = area_entrega_repo.consultar_frete(dados_cep["municipio"])
                    if valor_frete is not None:
                        municipio_resolvido = dados_cep["municipio"]
                        bairro = dados_cep.get("bairro") or bairro
                        # Salvar no cache pra próxima vez
                        if bairro:
                            bairro_municipio_cache_repo.salvar(
                                termo_original=bairro,
                                bairro=bairro,
                                municipio=municipio_resolvido,
                                fonte="viacep",
                                sessao_id=sessao_id,
                            )
            except Exception:
                logger.warning("Falha no ViaCEP para CEP '%s'", cep_texto)

        # ── CAMADA 4: Não resolveu — registrar para IA perguntar ──
        if valor_frete is None and municipio_resolvido is None:
            # Se tem municipio mas não é coberto → frete_nao_coberto
            if municipio:
                _registrar_frete_nao_coberto(sessao_id, municipio)
            else:
                # Tem bairro mas nem o cache nem o ViaCEP resolveram
                _registrar_localidade_nao_resolvida(sessao_id, bairro or "desconhecido")
            return

        # ── Frete encontrado! Registrar ──
        _registrar_frete_valor(sessao_id, valor_frete, municipio_resolvido)

        # Salvar bairro no cache (BI + resolução futura)
        if bairro and municipio_resolvido:
            try:
                bairro_municipio_cache_repo.salvar(
                    termo_original=bairro,
                    bairro=bairro,
                    municipio=municipio_resolvido,
                    fonte="confirmado_frete",
                    sessao_id=sessao_id,
                )
            except Exception:
                logger.warning("Falha ao salvar cache para '%s'", bairro)

    except Exception:
        logger.exception("Falha ao consultar frete para sessao %s", sessao_id)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de registro de fatos
# ──────────────────────────────────────────────────────────────────────────────

def _registrar_frete_valor(sessao_id: UUID, valor_frete, municipio: str) -> None:
    """Registra fato frete_valor."""
    try:
        contexto_repo.desativar_fato_anterior(sessao_id, ChaveContexto.FRETE_NAO_COBERTO)
    except Exception:
        pass
    contexto_repo.registrar_fato(ContextoConversaCreate(
        sessao_chat_id=sessao_id,
        chave=ChaveContexto.FRETE_VALOR,
        valor_texto=str(valor_frete),
        valor_json={"municipio": municipio},
        tipo_de_verdade=TipoDeVerdade.validado_tool,
        nivel_confirmacao=NivelConfirmacao.nenhum,
        fonte=OrigemContexto.backend,
    ))
    logger.info("Frete registrado: %s = R$%s", municipio, valor_frete)


def _registrar_frete_nao_coberto(sessao_id: UUID, municipio: str) -> None:
    """Registra fato frete_nao_coberto."""
    try:
        contexto_repo.desativar_fato_anterior(sessao_id, ChaveContexto.FRETE_VALOR)
    except Exception:
        pass
    contexto_repo.registrar_fato(ContextoConversaCreate(
        sessao_chat_id=sessao_id,
        chave=ChaveContexto.FRETE_NAO_COBERTO,
        valor_texto=municipio,
        valor_json=None,
        tipo_de_verdade=TipoDeVerdade.validado_tool,
        nivel_confirmacao=NivelConfirmacao.nenhum,
        fonte=OrigemContexto.backend,
    ))
    logger.info("Municipio sem cobertura de entrega: %s", municipio)


def _registrar_ambiguidade(sessao_id: UUID, termo: str, municipios: list[str]) -> None:
    """Registra fato municipio_ambiguo."""
    contexto_repo.registrar_fato(ContextoConversaCreate(
        sessao_chat_id=sessao_id,
        chave=ChaveContexto.MUNICIPIO_AMBIGUO,
        valor_texto=", ".join(municipios),
        valor_json={"municipios": municipios, "termo": termo},
        tipo_de_verdade=TipoDeVerdade.validado_tool,
        nivel_confirmacao=NivelConfirmacao.nenhum,
        fonte=OrigemContexto.backend,
    ))
    logger.info("Municipio ambiguo para '%s': %s", termo, municipios)


def _registrar_localidade_nao_resolvida(sessao_id: UUID, termo: str) -> None:
    """Registra fato para que a IA pergunte o município ou CEP ao cliente."""
    try:
        contexto_repo.desativar_fato_anterior(sessao_id, ChaveContexto.LOCALIDADE_NAO_RESOLVIDA)
    except Exception:
        pass
    contexto_repo.registrar_fato(ContextoConversaCreate(
        sessao_chat_id=sessao_id,
        chave=ChaveContexto.LOCALIDADE_NAO_RESOLVIDA,
        valor_texto=termo,
        valor_json=None,
        tipo_de_verdade=TipoDeVerdade.validado_tool,
        nivel_confirmacao=NivelConfirmacao.nenhum,
        fonte=OrigemContexto.backend,
    ))
    logger.info("Localidade nao resolvida: '%s' — IA vai perguntar ao cliente", termo)
