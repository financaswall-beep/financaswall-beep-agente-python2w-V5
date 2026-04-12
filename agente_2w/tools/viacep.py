"""Consulta ViaCEP — resolve CEP para bairro/município/UF.

API gratuita, sem autenticação. Latência ~100-200ms.
Fallback: retorna None se CEP inválido ou API fora do ar.
"""
import logging
import re

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 5  # segundos
_URL = "https://viacep.com.br/ws/{cep}/json/"
_REGEX_CEP = re.compile(r"^\d{5}-?\d{3}$")


def consultar_cep(cep: str) -> dict | None:
    """Consulta ViaCEP e retorna dict com bairro, municipio, uf.

    Retorna None se:
    - CEP inválido (formato)
    - CEP não encontrado (API retorna {"erro": true})
    - Timeout / erro de rede

    Exemplo de retorno:
        {"bairro": "Bangu", "municipio": "Rio de Janeiro", "uf": "RJ"}
    """
    if not cep:
        return None

    cep_limpo = cep.strip().replace("-", "").replace(".", "").replace(" ", "")
    if not re.match(r"^\d{8}$", cep_limpo):
        return None

    cep_formatado = f"{cep_limpo[:5]}-{cep_limpo[5:]}"
    url = _URL.format(cep=cep_limpo)

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(url)
            resp.raise_for_status()
            dados = resp.json()

        if dados.get("erro"):
            logger.info("CEP %s nao encontrado no ViaCEP", cep_formatado)
            return None

        resultado = {
            "bairro": dados.get("bairro") or None,
            "municipio": dados.get("localidade") or None,
            "uf": dados.get("uf") or None,
        }
        logger.info("ViaCEP %s → %s / %s", cep_formatado, resultado["bairro"], resultado["municipio"])
        return resultado

    except Exception:
        logger.warning("Falha ao consultar ViaCEP para CEP %s", cep_formatado)
        return None
