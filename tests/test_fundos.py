"""Pacote fundos/: leitura dos formatos da CVM e do CADPREV e cálculo dos indicadores.

Os CSV abaixo imitam o layout das fontes (cabeçalho e separador); os valores são inventados.
"""
import datetime as dt
import gzip
import io
import math
import zipfile

import pytest

from fundos import armazem, cadprev, cdi, cvm, metricas
from fundos.cvm import Cota
from fundos.tabela import formatar_cnpj, numero, so_digitos

INF_CVM175 = (
    "TP_FUNDO_CLASSE;CNPJ_FUNDO_CLASSE;ID_SUBCLASSE;DT_COMPTC;VL_TOTAL;VL_QUOTA;VL_PATRIM_LIQ;"
    "CAPTC_DIA;RESG_DIA;NR_COTST\n"
    "CLASSES - FIF;11.111.111/0001-11;;2026-08-03;100;1.500000000000;1000000.00;10.00;0.00;50\n"
    "CLASSES - FIF;11.111.111/0001-11;SUB1;2026-08-03;100;1.400000000000;500000.00;0;0;10\n"
    "CLASSES - FIF;22.222.222/0001-22;;2026-08-03;100;2.000000000000;2000000.00;0;5.00;80\n"
    "CLASSES - FIF;33.333.333/0001-33;;2026-08-03;100;;0;0;0;0\n"
)
INF_ANTIGO = (
    "TP_FUNDO;CNPJ_FUNDO;DT_COMPTC;VL_TOTAL;VL_QUOTA;VL_PATRIM_LIQ;CAPTC_DIA;RESG_DIA;NR_COTST\n"
    "FI;11.111.111/0001-11;2019-01-02;100;1.1;1000;0;0;40\n"
)


def test_cnpj_e_numeros():
    assert so_digitos("11.111.111/0001-11") == "11111111000111"
    assert formatar_cnpj("11111111000111") == "11.111.111/0001-11"
    assert numero("1.234,56") == 1234.56 and numero("1234.56") == 1234.56 and numero("") is None


def test_informe_cvm175_filtra_universo_e_ignora_cota_vazia():
    cotas = list(cvm.converter_informe(INF_CVM175, {"11111111000111", "33333333000133"}))
    assert [(c.cnpj, c.subclasse, c.cota) for c in cotas] == [
        ("11111111000111", "", 1.5), ("11111111000111", "SUB1", 1.4)]
    assert cotas[0].pl == 1_000_000 and cotas[0].cotistas == 50 and cotas[0].data == dt.date(2026, 8, 3)


def test_informe_formato_anterior_a_cvm175():
    (c,) = cvm.converter_informe(INF_ANTIGO, None)
    assert c.cnpj == "11111111000111" and c.subclasse == "" and c.cota == 1.1


class Resp:
    def __init__(self, status, conteudo=b""):
        self.status_code, self.content = status, conteudo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class Sessao:
    def __init__(self, rotas):
        self.rotas, self.urls = rotas, []

    def get(self, url, params=None, timeout=None, headers=None):
        self.urls.append(url)
        return self.rotas.get(url, Resp(404))


def _zip(arquivos):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, texto in arquivos.items():
            z.writestr(nome, texto.encode("latin-1"))
    return buf.getvalue()


def test_mes_sem_zip_mensal_usa_historico_anual():
    hist = _zip({"inf_diario_fi_201901.csv": INF_ANTIGO, "inf_diario_fi_201902.csv": INF_ANTIGO.replace("01-02", "02-01")})
    s = Sessao({cvm.URL_INF_ANO.format(aaaa=2019): Resp(200, hist)})
    cotas = cvm.baixar_informe(2019, 1, None, s)
    assert [c.data for c in cotas] == [dt.date(2019, 1, 2)]     # só o membro do mês pedido
    assert s.urls[0].endswith("inf_diario_fi_201901.zip")


