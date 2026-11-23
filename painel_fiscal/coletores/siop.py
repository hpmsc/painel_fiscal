"""SIOP — dados abertos do orçamento (dotação e execução por Resultado Primário x GND).

A consulta ao SIOP é feita em R, pelo pacote orcamentoBR (scripts/coleta_siop.R), que
grava dados/siop/siop_rp_gnd_AAAA.csv. Este módulo lê esse CSV e gera as observações.
Quais RP contam como primários e discricionários vem do YAML (fontes.siop).
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Any

from ..dados import Observacao


def ler_csv(caminho: str | Path) -> list[dict[str, Any]]:
    with open(caminho, encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    for ln in linhas:
        for c in ("ploa", "loa", "loa_mais_credito", "empenhado", "liquidado", "pago"):
            ln[c] = float(ln[c]) if ln.get(c) not in (None, "") else 0.0
        ln["rp_cod"] = str(ln.get("rp_cod", "")).strip()
        ln["gnd_cod"] = str(ln.get("gnd_cod", "")).strip()
    return linhas


def _soma(linhas, coluna, rp=None, gnd=None) -> float:
    return sum(ln[coluna] for ln in linhas
               if (rp is None or ln["rp_cod"] in rp) and (gnd is None or ln["gnd_cod"] in gnd))


def converter(linhas: list[dict[str, Any]], exercicio: int, cfg: dict[str, Any],
              data_coleta: dt.date) -> list[Observacao]:
    rp_prim = {str(x) for x in cfg.get("rp_primarias", [1, 2, 3, 6, 7, 8, 9])}
    rp_disc = {str(x) for x in cfg.get("rp_discricionarias", [2, 3, 6, 7, 8, 9])}
    ref = dt.date(exercicio, 12, 31)
    fonte = "siop:orcamentoBR"

    def obs(indicador, valor, tipo, nota):
        return Observacao(indicador=indicador, valor=valor / 1e9, data_referencia=ref,
                          data_coleta=data_coleta, fonte=fonte, tipo=tipo, nota=nota)

    return [
        obs("investimentos_loa_bi", _soma(linhas, cfg.get("coluna_investimentos", "loa"), rp_prim, {"4"}),
            "projecao", "GND 4, despesas primárias, dotação da LOA"),
        obs("investimentos_ploa_bi", _soma(linhas, "ploa", rp_prim, {"4"}),
            "projecao", "GND 4, despesas primárias, projeto de lei (PLOA)"),
        obs("despesas_discricionarias_bi", _soma(linhas, "loa_mais_credito", rp_disc),
            "projecao", "RP " + ",".join(sorted(rp_disc)) + ", dotação atualizada"),
        obs("despesas_discricionarias_empenhadas_bi", _soma(linhas, "empenhado", rp_disc),
            "realizado", "RP " + ",".join(sorted(rp_disc)) + ", empenhado"),
    ]
