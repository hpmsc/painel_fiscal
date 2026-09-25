"""Diagnóstico das fontes: baixa respostas reais e resume o que for preciso para
confirmar os itens "⚠ verificar" (códigos SGS, id_ente da União, rótulos do SICONFI).

Roda no GitHub Actions (workflow diagnostico.yml). Grava os JSON brutos em
<saida>/ e um resumo em Markdown em <saida>/resumo.md (também no resumo do job).

    python scripts/diagnostico.py --exercicio 2025 --saida diagnostico
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from painel_fiscal import config  # noqa: E402
from painel_fiscal.coletores import siconfi  # noqa: E402
from painel_fiscal.coletores.base import obter_json  # noqa: E402

CKAN_BCB = "https://dadosabertos.bcb.gov.br/api/3/action/package_search"
SGS_ULTIMOS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}"
SIDRA = "https://apisidra.ibge.gov.br/values/t/{tabela}/n1/all/v/{variavel}/p/last%20{n}"
CKAN_TESOURO = "https://www.tesourotransparente.gov.br/ckan/api/3/action/package_search"
ENTES = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/entes"

BUSCAS_SGS = [
    "resultado primário governo central",
    "necessidades de financiamento governo central primário",
    "dívida bruta do governo geral",
    "dívida líquida do setor público",
]
ANEXOS = {
    "rgf": ["RGF-Anexo 01", "RGF-Anexo 02", "RGF-Anexo 03", "RGF-Anexo 04"],
    "rreo": ["RREO-Anexo 08", "RREO-Anexo 09", "RREO-Anexo 12"],
}
PODERES = ["E", "L", "J", "M"]
MAX_LINHAS_CONTAS = 400


class Relatorio:
    def __init__(self, saida: Path):
        self.saida = saida
        self.linhas: list[str] = []

    def __call__(self, texto: str = "") -> None:
        print(texto)
        self.linhas.append(texto)

    def gravar_json(self, nome: str, conteudo) -> None:
        with open(self.saida / f"{nome}.json", "w", encoding="utf-8") as f:
            json.dump(conteudo, f, ensure_ascii=False, indent=1)

    def secao(self, titulo: str, fn) -> None:
        self(f"\n## {titulo}\n")
        try:
            fn()
        except Exception as e:  # o diagnóstico continua nas outras fontes
            self(f"**ERRO:** `{type(e).__name__}: {e}`")
            self("```\n" + traceback.format_exc()[-1500:] + "\n```")


def sgs(rel: Relatorio, params: config.Parametros) -> None:
    rel("### Busca no catálogo (dadosabertos.bcb.gov.br)\n")
    for termo in BUSCAS_SGS:
        resp = obter_json(CKAN_BCB, {"q": termo, "rows": 15})
        rel.gravar_json(f"sgs_busca_{termo.replace(' ', '_')}", resp)
        rel(f"**{termo}**\n")
        rel("| pacote | título | código SGS (recursos) |\n|---|---|---|")
        for p in resp.get("result", {}).get("results", []):
            codigos = sorted({u.split("bcdata.sgs.")[1].split("/")[0]
                              for u in (r.get("url") or "" for r in p.get("resources", []))
                              if "bcdata.sgs." in u})
            rel(f"| {p.get('name')} | {p.get('title')} | {', '.join(codigos) or '—'} |")
        rel()
    rel("### Últimos valores das séries do YAML\n")
    for indicador, codigo in params.fontes["bcb_sgs"]["series"].items():
        if codigo is None:
            rel(f"- `{indicador}`: sem código no YAML")
            continue
        dados = obter_json(SGS_ULTIMOS.format(codigo=codigo, n=3), {"formato": "json"})
        rel.gravar_json(f"sgs_{codigo}", dados)
        rel(f"- `{indicador}` ({codigo}): {dados}")


def entes(rel: Relatorio) -> None:
    resp = obter_json(ENTES)
    itens = resp.get("items", resp if isinstance(resp, list) else [])
    rel.gravar_json("siconfi_entes", itens)
    uniao = [e for e in itens if str(e.get("esfera", "")).upper() == "U"
             or "união" in str(e.get("ente", "")).lower()]
    rel(f"{len(itens)} entes. Candidatos à União:\n")
    rel("```\n" + json.dumps(uniao[:5], ensure_ascii=False, indent=1) + "\n```")


def _resumo_contas(rel: Relatorio, itens: list[dict]) -> None:
    rel(f"{len(itens)} linhas. Colunas: " + ", ".join(
        f"`{c}` ({n})" for c, n in Counter(i.get("coluna") for i in itens).most_common()))
    rel("\n| cod_conta | conta | coluna | valor (R$ bi) |\n|---|---|---|---|")
    for it in itens[:MAX_LINHAS_CONTAS]:
        try:
            v = f"{float(it.get('valor')) / 1e9:,.2f}"
        except (TypeError, ValueError):
            v = str(it.get("valor"))
        rel(f"| {it.get('cod_conta')} | {it.get('conta')} | {it.get('coluna')} | {v} |")
    if len(itens) > MAX_LINHAS_CONTAS:
        rel(f"\n… {len(itens) - MAX_LINHAS_CONTAS} linhas omitidas (ver JSON no artefato).")


def siconfi_demonstrativos(rel: Relatorio, exercicio: int, id_ente: int, mapa: dict) -> None:
    periodos = {"rgf": 3, "rreo": 6}
    for dem, anexos in ANEXOS.items():
        for anexo in anexos:
            poderes = PODERES if anexo == "RGF-Anexo 01" else ([None] if dem == "rreo" else ["E"])
            for poder in poderes:
                titulo = f"{dem.upper()} {exercicio} p{periodos[dem]} — {anexo}" + (f" — poder {poder}" if poder else "")
                rel(f"\n### {titulo}\n")
                params = {"an_exercicio": exercicio, "nr_periodo": periodos[dem],
                          "co_tipo_demonstrativo": dem.upper(), "no_anexo": anexo, "id_ente": id_ente}
                if dem == "rgf":
                    params.update(in_periodicidade="Q", co_poder=poder)
                try:
                    itens = siconfi.buscar_itens(dem, params)
                except Exception as e:
                    rel(f"**ERRO:** `{type(e).__name__}: {e}`")
                    continue
                rel.gravar_json(f"siconfi_{dem}_{anexo.replace(' ', '_')}_{poder or 'todos'}", itens)
                _resumo_contas(rel, itens)
                mapeamento = [m for m in mapa.get(dem, []) if m.get("anexo") == anexo]
                if poder and poder != "E":
                    mapeamento = [{**m, "indicador": f"{m['indicador']} (poder {poder})"}
                                  for m in mapeamento if m["indicador"] == "dtp_total_bi"]
                _testar_mapeamento(rel, itens, mapeamento)


def _testar_mapeamento(rel: Relatorio, itens: list[dict], mapeamento: list[dict]) -> None:
    if not mapeamento:
        return
    rel("\n**Teste do mapeamento atual:**\n")
    import datetime as dt
    for m in mapeamento:
        try:
            obs = siconfi.extrair(itens, [m], dt.date.today(), dt.date.today(), "diag")
            rel(f"- `{m['indicador']}`: " + (f"OK → {obs[0].valor:,.2f} bi" if obs else "**nenhuma linha casou**"))
        except ValueError as e:
            rel(f"- `{m['indicador']}`: **ambíguo** — {e}")


def sidra(rel: Relatorio) -> None:
    for nome, tabela, variavel in [("IPCA 12 meses", 1737, 2265), ("IPCA mensal", 1737, 63),
                                   ("PIB corrente trimestral", 1846, 585)]:
        linhas = obter_json(SIDRA.format(tabela=tabela, variavel=variavel, n=3))
        rel.gravar_json(f"sidra_{tabela}_{variavel}", linhas)
        rel(f"**{nome}** (t{tabela}/v{variavel}):\n```\n{json.dumps(linhas[:4], ensure_ascii=False, indent=1)}\n```")


def rtn(rel: Relatorio) -> None:
    resp = obter_json(CKAN_TESOURO, {"q": "resultado do tesouro nacional", "rows": 10})
    rel.gravar_json("stn_rtn_busca", resp)
    for p in resp.get("result", {}).get("results", []):
        rel(f"- **{p.get('title')}** (`{p.get('name')}`)")
        for r in p.get("resources", [])[:8]:
            rel(f"  - {r.get('name')} · {r.get('format')} · {r.get('last_modified') or r.get('created')} · {r.get('url')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exercicio", type=int, default=2025)
    ap.add_argument("--saida", default="diagnostico")
    args = ap.parse_args()
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    rel = Relatorio(saida)
    params = config.carregar()
    with open(config.RAIZ / "config" / "mapeamento_siconfi.yaml", encoding="utf-8") as f:
        mapa = yaml.safe_load(f)
    id_ente = params.fontes.get("siconfi", {}).get("id_ente_uniao", 1)

    rel(f"# Diagnóstico das fontes — exercício {args.exercicio}")
    rel.secao("BCB — SGS", lambda: sgs(rel, params))
    rel.secao("SICONFI — entes", lambda: entes(rel))
    rel.secao(f"SICONFI — demonstrativos (id_ente={id_ente})",
              lambda: siconfi_demonstrativos(rel, args.exercicio, id_ente, mapa))
    rel.secao("IBGE — SIDRA", lambda: sidra(rel))
    rel.secao("STN — RTN (CKAN)", lambda: rtn(rel))

    (saida / "resumo.md").write_text("\n".join(rel.linhas), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
