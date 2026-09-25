import datetime as dt

import pytest

from painel_fiscal.coletores import bcb_sgs, ibge_sidra, siconfi


def test_bcb_converte_formato_sgs():
    itens = [{"data": "01/07/2026", "valor": "78.95"}, {"data": "01/08/2026", "valor": "79,20"},
             {"data": "01/09/2026", "valor": ""}]
    obs = bcb_sgs.converter("dbgg_pct_pib", itens, 13762, dt.date(2026, 9, 25))
    assert [o.data_referencia for o in obs] == [dt.date(2026, 7, 31), dt.date(2026, 8, 31)]
    assert obs[1].valor == pytest.approx(79.2)
    assert obs[0].fonte == "bcb_sgs:13762"


def test_bcb_inverte_sinal_nfsp():
    obs = bcb_sgs.converter("primario_gc_abaixo_linha_bi", [{"data": "01/12/2025", "valor": "12.5"}],
                            1, dt.date.today(), fator=-1)
    assert obs[0].valor == -12.5


class SessaoFalsa:
    def __init__(self, paginas):
        self.paginas, self.chamadas = paginas, []

    def get(self, url, params=None, timeout=None, headers=None):
        self.chamadas.append(params)
        pagina = self.paginas[len(self.chamadas) - 1]

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return pagina
        return R()


def test_siconfi_pagina_ate_hasmore_false():
    s = SessaoFalsa([{"items": [{"a": 1}] * 2, "hasMore": True, "limit": 2},
                     {"items": [{"a": 2}], "hasMore": False, "limit": 2}])
    itens = siconfi.buscar_itens("rgf", {"an_exercicio": 2025}, s)
    assert len(itens) == 3
    assert [c["offset"] for c in s.chamadas] == [0, 2]


ITENS_RGF = [
    {"anexo": "RGF-Anexo 01", "conta": "RECEITA CORRENTE LÍQUIDA - RCL", "coluna": "VALOR", "valor": 1.48e12},
    {"anexo": "RGF-Anexo 01", "conta": "DESPESA TOTAL COM PESSOAL - DTP", "coluna": "VALOR", "valor": 4.4e11},
    {"anexo": "RGF-Anexo 01", "conta": "DESPESA TOTAL COM PESSOAL - DTP", "coluna": "% SOBRE A RCL", "valor": 29.7},
]


def test_siconfi_extrai_por_mapeamento():
    mapa = [{"indicador": "rcl_bi", "anexo": "RGF-Anexo 01", "conta": "RECEITA CORRENTE L[IÍ]QUIDA", "coluna": "^VALOR"},
            {"indicador": "dtp_total_bi", "anexo": "RGF-Anexo 01", "conta": "DESPESA TOTAL COM PESSOAL", "coluna": "^VALOR"}]
    obs = {o.indicador: o for o in siconfi.extrair(ITENS_RGF, mapa, dt.date(2026, 8, 31), dt.date.today(), "x")}
    assert obs["rcl_bi"].valor == pytest.approx(1480)
    assert obs["dtp_total_bi"].valor == pytest.approx(440)


def test_siconfi_mapeamento_ambiguo_falha():
    mapa = [{"indicador": "dtp_total_bi", "conta": "DESPESA TOTAL COM PESSOAL"}]
    with pytest.raises(ValueError, match="2 linhas"):
        siconfi.extrair(ITENS_RGF, mapa, dt.date(2026, 8, 31), dt.date.today(), "x")


def test_siconfi_fim_de_periodo():
    assert siconfi.data_fim_periodo("rgf", 2026, 2) == dt.date(2026, 8, 31)
    assert siconfi.data_fim_periodo("rreo", 2026, 1) == dt.date(2026, 2, 28)


def test_sidra_converte():
    linhas = [{"V": "Valor", "D3C": "Mês (Código)"}, {"V": "0.24", "D3C": "202606"},
              {"V": "...", "D3C": "202607"}]
    obs = ibge_sidra.converter("ipca_mensal", linhas, 1737, dt.date.today(), escala=0.01)
    assert len(obs) == 1 and obs[0].data_referencia == dt.date(2026, 6, 30)
    assert obs[0].valor == pytest.approx(0.0024)


def test_bcb_acumula_fluxo_mensal_no_ano():
    itens = [{"data": "01/11/2025", "valor": "10"}, {"data": "01/12/2025", "valor": "5"},
             {"data": "01/01/2026", "valor": "-2"}, {"data": "01/02/2026", "valor": "3"}]
    obs = bcb_sgs.converter("primario_gc_abaixo_linha_bi", itens, 4639, dt.date.today(),
                            fator=-0.001, acumular_no_ano=True)
    assert [round(o.valor, 4) for o in obs] == [-0.01, -0.015, 0.002, -0.001]
    assert obs[1].data_referencia == dt.date(2025, 12, 31)


