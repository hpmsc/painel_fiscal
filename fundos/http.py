"""Download com novas tentativas (mesma política de painel_fiscal.coletores.base)."""
from __future__ import annotations

import time

import requests

TIMEOUT = 120
CABECALHOS = {"User-Agent": "painel-fundos/0.1 (+https://github.com/hpmsc/painel_fiscal)"}
TENTATIVAS = 4
ESPERA_S = 5


class NaoEncontrado(Exception):
    """A fonte respondeu 404: o arquivo ainda não foi publicado ou mudou de lugar."""


def baixar(url: str, params: dict | None = None, sessao=None, timeout: int = TIMEOUT) -> bytes:
    """GET que devolve o corpo em bytes; 404 vira NaoEncontrado, 5xx/429/rede tenta de novo."""
    s = sessao or requests
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            r = s.get(url, params=params, timeout=timeout, headers=CABECALHOS)
            if r.status_code == 404:
                raise NaoEncontrado(url)
            if r.status_code != 429 and r.status_code < 500:
                r.raise_for_status()
                return r.content
            if tentativa == TENTATIVAS:
                r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            if tentativa == TENTATIVAS:
                raise
        time.sleep(ESPERA_S * 2 ** (tentativa - 1))
    raise RuntimeError("inalcançável")
