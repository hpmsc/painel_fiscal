"""IBGE — SIDRA (IPCA, PIB). Tabelas/variáveis vêm do YAML (⚠ confirmar variáveis)."""
from __future__ import annotations

import datetime as dt
from typing import Any

from ..dados import Observacao
from .base import gravar_bruto, obter_json

URL = "https://apisidra.ibge.gov.br/values/t/{tabela}/n1/all/v/{variavel}/p/{periodos}"


def _data_periodo(codigo: str) -> dt.date:
    """'202606' (mês) ou '20261' (trimestre) → último dia do período."""
    from .bcb_sgs import fim_do_mes
    if len(codigo) == 6:
        return fim_do_mes(dt.date(int(codigo[:4]), int(codigo[4:]), 1))
    if len(codigo) == 5:
        return fim_do_mes(dt.date(int(codigo[:4]), 3 * int(codigo[4]), 1))
    raise ValueError(f"período SIDRA não reconhecido: {codigo}")


def converter(indicador: str, linhas: list[dict[str, Any]], tabela: int,
              data_coleta: dt.date, escala: float = 1.0,
              campo_periodo: str = "D3C") -> list[Observacao]:
    obs = []
    for ln in linhas[1:]:      # primeira linha é o cabeçalho
        v = ln.get("V", "")
        if v in ("", "-", "...", "X"):
            continue
        obs.append(Observacao(indicador=indicador, valor=float(v) * escala,
                              data_referencia=_data_periodo(ln[campo_periodo]),
                              data_coleta=data_coleta, fonte=f"ibge_sidra:{tabela}"))
    return obs


def coletar(indicador: str, tabela: int, variavel: int, periodos: str = "last 12",
            escala: float = 1.0, sessao=None) -> list[Observacao]:
    url = URL.format(tabela=tabela, variavel=variavel, periodos=periodos.replace(" ", "%20"))
    linhas = obter_json(url, None, sessao)
    hoje = dt.date.today()
    gravar_bruto("ibge_sidra", f"{indicador}_{tabela}_{variavel}", linhas, url, None, hoje)
    return converter(indicador, linhas, tabela, hoje, escala)
