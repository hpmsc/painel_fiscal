import pytest

from painel_fiscal.apuracao import status as st
from painel_fiscal.apuracao.regras import APURADORES, apurar
from painel_fiscal.dados import carregar_arquivo
from painel_fiscal.config import RAIZ

from conftest import obs


def por_id(params, exercicio, base):
    return {r.id: r for r in apurar(params, exercicio, base)}


def test_yaml_e_apuradores_cobrem_as_mesmas_regras(params):
    assert {r["id"] for r in params.regras} == set(APURADORES)


def test_exercicios_tem_meta(params):
    for ano in (2026, 2027):
        assert params.exercicio(ano)["meta_primaria"]["centro_bi"] > 0


def test_sem_dados_nao_quebra(params, base):
    res = por_id(params, 2026, base())
    assert res["R01"].status == st.SEM_DADOS
    assert res["R09"].status == st.SEM_DADOS
    assert res["R04"].status == st.CONTROVERSIA          # vem só do YAML


# ---------------------------------------------------------------- R01

def test_r01_2026_projecao_com_deducao(params, base):
    b = base(2026,
             obs("primario_gc_abaixo_linha_bi", -8.0, "2026-12-31", "projecao"),
             obs("despesas_fundo_social_bi", 12.0, "2026-12-31", "projecao"),
             obs("precatorios_bi", 50.0, "2026-12-31", "projecao"))
    r = por_id(params, 2026, b)["R01"]
    assert r.base_apuracao == "projecao"
    assert r.valor == pytest.approx(4.0)                 # precatórios 2026: não deduz (a confirmar)
    assert r.status == st.CUMPRE
    assert r.extras["inferior"] == 0.0 and r.extras["superior"] == 68.5
    assert any("Precatórios" in n for n in r.notas)


def test_r01_realizado_de_dezembro_prevalece(params, base):
    b = base(2026,
             obs("primario_gc_abaixo_linha_bi", -3.0, "2026-12-31", "realizado"),
             obs("primario_gc_abaixo_linha_bi", 20.0, "2026-12-31", "projecao"))
    r = por_id(params, 2026, b)["R01"]
    assert r.base_apuracao == "realizado"
    assert r.status == st.DESCUMPRE


def test_r01_acumulado_parcial_fica_em_apuracao(params, base):
    b = base(2026, obs("primario_gc_abaixo_linha_bi", -45.0, "2026-08-31"))
    assert por_id(params, 2026, b)["R01"].status == st.EM_APURACAO


def test_r01_acima_do_teto_e_r06(params, base):
    b = base(2026, obs("primario_gc_abaixo_linha_bi", 100.0, "2026-12-31"),
             obs("fator_ipca_desde_jan2023", 1.2, "2025-12-31"))
    res = por_id(params, 2026, b)
    assert res["R01"].status == st.ACIMA_TETO
    assert res["R06"].valor == pytest.approx(100.0 - 68.5)
    assert res["R06"].limite == pytest.approx(30.0)
    assert res["R06"].extras["utilizavel_bi"] == pytest.approx(30.0)


def test_r01_2027_banda_e_deducoes_do_pldo(params, base):
    b = base(2027,
             obs("primario_gc_abaixo_linha_bi", -60.0, "2027-12-31", "projecao"),
             obs("precatorios_bi", 100.0, "2027-12-31", "projecao"),
             obs("despesas_excepcionalizadas_bi", 80.0, "2027-12-31", "projecao"))
    r = por_id(params, 2027, b)["R01"]
    assert r.extras["inferior"] == pytest.approx(73.2 - 36.61)
    assert r.extras["superior"] == pytest.approx(73.2 + 36.61)
    # precatórios: deduz 60,6% de 100; excepcionalizadas: limitado a 65,66
    assert r.extras["total_deducoes"] == pytest.approx(100 * (1 - 0.394) + 65.66)
    assert r.valor == pytest.approx(-60 + 60.6 + 65.66)
    assert r.status == st.CUMPRE


# ---------------------------------------------------------------- R02 / R03

