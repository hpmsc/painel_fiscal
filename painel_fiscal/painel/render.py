"""Gera o painel como um único HTML estático (sem dependências externas).

Gráficos em SVG inline, desenhados aqui para ficarem testáveis e sem JS.
"""
from __future__ import annotations

import datetime as dt
import html
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from jinja2 import Environment, FileSystemLoader, Undefined, select_autoescape
from markupsafe import Markup

from ..apuracao import status as st
from ..apuracao.regras import Resultado
from ..config import Parametros

DIR = Path(__file__).parent

NOMES_PODER = {
    "executivo": "Executivo", "legislativo": "Legislativo", "legislativo_incl_tcu": "Legislativo (incl. TCU)",
    "judiciario": "Judiciário", "mpu": "MPU", "dpu": "DPU",
}


# ----------------------------------------------------------------- formatação

def _num(v: float, casas: int = 1) -> str:
    s = f"{v:,.{casas}f}"
    return s.replace(",", "\u0001").replace(".", ",").replace("\u0001", ".")


def formatar(v: Any, unidade: str) -> str:
    if v is None or isinstance(v, Undefined):
        return "—"
    if isinstance(v, bool):
        return "sim" if v else "não"
    if unidade == "R$ bi":
        return f"R$ {_num(v)} bi"
    if unidade in ("fracao", "uso_limite"):
        casas = 2 if abs(v) < 0.1 else 1
        return f"{_num(v * 100, casas)}%"
    if unidade == "pct_pib":
        return f"{_num(v)}% do PIB"
    return _num(v)


def formatar_folga(r: Resultado) -> str:
    if r.folga is None:
        return "—"
    if r.unidade == "pct_pib":
        return f"{_num(r.folga)} p.p."
    if r.unidade in ("fracao", "uso_limite"):
        return f"{'+' if r.folga >= 0 else '−'}{_num(abs(r.folga) * 100, 2)} p.p."
    sinal = "+" if r.folga >= 0 else "−"
    return f"{sinal}R$ {_num(abs(r.folga))} bi"


def formatar_limite(r: Resultado) -> str:
    if r.tipo_limite == "banda":
        e = r.extras
        if e.get("inferior") is None:
            return "—"
        sup = f"R$ {_num(e['superior'])} bi" if e.get("superior") is not None else "sem teto"
        return f"R$ {_num(e['inferior'])} bi a {sup}"
    if r.limite is None:
        return "a confirmar" if r.status == st.PENDENTE else "sem limite legal"
    prefixo = {"minimo": "≥ ", "maximo": "≤ "}.get(r.tipo_limite or "", "")
    return prefixo + formatar(r.limite, r.unidade if r.unidade != "uso_limite" else "fracao")


def data_br(d: dt.date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


# ----------------------------------------------------------------- gráficos SVG

def _esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def _escala(dmin: float, dmax: float, pmin: float, pmax: float):
    span = (dmax - dmin) or 1.0
    return lambda v: pmin + (v - dmin) / span * (pmax - pmin)


def _ticks(dmin: float, dmax: float, n: int = 5) -> list[float]:
    import math
    bruto = (dmax - dmin) / max(n, 1)
    mag = 10 ** math.floor(math.log10(bruto)) if bruto > 0 else 1
    passo = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= bruto), default=mag)
    t = math.ceil(dmin / passo) * passo
    out = []
    while t <= dmax + 1e-9:
        out.append(round(t, 10))
        t += passo
    return out


