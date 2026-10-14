"""Linha de comando: python -m fundos <comando>."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import yaml

from painel_fiscal.config import RAIZ

from . import armazem, cadprev, cdi, cvm, metricas

CONFIG = RAIZ / "config" / "fundos_fontes.yaml"


def _cfg() -> dict:
    with open(CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _mes(s: str) -> dt.date:
    return dt.date.fromisoformat(s + "-01" if len(s) == 7 else s)


def _universo() -> list[dict]:
    return armazem.ler_universo(RAIZ / _cfg()["universo"])


def cmd_coletar_cvm(a) -> int:
    cnpjs = {u["cnpj14"] for u in _universo()}
    ate = _mes(a.ate) if a.ate else dt.date.today()
    lista = cvm.meses(_mes(a.desde), ate)
    cotas, ok, faltam = [], set(), []
    for ano, mes in lista:
        try:
            m = cvm.baixar_informe(ano, mes, cnpjs)
        except cvm.NaoEncontrado:
            faltam.append(f"{ano}-{mes:02d}")
            continue
        cotas += m
        ok.add((ano, mes))
        print(f"{ano}-{mes:02d}: {len(m)} cotas de {len({c.cnpj for c in m})} fundos")
    if ok:
        print("gravado:", armazem.gravar_cotas(cotas, ok))
    if faltam:
        print("não publicados:", ", ".join(faltam))
    achados = {c.cnpj for c in cotas}
    print(f"{len(achados)} de {len(cnpjs)} CNPJs do universo têm informe no período")
    return 0 if ok else 1


def cmd_cadastro_cvm(a) -> int:
    cnpjs = {u["cnpj14"] for u in _universo()}
    cad = cvm.baixar_cadastro(cnpjs)
    armazem.gravar_json("cadastro.json", cad)
    print(f"cadastro de {len(cad)} de {len(cnpjs)} fundos do universo")
    return 0


def cmd_coletar_cdi(a) -> int:
    pontos = cdi.coletar(dt.date.fromisoformat(a.desde))
    print(armazem.gravar_cdi(pontos), len(pontos), "dias")
    return 0


def cmd_calcular(a) -> int:
    cotas = armazem.ler_cotas()
    if not cotas:
        print("sem cotas em dados/fundos/cotas/: rode coletar-cvm antes", file=sys.stderr)
        return 1
    data_base = dt.date.fromisoformat(a.data_base) if a.data_base else max(c.data for c in cotas)
    cad_path = armazem.DIR / "cadastro.json"
    cad = json.loads(cad_path.read_text(encoding="utf-8")) if cad_path.exists() else None
    base = metricas.montar_base(cotas, _universo(), armazem.ler_cdi(), data_base,
                                _cfg()["cvm"].get("ano_inicial", 2010), cad)
    resumo = armazem.DIR / "cadprev" / "resumo_fundos.json"
    if resumo.exists():
        r = json.loads(resumo.read_text(encoding="utf-8"))
        for f in base["funds"]:
            if (x := r["fundos"].get(f["c"].replace(".", "").replace("/", "").replace("-", ""))):
                f["rpps"] = x
        base["cadprev_competencia"] = r.get("competencia")
    print(armazem.gravar_json("metricas.json", base), f"{len(base['funds'])} fundos,",
          f"{len(base['sem_dado'])} sem informe, data-base {base['data_base']}")
    return 0


def _gravar_cadprev(posicoes: list[dict], sobra: list[str], competencia: str) -> int:
    ente = _cfg()["cadprev"]["ente"]
    armazem.gravar_json(f"cadprev/carteiras_{competencia}.json", posicoes)
    resumo = cadprev.resumo_por_fundo(posicoes, ente.get("cnpj", ""), ente.get("nome", ""))
    armazem.gravar_json("cadprev/resumo_fundos.json", {"competencia": competencia, "fundos": resumo})
    print(f"{len(posicoes)} posições, {len(resumo)} fundos distintos, competência {competencia}")
    if sobra:
        print("colunas não mapeadas (ver cadprev.ALIASES):", ", ".join(sobra))
    sem_cnpj = sum(1 for p in posicoes if not p["cnpj_fundo"])
    if sem_cnpj:
        print(f"{sem_cnpj} posições sem CNPJ de fundo (títulos públicos, poupança etc.)")
    return 0 if posicoes else 1


def cmd_importar_cadprev(a) -> int:
    posicoes, sobra = cadprev.importar_arquivo(Path(a.arquivo))
    return _gravar_cadprev(posicoes, sobra, a.competencia)


def cmd_coletar_cadprev(a) -> int:
    cfg = _cfg()["cadprev"]
    posicoes, sobra = cadprev.coletar_api(cfg["api"], a.ano, a.mes, a.uf or cfg["ente"].get("uf", ""))
    return _gravar_cadprev(posicoes, sobra, f"{a.ano}-{a.mes:02d}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m fundos", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("coletar-cvm", help="cotas diárias do informe diário da CVM")
    c.add_argument("--desde", required=True, help="AAAA-MM")
    c.add_argument("--ate", help="AAAA-MM (padrão: mês atual)")
    c.set_defaults(f=cmd_coletar_cvm)
    c = sub.add_parser("cadastro-cvm", help="cadastro CVM (registro de fundos e classes)")
    c.set_defaults(f=cmd_cadastro_cvm)
    c = sub.add_parser("coletar-cdi", help="CDI diário do BCB (SGS 12)")
    c.add_argument("--desde", default="2009-01-01")
    c.set_defaults(f=cmd_coletar_cdi)
    c = sub.add_parser("calcular", help="gera dados/fundos/metricas.json no formato da Matriz")
    c.add_argument("--data-base", help="AAAA-MM-DD (padrão: última cota coletada)")
    c.set_defaults(f=cmd_calcular)
    c = sub.add_parser("importar-cadprev", help="carteiras DAIR de um CSV exportado do CADPREV")
    c.add_argument("--arquivo", required=True)
    c.add_argument("--competencia", required=True, help="AAAA-MM")
    c.set_defaults(f=cmd_importar_cadprev)
    c = sub.add_parser("coletar-cadprev", help="carteiras DAIR pela API do CADPREV (⚠ verificar)")
    c.add_argument("--ano", type=int, required=True)
    c.add_argument("--mes", type=int, required=True)
    c.add_argument("--uf")
    c.set_defaults(f=cmd_coletar_cadprev)
    a = p.parse_args(argv)
    return a.f(a)
