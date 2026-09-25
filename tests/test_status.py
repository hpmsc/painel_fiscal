from painel_fiscal.apuracao import status as st

NIVEIS = {"alerta": 0.90, "prudencial": 0.95, "excedido": 1.00}


def test_percentual_faixas():
    assert st.percentual(0.8999, NIVEIS) == st.OK
    assert st.percentual(0.90, NIVEIS) == st.ALERTA
    assert st.percentual(0.95, NIVEIS) == st.PRUDENCIAL
    assert st.percentual(1.00, NIVEIS) == st.EXCEDIDO


def test_meta_banda():
    assert st.meta_banda(-0.1, 0.0, 68.5) == st.DESCUMPRE
    assert st.meta_banda(0.0, 0.0, 68.5) == st.CUMPRE
    assert st.meta_banda(68.6, 0.0, 68.5) == st.ACIMA_TETO


def test_minimo_maximo_pior():
    assert st.minimo(0.15, 0.15) == st.CUMPRE
    assert st.minimo(0.149, 0.15) == st.DESCUMPRE
    assert st.maximo(0, 0) == st.CUMPRE
    assert st.pior([st.OK, st.PRUDENCIAL, st.ALERTA]) == st.PRUDENCIAL
    assert st.pior([]) == st.SEM_DADOS