def grafico_meta(r01: Resultado) -> str:
    """Banda da meta (faixa), centro (traço) e marcadores do resultado."""
    e = r01.extras
    inf, cen, sup = e.get("inferior"), e.get("centro"), e.get("superior")
    if inf is None:
        return ""
    pontos = []
    if r01.valor is not None and r01.base_apuracao != "parcial":
        rot = "Resultado ajustado (projeção)" if r01.base_apuracao == "projecao" else "Resultado ajustado"
        pontos.append(("ajustado", rot, r01.valor, "var(--serie-1)"))
    if e.get("realizado_acumulado") is not None:
        pontos.append(("acumulado", f"Realizado acumulado até {data_br(e.get('realizado_data'))}",
                       e["realizado_acumulado"], "var(--serie-2)"))
    valores = [inf, sup if sup is not None else inf] + [p[2] for p in pontos]
    lo, hi = min(valores + [0.0]), max(valores)
    pad = (hi - lo) * 0.12 or 10
    lo, hi = lo - pad, hi + pad
    W, H, ml, mr = 640, 150, 16, 16
    x = _escala(lo, hi, ml, W - mr)
    y0, y1 = 44, 92
    partes = [f'<svg class="grafico" viewBox="0 0 {W} {H}" role="img" '
              f'aria-label="Meta de resultado primário: banda de R$ {_num(inf)} bi a '
              f'{"R$ " + _num(sup) + " bi" if sup is not None else "sem teto"}">']
    for t in _ticks(lo, hi):
        partes.append(f'<line class="grade" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{y0 - 14}" y2="{y1 + 6}"/>'
                      f'<text class="eixo" x="{x(t):.1f}" y="{y1 + 22}" text-anchor="middle">{_num(t, 0)}</text>')
    xs = x(sup) if sup is not None else W - mr
    partes.append(f'<rect class="banda" x="{x(inf):.1f}" y="{y0}" width="{xs - x(inf):.1f}" '
                  f'height="{y1 - y0}" rx="4"><title>Banda de tolerância: R$ {_num(inf)} bi a '
                  f'{"R$ " + _num(sup) + " bi" if sup is not None else "sem teto"}</title></rect>')
    partes.append(f'<text class="rotulo-sec" x="{x(inf):.1f}" y="{y0 - 20}" text-anchor="middle">piso {_num(inf)}</text>')
    if sup is not None:
        partes.append(f'<text class="rotulo-sec" x="{xs:.1f}" y="{y0 - 20}" text-anchor="middle">teto {_num(sup)}</text>')
    if cen is not None:
        partes.append(f'<line class="centro" x1="{x(cen):.1f}" x2="{x(cen):.1f}" y1="{y0}" y2="{y1}">'
                      f'<title>Centro da meta: R$ {_num(cen)} bi</title></line>'
                      f'<text class="rotulo-sec" x="{x(cen):.1f}" y="{y0 - 20}" text-anchor="middle">meta {_num(cen)}</text>')
    if lo < 0 < hi:
        partes.append(f'<line class="zero" x1="{x(0):.1f}" x2="{x(0):.1f}" y1="{y0 - 6}" y2="{y1 + 6}"/>')
    ymid = (y0 + y1) / 2
    for i, (chave, rot, v, cor) in enumerate(pontos):
        yy = ymid + (i - (len(pontos) - 1) / 2) * 14
        forma = (f'<circle cx="{x(v):.1f}" cy="{yy:.1f}" r="6" fill="{cor}" class="marca"/>'
                 if chave == "ajustado" else
                 f'<rect x="{x(v) - 5.5:.1f}" y="{yy - 5.5:.1f}" width="11" height="11" rx="2" fill="{cor}" class="marca"/>')
        partes.append(f'<g class="alvo"><circle cx="{x(v):.1f}" cy="{yy:.1f}" r="14" fill="transparent"/>'
                      f'{forma}<title>{_esc(rot)}: R$ {_num(v)} bi</title></g>')
    partes.append(f'<text class="eixo" x="{W - mr}" y="{H - 4}" text-anchor="end">R$ bilhões</text></svg>')
    legenda = "".join(
        f'<span class="leg-item"><span class="leg-marca {"circ" if c == "ajustado" else "quad"}" '
        f'style="background:{cor}"></span>{_esc(rot)}: <b>R$ {_num(v)} bi</b></span>'
        for c, rot, v, cor in pontos)
    legenda += '<span class="leg-item"><span class="leg-marca banda-leg"></span>Banda de tolerância</span>'
    return Markup("".join(partes) + f'<div class="legenda">{legenda}</div>')


