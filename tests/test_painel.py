from painel_fiscal.apuracao.regras import apurar
from painel_fiscal.config import RAIZ
from painel_fiscal.dados import BaseDados, carregar_arquivo
from painel_fiscal.painel.render import formatar, renderizar


def test_formatacao_pt_br():
    assert formatar(2219.3, "R$ bi") == "R$ 2.219,3 bi"
    assert formatar(0.297, "fracao") == "29,7%"
    assert formatar(0.0057, "fracao") == "0,57%"
    assert formatar(None, "R$ bi") == "—"


def test_painel_ilustrativo_tem_aviso_e_todas_as_regras(params):
    b = carregar_arquivo(RAIZ / "exemplos" / "dados_ilustrativos_2026.yaml")
    html = renderizar(params, 2026, apurar(params, 2026, b), ilustrativo=b.tem_ilustrativo)
    assert "DADOS ILUSTRATIVOS" in html
    for i in range(1, 18):
        assert f">R{i:02d}<" in html
    assert html.count("<svg") == 4


def test_painel_vazio_renderiza(params):
    html = renderizar(params, 2027, apurar(params, 2027, BaseDados(2027)))
    assert "DADOS ILUSTRATIVOS" not in html
    assert "PLDO" in html
