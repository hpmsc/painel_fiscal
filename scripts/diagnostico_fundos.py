"""Confere as fontes da base de fundos contra as respostas reais (roda no GitHub Actions).

Mostra, para cada fonte, se o endereço responde, os arquivos e as colunas que vieram e
quantos CNPJs do universo aparecem. Serve para confirmar os itens "⚠ verificar" de
fundos/cvm.py e config/fundos_fontes.yaml. Não grava nada em dados/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fundos import armazem, cvm  # noqa: E402
from fundos.http import CABECALHOS  # noqa: E402
from fundos.tabela import arquivos_csv, chave_coluna, linhas  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def get(url, **kw):
    try:
        return requests.get(url, headers=CABECALHOS, timeout=180, **kw)
    except requests.RequestException as e:
        return e


def bloco(out, titulo, linhas_txt):
    out.append(f"## {titulo}\n```\n" + "\n".join(linhas_txt) + "\n```\n")


def diag_zip(out, titulo, url, cnpjs=None, coluna_cnpj=("cnpj_fundo_classe", "cnpj_fundo")):
    r = get(url)
    if not isinstance(r, requests.Response) or r.status_code != 200:
        bloco(out, titulo, [url, f"falhou: {getattr(r, 'status_code', r)}"])
        return False
    txt = [url, f"HTTP 200, {len(r.content) / 1e6:.1f} MB"]
    for nome, texto in arquivos_csv(r.content):
        n = 0
        achados = set()
        for l in linhas(texto):
            n += 1
            if cnpjs:
                c = next((l[k] for k in coluna_cnpj if k in l), "")
                achados.add("".join(ch for ch in c if ch.isdigit()))
        cab = texto.split("\n", 1)[0].strip()
        txt += [f"- {nome or '(csv)'}: {n} linhas", f"  colunas: {cab}"]
        if cnpjs:
            txt.append(f"  CNPJs do universo presentes: {len(cnpjs & achados)} de {len(cnpjs)}")
        txt.append("  1ª linha: " + texto.split("\n", 2)[1][:300] if "\n" in texto else "")
    bloco(out, titulo, txt)
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--saida", default="diagnostico")
    a = p.parse_args()
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load(open(RAIZ / "config" / "fundos_fontes.yaml", encoding="utf-8"))
    cnpjs = {u["cnpj14"] for u in armazem.ler_universo(RAIZ / cfg["universo"])}
    out = ["# Diagnóstico das fontes de fundos\n"]

    hoje = dt.date.today()
    mes_ant = hoje.replace(day=1) - dt.timedelta(days=1)
    diag_zip(out, f"CVM — informe diário {mes_ant:%Y-%m}",
             cvm.URL_INF_MES.format(aaaamm=f"{mes_ant:%Y%m}"), cnpjs)
    diag_zip(out, "CVM — registro de fundos e classes (CVM 175)", cvm.URL_REGISTRO, cnpjs,
             ("cnpj_classe", "cnpj_fundo"))
    diag_zip(out, "CVM — cad_fi.csv (cadastro antigo)", cvm.URL_CAD_ANTIGO, cnpjs, ("cnpj_fundo",))

    # Até quando há ZIP mensal e desde quando só o histórico anual.
    txt = []
    for ano in range(2005, hoje.year + 1):
        rm = get(cvm.URL_INF_MES.format(aaaamm=f"{ano}01"), stream=True)
        ra = get(cvm.URL_INF_ANO.format(aaaa=ano), stream=True)
        txt.append(f"{ano}: mensal jan {getattr(rm, 'status_code', rm)} · HIST anual {getattr(ra, 'status_code', ra)}")
    bloco(out, "CVM — onde está cada ano do informe diário", txt)

    r = get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/5", params={"formato": "json"})
    bloco(out, "BCB — CDI (SGS 12), últimos 5", [str(getattr(r, "text", r))[:500]])

    txt = []
    for url in cfg["cadprev"]["api"].get("candidatos_diagnostico", []):
        r = get(url)
        if isinstance(r, requests.Response):
            txt += [f"{url}", f"  HTTP {r.status_code} · {r.headers.get('content-type', '')} · {len(r.content)} bytes",
                    "  " + r.text[:600].replace("\n", " ")]
        else:
            txt += [url, f"  falhou: {r}"]
    api = cfg["cadprev"]["api"]
    params = {k: str(v).format(ano=mes_ant.year, mes=f"{mes_ant.month:02d}", uf=cfg["cadprev"]["ente"].get("uf", ""))
              for k, v in api.get("parametros", {}).items()}
    r = get(api["url"], params=params)
    txt += [f"consulta configurada: {api['url']} {params}",
            f"  {getattr(r, 'status_code', r)} · " + (r.text[:1500].replace(chr(10), ' ') if isinstance(r, requests.Response) else "")]
    bloco(out, "CADPREV — DAIR", txt)

    (saida / "resumo_fundos.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
