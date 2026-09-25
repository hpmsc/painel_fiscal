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


def test_pendencia_de_deducao_some_com_total_informado(params):
    import datetime as dt
    from painel_fiscal.dados import Observacao
    from painel_fiscal.painel.render import _pendencias

    def o(ind, v):
        return Observacao(indicador=ind, valor=v, data_referencia=dt.date(2026, 12, 31),
                          fonte="rardp", tipo="projecao")
    sem = _pendencias(params, 2026, apurar(params, 2026, BaseDados(2026, [o("primario_gc_abaixo_linha_bi", -80.9)])))
    com = _pendencias(params, 2026, apurar(params, 2026, BaseDados(2026, [
        o("primario_gc_abaixo_linha_bi", -80.9), o("deducoes_meta_total_bi", 67.3)])))
    assert any("Precatórios" in p["texto"] for p in sem)
    assert not any("Precatórios" in p["texto"] for p in com)