def test_r03_fator_piso_e_teto(params, base):
    def calc(var, cumprida):
        b = base(2026, obs("variacao_real_receita_primaria_12m_jun", var, "2025-06-30"),
                 obs("meta_ano_anterior_cumprida", cumprida, "2025-12-31"))
        return por_id(params, 2026, b)["R03"].valor
    assert calc(0.02, True) == pytest.approx(0.014)
    assert calc(0.02, False) == pytest.approx(0.010)
    assert calc(0.10, True) == pytest.approx(0.025)
    assert calc(-0.05, True) == pytest.approx(0.006)


def test_r02_calcula_limite_quando_ausente(params, base):
    b = base(2026,
             obs("variacao_real_receita_primaria_12m_jun", 0.02, "2025-06-30"),
             obs("meta_ano_anterior_cumprida", True, "2025-12-31"),
             obs("limite_despesa_anterior_bi", 2000.0, "2025-12-31"),
             obs("ipca_12m_jun", 0.05, "2025-06-30"),
             obs("despesa_sujeita_limite_bi", 2100.0, "2026-12-31", "projecao"))
    r = por_id(params, 2026, b)["R02"]
    esperado = 2000 * 1.05 * 1.014
    assert r.limite == pytest.approx(esperado)
    assert r.extras["uso_do_limite"] == pytest.approx(2100 / esperado)
    assert r.status == st.PRUDENCIAL


def test_r02_por_poder_puxa_o_pior(params, base):
    b = base(2026,
             obs("despesa_sujeita_limite_bi", 100, "2026-12-31", "projecao"),
             obs("limite_despesa_bi", 200, "2026-12-31", "projecao"),
             obs("despesa_sujeita_limite_mpu_bi", 10.2, "2026-12-31", "projecao"),
             obs("limite_despesa_mpu_bi", 10.0, "2026-12-31", "projecao"))
    r = por_id(params, 2026, b)["R02"]
    assert r.status == st.EXCEDIDO
    assert [d.nome for d in r.detalhes] == ["mpu"]


# ---------------------------------------------------------------- demais

def test_r08_regra_de_ouro_com_ressalva(params, base):
    b = base(2026, obs("receitas_operacoes_credito_bi", 1300), obs("despesas_capital_bi", 1050))
    assert por_id(params, 2026, b)["R08"].status == st.DESCUMPRE
    b.adicionar([obs("creditos_maioria_absoluta_bi", 300)])
    r = por_id(params, 2026, b)["R08"]
    assert r.status == st.CUMPRE and r.valor == pytest.approx(250)


def test_pessoal_r09_r10_r11(params, base):
    b = base(2026, obs("rcl_bi", 1000), obs("dtp_total_bi", 300),
             obs("dtp_executivo_bi", 250), obs("dtp_mpu_bi", 5.8))
    res = por_id(params, 2026, b)
    assert res["R09"].status == st.OK and res["R09"].valor == pytest.approx(0.30)
    mpu = next(d for d in res["R10"].detalhes if d.nome == "mpu")
    assert mpu.extras["uso_do_limite"] == pytest.approx(0.0058 / 0.006)
    assert mpu.status == st.PRUDENCIAL
    assert res["R10"].status == st.PRUDENCIAL
    assert res["R11"].status == st.PRUDENCIAL


def test_limite_a_confirmar_vira_pendente(params, base):
    b = base(2026, obs("contingenciamento_bi", 10, "2026-12-31", "projecao"),
             obs("despesas_discricionarias_bi", 200, "2026-12-31", "projecao"),
             obs("rcl_bi", 1000), obs("dcl_bi", 6000))
    res = por_id(params, 2026, b)
    assert res["R07"].status == st.PENDENTE            # limite null + verificar
    assert res["R14"].status == st.MONITORAMENTO       # sem limite legal


def test_minimos_saude_educacao(params, base):
    b = base(2026, obs("rcl_bi", 1000), obs("asps_bi", 149),
             obs("mde_bi", 190), obs("receita_liquida_impostos_bi", 1000))
    res = por_id(params, 2026, b)
    assert res["R16"].status == st.DESCUMPRE
    assert res["R17"].status == st.CUMPRE


