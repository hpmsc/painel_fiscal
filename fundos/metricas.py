"""Indicadores no formato da Matriz de Indicadores, calculados das cotas diárias.

Convenções (frações, 0,05 = 5%):
- retorno da janela: cota no fim ÷ cota no último dia útil antes do início − 1;
- volatilidade: desvio-padrão amostral dos retornos diários × √252;
- drawdown: pior queda da cota frente ao maior valor anterior dentro da janela
  (o ponto de partida conta como pico);
- Sharpe 12m: (retorno 12m − CDI 12m) ÷ volatilidade 12m.
Uma janela sem cota no seu início (fundo mais novo que ela) fica None, nunca parcial.
"""
from __future__ import annotations

import bisect
import datetime as dt
import math
from collections import defaultdict
from typing import Sequence

from .cvm import Cota

Serie = list[tuple[dt.date, float]]
JANELAS = {"12": 12, "24": 24, "36": 36}
MIN_DIAS_VOL = 15
MAX_DEFASAGEM_DIAS = 7


def menos_meses(d: dt.date, n: int) -> dt.date:
    a, m = divmod(d.year * 12 + d.month - 1 - n, 12)
    m += 1
    ultimo = (dt.date(a + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
    return dt.date(a, m, min(d.day, ultimo))


def _ponto_ate(datas: list[dt.date], d: dt.date) -> int | None:
    i = bisect.bisect_right(datas, d) - 1
    return i if i >= 0 else None


def janela(serie: Serie, inicio: dt.date, fim: dt.date) -> dict[str, float | None]:
    """Retorno, volatilidade e drawdown entre o fechamento de `inicio` e o de `fim`."""
    vazio = {"r": None, "v": None, "d": None}
    if not serie:
        return vazio
    datas = [d for d, _ in serie]
    i0, i1 = _ponto_ate(datas, inicio), _ponto_ate(datas, fim)
    if i0 is None or i1 is None or i1 <= i0 or serie[i1][0] <= inicio:
        return vazio
    if (fim - serie[i1][0]).days > MAX_DEFASAGEM_DIAS:   # fundo parou de informar
        return vazio
    trecho = [v for _, v in serie[i0:i1 + 1]]
    diarios = [b / a - 1 for a, b in zip(trecho, trecho[1:])]
    vol = None
    if len(diarios) >= MIN_DIAS_VOL:
        media = sum(diarios) / len(diarios)
        vol = math.sqrt(sum((x - media) ** 2 for x in diarios) / (len(diarios) - 1) * 252)
    pico, pior = trecho[0], 0.0
    for v in trecho:
        pico = max(pico, v)
        pior = min(pior, v / pico - 1)
    return {"r": trecho[-1] / trecho[0] - 1, "v": vol, "d": pior}


def _r4(x: float | None) -> float | None:
    return None if x is None else round(x, 4)


def indicadores(serie: Serie, data_base: dt.date, anos: Sequence[int], meses: Sequence[str],
                cdi: Serie | None = None) -> dict:
    out: dict = {}
    for k, n in JANELAS.items():
        j = janela(serie, menos_meses(data_base, n), data_base)
        out["r" + k], out["v" + k], out["dd" + k] = _r4(j["r"]), _r4(j["v"]), _r4(j["d"])
    fim_mes_ant = data_base.replace(day=1) - dt.timedelta(days=1)
    for k, ini in (("mes", fim_mes_ant), ("ano", dt.date(data_base.year - 1, 12, 31))):
        j = janela(serie, ini, data_base)
        out["r" + k], out["v" + k], out["dd" + k] = _r4(j["r"]), _r4(j["v"]), _r4(j["d"])
    por_ano = [janela(serie, dt.date(a - 1, 12, 31), dt.date(a, 12, 31)) for a in anos]
    out["ry"] = [_r4(j["r"]) for j in por_ano]
    out["vy"] = [_r4(j["v"]) for j in por_ano]
    out["dy"] = [_r4(j["d"]) for j in por_ano]
    rm = []
    for m in meses:
        a, mm = int(m[:4]), int(m[5:7])
        fim = (dt.date(a + (mm == 12), mm % 12 + 1, 1) - dt.timedelta(days=1))
        rm.append(_r4(janela(serie, dt.date(a, mm, 1) - dt.timedelta(days=1), fim)["r"]))
    out["rm"] = rm
    if cdi and out["r12"] is not None and out["v12"]:
        c12 = janela(cdi, menos_meses(data_base, 12), data_base)["r"]
        out["sh"] = None if c12 is None else round((out["r12"] - c12) / out["v12"], 2)
    return out


def series_por_fundo(cotas: list[Cota]) -> dict[str, list[Cota]]:
    """Uma série por CNPJ. Havendo informe da classe (subclasse vazia) fica ele; senão a
    subclasse com mais dias informados (⚠ revisar fundos com subclasses de taxas diferentes)."""
    grupos: dict[tuple[str, str], dict[dt.date, Cota]] = defaultdict(dict)
    for c in cotas:
        grupos[(c.cnpj, c.subclasse)][c.data] = c
    escolhida: dict[str, tuple[str, str]] = {}
    for chave in grupos:
        cnpj, sub = chave
        atual = escolhida.get(cnpj)
        if atual is None or (sub == "" and atual[1] != "") or (
                (sub == "") == (atual[1] == "") and len(grupos[chave]) > len(grupos[atual])):
            escolhida[cnpj] = chave
    return {cnpj: sorted(grupos[ch].values(), key=lambda c: c.data) for cnpj, ch in escolhida.items()}


def complementos(serie: list[Cota], data_base: dt.date) -> dict:
    """PL, cotistas e captação líquida em 12 meses, do informe diário."""
    ate = [c for c in serie if c.data <= data_base]
    if not ate:
        return {}
    ult = ate[-1]
    ini = menos_meses(data_base, 12)
    fluxo = [c for c in ate if c.data > ini]
    cap = sum((c.captacao or 0) - (c.resgate or 0) for c in fluxo) if fluxo else None
    return {"pl": ult.pl, "cotistas": ult.cotistas, "cap12": None if cap is None else round(cap, 2),
            "ult_cota": ult.data.isoformat()}


def montar_base(cotas: list[Cota], universo: list[dict], cdi: Serie, data_base: dt.date,
                ano_inicial: int = 2010, cadastro: dict | None = None) -> dict:
    """Base completa: anos fechados em `years` (como na Matriz) e 36 meses em `meses`."""
    anos = list(range(ano_inicial, data_base.year))
    meses = []
    d = data_base.replace(day=1)
    for _ in range(36):
        d = (d - dt.timedelta(days=1)).replace(day=1)
        meses.append(d.strftime("%Y-%m"))
    meses.reverse()
    series = series_por_fundo(cotas)
    fundos, sem_dado = [], []
    for u in universo:
        s = series.get(u["cnpj14"])
        if not s:
            sem_dado.append(u["cnpj"])
            continue
        f = {"c": u["cnpj"], "n": u.get("nome", ""), **indicadores([(c.data, c.cota) for c in s], data_base,
                                                                     anos, meses, cdi),
             **complementos(s, data_base)}
        cad = (cadastro or {}).get(u["cnpj14"])
        if cad:
            f["cvm"] = {k: cad[k] for k in ("situacao", "classificacao_anbima", "taxa_adm", "taxa_perfm",
                                            "data_inicio") if cad.get(k) not in (None, "")}
        fundos.append(f)
    return {"data_base": data_base.isoformat(), "years": anos, "meses": meses, "funds": fundos,
            "bench": {"CDI": indicadores(cdi, data_base, anos, meses)} if cdi else {},
            "sem_dado": sem_dado, "fonte": "CVM informe diário; CDI: BCB SGS 12"}