def test_siconfi_filtra_cod_conta_periodo_e_instituicao():
    itens = [
        {"cod_conta": "DividaConsolidadaLiquida", "coluna": "Até o 2º Quadrimestre", "valor": 1e12},
        {"cod_conta": "DividaConsolidadaLiquida", "coluna": "Até o 3º Quadrimestre", "valor": 2e12},
        {"cod_conta": "DespesaComPessoalTotal", "coluna": "Valor", "instituicao": "Câmara", "valor": 4e9},
        {"cod_conta": "DespesaComPessoalTotal", "coluna": "Valor", "instituicao": "Senado", "valor": 5e9},
        {"cod_conta": "DespesaComPessoalTotal", "coluna": "% sobre a RCL", "instituicao": "Senado", "valor": 0.3},
    ]
    mapa = [{"indicador": "dcl_bi", "cod_conta": "DividaConsolidadaLiquida", "coluna": "^At[eé] o {periodo}º"},
            {"indicador": "dtp_legislativo_incl_tcu_bi", "cod_conta": "DespesaComPessoalTotal",
             "coluna": "^valor$", "somar": True},
            {"indicador": "dtp_senado_bi", "cod_conta": "DespesaComPessoalTotal", "coluna": "^valor$",
             "instituicao": "senado"}]
    obs = {o.indicador: o.valor for o in siconfi.extrair(itens, mapa, dt.date(2025, 12, 31),
                                                          dt.date.today(), "x", periodo=3)}
    assert obs == {"dcl_bi": pytest.approx(2000), "dtp_legislativo_incl_tcu_bi": pytest.approx(9),
                   "dtp_senado_bi": pytest.approx(5)}


def test_siop_investimentos_e_discricionarias(tmp_path):
    from painel_fiscal.coletores import siop
    csv_ = tmp_path / "siop_rp_gnd_2025.csv"
    csv_.write_text(
        '"exercicio";"rp_cod";"rp_desc";"gnd_cod";"gnd_desc";"ploa";"loa";"loa_mais_credito";"empenhado";"liquidado";"pago"\n'
        '2025;"1";"Obrigatória";"4";"Investimentos";0;10e9;11e9;9e9;0;0\n'
        '2025;"2";"Discricionária";"4";"Investimentos";0;50e9;55e9;40e9;0;0\n'
        '2025;"2";"Discricionária";"3";"Outras Despesas Correntes";0;100e9;120e9;90e9;0;0\n'
        '2025;"0";"Financeira";"4";"Investimentos";0;7e9;7e9;7e9;0;0\n'
        '2025;"6";"Emendas individuais";"4";"Investimentos";0;5e9;5e9;1e9;0;0\n', encoding="utf-8")
    cfg = {"rp_primarias": [1, 2, 3, 6, 7, 8, 9], "rp_discricionarias": [2, 3, 6, 7, 8, 9]}
    obs = {o.indicador: o for o in siop.converter(siop.ler_csv(csv_), 2025, cfg, dt.date.today())}
    assert obs["investimentos_loa_bi"].valor == pytest.approx(65)          # 10+50+5, sem RP 0
    assert obs["investimentos_ploa_bi"].valor == 0                          # coluna ploa zerada no teste
    assert obs["despesas_discricionarias_bi"].valor == pytest.approx(180)  # 55+120+5
    assert obs["despesas_discricionarias_bi"].tipo == "projecao"
    assert obs["despesas_discricionarias_empenhadas_bi"].valor == pytest.approx(131)


def test_siconfi_conta_blocos():
    itens = [{"cod_conta": "DespesaComPessoalTotal", "coluna": "Valor", "valor": 1e9},
             {"cod_conta": "DespesaComPessoalTotal", "coluna": "Valor", "valor": 2e9},
             {"cod_conta": "DespesaComPessoalTotal", "coluna": "% sobre a RCL", "valor": 0.1}]
    mapa = [{"indicador": "n_blocos_dtp_mpu", "cod_conta": "DespesaComPessoalTotal", "coluna": "^valor$", "contar": True}]
    obs = siconfi.extrair(itens, mapa, dt.date(2026, 4, 30), dt.date.today(), "x", periodo=1)
    assert obs[0].valor == 2
