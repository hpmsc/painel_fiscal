import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from painel_fiscal import config  # noqa: E402
from painel_fiscal.dados import BaseDados, Observacao  # noqa: E402


@pytest.fixture(scope="session")
def params():
    return config.carregar()


def obs(indicador, valor, ref="2026-08-31", tipo="realizado", fonte="teste"):
    return Observacao(indicador=indicador, valor=valor, data_referencia=dt.date.fromisoformat(ref),
                      fonte=fonte, tipo=tipo)


@pytest.fixture
def base():
    def _base(exercicio=2026, *observacoes):
        return BaseDados(exercicio, list(observacoes))
    return _base
