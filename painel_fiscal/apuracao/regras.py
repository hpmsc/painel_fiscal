"""Apuração das regras R01–R17 a partir das observações e dos parâmetros do YAML.

Cada função recebe (regra do YAML, parâmetros do exercício, base de dados,
contexto) e devolve um `Resultado`. Valores em R$ bilhões; razões como fração
(0,5 = 50%). Nenhuma meta, limite ou dedução é fixada aqui: tudo vem do YAML.

Catálogo de indicadores esperados: docs/catalogo_indicadores.md.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Callable

from ..config import Parametros
from ..dados import BaseDados, Observacao
from . import status as st

PODERES_LIMITE_DESPESA = ("executivo", "legislativo", "judiciario", "mpu", "dpu")


@dataclass
class Resultado:
    id: str
    nome: str
    base_legal: list[str]
    frequencia: str
    fontes: list[str]
    status: str
    valor: float | None = None
    unidade: str = ""                 # "R$ bi", "fracao", "pp_pib", "bool"
    limite: float | None = None
    tipo_limite: str | None = None    # "maximo", "minimo", "banda", None
    folga: float | None = None        # positiva = há espaço; negativa = excesso
    base_apuracao: str | None = None  # "realizado", "projecao", "parcial"
    data_referencia: dt.date | None = None
    data_coleta: dt.date | None = None
    verificar: bool = False
    notas: list[str] = field(default_factory=list)
    detalhes: list["Resultado"] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def rotulo_status(self) -> str:
        return st.ROTULOS.get(self.status, self.status)

    @property
    def tom(self) -> str:
        return st.TOM.get(self.status, "neutro")


@dataclass
class Contexto:
    parametros: Parametros
    exercicio: int
    base: BaseDados
    resultados: dict[str, Resultado] = field(default_factory=dict)

    @property
    def params_ano(self) -> dict[str, Any]:
        return self.parametros.exercicio(self.exercicio)

    @property
    def niveis(self) -> dict[str, float]:
        return self.parametros.status_percentual


# ---------------------------------------------------------------- utilidades

def _novo(regra: dict, status: str, **kw) -> Resultado:
    fontes = regra.get("fonte", [])
    return Resultado(
        id=regra["id"], nome=regra["nome"], base_legal=list(regra.get("base_legal", [])),
        frequencia=regra.get("frequencia", ""),
        fontes=list(fontes) if isinstance(fontes, list) else [fontes],
        status=status, verificar=bool(regra.get("verificar", False)), **kw,
    )


def _preferida(base: BaseDados, indicador: str,
               ordem: tuple[str, ...] = ("realizado", "projecao")) -> Observacao | None:
    for tipo in ordem:
        o = base.ultima(indicador, tipo)
        if o is not None:
            return o
    return None


def _datas(*obs: Observacao | None) -> dict[str, Any]:
    validas = [o for o in obs if o is not None]
    if not validas:
        return {}
    return {
        "data_referencia": min(o.data_referencia for o in validas),
        "data_coleta": max((o.data_coleta for o in validas if o.data_coleta), default=None),
        "base_apuracao": "projecao" if any(o.tipo == "projecao" for o in validas) else "realizado",
    }


def _faltantes(**obs: Observacao | None) -> list[str]:
    return [k for k, v in obs.items() if v is None]


def _sem_dados(regra: dict, faltam: list[str], **kw) -> Resultado:
    return _novo(regra, st.SEM_DADOS, notas=[f"Faltam indicadores: {', '.join(faltam)}"], **kw)


def _razao_sobre(regra: dict, ctx: Contexto, numerador: str, denominador: str,
                 limite: float | None, tipo_limite: str | None,
                 modo: str, ordem=("realizado", "projecao")) -> Resultado:
    """Regras do tipo numerador ÷ denominador comparadas a um limite.

    modo: "percentual" (teto com alerta/prudencial), "minimo", ou
    "monitoramento" (sem limite legal).
    """
    n = _preferida(ctx.base, numerador, ordem)
    d = _preferida(ctx.base, denominador, ordem)
    falta = _faltantes(**{numerador: n, denominador: d})
    if falta:
        return _sem_dados(regra, falta, unidade="fracao", limite=limite, tipo_limite=tipo_limite)
    razao = n.valor / d.valor
    res = _novo(regra, st.MONITORAMENTO, valor=razao, unidade="fracao",
                limite=limite, tipo_limite=tipo_limite, **_datas(n, d))
    if limite is None:
        res.status = st.PENDENTE if res.verificar else st.MONITORAMENTO
        if res.verificar:
            res.notas.append("Limite legal não confirmado; valor exibido só para acompanhamento.")
        return res
    if modo == "percentual":
        res.status = st.percentual(razao / limite, ctx.niveis)
        res.folga = limite - razao
        res.extras["uso_do_limite"] = razao / limite
    elif modo == "minimo":
        res.status = st.minimo(razao, limite)
        res.folga = razao - limite
    return res


# ---------------------------------------------------------------- R01 / R06

def _limites_meta(meta: dict) -> tuple[float, float | None, float | None]:
    centro = meta.get("centro_bi")
    inferior = meta.get("limite_inferior_bi")
    superior = meta.get("limite_superior_bi")
    banda = meta.get("banda_bi")
    if inferior is None and centro is not None and banda is not None:
        inferior = centro - banda
    if superior is None and centro is not None and banda is not None:
        superior = centro + banda
    return inferior, centro, superior


def _deducoes(ctx: Contexto, tipo_base: str) -> tuple[float, list[dict], list[str]]:
    """Soma das despesas excluídas do cômputo da meta (somadas ao resultado)."""
    total, itens, notas = 0.0, [], []
    ordem = (tipo_base, "projecao" if tipo_base == "realizado" else "realizado")
    # Quando a fonte (p. ex. o Relatório Bimestral) informa só o total deduzido, ele prevalece
    # sobre a soma item a item do YAML.
    informado = ctx.base.ultima("deducoes_meta_total_bi", tipo_base)
    if informado is not None:
        itens.append({"item": "Total de deduções informado", "base_legal": informado.nota,
                      "valor_bruto_bi": informado.valor, "deduzido_bi": informado.valor,
                      "fonte": informado.fonte})
        return informado.valor, itens, notas
    for d in ctx.params_ano.get("deducoes", []) or []:
        nome = d["item"]
        if "tratamento_meta" in d and d["tratamento_meta"] is None:
            notas.append(f"“{nome}”: tratamento na meta a confirmar — não deduzido.")
            continue
        valor = d.get("valor_bi")
        obs = None
        if valor is None and d.get("indicador"):
            obs = _preferida(ctx.base, d["indicador"], ordem)
            valor = None if obs is None else obs.valor
        if valor is None:
            notas.append(f"“{nome}”: sem valor informado — não deduzido.")
            continue
        deduzido = valor
        if d.get("percentual_computado") is not None:
            deduzido = valor * (1 - d["percentual_computado"])
        if d.get("valor_max_bi") is not None:
            deduzido = min(deduzido, d["valor_max_bi"])
        total += deduzido
        itens.append({"item": nome, "base_legal": d.get("base_legal"),
                      "valor_bruto_bi": valor, "deduzido_bi": deduzido,
                      "fonte": obs.fonte if obs else "YAML"})
    return total, itens, notas


def r01_meta_primaria(regra, ctx: Contexto) -> Resultado:
    meta = ctx.params_ano.get("meta_primaria", {})
    inferior, centro, superior = _limites_meta(meta)
    ind = "primario_gc_abaixo_linha_bi"

    realizado = ctx.base.ultima(ind, "realizado")
    projecao = ctx.base.ultima(ind, "projecao")
    fechado = realizado is not None and realizado.data_referencia >= dt.date(ctx.exercicio, 12, 1)
    if fechado:
        obs, base_ap = realizado, "realizado"
    elif projecao is not None:
        obs, base_ap = projecao, "projecao"
    elif realizado is not None:
        obs, base_ap = realizado, "parcial"
    else:
        return _sem_dados(regra, [ind], unidade="R$ bi", limite=inferior, tipo_limite="banda",
                          extras={"inferior": inferior, "centro": centro, "superior": superior})

    total_ded, itens, notas = _deducoes(ctx, "realizado" if base_ap != "projecao" else "projecao")
    ajustado = round(obs.valor + total_ded, 6)      # evita −1e-14 abaixo do piso por arredondamento

    if inferior is None:
        status = st.PENDENTE
        notas.append("Banda da meta não definida no YAML.")
    elif base_ap == "parcial":
        status = st.EM_APURACAO
        notas.append("Exercício aberto e sem projeção oficial: acumulado no ano não é comparável à meta anual.")
    else:
        status = st.meta_banda(ajustado, inferior, superior)

    # Projeção oficial: a limitação de empenho (contingenciamento) anunciada no mesmo relatório
    # reduz a despesa discricionária e entra no resultado esperado para o ano.
    contingenciamento = ctx.base.ultima("contingenciamento_bi", "projecao") if base_ap == "projecao" else None
    antes_contingenciamento = None
    if contingenciamento is not None and contingenciamento.valor and inferior is not None:
        antes_contingenciamento = ajustado
        ajustado = round(ajustado + contingenciamento.valor, 6)
        status = st.meta_banda(ajustado, inferior, superior)
        notas.append(f"Resultado ajustado antes do contingenciamento: {_rs(antes_contingenciamento)}; "
                     f"com a limitação de empenho de {_rs(contingenciamento.valor)}: {_rs(ajustado)}.")

    res = _novo(regra, status, valor=ajustado, unidade="R$ bi", limite=inferior,
                tipo_limite="banda", base_apuracao=base_ap,
                data_referencia=obs.data_referencia, data_coleta=obs.data_coleta,
                folga=None if inferior is None else ajustado - inferior, notas=notas)
    if base_ap == "projecao":
        res.notas.insert(0, f"Status sobre projeção ({obs.fonte}); apuração oficial só com o dado de dezembro (BCB).")
    # fontes efetivamente usadas: a do resultado, a do acumulado (se diferente) e as das deduções
    usadas = [obs.fonte] + ([realizado.fonte] if realizado is not None else [])
    usadas += [d["fonte"] for d in itens if d.get("fonte") and d["fonte"] != "YAML"]
    if contingenciamento is not None:
        usadas.append(contingenciamento.fonte)
    res.fontes = list(dict.fromkeys(usadas))
    acima = ctx.base.ultima("primario_gc_acima_linha_bi", "realizado")
    res.extras.update({
        "inferior": inferior, "centro": centro, "superior": superior,
        "resultado_sem_deducoes": obs.valor, "deducoes": itens, "total_deducoes": total_ded,
        "realizado_acumulado": realizado.valor if realizado else None,
        "realizado_data": realizado.data_referencia if realizado else None,
        "projecao": projecao.valor if projecao else None,
        "projecao_fonte": projecao.fonte if projecao else None,
        "acima_linha": acima.valor if acima else None,
        "contingenciamento_mira_piso": meta.get("contingenciamento_mira_piso"),
        "antes_contingenciamento": antes_contingenciamento,
    })
    if acima and realizado and acima.data_referencia == realizado.data_referencia:
        res.extras["discrepancia_estatistica"] = realizado.valor - acima.valor
    return res


def r06_excesso_investimentos(regra, ctx: Contexto) -> Resultado:
    p = regra.get("parametros", {})
    ini, fim = p.get("vigencia", [None, None])
    r01 = ctx.resultados.get("R01")
    if ini is not None and not (ini <= ctx.exercicio <= fim):
        return _novo(regra, st.INFORMATIVO, notas=[f"Fora da vigência ({ini}–{fim})."])
    if r01 is None or r01.valor is None or r01.extras.get("superior") is None:
        return _sem_dados(regra, ["R01 (resultado ajustado e teto da banda)"], unidade="R$ bi")
    if r01.base_apuracao == "parcial":
        return _novo(regra, st.EM_APURACAO, unidade="R$ bi", base_apuracao="parcial",
                     notas=["Depende do resultado primário do ano (ou da projeção oficial)."])
    excesso = max(0.0, r01.valor - r01.extras["superior"])
    fator = _preferida(ctx.base, "fator_ipca_desde_jan2023")
    base_nominal = p.get("limite_nominal_base_bi")
    notas = []
    if fator is not None and base_nominal is not None:
        teto = base_nominal * fator.valor
    else:
        teto = base_nominal
    utilizavel = min(excesso, teto) if teto is not None else excesso
    if excesso == 0:
        notas.append(f"Resultado ajustado (R$ {_br(r01.valor)} bi) não supera o teto da banda "
                     f"(R$ {_br(r01.extras['superior'])} bi): não há excesso a destinar a investimentos.")
    elif fator is None:
        notas.append("Sem fator IPCA (fator_ipca_desde_jan2023): teto exibido sem correção.")
    res = _novo(regra, st.INFORMATIVO, valor=excesso, unidade="R$ bi", limite=teto,
                tipo_limite="maximo", base_apuracao=r01.base_apuracao,
                data_referencia=r01.data_referencia, notas=notas)
    res.extras["utilizavel_bi"] = utilizavel
    if r01.base_apuracao != "realizado" and excesso > 0:
        res.notas.append("Excesso calculado sobre projeção; só vale com o resultado fechado do ano.")
    return res


# ---------------------------------------------------------------- R02 / R03 / R04

def _limite_despesa_calculado(ctx: Contexto) -> tuple[float | None, list[str]]:
    anterior = _preferida(ctx.base, "limite_despesa_anterior_bi")
    ipca = _preferida(ctx.base, "ipca_12m_jun")
    cresc = ctx.params_ano.get("crescimento_real_limite")
    if cresc is None and "R03" in ctx.resultados:
        cresc = ctx.resultados["R03"].valor
    if None in (anterior, ipca, cresc):
        return None, []
    lim = anterior.valor * (1 + ipca.valor) * (1 + cresc)
    return lim, [f"Limite calculado: {anterior.valor:.1f} × (1 + {ipca.valor:.2%}) × (1 + {cresc:.2%})."]


def r02_limite_despesas(regra, ctx: Contexto) -> Resultado:
    ordem = ("projecao", "realizado")   # relatório bimestral projeta o ano
    detalhes = []
    for poder in PODERES_LIMITE_DESPESA:
        desp = _preferida(ctx.base, f"despesa_sujeita_limite_{poder}_bi", ordem)
        lim = _preferida(ctx.base, f"limite_despesa_{poder}_bi", ordem)
        if desp is None or lim is None:
            continue
        uso = desp.valor / lim.valor
        d = _novo(regra, st.percentual(uso, ctx.niveis), valor=desp.valor, unidade="R$ bi",
                  limite=lim.valor, tipo_limite="maximo", folga=lim.valor - desp.valor,
                  **_datas(desp, lim))
        d.nome = poder
        d.extras["uso_do_limite"] = uso
        detalhes.append(d)

    desp = _preferida(ctx.base, "despesa_sujeita_limite_bi", ordem)
    lim_obs = _preferida(ctx.base, "limite_despesa_bi", ordem)
    notas: list[str] = []
    limite = lim_obs.valor if lim_obs else None
    if limite is None:
        limite, notas = _limite_despesa_calculado(ctx)
    if desp is None or limite is None:
        faltam = [] if desp else ["despesa_sujeita_limite_bi"]
        if limite is None:
            faltam.append("limite_despesa_bi (ou limite_despesa_anterior_bi + ipca_12m_jun"
                          " + crescimento real)")
        res = _sem_dados(regra, faltam, unidade="R$ bi", detalhes=detalhes)
        if detalhes:
            res.status = st.pior([d.status for d in detalhes])
        return res
    uso = desp.valor / limite
    res = _novo(regra, st.percentual(uso, ctx.niveis), valor=desp.valor, unidade="R$ bi",
                limite=limite, tipo_limite="maximo", folga=limite - desp.valor,
                notas=notas, detalhes=detalhes, **_datas(desp, lim_obs))
    res.extras["uso_do_limite"] = uso
    if detalhes:
        res.status = st.pior([res.status] + [d.status for d in detalhes])
    return res


def r03_crescimento_real(regra, ctx: Contexto) -> Resultado:
    p = regra.get("parametros", {})
    var = _preferida(ctx.base, "variacao_real_receita_primaria_12m_jun")
    cumprida = _preferida(ctx.base, "meta_ano_anterior_cumprida")
    if var is None or cumprida is None:
        return _sem_dados(regra, _faltantes(variacao_real_receita_primaria_12m_jun=var,
                                            meta_ano_anterior_cumprida=cumprida),
                          unidade="fracao", extras={"piso": p.get("piso_real"), "teto": p.get("teto_real")})
    fator = p["fator_meta_cumprida"] if cumprida.valor else p["fator_meta_descumprida"]
    bruto = fator * var.valor
    calc = min(max(bruto, p["piso_real"]), p["teto_real"])
    res = _novo(regra, st.INFORMATIVO, valor=calc, unidade="fracao", **_datas(var, cumprida),
                extras={"fator": fator, "antes_piso_teto": bruto,
                        "piso": p["piso_real"], "teto": p["teto_real"]})
    oficial = ctx.params_ano.get("crescimento_real_limite")
    if oficial is not None:
        res.extras["oficial"] = oficial
        if abs(oficial - calc) > 0.0005:
            res.status = st.ALERTA
            res.notas.append(f"Diverge do valor oficial no YAML ({oficial:.2%}).")
    else:
        res.notas.append("Crescimento oficial do PLOA/LOA ainda não informado no YAML.")
    return res


def r04_gatilhos(regra, ctx: Contexto) -> Resultado:
    g = ctx.params_ano.get("gatilhos_art_6A") or {}
    mapa = {"ativo": st.ATIVO, "inativo": st.INATIVO, "controversia": st.CONTROVERSIA}
    status = mapa.get(g.get("status"), st.PENDENTE)
    notas = [n for n in [g.get("nota")] if n]
    if g.get("exemplos"):
        notas.append("Vedações: " + "; ".join(g["exemplos"]))
    return _novo(regra, status, unidade="bool", notas=notas, base_apuracao="projecao"
                 if "PLDO" in str(ctx.params_ano.get("fonte_legal", "")) else None)


# ---------------------------------------------------------------- demais regras

def r05_piso_investimentos(regra, ctx: Contexto) -> Resultado:
    """Piso de investimentos, verificado no PLOA: investimentos do OFSS (SIOP, coluna PLOA)
    mais, se `incluir_estatais`, o Orçamento de Investimento das estatais, sobre o PIB do PLOA."""
    ordem = ("projecao", "realizado")
    piso = regra.get("limite")
    ofss = _preferida(ctx.base, "investimentos_ploa_bi", ordem)
    usado_loa = False
    if ofss is None:                       # sem a coluna PLOA, cai para a dotação da LOA
        ofss = _preferida(ctx.base, "investimentos_loa_bi", ordem)
        usado_loa = ofss is not None
    pib = _preferida(ctx.base, "pib_estimado_ploa_bi", ordem)
    estatais = (_preferida(ctx.base, "investimentos_estatais_ploa_bi", ordem)
                if (regra.get("parametros") or {}).get("incluir_estatais") else None)
    falta = _faltantes(investimentos_ploa_bi=ofss, pib_estimado_ploa_bi=pib)
    if falta:
        return _sem_dados(regra, falta, unidade="fracao", limite=piso, tipo_limite="minimo")
    total = ofss.valor + (estatais.valor if estatais else 0.0)
    razao = total / pib.valor
    res = _novo(regra, st.minimo(razao, piso), valor=razao, unidade="fracao", limite=piso,
                tipo_limite="minimo", folga=razao - piso, **_datas(ofss, pib, estatais))
    res.fontes = list(dict.fromkeys([ofss.fonte, pib.fonte] + ([estatais.fonte] if estatais else [])))
    res.extras.update({"ofss_bi": ofss.valor, "estatais_bi": estatais.valor if estatais else None,
                       "pib_bi": pib.valor, "piso_bi": piso * pib.valor})
    partes = f"OFSS {_rs(ofss.valor)}" + (f" + estatais {_rs(estatais.valor)}" if estatais else "")
    res.notas.append(f"{partes} = {_rs(total)}; piso {_rs(piso * pib.valor)} "
                     f"(0,6% do PIB do PLOA, {_rs(pib.valor)}).")
    if estatais:
        res.notas.append(f"Só OFSS: {ofss.valor / pib.valor * 100:.2f}% do PIB.".replace(".", ",", 1))
    if usado_loa:
        res.notas.append("Sem o valor do PLOA: usada a dotação da LOA.")
    return res


def r07_contingenciamento(regra, ctx):
    return _razao_sobre(regra, ctx, "contingenciamento_bi", "despesas_discricionarias_bi",
                        regra.get("limite"), "maximo", "percentual", ("projecao", "realizado"))


def r08_regra_de_ouro(regra, ctx: Contexto) -> Resultado:
    oc = _preferida(ctx.base, "receitas_operacoes_credito_bi")
    dk = _preferida(ctx.base, "despesas_capital_bi")
    falta = _faltantes(receitas_operacoes_credito_bi=oc, despesas_capital_bi=dk)
    if falta:
        return _sem_dados(regra, falta, unidade="R$ bi", limite=0, tipo_limite="maximo")
    excesso = oc.valor - dk.valor
    ressalva = _preferida(ctx.base, "creditos_maioria_absoluta_bi")
    ressalvado = ressalva.valor if ressalva else 0.0
    res = _novo(regra, st.maximo(excesso - ressalvado, regra.get("limite", 0)), valor=excesso,
                unidade="R$ bi", limite=regra.get("limite", 0), tipo_limite="maximo",
                folga=ressalvado - excesso, **_datas(oc, dk))
    res.extras.update({"operacoes_credito": oc.valor, "despesas_capital": dk.valor,
                       "ressalvado": ressalvado})
    if excesso > 0 and ressalva:
        res.notas.append(f"Excesso de R$ {excesso:.1f} bi coberto por R$ {ressalvado:.1f} bi "
                         "em créditos aprovados por maioria absoluta.")
    return res


def _datas_completas(ctx: Contexto, poder: str) -> list[dt.date]:
    """Datas (mais recente primeiro) em que o Poder tem DTP publicada COMPLETA: nº de blocos
    (instituições) igual ao máximo já visto no exercício. Sem contagem, todas as datas."""
    datas = sorted({o.data_referencia for o in ctx.base.serie(f"dtp_{poder}_bi")}, reverse=True)
    blocos = {o.data_referencia: o.valor for o in ctx.base.serie(f"n_blocos_dtp_{poder}")}
    if not blocos:
        return datas
    maximo = max(blocos.values())
    return [d for d in datas if blocos.get(d, 0) >= maximo]


def _pessoal_em(ctx: Contexto, poder: str, data: dt.date) -> tuple[Observacao | None, Observacao | None]:
    def em(ind):
        s = [o for o in ctx.base.serie(ind) if o.data_referencia == data]
        return s[-1] if s else None
    return em(f"dtp_{poder}_bi"), em(f"limite_dtp_{poder}_bi")


def _pessoal_completo(ctx: Contexto, poder: str) -> tuple[Observacao | None, Observacao | None, str | None]:
    """DTP e limite oficial do Poder no período mais recente completo. Evita usar um
    quadrimestre em que só parte dos tribunais enviou o RGF."""
    todas = sorted({o.data_referencia for o in ctx.base.serie(f"dtp_{poder}_bi")}, reverse=True)
    completas = _datas_completas(ctx, poder)
    if not todas:
        return None, None, None
    d = (completas or todas)[0]
    nota = None
    if d != todas[0]:
        blocos = {o.data_referencia: o.valor for o in ctx.base.serie(f"n_blocos_dtp_{poder}")}
        nota = (f"Período de {todas[0]:%m/%Y} incompleto ({blocos.get(todas[0], 0):.0f} de "
                f"{max(blocos.values()):.0f} instituições); usado {d:%m/%Y}.")
    dtp, lim = _pessoal_em(ctx, poder, d)
    return dtp, lim, nota


def _somar_poderes(ctx: Contexto, prefixo: str) -> None:
    """Sem `{prefixo}_total_bi`, soma os Poderes do R10 na data mais recente em que TODOS
    estão completos (não mistura quadrimestres)."""
    if _preferida(ctx.base, f"{prefixo}_total_bi"):
        return
    poderes = list((ctx.parametros.regra("R10").get("limites") or {}))
    if not poderes:
        return
    comuns = set(_datas_completas(ctx, poderes[0]))
    for p in poderes[1:]:
        comuns &= set(_datas_completas(ctx, p))
    if not comuns:
        return
    d = max(comuns)
    obs = [_pessoal_em(ctx, p, d)[0] for p in poderes]
    if all(obs):
        ctx.base.adicionar([Observacao(
            indicador=f"{prefixo}_total_bi", valor=sum(o.valor for o in obs), data_referencia=d,
            data_coleta=max((o.data_coleta for o in obs if o.data_coleta), default=None),
            fonte="soma dos Poderes (RGF Anexo 1)", tipo=obs[0].tipo)])


def _rcl_em(ctx: Contexto, data: dt.date) -> Observacao | None:
    """RCL do mesmo período da despesa (ou a mais recente anterior a ele)."""
    anteriores = [o for o in ctx.base.serie("rcl_bi") if o.data_referencia <= data]
    return anteriores[-1] if anteriores else _preferida(ctx.base, "rcl_bi")


def r09_pessoal_total(regra, ctx):
    _somar_poderes(ctx, "dtp")
    dtp = _preferida(ctx.base, "dtp_total_bi")
    if dtp is None:
        return _razao_sobre(regra, ctx, "dtp_total_bi", "rcl_bi", regra.get("limite"),
                            "maximo", "percentual")
    rcl = _rcl_em(ctx, dtp.data_referencia)
    if rcl is None:
        return _sem_dados(regra, ["rcl_bi"], unidade="fracao", limite=regra.get("limite"))
    limite = regra.get("limite")
    razao = dtp.valor / rcl.valor
    res = _novo(regra, st.percentual(razao / limite, ctx.niveis), valor=razao, unidade="fracao",
                limite=limite, tipo_limite="maximo", folga=limite - razao, **_datas(dtp, rcl))
    res.extras["uso_do_limite"] = razao / limite
    return res


def r10_pessoal_poder(regra, ctx: Contexto) -> Resultado:
    detalhes = []
    for poder, limite in (regra.get("limites") or {}).items():
        dtp, oficial, nota_periodo = _pessoal_completo(ctx, poder)
        rcl = _rcl_em(ctx, dtp.data_referencia) if dtp else None
        if dtp and oficial and rcl:
            # limite oficial do RGF (soma dos blocos do Poder), convertido em fração da RCL
            limite_rcl = oficial.valor / rcl.valor
            d = _novo(regra, st.percentual(dtp.valor / oficial.valor, ctx.niveis),
                      valor=dtp.valor / rcl.valor, unidade="fracao", limite=limite_rcl,
                      tipo_limite="maximo", folga=limite_rcl - dtp.valor / rcl.valor,
                      **_datas(dtp, oficial, rcl))
            d.extras["uso_do_limite"] = dtp.valor / oficial.valor
            d.notas.append("Limite oficial informado no RGF.")
            if nota_periodo:
                d.notas.append(nota_periodo)
        else:
            d = _razao_sobre(regra, ctx, f"dtp_{poder}_bi", "rcl_bi", limite, "maximo", "percentual")
        d.nome = poder
        detalhes.append(d)
    com_dados = [d for d in detalhes if d.status != st.SEM_DADOS]
    if not com_dados:
        return _sem_dados(regra, [f"dtp_{p}_bi" for p in regra.get("limites", {})],
                          unidade="fracao", detalhes=detalhes)
    pior = max(com_dados, key=lambda d: d.extras.get("uso_do_limite", 0))
    res = _novo(regra, st.pior([d.status for d in detalhes]), valor=pior.extras["uso_do_limite"],
                unidade="uso_limite", limite=1.0, tipo_limite="maximo",
                data_referencia=pior.data_referencia, data_coleta=pior.data_coleta,
                base_apuracao=pior.base_apuracao, detalhes=detalhes,
                notas=[f"Maior uso do limite: {pior.nome}."])
    return res


def r11_alerta_prudencial(regra, ctx: Contexto) -> Resultado:
    fontes = [ctx.resultados.get("R09")] + (ctx.resultados["R10"].detalhes if "R10" in ctx.resultados else [])
    validos = [r for r in fontes if r is not None and "uso_do_limite" in r.extras]
    if not validos:
        return _sem_dados(regra, ["R09/R10"], unidade="uso_limite")
    maior = max(validos, key=lambda r: r.extras["uso_do_limite"])
    niv = ctx.niveis
    res = _novo(regra, st.pior([r.status for r in validos]), valor=maior.extras["uso_do_limite"],
                unidade="uso_limite", limite=niv["alerta"], tipo_limite="maximo",
                folga=niv["alerta"] - maior.extras["uso_do_limite"],
                data_referencia=maior.data_referencia, base_apuracao=maior.base_apuracao,
                notas=[f"Maior uso: {maior.nome} (alerta {niv['alerta']:.0%}, prudencial {niv['prudencial']:.0%})."])
    return res


def r12_garantias(regra, ctx):
    return _razao_sobre(regra, ctx, "garantias_bi", "rcl_bi", regra.get("limite"),
                        "maximo", "percentual")


def r13_operacoes_credito(regra, ctx):
    return _razao_sobre(regra, ctx, "operacoes_credito_rgf_bi", "rcl_bi", regra.get("limite"),
                        "maximo", "percentual")


def r14_dcl(regra, ctx):
    res = _razao_sobre(regra, ctx, "dcl_bi", "rcl_bi", None, None, "monitoramento")
    if res.status != st.SEM_DADOS:
        res.notas.append("Limite da União nunca aprovado pelo Senado (LRF art. 30).")
    return res


def r15_trajetoria_divida(regra, ctx: Contexto) -> Resultado:
    dbgg = ctx.base.serie("dbgg_pct_pib", "realizado")
    dlsp = ctx.base.serie("dlsp_pct_pib", "realizado")
    traj = ctx.base.serie("trajetoria_ldo_dbgg_pct_pib", "projecao")
    if not dbgg:
        return _sem_dados(regra, ["dbgg_pct_pib"], unidade="pct_pib")
    ultimo = dbgg[-1]
    res = _novo(regra, st.MONITORAMENTO, valor=ultimo.valor, unidade="pct_pib",
                data_referencia=ultimo.data_referencia, data_coleta=ultimo.data_coleta,
                base_apuracao="realizado")
    fim_ano = [t for t in traj if t.data_referencia.year == ctx.exercicio]
    if fim_ano:
        res.limite = fim_ano[-1].valor
        res.folga = fim_ano[-1].valor - ultimo.valor
        res.notas.append(f"Projeção da LDO para dez/{ctx.exercicio}: {fim_ano[-1].valor:.1f}% do PIB "
                         "(referência, não limite legal).")
    res.extras.update({
        "dbgg": [(o.data_referencia, o.valor) for o in dbgg],
        "dlsp": [(o.data_referencia, o.valor) for o in dlsp],
        "trajetoria": [(o.data_referencia, o.valor) for o in traj],
    })
    return res


def _minimo_aplicado(regra, ctx: Contexto, aplicado: str, minimo: str, denominador: str) -> Resultado:
    """Mínimos constitucionais. Com o valor mínimo publicado no RREO (Anexo 14 da União),
    a base é mínimo ÷ piso e o % aplicado = aplicado ÷ base. Sem ele, aplicado ÷ denominador."""
    ap = _preferida(ctx.base, aplicado)
    mi = _preferida(ctx.base, minimo)
    piso = regra.get("limite")
    if ap is None or mi is None or not piso:
        return _razao_sobre(regra, ctx, aplicado, denominador, piso, "minimo", "minimo")
    base_calc = mi.valor / piso
    pct = ap.valor / base_calc
    fechado = ap.data_referencia >= dt.date(ctx.exercicio, 12, 1)
    res = _novo(regra, st.minimo(pct, piso) if fechado else st.EM_APURACAO, valor=pct,
                unidade="fracao", limite=piso, tipo_limite="minimo",
                folga=pct - piso if fechado else None,
                **{**_datas(ap, mi), "base_apuracao": "realizado" if fechado else "parcial"})
    res.extras.update({"aplicado_bi": ap.valor, "minimo_bi": mi.valor, "uso_do_minimo": ap.valor / mi.valor})
    res.notas.append(f"Aplicado R$ {_br(ap.valor)} bi; mínimo R$ {_br(mi.valor)} bi "
                     f"({_br(ap.valor / mi.valor * 100)}% do mínimo).")
    if not fechado:
        res.notas.append(f"Aplicado até {ap.data_referencia:%m/%Y} contra o mínimo anual; "
                         "o cumprimento só se apura com o 6º bimestre.")
    return res


def _rs(v: float) -> str:
    return ("−" if v < 0 else "") + f"R$ {_br(abs(v))} bi"


def _br(v: float) -> str:
    return f"{v:,.1f}".replace(",", "\u0001").replace(".", ",").replace("\u0001", ".")


def r16_saude(regra, ctx):
    return _minimo_aplicado(regra, ctx, "asps_bi", "asps_minimo_bi", "rcl_bi")


def r17_educacao(regra, ctx):
    return _minimo_aplicado(regra, ctx, "mde_bi", "mde_minimo_bi", "receita_liquida_impostos_bi")


# Ordem importa: R06 usa R01; R02 pode usar R03; R11 usa R09/R10.
APURADORES: dict[str, Callable[[dict, Contexto], Resultado]] = {
    "R01": r01_meta_primaria,
    "R03": r03_crescimento_real,
    "R02": r02_limite_despesas,
    "R04": r04_gatilhos,
    "R05": r05_piso_investimentos,
    "R06": r06_excesso_investimentos,
    "R07": r07_contingenciamento,
    "R08": r08_regra_de_ouro,
    "R09": r09_pessoal_total,
    "R10": r10_pessoal_poder,
    "R11": r11_alerta_prudencial,
    "R12": r12_garantias,
    "R13": r13_operacoes_credito,
    "R14": r14_dcl,
    "R15": r15_trajetoria_divida,
    "R16": r16_saude,
    "R17": r17_educacao,
}


def apurar(parametros: Parametros, exercicio: int, base: BaseDados) -> list[Resultado]:
    """Apura todas as regras do YAML; devolve na ordem R01…R17."""
    ctx = Contexto(parametros, exercicio, base)
    ids_yaml = {r["id"] for r in parametros.regras}
    for id_regra, fn in APURADORES.items():
        if id_regra in ids_yaml:
            ctx.resultados[id_regra] = fn(parametros.regra(id_regra), ctx)
    return [ctx.resultados[r["id"]] for r in parametros.regras if r["id"] in ctx.resultados]