def test_r15_compara_com_trajetoria(params, base):
    b = base(2026, obs("dbgg_pct_pib", 78.0, "2026-07-31"), obs("dbgg_pct_pib", 79.0),
             obs("trajetoria_ldo_dbgg_pct_pib", 80.5, "2026-12-31", "projecao"))
    r = por_id(params, 2026, b)["R15"]
    assert r.valor == 79.0 and r.limite == 80.5 and r.folga == pytest.approx(1.5)
    assert r.status == st.MONITORAMENTO


def test_exemplo_ilustrativo_apura_tudo(params):
    b = carregar_arquivo(RAIZ / "exemplos" / "dados_ilustrativos_2026.yaml")
    assert b.tem_ilustrativo
    res = apurar(params, 2026, b)
    assert len(res) == 17
    assert all(r.status != st.SEM_DADOS for r in res)


def test_r09_soma_os_poderes_quando_falta_total(params, base):
    b = base(2026, obs("rcl_bi", 1000), obs("dtp_executivo_bi", 300),
             obs("dtp_legislativo_incl_tcu_bi", 12), obs("dtp_judiciario_bi", 50), obs("dtp_mpu_bi", 7))
    r = por_id(params, 2026, b)["R09"]
    assert r.valor == pytest.approx(0.369)
    b2 = base(2026, obs("rcl_bi", 1000), obs("dtp_executivo_bi", 300))   # Poder faltando: não soma
    assert por_id(params, 2026, b2)["R09"].status == st.SEM_DADOS


def test_minimos_com_valor_minimo_publicado(params, base):
    # RREO Anexo 14 da União, 2025: saúde 234,55 aplicado vs. 227,66 mínimo; MDE 129,89 vs. 122,10
    b = base(2026, obs("asps_bi", 234.55, "2026-12-31"), obs("asps_minimo_bi", 227.66, "2026-12-31"),
             obs("mde_bi", 110.0, "2026-12-31"), obs("mde_minimo_bi", 122.10, "2026-12-31"))
    res = por_id(params, 2026, b)
    assert res["R16"].status == st.CUMPRE
    assert res["R16"].valor == pytest.approx(0.15 * 234.55 / 227.66)      # 15,45% da RCL
    assert res["R16"].extras["uso_do_minimo"] == pytest.approx(1.0303, abs=1e-4)
    assert res["R17"].status == st.DESCUMPRE


def test_minimos_no_meio_do_ano_ficam_em_apuracao(params, base):
    # RREO 2026, 3º bimestre (dado real): saúde 116,93 aplicado vs. mínimo anual 133,68
    b = base(2026, obs("asps_bi", 116.93, "2026-06-30"), obs("asps_minimo_bi", 133.68, "2026-06-30"))
    r = por_id(params, 2026, b)["R16"]
    assert r.status == st.EM_APURACAO and r.folga is None
    assert any("6º bimestre" in n for n in r.notas)


def test_pessoal_ignora_quadrimestre_incompleto(params, base):
    # RGF 2026 (dado real): Judiciário com 65 blocos no 1º quad. e só parte no 2º
    b = base(2026, obs("rcl_bi", 1561.14, "2026-04-30"),
             obs("dtp_judiciario_bi", 42.5, "2026-04-30"), obs("limite_dtp_judiciario_bi", 99.9, "2026-04-30"),
             obs("n_blocos_dtp_judiciario", 65, "2026-04-30"),
             obs("dtp_judiciario_bi", 3.78, "2026-08-31"), obs("limite_dtp_judiciario_bi", 8.67, "2026-08-31"),
             obs("n_blocos_dtp_judiciario", 9, "2026-08-31"))
    d = {x.nome: x for x in por_id(params, 2026, b)["R10"].detalhes}["judiciario"]
    assert d.extras["uso_do_limite"] == pytest.approx(42.5 / 99.9)
    assert d.data_referencia.isoformat() == "2026-04-30"
    assert any("incompleto" in n for n in d.notas)
    # quando o 2º quadrimestre fica completo, passa a ser usado
    b.adicionar([obs("dtp_judiciario_bi", 44.0, "2026-08-31"), obs("limite_dtp_judiciario_bi", 101.0, "2026-08-31"),
                 obs("n_blocos_dtp_judiciario", 65, "2026-08-31")])
    d = {x.nome: x for x in por_id(params, 2026, b)["R10"].detalhes}["judiciario"]
    assert d.extras["uso_do_limite"] == pytest.approx(44.0 / 101.0)


