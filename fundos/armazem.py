"""Onde a base fica no repositório (dados/fundos/).

cotas/AAAA.csv.gz   cotas diárias do universo, um arquivo por ano (só os CNPJs do universo)
cdi.csv             índice do CDI
cadastro.json       cadastro CVM do universo
cadprev/            carteiras DAIR importadas
metricas.json       indicadores no formato da Matriz
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import json
from collections import defaultdict
from pathlib import Path

from painel_fiscal.config import RAIZ

from .cvm import Cota
from .tabela import so_digitos

DIR = RAIZ / "dados" / "fundos"
UNIVERSO = RAIZ / "config" / "fundos_universo.csv"
CAMPOS = ["cnpj", "subclasse", "data", "cota", "pl", "captacao", "resgate", "cotistas"]


def ler_universo(caminho: Path = UNIVERSO) -> list[dict[str, str]]:
    with open(caminho, encoding="utf-8") as f:
        return [{**l, "cnpj14": so_digitos(l["cnpj"])} for l in csv.DictReader(f, delimiter=";")]


def _fmt(v) -> str:
    return "" if v is None else (repr(v) if isinstance(v, float) else str(v))


def ler_cotas(diretorio: Path = DIR) -> list[Cota]:
    out = []
    for arq in sorted((diretorio / "cotas").glob("*.csv.gz")):
        with gzip.open(arq, "rt", encoding="utf-8") as f:
            for l in csv.DictReader(f, delimiter=";"):
                num = lambda k: float(l[k]) if l[k] else None  # noqa: E731
                out.append(Cota(cnpj=l["cnpj"], subclasse=l["subclasse"], data=dt.date.fromisoformat(l["data"]),
                                cota=float(l["cota"]), pl=num("pl"), captacao=num("captacao"),
                                resgate=num("resgate"), cotistas=int(l["cotistas"]) if l["cotistas"] else None))
    return out


def gravar_cotas(novas: list[Cota], meses: set[tuple[int, int]], diretorio: Path = DIR) -> dict[int, int]:
    """Substitui, nos arquivos anuais, os meses coletados pelas cotas novas (republicações da
    CVM corrigem o mês inteiro). Devolve linhas gravadas por ano."""
    por_ano: dict[int, list[Cota]] = defaultdict(list)
    for c in novas:
        por_ano[c.data.year].append(c)
    anos = {a for a, _ in meses}
    existentes = [c for c in ler_cotas(diretorio) if c.data.year in anos and (c.data.year, c.data.month) not in meses]
    for c in existentes:
        por_ano[c.data.year].append(c)
    (diretorio / "cotas").mkdir(parents=True, exist_ok=True)
    gravadas = {}
    for ano in sorted(anos):
        linhas = sorted(set(por_ano.get(ano, [])), key=lambda c: (c.cnpj, c.subclasse, c.data))
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";", lineterminator="\n")
        w.writerow(CAMPOS)
        for c in linhas:
            w.writerow([c.cnpj, c.subclasse, c.data.isoformat(), _fmt(c.cota), _fmt(c.pl), _fmt(c.captacao),
                        _fmt(c.resgate), _fmt(c.cotistas)])
        # mtime=0: o mesmo conteúdo gera os mesmos bytes, então coletas repetidas não viram commit
        with open(diretorio / "cotas" / f"{ano}.csv.gz", "wb") as f:
            with gzip.GzipFile(fileobj=f, mode="wb", mtime=0, filename="") as gz:
                gz.write(buf.getvalue().encode("utf-8"))
        gravadas[ano] = len(linhas)
    return gravadas


def gravar_cdi(pontos: list[tuple[dt.date, float]], diretorio: Path = DIR) -> Path:
    diretorio.mkdir(parents=True, exist_ok=True)
    caminho = diretorio / "cdi.csv"
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(["data", "indice"])
        for d, v in pontos:
            w.writerow([d.isoformat(), f"{v:.10f}"])
    return caminho


def ler_cdi(diretorio: Path = DIR) -> list[tuple[dt.date, float]]:
    caminho = diretorio / "cdi.csv"
    if not caminho.exists():
        return []
    with open(caminho, encoding="utf-8") as f:
        return [(dt.date.fromisoformat(l["data"]), float(l["indice"])) for l in csv.DictReader(f, delimiter=";")]


def gravar_json(nome: str, conteudo, diretorio: Path = DIR) -> Path:
    caminho = diretorio / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(conteudo, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    return caminho
