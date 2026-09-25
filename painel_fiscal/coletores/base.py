"""HTTP e gravação do bruto em dados/brutos/AAAA-MM-DD/<fonte>/ (spec., seção 5, item 4)."""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

import requests

from ..config import RAIZ

DIR_BRUTOS = RAIZ / "dados" / "brutos"
TIMEOUT = 60
CABECALHOS = {"User-Agent": "painel-fiscal-uniao/0.1 (+https://github.com/hpmsc/painel_fiscal)"}


def obter_json(url: str, params: dict[str, Any] | None = None,
               sessao: requests.Session | None = None, timeout: int = TIMEOUT) -> Any:
    s = sessao or requests
    r = s.get(url, params=params, timeout=timeout, headers=CABECALHOS)
    r.raise_for_status()
    return r.json()


def gravar_bruto(fonte: str, nome: str, conteudo: Any, url: str,
                 params: dict[str, Any] | None = None,
                 hoje: dt.date | None = None, raiz: Path = DIR_BRUTOS) -> Path:
    hoje = hoje or dt.date.today()
    seguro = re.sub(r"[^A-Za-z0-9_.-]+", "_", nome)
    caminho = raiz / hoje.isoformat() / fonte / f"{seguro}.json"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump({"coletado_em": dt.datetime.now().isoformat(timespec="seconds"),
                   "url": url, "params": params or {}, "conteudo": conteudo},
                  f, ensure_ascii=False, indent=1)
    return caminho
