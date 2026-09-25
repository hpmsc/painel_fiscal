"""BCB — Sistema Gerenciador de Séries Temporais (SGS).

Códigos das séries vêm de `fontes.bcb_sgs.series` no YAML (⚠ confirmar no catálogo SGS).
Atenção ao sinal: nas séries de NFSP, valor positivo = déficit. O indicador
`primario_gc_abaixo_linha_bi` do painel usa superávit positivo; use `inverter_sinal`.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from ..dados import Observacao
from .base import gravar_bruto, obter_json

URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"


def _data_br(s: str) -> dt.date:
    d, m, a = s.split("/")
    return dt.date(int(a), int(m), int(d))


def fim_do_mes(d: dt.date) -> dt.date:
    prox = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return prox - dt.timedelta(days=1)


def converter(indicador: str, itens: list[dict[str, Any]], codigo: int,
              data_coleta: dt.date, fator: float = 1.0) -> list[Observacao]:
    """Converte a resposta do SGS ([{"data": "dd/mm/aaaa", "valor": "1,23"}...]).

    Séries mensais do SGS vêm datadas no dia 1º; a referência vira o fim do mês.
    """
    obs = []
    for it in itens:
        bruto = str(it["valor"]).strip()
        if not bruto:
            continue
        valor = float(bruto.replace(",", ".")) if "," in bruto else float(bruto)
        obs.append(Observacao(
            indicador=indicador, valor=valor * fator,
            data_referencia=fim_do_mes(_data_br(it["data"])),
            data_coleta=data_coleta, fonte=f"bcb_sgs:{codigo}", tipo="realizado",
        ))
    return obs


def coletar(indicador: str, codigo: int, data_inicial: dt.date,
            data_final: dt.date | None = None, fator: float = 1.0,
            sessao=None) -> list[Observacao]:
    url = URL.format(codigo=codigo)
    params = {"formato": "json", "dataInicial": data_inicial.strftime("%d/%m/%Y")}
    if data_final:
        params["dataFinal"] = data_final.strftime("%d/%m/%Y")
    itens = obter_json(url, params, sessao)
    hoje = dt.date.today()
    gravar_bruto("bcb_sgs", f"{indicador}_{codigo}", itens, url, params, hoje)
    return converter(indicador, itens, codigo, hoje, fator)