def test_r09_nao_mistura_quadrimestres(params, base):
    b = base(2026, obs("rcl_bi", 1000, "2026-04-30"), obs("rcl_bi", 1050, "2026-08-31"))
    for p, v in (("executivo", 300), ("legislativo_incl_tcu", 12), ("judiciario", 42), ("mpu", 7)):
        b.adicionar([obs(f"dtp_{p}_bi", v, "2026-04-30")])
    b.adicionar([obs("dtp_executivo_bi", 310, "2026-08-31")])      # só o Executivo publicou o 2º quad.
    r = por_id(params, 2026, b)["R09"]
    assert r.valor == pytest.approx(361 / 1000)
    assert r.data_referencia.isoformat() == "2026-04-30"


def test_r01_relatorio_bimestral_total_de_deducoes_e_contingenciamento(params, base):
    # RARDP 4º bimestre/2026: −80,9 projetado, deduções 67,3 → −13,6; contingenciamento 13,6 → piso
    b = base(2026,
             obs("primario_gc_abaixo_linha_bi", -80.9, "2026-12-31", "projecao"),
             obs("deducoes_meta_total_bi", 67.3, "2026-12-31", "projecao"),
             obs("contingenciamento_bi", 13.6, "2026-12-31", "projecao"),
             obs("despesas_fundo_social_bi", 99.0, "2026-12-31", "projecao"))   # ignorado: total prevalece
    r = por_id(params, 2026, b)["R01"]
    assert r.extras["total_deducoes"] == pytest.approx(67.3)
    assert r.extras["antes_contingenciamento"] == pytest.approx(-13.6)
    assert r.valor == pytest.approx(0.0, abs=1e-9)
    assert r.status == st.CUMPRE
    assert any("antes do contingenciamento" in n for n in r.notas)


def test_r01_fontes_e_r06_sem_excesso_com_relatorio(params, base):
    b = base(2026,
             obs("primario_gc_abaixo_linha_bi", -82.4, "2026-07-31", fonte="bcb_sgs:4639"),
             obs("primario_gc_abaixo_linha_bi", -80.9, "2026-12-31", "projecao", fonte="rardp_4bim_2026"),
             obs("deducoes_meta_total_bi", 67.3, "2026-12-31", "projecao", fonte="rardp_4bim_2026"),
             obs("contingenciamento_bi", 13.6, "2026-12-31", "projecao", fonte="rardp_4bim_2026"))
    res = por_id(params, 2026, b)
    assert res["R01"].fontes == ["rardp_4bim_2026", "bcb_sgs:4639"]
    assert res["R06"].valor == 0
    assert any("não há excesso" in n for n in res["R06"].notas)
    assert not any("IPCA" in n for n in res["R06"].notas)


def test_r05_piso_no_ploa_com_estatais(params, base):
    # PLOA 2026: OFSS 55,31 (SIOP) + estatais 197,9; PIB 13.826 → 1,83%; piso 0,6% = R$ 83,0 bi
    b = base(2026, obs("investimentos_ploa_bi", 55.31, "2026-12-31", "projecao"),
             obs("investimentos_loa_bi", 80.82, "2026-12-31", "projecao"),
             obs("investimentos_estatais_ploa_bi", 197.9, "2026-12-31", "projecao"),
             obs("pib_estimado_ploa_bi", 13826.0, "2026-12-31", "projecao"))
    r = por_id(params, 2026, b)["R05"]
    assert r.valor == pytest.approx(253.21 / 13826)
    assert r.status == st.CUMPRE
    assert r.extras["piso_bi"] == pytest.approx(82.956)
    assert any("Só OFSS" in n for n in r.notas)
    # sem as estatais, o OFSS sozinho fica abaixo do piso
    b2 = base(2026, obs("investimentos_ploa_bi", 55.31, "2026-12-31", "projecao"),
              obs("pib_estimado_ploa_bi", 13826.0, "2026-12-31", "projecao"))
    assert por_id(params, 2026, b2)["R05"].status == st.DESCUMPRE