def test_cadastro_junta_fundo_e_classe():
    arquivos = [
        ("registro_fundo.csv", "ID_Registro_Fundo;CNPJ_Fundo;Denominacao_Social;Administrador;Gestor\n"
                               "7;99.999.999/0001-99;FUNDO X;ADM SA;GESTORA SA\n"),
        ("registro_classe.csv", "ID_Registro_Fundo;ID_Registro_Classe;CNPJ_Classe;Denominacao_Social;"
                                "Situacao;Classificacao_Anbima;Patrimonio_Liquido\n"
                                "7;70;11.111.111/0001-11;CLASSE X;Em Funcionamento Normal;Renda Fixa;1234,5\n"
                                "7;71;44.444.444/0001-44;FORA;Em Funcionamento Normal;;\n"),
    ]
    cad = cvm.converter_cadastro(arquivos, {"11111111000111"})
    assert list(cad) == ["11111111000111"]
    r = cad["11111111000111"]
    assert r["nome"] == "CLASSE X" and r["gestor"] == "GESTORA SA" and r["pl"] == 1234.5


def _serie_diaria(inicio, fim, taxa_dia, choque=None, oscila=0.0):
    """Dias úteis (seg–sex) com retorno constante (± `oscila` alternado); `choque` = (data, retorno)."""
    s, v, d = [], 1.0, inicio
    while d <= fim:
        if d.weekday() < 5:
            osc = oscila if len(s) % 2 else -oscila
            v *= 1 + (choque[1] if choque and d == choque[0] else taxa_dia + osc)
            s.append((d, v))
        d += dt.timedelta(days=1)
    return s


def test_janela_retorno_vol_drawdown():
    s = _serie_diaria(dt.date(2024, 1, 1), dt.date(2025, 12, 31), 0.0005, choque=(dt.date(2025, 6, 2), -0.10))
    j = metricas.janela(s, dt.date(2024, 12, 31), dt.date(2025, 12, 31))
    dias = sum(1 for d, _ in s if d.year == 2025)
    assert j["r"] == pytest.approx(1.0005 ** (dias - 1) * 0.9 - 1)
    assert j["d"] == pytest.approx(-0.10)
    assert j["v"] > 0.05                        # o choque domina a volatilidade


def test_janela_maior_que_historico_fica_vazia():
    s = _serie_diaria(dt.date(2025, 3, 1), dt.date(2025, 12, 31), 0.001)
    assert metricas.janela(s, dt.date(2024, 12, 31), dt.date(2025, 12, 31)) == {"r": None, "v": None, "d": None}


def test_fundo_que_parou_de_informar_nao_tem_retorno_recente():
    s = _serie_diaria(dt.date(2024, 1, 1), dt.date(2025, 3, 31), 0.001)
    assert metricas.janela(s, dt.date(2024, 12, 31), dt.date(2025, 12, 31))["r"] is None


def test_menos_meses_respeita_fim_de_mes():
    assert metricas.menos_meses(dt.date(2026, 3, 31), 1) == dt.date(2026, 2, 28)
    assert metricas.menos_meses(dt.date(2026, 8, 31), 12) == dt.date(2025, 8, 31)


def test_serie_prefere_informe_da_classe():
    d = dt.date(2026, 1, 2)
    cotas = [Cota("1", "SUB", d, 1.0), Cota("1", "SUB", d + dt.timedelta(1), 1.1), Cota("1", "", d, 2.0)]
    assert [c.subclasse for c in metricas.series_por_fundo(cotas)["1"]] == [""]


