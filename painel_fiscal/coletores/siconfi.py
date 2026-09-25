"""SICONFI (API de dados abertos do Tesouro) — RREO e RGF da União.

Endpoints: .../ords/siconfi/tt/rreo e .../tt/rgf. Paginação ORDS por `offset`
(`hasMore`, `limit`). O `id_ente` da União vem do YAML (⚠ confirmar; usualmente 1).

A extração conta/coluna → indicador fica em config/mapeamento_siconfi.yaml,
porque os rótulos mudam entre versões do MDF (Manual de Demonstrativos Fiscais).
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any, Iterable

from ..dados import Observacao
from .base import gravar_bruto, obter_json

URLS = {
    "rreo": "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo",
    "rgf": "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rgf",
}

# Fim do período: RREO bimestral (1..6) e RGF quadrimestral (1..3).
MESES_FIM = {"rreo": {i: 2 * i for i in range(1, 7)}, "rgf": {i: 4 * i for i in range(1, 4)}}


def buscar_itens(demonstrativo: str, params: dict[str, Any], sessao=None,
                 max_paginas: int = 200) -> list[dict[str, Any]]:
    url = URLS[demonstrativo]
    itens, offset = [], 0
    for _ in range(max_paginas):
        pagina = obter_json(url, {**params, "offset": offset}, sessao)
        lote = pagina.get("items", [])
        itens.extend(lote)
        if not pagina.get("hasMore"):
            break
        offset += pagina.get("limit") or len(lote) or 1
    else:
        raise RuntimeError(f"SICONFI: paginação excedeu {max_paginas} páginas")
    return itens


def data_fim_periodo(demonstrativo: str, exercicio: int, periodo: int) -> dt.date:
    from .bcb_sgs import fim_do_mes
    return fim_do_mes(dt.date(exercicio, MESES_FIM[demonstrativo][periodo], 1))


def extrair(itens: Iterable[dict[str, Any]], mapeamento: list[dict[str, Any]],
            data_referencia: dt.date, data_coleta: dt.date, fonte: str,
            periodo: int | None = None) -> list[Observacao]:
    """Aplica o mapeamento. Cada entrada tem `indicador` e filtros opcionais:
    `anexo` e `cod_conta` (exatos); `conta`, `coluna` e `instituicao` (regex, sem
    diferenciar maiúsculas; `{periodo}` em `coluna` vira o número do período);
    `somar` (soma as linhas que casarem) e `escala` (padrão 1e-9: R$ → R$ bi)."""
    itens = list(itens)
    obs = []
    for m in mapeamento:
        def _re(chave):
            if not m.get(chave):
                return None
            padrao = m[chave].replace("{periodo}", str(periodo)) if periodo is not None else m[chave]
            return re.compile(padrao, re.I)
        re_conta, re_col, re_inst = _re("conta"), _re("coluna"), _re("instituicao")
        achados = [
            it for it in itens
            if (not m.get("anexo") or it.get("anexo", m["anexo"]) == m["anexo"])
            and (not m.get("cod_conta") or it.get("cod_conta") == m["cod_conta"])
            and (re_conta is None or re_conta.search(str(it.get("conta", ""))))
            and (re_col is None or re_col.search(str(it.get("coluna", ""))))
            and (re_inst is None or re_inst.search(str(it.get("instituicao", ""))))
        ]
        if not achados:
            continue
        if len(achados) > 1 and not m.get("somar", False):
            raise ValueError(
                f"{m['indicador']}: {len(achados)} linhas casam com o mapeamento; "
                "refine conta/coluna ou use somar: true")
        valor = sum(float(it["valor"]) for it in achados) * m.get("escala", 1e-9)
        obs.append(Observacao(indicador=m["indicador"], valor=valor,
                              data_referencia=data_referencia, data_coleta=data_coleta,
                              fonte=fonte, tipo="realizado"))
    return obs


def coletar(demonstrativo: str, exercicio: int, periodo: int, anexo: str,
            mapeamento: list[dict[str, Any]], id_ente: int = 1,
            co_poder: str | None = None, sessao=None) -> list[Observacao]:
    params: dict[str, Any] = {
        "an_exercicio": exercicio, "nr_periodo": periodo,
        "co_tipo_demonstrativo": demonstrativo.upper(), "no_anexo": anexo, "id_ente": id_ente,
    }
    if demonstrativo == "rgf":
        params["in_periodicidade"] = "Q"
        if co_poder:
            params["co_poder"] = co_poder
    itens = buscar_itens(demonstrativo, params, sessao)
    hoje = dt.date.today()
    nome = f"{demonstrativo}_{exercicio}_p{periodo}_{anexo}_{co_poder or 'todos'}"
    gravar_bruto("siconfi", nome, itens, URLS[demonstrativo], params, hoje)
    fonte = f"siconfi_{demonstrativo}_{anexo}".lower().replace(" ", "_")
    ref = data_fim_periodo(demonstrativo, exercicio, periodo)
    return extrair(itens, [m for m in mapeamento if m.get("anexo") in (None, anexo)],
                   ref, hoje, fonte, periodo)
