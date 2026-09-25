"""Classificação de status (especificação, seção 5, item 3)."""
from __future__ import annotations

CUMPRE = "cumpre"
ACIMA_TETO = "acima_teto"          # cumpre a meta e aciona R06
DESCUMPRE = "descumpre"
OK = "ok"
ALERTA = "alerta"
PRUDENCIAL = "prudencial"
EXCEDIDO = "excedido"
MONITORAMENTO = "monitoramento"
INFORMATIVO = "informativo"
PENDENTE = "pendente"              # limite legal a confirmar (⚠ verificar)
SEM_DADOS = "sem_dados"
EM_APURACAO = "em_apuracao"        # exercício aberto, sem projeção oficial
ATIVO = "ativo"
INATIVO = "inativo"
CONTROVERSIA = "controversia"

ROTULOS = {
    CUMPRE: "Cumpre",
    ACIMA_TETO: "Cumpre (acima do teto)",
    DESCUMPRE: "Descumpre",
    OK: "OK",
    ALERTA: "Alerta",
    PRUDENCIAL: "Prudencial",
    EXCEDIDO: "Excedido",
    MONITORAMENTO: "Monitoramento",
    INFORMATIVO: "Informativo",
    PENDENTE: "Limite a confirmar",
    SEM_DADOS: "Sem dados",
    EM_APURACAO: "Em apuração",
    ATIVO: "Gatilho ativo",
    INATIVO: "Gatilho inativo",
    CONTROVERSIA: "Controvérsia",
}

# Gravidade para ordenar e para "pior status" (R11). Quanto maior, pior.
GRAVIDADE = {
    DESCUMPRE: 4, EXCEDIDO: 4,
    PRUDENCIAL: 3, ATIVO: 3,
    ALERTA: 2, CONTROVERSIA: 2,
    PENDENTE: 1, SEM_DADOS: 1, EM_APURACAO: 1,
    CUMPRE: 0, ACIMA_TETO: 0, OK: 0, INATIVO: 0,
    MONITORAMENTO: 0, INFORMATIVO: 0,
}

# Tom visual do semáforo (usa a paleta de status do painel).
TOM = {
    CUMPRE: "bom", ACIMA_TETO: "bom", OK: "bom", INATIVO: "bom",
    ALERTA: "atencao", CONTROVERSIA: "atencao",
    PRUDENCIAL: "serio", ATIVO: "serio",
    DESCUMPRE: "critico", EXCEDIDO: "critico",
    MONITORAMENTO: "neutro", INFORMATIVO: "neutro", PENDENTE: "neutro",
    SEM_DADOS: "neutro", EM_APURACAO: "neutro",
}


def percentual(uso_do_limite: float, niveis: dict[str, float]) -> str:
    """Status de regra com teto em % (pessoal, garantias, limite de despesa).

    `uso_do_limite` = valor apurado ÷ limite (1,0 = no limite).
    """
    if uso_do_limite >= niveis["excedido"]:
        return EXCEDIDO
    if uso_do_limite >= niveis["prudencial"]:
        return PRUDENCIAL
    if uso_do_limite >= niveis["alerta"]:
        return ALERTA
    return OK


def minimo(valor: float, piso: float) -> str:
    return CUMPRE if valor >= piso else DESCUMPRE


def maximo(valor: float, teto: float) -> str:
    return CUMPRE if valor <= teto else DESCUMPRE


def meta_banda(resultado: float, inferior: float, superior: float | None) -> str:
    if resultado < inferior:
        return DESCUMPRE
    if superior is not None and resultado > superior:
        return ACIMA_TETO
    return CUMPRE


def pior(statuses: list[str]) -> str:
    return max(statuses, key=lambda s: GRAVIDADE.get(s, 0)) if statuses else SEM_DADOS
