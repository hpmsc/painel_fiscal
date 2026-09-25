import datetime as dt

from painel_fiscal import cli, dados


def _o(valor, ref="2026-08-31"):
    return dados.Observacao(indicador="rcl_bi", valor=valor, data_referencia=dt.date.fromisoformat(ref),
                            fonte="siconfi", data_coleta=dt.date.today())


def test_acrescentar_ignora_repeticao_e_guarda_revisao(tmp_path):
    cli._acrescentar_tratados(2026, [_o(1500.0)], tmp_path)
    cli._acrescentar_tratados(2026, [_o(1500.0), _o(1500.0)], tmp_path)      # coleta repetida
    cli._acrescentar_tratados(2026, [_o(1502.3)], tmp_path)                  # revisão
    base = dados.carregar_arquivo(tmp_path / "2026.json")
    assert [o.valor for o in base.serie("rcl_bi")] == [1500.0, 1502.3]