def grafico_uso_limite(linhas: list[tuple[str, float, str]], niveis: dict[str, float],
                       titulo_aria: str) -> str:
    """Barras horizontais de uso do limite (1,0 = 100%), com referências 90/95/100%."""
    if not linhas:
        return ""
    W, alt, ml, mr, topo = 640, 30, 150, 140, 26
    H = topo + alt * len(linhas) + 26
    xmax = max(1.25, max(v for _, v, _ in linhas) * 1.15)
    x = _escala(0, xmax, ml, W - mr)
    p = [f'<svg class="grafico" viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(titulo_aria)}">']
    for t in _ticks(0, xmax, 5):
        p.append(f'<line class="grade" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{topo - 4}" y2="{H - 22}"/>'
                 f'<text class="eixo" x="{x(t):.1f}" y="{H - 6}" text-anchor="middle">{_num(t * 100, 0)}%</text>')
    refs = [("alerta", niveis["alerta"]), ("prudencial", niveis["prudencial"]), ("limite", niveis["excedido"])]
    for nome, v in refs:
        p.append(f'<line class="ref ref-{nome}" x1="{x(v):.1f}" x2="{x(v):.1f}" y1="{topo - 8}" y2="{H - 22}"/>')
    p.append(f'<text class="rotulo-sec" x="{x(niveis["alerta"]) - 3:.1f}" y="{topo - 12}" text-anchor="end">alerta {_num(niveis["alerta"] * 100, 0)}%</text>'
             f'<text class="rotulo-sec" x="{x(niveis["excedido"]) + 3:.1f}" y="{topo - 12}">limite</text>')
    for i, (rot, v, status) in enumerate(linhas):
        yy = topo + i * alt
        largura = max(x(v) - ml, 2)
        p.append(f'<g class="alvo"><rect x="{ml}" y="{yy}" width="{W - mr - ml}" height="{alt - 4}" fill="transparent"/>'
                 f'<text class="rotulo" x="{ml - 8}" y="{yy + alt / 2 + 2}" text-anchor="end">{_esc(rot)}</text>'
                 f'<rect class="barra" x="{ml}" y="{yy + 6}" width="{largura:.1f}" height="{alt - 16}" rx="4"/>'
                 f'<text class="valor" x="{ml + largura + 6:.1f}" y="{yy + alt / 2 + 2}">{_num(v * 100)}%</text>'
                 f'<title>{_esc(rot)}: {_num(v * 100)}% do limite — {_esc(st.ROTULOS.get(status, status))}</title></g>')
        p.append(f'<g transform="translate({W - mr + 12},{yy + 4})">{_chip_svg(status)}</g>')
    p.append("</svg>")
    return Markup("".join(p))


_ICONE = {"bom": "✓", "atencao": "!", "serio": "!!", "critico": "✕", "neutro": "·"}


def _chip_svg(status: str) -> str:
    tom = st.TOM.get(status, "neutro")
    return (f'<rect class="chip-svg tom-{tom}" width="126" height="20" rx="10"/>'
            f'<text class="chip-svg-txt" x="10" y="14">{_ICONE[tom]} {_esc(st.ROTULOS.get(status, status))}</text>')


