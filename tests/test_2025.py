"""Regressão com números reais de 2025 (SICONFI, RGF 3º quadrimestre e RREO 6º bimestre),
obtidos no diagnóstico de 25/09/2026 (workflow diagnostico.yml). Valores em R$ bilhões."""
import datetime as dt

import pytest

from painel_fiscal.apuracao import status as st
from painel_fiscal.apuracao.regras import apurar
from painel_fiscal.coletores import siconfi
from painel_fiscal.dados import BaseDados, Observacao

REF = "2025-12-31"


def o(indicador, valor):
    return Observacao(indicador=indicador, valor=valor, data_referencia=dt.date.fromisoformat(REF),
                      fonte="siconfi_2025")


@pytest.fixture
def base_2025():
    return BaseDados(2025, [
        o("rcl_bi", 1517.74),
        # RGF Anexo 1 — soma dos blocos de cada Poder
        o("dtp_executivo_bi", 284.02 + 18.78 + 1.02 + 0.69),        # União, DF, Amapá, Roraima
        o("limite_dtp_executivo_bi", 575.22 + 33.39 + 2.56 + 1.50),
        o("dtp_legislativo_incl_tcu_bi", 4.50 + 5.37 + 2.01),       # Senado, Câmara, TCU
        o("limite_dtp_legislativo_incl_tcu_bi", 13.05 + 18.36 + 6.53),
        o("dtp_mpu_bi", 6.09 + 0.95),                               # MPU, MPDFT
        o("limite_dtp_mpu_bi", 9.11 + 2.02),
        # RGF Anexo 4 e RREO Anexo 9
        o("operacoes_credito_rgf_bi", 664.97),
        o("receitas_operacoes_credito_bi", 2035.72),
        o("despesas_capital_bi", 2114.90),
    ])


@pytest.fixture
def params_2025(params):
    # 2025 não tem parâmetros no YAML (só 2026/2027); para as regras testadas aqui
    # basta a estrutura de um exercício.
    from painel_fiscal.config import Parametros
    bruto = dict(params.bruto)
    bruto["exercicios"] = {**params.bruto["exercicios"], 2025: params.bruto["exercicios"][2026]}
    return Parametros(bruto)


def test_regra_de_ouro_2025(params_2025, base_2025):
    r = {x.id: x for x in apurar(params_2025, 2025, base_2025)}["R08"]
    # RREO Anexo 9 publica "resultado para apuração da regra de ouro" = 79,19 (II − I)
    assert r.valor == pytest.approx(-79.18, abs=0.01)
    assert r.status == st.CUMPRE


def test_pessoal_por_poder_2025_usa_limite_oficial(params_2025, base_2025):
    r10 = {x.id: x for x in apurar(params_2025, 2025, base_2025)}["R10"]
    d = {x.nome: x for x in r10.detalhes}
    assert d["executivo"].extras["uso_do_limite"] == pytest.approx(304.51 / 612.67)
    # 575,22 é 37,9% da RCL: 40,9% menos os 3% do DF e ex-territórios, que ficam nos outros blocos
    assert d["executivo"].limite == pytest.approx(612.67 / 1517.74)
    assert d["mpu"].extras["uso_do_limite"] == pytest.approx(7.04 / 11.13)
    assert all(x.status == st.OK for x in d.values() if "uso_do_limite" in x.extras)
    assert d["judiciario"].status == st.SEM_DADOS


def test_operacoes_de_credito_2025(params_2025, base_2025):
    r = {x.id: x for x in apurar(params_2025, 2025, base_2025)}["R13"]
    assert r.valor == pytest.approx(664.97 / 1517.74)
    assert r.limite == 0.60          # RGF Anexo 4: limite 910,64 = 60% de 1.517,74
    assert r.status == st.OK


def test_mapeamento_casa_com_linhas_reais_do_rgf():
    import yaml
    from painel_fiscal.config import RAIZ
    mapa = yaml.safe_load(open(RAIZ / "config" / "mapeamento_siconfi.yaml", encoding="utf-8"))
    itens = [  # recorte das linhas reais do RGF 2025 (3º quadrimestre)
        {"anexo": "RGF-Anexo 02", "cod_conta": "DividaConsolidadaLiquida", "coluna": "SALDO DO EXERCÍCIO ANTERIOR", "valor": 7109.71e9},
        {"anexo": "RGF-Anexo 02", "cod_conta": "DividaConsolidadaLiquida", "coluna": "Até o 3º Quadrimestre", "valor": 7500e9},
        {"anexo": "RGF-Anexo 04", "cod_conta": "RGF4ReceitaCorrenteLiquida", "coluna": "VALOR", "valor": 1517.74e9},
        {"anexo": "RGF-Anexo 04", "cod_conta": "TotalConsideradoParaFinsDaApuracaoDoCumprimentoDoLimiteOperacoesDeCredito", "coluna": "VALOR", "valor": 664.97e9},
    ]
    obs = {x.indicador: x.valor for x in siconfi.extrair(itens, mapa["rgf"], dt.date(2025, 12, 31),
                                                          dt.date.today(), "t", periodo=3)}
    assert obs["rcl_bi"] == pytest.approx(1517.74)
    assert obs["dcl_bi"] == pytest.approx(7500)      # coluna do período, não o saldo anterior
    assert obs["operacoes_credito_rgf_bi"] == pytest.approx(664.97)
    pessoal = [{**e, "indicador": e["indicador"].format(poder="mpu")} for e in mapa["rgf_pessoal"]]
    linhas = [
        {"anexo": "RGF-Anexo 01", "cod_conta": "DespesaComPessoalTotal", "coluna": "Valor", "valor": 6.09e9},
        {"anexo": "RGF-Anexo 01", "cod_conta": "DespesaComPessoalTotal", "coluna": "% sobre a RCL", "valor": 0.4},
        {"anexo": "RGF-Anexo 01", "cod_conta": "DespesaComPessoalTotal", "coluna": "Valor", "valor": 0.95e9},
        {"anexo": "RGF-Anexo 01", "cod_conta": "LimiteMaximoDespesaComPessoalTotal", "coluna": "Valor", "valor": 9.11e9},
        {"anexo": "RGF-Anexo 01", "cod_conta": "LimiteMaximoDespesaComPessoalTotal", "coluna": "Valor", "valor": 2.02e9},
    ]
    obs = {x.indicador: x.valor for x in siconfi.extrair(linhas, pessoal, dt.date(2025, 12, 31),
                                                          dt.date.today(), "t", periodo=3)}
    assert obs == {"dtp_mpu_bi": pytest.approx(7.04), "limite_dtp_mpu_bi": pytest.approx(11.13)}
