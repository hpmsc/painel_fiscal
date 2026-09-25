"""Leitura do YAML de parâmetros. Metas e deduções nunca ficam no código."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_PADRAO = RAIZ / "config" / "parametros_regras_fiscais_uniao.yaml"


@dataclass
class Parametros:
    bruto: dict[str, Any]

    @property
    def metadados(self) -> dict[str, Any]:
        return self.bruto.get("metadados", {})

    @property
    def status_percentual(self) -> dict[str, float]:
        return self.bruto["status_percentual"]

    @property
    def regras(self) -> list[dict[str, Any]]:
        return self.bruto["regras"]

    def regra(self, id_regra: str) -> dict[str, Any]:
        for r in self.regras:
            if r["id"] == id_regra:
                return r
        raise KeyError(id_regra)

    def exercicio(self, ano: int) -> dict[str, Any]:
        exercicios = self.bruto.get("exercicios", {})
        if ano not in exercicios:
            raise KeyError(
                f"Exercício {ano} sem parâmetros no YAML (disponíveis: {sorted(exercicios)})"
            )
        return exercicios[ano]

    @property
    def fontes(self) -> dict[str, Any]:
        return self.bruto.get("fontes", {})


def carregar(caminho: str | Path = CAMINHO_PADRAO) -> Parametros:
    with open(caminho, encoding="utf-8") as f:
        return Parametros(yaml.safe_load(f))
