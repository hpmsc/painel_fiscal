"""CADPREV — DAIR (carteiras de investimento dos RPPS).

Dois caminhos, com a mesma normalização:
- `importar_arquivo`: CSV exportado da consulta pública do CADPREV;
- `coletar_api`: consulta JSON configurada em config/fundos_fontes.yaml (⚠ verificar).

Cada posição vira {competencia, ente, uf, cnpj_ente, cnpj_fundo, nome_ativo, segmento,
artigo, valor}. Os nomes de coluna variam entre exportações; `ALIASES` lista os aceitos e
`colunas_nao_mapeadas` mostra o que sobrou, para ajustar a lista.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .http import baixar
from .tabela import arquivos_csv, campo, chave_coluna, linhas, numero, so_digitos

ALIASES = {
    "competencia": ("competencia", "mes_ano", "data_referencia", "dt_referencia", "mes_referencia", "periodo"),
    "ente": ("ente", "nome_ente", "ente_federativo", "rpps", "nome_rpps", "unidade_gestora"),
    "uf": ("uf", "sg_uf", "sigla_uf"),
    "cnpj_ente": ("cnpj_ente", "cnpj_do_ente", "cnpj_rpps", "cnpj_unidade_gestora", "nr_cnpj_ente"),
    "cnpj_fundo": ("cnpj_fundo", "cnpj_do_fundo", "cnpj_ativo", "nr_cnpj_fundo", "identificacao_do_ativo",
                   "cnpj"),
    "nome_ativo": ("nome_fundo", "nome_do_fundo", "nome_ativo", "descricao_ativo", "ativo", "fundo"),
    "segmento": ("segmento", "nm_segmento", "segmento_aplicacao"),
    "artigo": ("artigo", "tipo_ativo", "enquadramento", "dispositivo_legal", "tipo_de_ativo"),
    "valor": ("valor_total", "valor_atual", "vl_total_atual", "valor_total_atual", "saldo", "valor"),
}
CHAVES_ALIAS = {chave_coluna(a) for alts in ALIASES.values() for a in alts}


def normalizar(registro: dict) -> dict:
    l = {chave_coluna(k): ("" if v is None else str(v)) for k, v in registro.items()}
    pos = {k: campo(l, *alts) for k, alts in ALIASES.items()}
    pos["cnpj_fundo"] = so_digitos(pos["cnpj_fundo"])
    pos["cnpj_ente"] = so_digitos(pos["cnpj_ente"])
    pos["valor"] = numero(pos["valor"])
    return pos


def colunas_nao_mapeadas(registros: list[dict]) -> list[str]:
    vistas = {chave_coluna(k) for r in registros[:50] for k in r}
    return sorted(vistas - CHAVES_ALIAS)


def importar_arquivo(caminho: Path) -> tuple[list[dict], list[str]]:
    brutos = [l for _, t in arquivos_csv(Path(caminho).read_bytes()) for l in linhas(t)]
    return [normalizar(r) for r in brutos], colunas_nao_mapeadas(brutos)


def coletar_api(cfg: dict, ano: int, mes: int, uf: str = "", sessao=None) -> tuple[list[dict], list[str]]:
    params = {k: str(v).format(ano=ano, mes=f"{mes:02d}", uf=uf) for k, v in cfg.get("parametros", {}).items()}
    dados = json.loads(baixar(cfg["url"], params, sessao=sessao))
    if isinstance(dados, dict):   # respostas paginadas costumam trazer a lista sob uma chave
        dados = next((v for k, v in dados.items() if isinstance(v, list)), [])
    return [normalizar(r) for r in dados], colunas_nao_mapeadas(dados)


def resumo_por_fundo(posicoes: list[dict], cnpj_ente: str = "", nome_ente: str = "") -> dict[str, dict]:
    """Quantos RPPS têm cada fundo, quanto somam, e se o próprio ente tem (carteira própria)."""
    out: dict[str, dict] = defaultdict(lambda: {"rpps": set(), "valor": 0.0, "proprio": 0.0})
    proprio_cnpj = so_digitos(cnpj_ente)
    for p in posicoes:
        if not p["cnpj_fundo"]:
            continue
        r = out[p["cnpj_fundo"]]
        r["rpps"].add(p["cnpj_ente"] or p["ente"])
        r["valor"] += p["valor"] or 0
        e_proprio = (proprio_cnpj and p["cnpj_ente"] == proprio_cnpj) or (
            not proprio_cnpj and nome_ente and nome_ente.upper() in p["ente"].upper())
        if e_proprio:
            r["proprio"] += p["valor"] or 0
    return {c: {"n_rpps": len(r["rpps"]), "valor_rpps": round(r["valor"], 2),
                "valor_proprio": round(r["proprio"], 2) or None} for c, r in out.items()}
