"""CVM — dados abertos de fundos (https://dados.cvm.gov.br).

Informe diário (cota, PL, captação, resgate, cotistas), um ZIP por mês:
    FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_AAAAMM.zip
meses antigos ficam num ZIP por ano em .../DADOS/HIST/inf_diario_fi_AAAA.zip.
Com a Resolução CVM 175 as colunas passaram de CNPJ_FUNDO/TP_FUNDO para
CNPJ_FUNDO_CLASSE/TP_FUNDO_CLASSE e ganharam ID_SUBCLASSE; os dois formatos são aceitos.

Cadastro pós-CVM 175: FI/CAD/DADOS/registro_fundo_classe.zip (registro_fundo.csv,
registro_classe.csv, registro_subclasse.csv). O cad_fi.csv antigo segue aceito.
⚠ verificar: nomes de arquivo e colunas conferidos pelo workflow "Diagnóstico — fundos".
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Iterable, Iterator

from .http import NaoEncontrado, baixar
from .tabela import arquivos_csv, campo, linhas, numero, so_digitos

URL_BASE = "https://dados.cvm.gov.br/dados/FI"
URL_INF_MES = URL_BASE + "/DOC/INF_DIARIO/DADOS/inf_diario_fi_{aaaamm}.zip"
URL_INF_ANO = URL_BASE + "/DOC/INF_DIARIO/DADOS/HIST/inf_diario_fi_{aaaa}.zip"
URL_REGISTRO = URL_BASE + "/CAD/DADOS/registro_fundo_classe.zip"
URL_CAD_ANTIGO = URL_BASE + "/CAD/DADOS/cad_fi.csv"


@dataclass(frozen=True)
class Cota:
    cnpj: str            # 14 dígitos, sem máscara
    subclasse: str       # "" quando o informe é da classe (ou de fundo pré-CVM 175)
    data: dt.date
    cota: float
    pl: float | None = None
    captacao: float | None = None
    resgate: float | None = None
    cotistas: int | None = None


def converter_informe(texto: str, cnpjs: set[str] | None = None) -> Iterator[Cota]:
    """Linhas de um CSV do informe diário → Cota, só dos CNPJs pedidos (None = todos)."""
    for l in linhas(texto):
        cnpj = so_digitos(campo(l, "CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO"))
        if not cnpj or (cnpjs is not None and cnpj not in cnpjs):
            continue
        cota = numero(campo(l, "VL_QUOTA"))
        data = campo(l, "DT_COMPTC")
        if cota is None or cota <= 0 or not data:
            continue
        cot = numero(campo(l, "NR_COTST"))
        yield Cota(cnpj=cnpj, subclasse=campo(l, "ID_SUBCLASSE"),
                   data=dt.date.fromisoformat(data[:10]), cota=cota,
                   pl=numero(campo(l, "VL_PATRIM_LIQ")), captacao=numero(campo(l, "CAPTC_DIA")),
                   resgate=numero(campo(l, "RESG_DIA")), cotistas=int(cot) if cot is not None else None)


def meses(desde: dt.date, ate: dt.date) -> list[tuple[int, int]]:
    out, a, m = [], desde.year, desde.month
    while (a, m) <= (ate.year, ate.month):
        out.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


_HIST: dict[int, bytes] = {}   # o ZIP anual serve aos 12 meses: guarda só o do último ano


def baixar_informe(ano: int, mes: int, cnpjs: set[str] | None, sessao=None) -> list[Cota]:
    """Cotas de um mês. Tenta o ZIP mensal e, se não existir, o histórico do ano."""
    try:
        conteudo = baixar(URL_INF_MES.format(aaaamm=f"{ano}{mes:02d}"), sessao=sessao)
        padrao = r"\.csv$"
    except NaoEncontrado:
        if ano not in _HIST:
            _HIST.clear()
            _HIST[ano] = baixar(URL_INF_ANO.format(aaaa=ano), sessao=sessao)
        conteudo = _HIST[ano]
        padrao = rf"{ano}{mes:02d}\.csv$"
    cotas: list[Cota] = []
    for _, texto in arquivos_csv(conteudo, padrao):
        cotas.extend(converter_informe(texto, cnpjs))
    return cotas


# ---------- cadastro ----------

CAMPOS_CADASTRO = {
    # campo da base: alternativas de coluna (registro_classe / registro_fundo / cad_fi antigo)
    "nome": ("Denominacao_Social", "DENOM_SOCIAL"),
    "situacao": ("Situacao", "SIT"),
    "data_inicio": ("Data_Inicio", "Data_Inicio_Atividade", "DT_INI_ATIV"),
    "data_cancelamento": ("Data_Cancelamento", "DT_CANCEL"),
    "tipo": ("Tipo_Classe", "Tipo_Fundo", "TP_FUNDO"),
    "classificacao_cvm": ("Classificacao", "CLASSE"),
    "classificacao_anbima": ("Classificacao_Anbima", "CLASSE_ANBIMA"),
    "indicador_desempenho": ("Indicador_Desempenho", "RENTAB_FUNDO"),
    "publico_alvo": ("Publico_Alvo",),
    "condominio": ("Forma_Condominio", "CONDOM"),
    "exclusivo": ("Exclusivo", "FUNDO_EXCLUSIVO"),
    "pl": ("Patrimonio_Liquido", "VL_PATRIM_LIQ"),
    "data_pl": ("Data_Patrimonio_Liquido", "DT_PATRIM_LIQ"),
    "administrador": ("Administrador", "ADMIN"),
    "cnpj_administrador": ("CNPJ_Administrador", "CNPJ_ADMIN"),
    "gestor": ("Gestor",),
    "cnpj_gestor": ("CPF_CNPJ_Gestor", "CPF_CNPJ_GESTOR"),
    "custodiante": ("Custodiante", "CUSTODIANTE"),
    "taxa_adm": ("Taxa_Administracao", "TAXA_ADM"),
    "taxa_perfm": ("Taxa_Performance", "TAXA_PERFM"),
}


def converter_cadastro(arquivos: Iterable[tuple[str, str]], cnpjs: set[str] | None) -> dict[str, dict]:
    """Junta registro_fundo + registro_classe (ou cad_fi) por CNPJ da classe/fundo.

    A classe herda do fundo o que não tem (administrador, gestor). Campos sem coluna
    na fonte ficam de fora; `_fonte` diz de qual arquivo veio cada registro.
    """
    fundos_por_id: dict[str, dict] = {}
    classes: dict[str, dict] = {}
    antigos: dict[str, dict] = {}
    for nome, texto in arquivos:
        base = re.sub(r".*/", "", nome).lower()
        for l in linhas(texto):
            reg = {k: v for k, alts in CAMPOS_CADASTRO.items() if (v := campo(l, *alts, padrao=None)) not in (None, "")}
            if base.startswith("registro_fundo"):
                fundos_por_id[campo(l, "ID_Registro_Fundo")] = {**reg, "cnpj_fundo": so_digitos(campo(l, "CNPJ_Fundo"))}
            elif base.startswith("registro_classe"):
                cnpj = so_digitos(campo(l, "CNPJ_Classe"))
                if cnpj and (cnpjs is None or cnpj in cnpjs):
                    classes[cnpj] = {**reg, "_id_fundo": campo(l, "ID_Registro_Fundo"), "_fonte": "registro_classe"}
            elif base.startswith("registro_subclasse"):
                continue
            else:
                cnpj = so_digitos(campo(l, "CNPJ_FUNDO"))
                if cnpj and (cnpjs is None or cnpj in cnpjs):
                    # cad_fi repete o CNPJ em registros cancelados: fica o em funcionamento.
                    if cnpj not in antigos or reg.get("situacao", "").upper().startswith("EM FUNCIONAMENTO"):
                        antigos[cnpj] = {**reg, "_fonte": "cad_fi"}
    out = dict(antigos)
    for cnpj, reg in classes.items():
        fundo = fundos_por_id.get(reg.pop("_id_fundo"), {})
        out[cnpj] = {**{k: v for k, v in fundo.items()}, **reg}
    for reg in out.values():
        for k in ("pl", "taxa_adm", "taxa_perfm"):
            if k in reg:
                reg[k] = numero(reg[k])
    return out


def baixar_cadastro(cnpjs: set[str] | None, sessao=None) -> dict[str, dict]:
    arquivos = list(arquivos_csv(baixar(URL_REGISTRO, sessao=sessao)))
    try:
        arquivos.append(("cad_fi.csv", next(arquivos_csv(baixar(URL_CAD_ANTIGO, sessao=sessao)))[1]))
    except NaoEncontrado:
        pass
    return converter_cadastro(arquivos, cnpjs)