def test_montar_base_no_formato_da_matriz():
    serie = _serie_diaria(dt.date(2022, 1, 1), dt.date(2026, 8, 31), 0.0004, oscila=0.002)
    cotas = [Cota("11111111000111", "", d, v, pl=1e6, captacao=10.0, resgate=4.0) for d, v in serie]
    cdi_s = _serie_diaria(dt.date(2022, 1, 1), dt.date(2026, 8, 31), 0.0005)
    universo = [{"cnpj": "11.111.111/0001-11", "cnpj14": "11111111000111", "nome": "F"},
                {"cnpj": "22.222.222/0001-22", "cnpj14": "22222222000122", "nome": "G"}]
    base = metricas.montar_base(cotas, universo, cdi_s, dt.date(2026, 8, 31), 2020)
    assert base["years"] == [2020, 2021, 2022, 2023, 2024, 2025]
    assert len(base["meses"]) == 36 and base["meses"][-1] == "2026-07"
    (f,) = base["funds"]
    assert f["c"] == "11.111.111/0001-11" and base["sem_dado"] == ["22.222.222/0001-22"]
    assert f["ry"][:2] == [None, None] and f["ry"][3] > 0          # 2022 sem cota de dez/2021
    assert f["r36"] is not None and -0.01 < f["dd12"] < 0
    assert f["sh"] < 0                                             # rende abaixo do "CDI"
    assert f["cap12"] > 0 and f["pl"] == 1e6
    assert set(base["bench"]["CDI"]) >= {"r12", "ry", "rm"}


def test_cdi_vira_indice():
    pts = cdi.converter([{"data": "03/01/2026", "valor": "0,05"}, {"data": "02/01/2026", "valor": "0.05"}])
    assert pts[0][0] == dt.date(2026, 1, 2) and pts[1][1] == pytest.approx(1.0005 ** 2)


def test_armazem_substitui_mes_e_e_deterministico(tmp_path):
    d1, d2 = dt.date(2026, 7, 31), dt.date(2026, 8, 3)
    armazem.gravar_cotas([Cota("1", "", d1, 1.0), Cota("1", "", d2, 1.1)], {(2026, 7), (2026, 8)}, tmp_path)
    antes = (tmp_path / "cotas" / "2026.csv.gz").read_bytes()
    armazem.gravar_cotas([Cota("1", "", d2, 1.2)], {(2026, 8)}, tmp_path)   # CVM republicou agosto
    assert [(c.data, c.cota) for c in armazem.ler_cotas(tmp_path)] == [(d1, 1.0), (d2, 1.2)]
    armazem.gravar_cotas([Cota("1", "", d1, 1.0), Cota("1", "", d2, 1.1)], {(2026, 7), (2026, 8)}, tmp_path)
    assert (tmp_path / "cotas" / "2026.csv.gz").read_bytes() == antes
    assert gzip.decompress(antes).decode().startswith("cnpj;subclasse;data")


CSV_DAIR = (
    "Ente;UF;CNPJ do Ente;Competência;Segmento;Tipo de Ativo;CNPJ do Fundo;Nome do Fundo;Valor Total;Coluna Nova\n"
    "IGEPPS - PARÁ;PA;05.000.000/0001-00;08/2026;Renda Fixa;Art. 7º, I, b;11.111.111/0001-11;F;1.000,00;x\n"
    "RPPS OUTRO;PA;06.000.000/0001-00;08/2026;Renda Fixa;Art. 7º, I, b;11.111.111/0001-11;F;500,00;x\n"
    "RPPS OUTRO;PA;06.000.000/0001-00;08/2026;Renda Fixa;Título Público;;NTN-B 2035;300,00;x\n"
)


def test_cadprev_importa_csv_e_resume(tmp_path):
    arq = tmp_path / "dair.csv"
    arq.write_bytes(CSV_DAIR.encode("latin-1"))
    pos, sobra = cadprev.importar_arquivo(arq)
    assert pos[0]["cnpj_fundo"] == "11111111000111" and pos[0]["valor"] == 1000.0
    assert pos[0]["artigo"] == "Art. 7º, I, b" and pos[0]["competencia"] == "08/2026"
    assert sobra == ["coluna_nova"]
    r = cadprev.resumo_por_fundo(pos, nome_ente="IGEPPS")
    assert r == {"11111111000111": {"n_rpps": 2, "valor_rpps": 1500.0, "valor_proprio": 1000.0}}


def test_universo_da_matriz_carrega():
    u = armazem.ler_universo()
    assert len(u) > 300 and all(len(x["cnpj14"]) == 14 for x in u)
    assert len({x["cnpj14"] for x in u}) == len(u)
