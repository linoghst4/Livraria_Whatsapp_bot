"""Utilitários partilhados: erros, datas e dinheiro."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import config


class ServiceError(Exception):
    """Erro de regra de negócio, com mensagem segura para mostrar ao cliente."""


def now() -> datetime:
    return datetime.now(ZoneInfo(config.TIMEZONE))


def today() -> date:
    return now().date()


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def fmt_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def fmt_money(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".") + f" {config.CURRENCY}"
