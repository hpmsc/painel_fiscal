"""STN — Resultado do Tesouro Nacional (RTN), via CKAN do Tesouro Transparente.

Aqui só localizamos e baixamos a planilha (xlsx) da série histórica, gravando-a
com a data de publicação. O parser das abas (primário acima da linha, despesa
sujeita ao limite) depende do layout da planilha vigente e fica como próxima
etapa — ver docs/desenho_painel.md, "Roadmap".
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import requests

from .base import CABECALHOS, DIR_BRUTOS, TIMEOUT, gravar_bruto, obter_json

URL_BUSCA = "https://www.tesourotransparente.gov.br/ckan/api/3/action/package_search"


def listar_recursos(consulta: str = "resultado do tesouro nacional", sessao=None) -> list[dict[str, Any]]:
    resp = obter_json(URL_BUSCA, {"q": consulta, "rows": 20}, sessao)
    gravar_bruto("stn_rtn", "package_search", resp, URL_BUSCA, {"q": consulta})
    recursos = []
    for pacote in resp.get("result", {}).get("results", []):
        for r in pacote.get("resources", []):
            recursos.append({
                "pacote": pacote.get("title"), "nome": r.get("name"), "url": r.get("url"),
                "formato": (r.get("format") or "").lower(),
                "atualizado": r.get("last_modified") or r.get("created"),
            })
    return recursos


def baixar(recurso: dict[str, Any], sessao=None) -> Path:
    s = sessao or requests
    r = s.get(recurso["url"], timeout=TIMEOUT, headers=CABECALHOS)
    r.raise_for_status()
    destino = DIR_BRUTOS / dt.date.today().isoformat() / "stn_rtn" / Path(recurso["url"]).name
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(r.content)
    return destino
