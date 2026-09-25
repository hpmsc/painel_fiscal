"""Linha de comando.

    python -m painel_fiscal painel --exercicio 2026 --dados dados/tratados/2026.json dados/entrada_manual/2026.yaml
    python -m painel_fiscal apurar --exercicio 2026 --dados ...          # tabela no terminal
    python -m painel_fiscal coletar-bcb --exercicio 2026 --desde 2025-01-01
    python -m painel_fiscal coletar-siconfi --exercicio 2026 --demonstrativo rgf --periodo 2
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import yaml

from . import config, dados
from .apuracao.regras import apurar
from .config import RAIZ

DIR_TRATADOS = RAIZ / "dados" / "tratados"


def _base(args) -> dados.BaseDados:
    caminhos = args.dados or [p for p in (DIR_TRATADOS / f"{args.exercicio}.json",
                                          RAIZ / "dados" / "entrada_manual" / f"{args.exercicio}.yaml")
                              if p.exists()]
    return dados.carregar_varios(args.exercicio, caminhos)


def _acrescentar_tratados(exercicio: int, novas: list[dados.Observacao]) -> Path:
    destino = DIR_TRATADOS / f"{exercicio}.json"
    base = dados.carregar_arquivo(destino) if destino.exists() else dados.BaseDados(exercicio)
    base.adicionar(novas)
    dados.salvar_json(base, destino)
    return destino


def cmd_apurar(args) -> int:
    p = config.carregar(args.config)
    for r in apurar(p, args.exercicio, _base(args)):
        from .painel.render import formatar
        print(f"{r.id:4} {r.rotulo_status:24} {formatar(r.valor, r.unidade):>18}  {r.nome}")
    return 0


def cmd_painel(args) -> int:
    from .painel.render import renderizar
    p = config.carregar(args.config)
    base = _base(args)
    html = renderizar(p, args.exercicio, apurar(p, args.exercicio, base), ilustrativo=base.tem_ilustrativo)
    saida = Path(args.saida or RAIZ / "saida" / f"painel_{args.exercicio}.html")
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(html, encoding="utf-8")
    print(f"Painel gravado em {saida}")
    return 0


def cmd_coletar_bcb(args) -> int:
    from .coletores import bcb_sgs
    p = config.carregar(args.config)
    series = p.fontes["bcb_sgs"]["series"]
    novas = []
    for indicador, serie in series.items():
        serie = serie if isinstance(serie, dict) else {"codigo": serie}
        if serie.get("codigo") is None:
            print(f"! {indicador}: código SGS não definido no YAML — ignorado", file=sys.stderr)
            continue
        novas += bcb_sgs.coletar(indicador, int(serie["codigo"]), dt.date.fromisoformat(args.desde),
                                 fator=serie.get("fator", 1.0),
                                 acumular_no_ano=serie.get("acumular_no_ano", False))
    print(f"{len(novas)} observações → {_acrescentar_tratados(args.exercicio, novas)}")
    return 0


def cmd_coletar_siconfi(args) -> int:
    from .coletores import siconfi
    p = config.carregar(args.config)
    id_ente = p.fontes.get("siconfi", {}).get("id_ente_uniao", 1)
    with open(RAIZ / "config" / "mapeamento_siconfi.yaml", encoding="utf-8") as f:
        mapa = yaml.safe_load(f)
    novas = []
    for anexo in sorted({m["anexo"] for m in mapa[args.demonstrativo]}):
        novas += siconfi.coletar(args.demonstrativo, args.exercicio, args.periodo, anexo,
                                 mapa[args.demonstrativo], id_ente,
                                 co_poder="E" if args.demonstrativo == "rgf" else None)
    if args.demonstrativo == "rgf":
        for co_poder, nome in mapa.get("rgf_por_poder", {}).items():
            m = [{**e, "indicador": e["indicador"].format(poder=nome)} for e in mapa["rgf_pessoal"]]
            novas += siconfi.coletar("rgf", args.exercicio, args.periodo, "RGF-Anexo 01", m,
                                     id_ente, co_poder=co_poder)
    print(f"{len(novas)} observações → {_acrescentar_tratados(args.exercicio, novas)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="painel_fiscal", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=config.CAMINHO_PADRAO)
    sub = ap.add_subparsers(dest="cmd", required=True)

    for nome, fn in (("apurar", cmd_apurar), ("painel", cmd_painel)):
        s = sub.add_parser(nome)
        s.add_argument("--exercicio", type=int, required=True)
        s.add_argument("--dados", nargs="*", help="arquivos JSON/YAML de observações")
        if nome == "painel":
            s.add_argument("--saida")
        s.set_defaults(fn=fn)

    s = sub.add_parser("coletar-bcb")
    s.add_argument("--exercicio", type=int, required=True)
    s.add_argument("--desde", required=True, help="AAAA-MM-DD")
    s.set_defaults(fn=cmd_coletar_bcb)

    s = sub.add_parser("coletar-siconfi")
    s.add_argument("--exercicio", type=int, required=True)
    s.add_argument("--demonstrativo", choices=["rreo", "rgf"], required=True)
    s.add_argument("--periodo", type=int, required=True)
    s.set_defaults(fn=cmd_coletar_siconfi)

    args = ap.parse_args(argv)
    return args.fn(args)
