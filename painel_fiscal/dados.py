"""Observações de indicadores, com data de referência, data de coleta e fonte.

Formato comum a coletores e carga manual (JSON ou YAML):

    exercicio: 2026
    observacoes:
      - indicador: rcl_bi
        valor: 1450.2
        data_referencia: 2026-08-31
        data_coleta: 2026-09-20
        fonte: siconfi_rgf_anexo_01
        tipo: realizado        # ou "projecao" (LDO, relatório bimestral)
        nota: opcional

Nada é sobrescrito: cada coleta acrescenta observações. A apuração usa a mais
recente (data de referência, depois data de coleta) de cada indicador e tipo.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

TIPOS = ("realizado", "projecao")


@dataclass(frozen=True)
class Observacao:
    indicador: str
    valor: Any
    data_referencia: dt.date
    fonte: str
    data_coleta: dt.date | None = None
    tipo: str = "realizado"
    nota: str | None = None
    ilustrativo: bool = False

    def __post_init__(self):
        if self.tipo not in TIPOS:
            raise ValueError(f"tipo inválido: {self.tipo!r} (use {TIPOS})")

    def chave_ordem(self):
        return (self.data_referencia, self.data_coleta or dt.date.min)

    def para_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["data_referencia"] = self.data_referencia.isoformat()
        d["data_coleta"] = self.data_coleta.isoformat() if self.data_coleta else None
        return {k: v for k, v in d.items() if v is not None and v is not False}


def _data(v: Any) -> dt.date | None:
    if v is None or isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v))


def observacao_de_dict(d: dict[str, Any]) -> Observacao:
    return Observacao(
        indicador=d["indicador"],
        valor=d["valor"],
        data_referencia=_data(d["data_referencia"]),
        fonte=d["fonte"],
        data_coleta=_data(d.get("data_coleta")),
        tipo=d.get("tipo", "realizado"),
        nota=d.get("nota"),
        ilustrativo=bool(d.get("ilustrativo", False)),
    )


@dataclass
class BaseDados:
    exercicio: int
    observacoes: list[Observacao] = field(default_factory=list)

    def adicionar(self, obs: Iterable[Observacao]) -> None:
        self.observacoes.extend(obs)

    def serie(self, indicador: str, tipo: str | None = None) -> list[Observacao]:
        return sorted(
            (o for o in self.observacoes
             if o.indicador == indicador and (tipo is None or o.tipo == tipo)),
            key=Observacao.chave_ordem,
        )

    def ultima(self, indicador: str, tipo: str = "realizado") -> Observacao | None:
        s = self.serie(indicador, tipo)
        return s[-1] if s else None

    def valor(self, indicador: str, tipo: str = "realizado") -> Any:
        o = self.ultima(indicador, tipo)
        return None if o is None else o.valor

    @property
    def tem_ilustrativo(self) -> bool:
        return any(o.ilustrativo for o in self.observacoes)


def carregar_arquivo(caminho: str | Path) -> BaseDados:
    caminho = Path(caminho)
    with open(caminho, encoding="utf-8") as f:
        bruto = json.load(f) if caminho.suffix == ".json" else yaml.safe_load(f)
    ilustrativo = bool(bruto.get("ilustrativo", False))
    obs = []
    for d in bruto.get("observacoes", []):
        o = observacao_de_dict(d)
        if ilustrativo and not o.ilustrativo:
            o = Observacao(**{**o.__dict__, "ilustrativo": True})
        obs.append(o)
    return BaseDados(int(bruto["exercicio"]), obs)


def carregar_varios(exercicio: int, caminhos: Iterable[str | Path]) -> BaseDados:
    base = BaseDados(exercicio)
    for c in caminhos:
        b = carregar_arquivo(c)
        if b.exercicio != exercicio:
            raise ValueError(f"{c}: exercício {b.exercicio}, esperado {exercicio}")
        base.adicionar(b.observacoes)
    return base


def salvar_json(base: BaseDados, caminho: str | Path) -> None:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(
            {"exercicio": base.exercicio,
             "observacoes": [o.para_dict() for o in base.observacoes]},
            f, ensure_ascii=False, indent=2,
        )
