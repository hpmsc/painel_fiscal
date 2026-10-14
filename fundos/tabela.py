"""Leitura tolerante dos CSV das fontes: separador, codificação, ZIP e nomes de coluna."""
from __future__ import annotations

import csv
import io
import re
import unicodedata
import zipfile
from typing import Iterator


def so_digitos(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj or "").zfill(14) if cnpj and re.search(r"\d", cnpj) else ""


def formatar_cnpj(digitos: str) -> str:
    d = so_digitos(digitos)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else digitos


def chave_coluna(nome: str) -> str:
    """'CNPJ_FUNDO_CLASSE', 'Cnpj Fundo Classe' e 'cnpj-fundo-classe' viram a mesma chave."""
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def decodificar(conteudo: bytes) -> str:
    for cod in ("utf-8-sig", "latin-1"):
        try:
            return conteudo.decode(cod)
        except UnicodeDecodeError:
            continue
    return conteudo.decode("latin-1", errors="replace")


def arquivos_csv(conteudo: bytes, padrao: str = r"\.csv$") -> Iterator[tuple[str, str]]:
    """(nome, texto) de cada CSV: o próprio conteúdo, ou os membros de um ZIP."""
    if conteudo[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            for nome in sorted(z.namelist()):
                if re.search(padrao, nome, re.I):
                    yield nome, decodificar(z.read(nome))
    else:
        yield "", decodificar(conteudo)


def linhas(texto: str) -> Iterator[dict[str, str]]:
    """Linhas do CSV com colunas normalizadas por `chave_coluna` (separador ; ou ,)."""
    primeira = texto.split("\n", 1)[0]
    sep = ";" if primeira.count(";") >= primeira.count(",") else ","
    leitor = csv.reader(io.StringIO(texto), delimiter=sep)
    try:
        cab = [chave_coluna(c) for c in next(leitor)]
    except StopIteration:
        return
    for valores in leitor:
        if valores:
            yield dict(zip(cab, (v.strip() for v in valores)))


def campo(linha: dict[str, str], *alternativas: str, padrao: str = "") -> str:
    """Primeiro nome de coluna presente (as fontes renomeiam colunas entre versões)."""
    for a in alternativas:
        v = linha.get(chave_coluna(a))
        if v is not None:
            return v
    return padrao


def numero(s: str | None) -> float | None:
    """'1.234,56', '1234.56' e '' → float ou None."""
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None