def grafico_divida(r15: Resultado) -> str:
    e = r15.extras
    series = [("DBGG", e.get("dbgg") or [], "var(--serie-1)", False),
              ("DLSP", e.get("dlsp") or [], "var(--serie-2)", False),
              ("LDO (projeção DBGG)", e.get("trajetoria") or [], "var(--serie-1)", True)]
    series = [s for s in series if s[1]]
    if not series:
        return ""
    todos = [pt for s in series for pt in s[1]]
    d0, d1 = min(d for d, _ in todos), max(d for d, _ in todos)
    v0, v1 = min(v for _, v in todos), max(v for _, v in todos)
    pad = (v1 - v0) * 0.15 or 5
    v0, v1 = v0 - pad, v1 + pad
    W, H, ml, mr, mt, mb = 640, 240, 44, 96, 14, 28
    x = _escala(d0.toordinal(), d1.toordinal(), ml, W - mr)
    y = _escala(v0, v1, H - mb, mt)
    p = [f'<svg class="grafico" viewBox="0 0 {W} {H}" role="img" aria-label="Dívida em % do PIB">']
    for t in _ticks(v0, v1, 4):
        p.append(f'<line class="grade" x1="{ml}" x2="{W - mr}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                 f'<text class="eixo" x="{ml - 6}" y="{y(t) + 4:.1f}" text-anchor="end">{_num(t, 0)}</text>')
    anos = sorted({d.year for d, _ in todos})
    for a in anos:
        dj = dt.date(a, 1, 1).toordinal()
        if d0.toordinal() <= dj <= d1.toordinal():
            p.append(f'<text class="eixo" x="{x(dj):.1f}" y="{H - 8}" text-anchor="middle">{a}</text>')
    p.append(f'<line class="base" x1="{ml}" x2="{W - mr}" y1="{H - mb}" y2="{H - mb}"/>')
    ultimo_dbgg = sorted(e.get("dbgg") or [])[-1:]
    for nome, pts, cor, projecao in series:
        pts = sorted(pts)
        # a projeção parte do último DBGG observado, para ler como continuação
        tracado = (ultimo_dbgg + pts) if projecao else pts
        caminho = " ".join(f"{'M' if i == 0 else 'L'}{x(d.toordinal()):.1f},{y(v):.1f}" for i, (d, v) in enumerate(tracado))
        classe = "linha projecao" if projecao else "linha"
        p.append(f'<path class="{classe}" d="{caminho}" stroke="{cor}"/>')
        for d, v in pts:
            p.append(f'<g class="alvo"><circle cx="{x(d.toordinal()):.1f}" cy="{y(v):.1f}" r="9" fill="transparent"/>'
                     f'<circle cx="{x(d.toordinal()):.1f}" cy="{y(v):.1f}" r="{4 if projecao else 2.5}" '
                     f'fill="{"var(--superficie)" if projecao else cor}" stroke="{cor}" stroke-width="2" class="ponto"/>'
                     f'<title>{_esc(nome)} — {d.strftime("%m/%Y")}: {_num(v)}% do PIB</title></g>')
        dl, vl = pts[-1]
        p.append(f'<text class="valor" x="{x(dl.toordinal()) + 8:.1f}" y="{y(vl) + 4:.1f}">{_esc(nome.split(" ")[0])} {_num(vl)}</text>')
    p.append("</svg>")
    legenda = "".join(
        f'<span class="leg-item"><span class="leg-linha{" tracejada" if proj else ""}" style="border-color:{cor}"></span>{_esc(n)}</span>'
        for n, _, cor, proj in series)
    return Markup("".join(p) + f'<div class="legenda">{legenda}</div>')


# ----------------------------------------------------------------- página

def _linhas_poder(detalhes: Iterable[Resultado]) -> list[tuple[str, float, str]]:
    return [(NOMES_PODER.get(d.nome, d.nome), d.extras["uso_do_limite"], d.status)
            for d in detalhes if "uso_do_limite" in d.extras]


def _pendencias(parametros: Parametros, exercicio: int, resultados: list[Resultado]) -> list[dict[str, str]]:
    itens = []
    pano = parametros.exercicio(exercicio)
    g = pano.get("gatilhos_art_6A") or {}
    if g.get("status") == "controversia":
        itens.append({"tipo": "Controvérsia", "regra": "R04", "texto": g.get("nota", "")})
    for d in pano.get("deducoes", []) or []:
        if d.get("verificar") or ("tratamento_meta" in d and d["tratamento_meta"] is None):
            itens.append({"tipo": "Verificar", "regra": "R01", "texto": f"Dedução “{d['item']}”: tratamento na meta."})
    if pano.get("crescimento_real_limite") is None:
        itens.append({"tipo": "Extrair", "regra": "R02/R03",
                      "texto": "Crescimento real do limite de despesa (PLOA/LOA)."})
    if "PLDO" in str(pano.get("fonte_legal", "")):
        itens.append({"tipo": "Atualizar", "regra": "R01",
                      "texto": f"Parâmetros de {exercicio} vêm do PLDO; atualizar após a sanção da LDO."})
    for r in resultados:
        if r.verificar:
            itens.append({"tipo": "Verificar", "regra": r.id,
                          "texto": f"{r.nome}: base legal ou limite a confirmar na fonte primária."})
    fontes = parametros.fontes
    series = (fontes.get("bcb_sgs") or {}).get("series", {})
    faltando = [k for k, v in series.items() if v is None]
    if faltando:
        itens.append({"tipo": "Identificar", "regra": "Fontes",
                      "texto": "Código SGS ausente: " + ", ".join(faltando) + "."})
    itens.append({"tipo": "Verificar", "regra": "Fontes",
                  "texto": "Códigos SGS (DBGG, DLSP), id_ente da União no SICONFI e mapeamento de contas."})
    return itens


def montar_contexto(parametros: Parametros, exercicio: int, resultados: list[Resultado],
                    ilustrativo: bool = False, gerado_em: dt.datetime | None = None) -> dict[str, Any]:
    por_id = {r.id: r for r in resultados}
    contagem = Counter(r.tom for r in resultados)
    graficos = {}
    if "R01" in por_id:
        graficos["meta"] = grafico_meta(por_id["R01"])
    if "R02" in por_id:
        graficos["despesa"] = grafico_uso_limite(_linhas_poder(por_id["R02"].detalhes),
                                                 parametros.status_percentual,
                                                 "Uso do limite de despesas por Poder")
    linhas_pessoal = []
    if "R09" in por_id and "uso_do_limite" in por_id["R09"].extras:
        linhas_pessoal.append(("União (total)", por_id["R09"].extras["uso_do_limite"], por_id["R09"].status))
    if "R10" in por_id:
        linhas_pessoal += _linhas_poder(por_id["R10"].detalhes)
    graficos["pessoal"] = grafico_uso_limite(linhas_pessoal, parametros.status_percentual,
                                             "Despesa com pessoal: uso do limite por Poder")
    if "R15" in por_id:
        graficos["divida"] = grafico_divida(por_id["R15"])
    pano = parametros.exercicio(exercicio)
    return {
        "exercicio": exercicio,
        "fonte_legal": pano.get("fonte_legal", ""),
        "escopo": parametros.metadados.get("escopo", ""),
        "data_normativa": parametros.metadados.get("data_referencia", ""),
        "gerado_em": (gerado_em or dt.datetime.now()).strftime("%d/%m/%Y %H:%M"),
        "ilustrativo": ilustrativo,
        "resultados": resultados,
        "r": por_id,
        "resumo": [
            ("critico", "Descumpre / excedido", contagem.get("critico", 0)),
            ("serio", "Prudencial / gatilho", contagem.get("serio", 0)),
            ("atencao", "Alerta / controvérsia", contagem.get("atencao", 0)),
            ("bom", "Cumpre", contagem.get("bom", 0)),
            ("neutro", "Monitoramento / pendente", contagem.get("neutro", 0)),
        ],
        "graficos": graficos,
        "pendencias": _pendencias(parametros, exercicio, resultados),
        "icone": _ICONE,
        "nomes_poder": NOMES_PODER,
    }


def renderizar(parametros: Parametros, exercicio: int, resultados: list[Resultado],
               ilustrativo: bool = False, gerado_em: dt.datetime | None = None) -> str:
    env = Environment(loader=FileSystemLoader(DIR), autoescape=select_autoescape(["html"]))
    env.filters.update(fmt=formatar, folga=formatar_folga, limite=formatar_limite, data=data_br)
    return env.get_template("template.html").render(
        **montar_contexto(parametros, exercicio, resultados, ilustrativo, gerado_em))
