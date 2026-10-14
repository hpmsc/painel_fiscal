"""CDI diário (BCB SGS 12, % ao dia) transformado em índice acumulado, base 1."""
from __future__ import annotations

import datetime as dt

from painel_fiscal.coletores.base import obter_json

URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"


def converter(itens: list[dict]) -> list[tuple[dt.date, float]]:
    """[{"data": "dd/mm/aaaa", "valor": "0,0551"}] → [(data, índice)] com índice no fim do dia."""
    pontos, indice = [], 1.0
    for it in sorted(itens, key=lambda i: i["data"][6:] + i["data"][3:5] + i["data"][:2]):
        d, m, a = it["data"].split("/")
        indice *= 1 + float(str(it["valor"]).replace(",", ".")) / 100
        pontos.append((dt.date(int(a), int(m), int(d)), indice))
    return pontos


def coletar(desde: dt.date, ate: dt.date | None = None, sessao=None) -> list[tuple[dt.date, float]]:
    """O SGS limita consultas diárias a 10 anos: busca em blocos."""
    ate = ate or dt.date.today()
    itens, ini = [], desde
    while ini <= ate:
        fim = min(dt.date(ini.year + 9, 12, 31), ate)
        itens += obter_json(URL, {"formato": "json", "dataInicial": ini.strftime("%d/%m/%Y"),
                                  "dataFinal": fim.strftime("%d/%m/%Y")}, sessao)
        ini = fim + dt.timedelta(days=1)
    return converter(itens)
