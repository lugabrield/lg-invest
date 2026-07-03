"""Helpers de formatacao visual para as telas Streamlit.

Puramente apresentacao: nenhuma funcao aqui calcula nada, so formata
valores ja calculados pelas engines/servicos. Existe para que nenhuma
tela mostre numeros como `13888.7601` ou misture separador americano
com moeda brasileira. Todos os valores (BRL ou USD) usam o padrao
brasileiro de separador (ponto de milhar, virgula decimal), ja que o
publico da LG INVEST le tudo em pt-BR - so o simbolo muda.
"""

from __future__ import annotations

from decimal import Decimal

_QUANTITY_DECIMALS_BY_CLASS = {"crypto": 8}
_DEFAULT_QUANTITY_DECIMALS = 2
_USD_QUANTITY_DECIMALS = 6


def _grouped(value: Decimal | float | int, decimals: int = 2) -> str:
    """Formata com separador de milhar `.` e decimal `,` (padrao brasileiro)."""
    s = f"{float(value):,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def format_brl(value: Decimal | float | int, decimals: int = 2) -> str:
    """Ex.: 24344.82 -> 'R$ 24.344,82'."""
    return f"R$ {_grouped(value, decimals)}"


def format_usd(value: Decimal | float | int, decimals: int = 2) -> str:
    """Ex.: 1234.5 -> 'US$ 1.234,50' (separador brasileiro, simbolo americano)."""
    return f"US$ {_grouped(value, decimals)}"


def format_money(value: Decimal | float | int, currency: str, decimals: int = 2) -> str:
    """Formata pelo simbolo correto conforme a moeda da posicao, sempre em padrao brasileiro."""
    if currency == "USD":
        return format_usd(value, decimals)
    if currency == "BRL":
        return format_brl(value, decimals)
    return f"{currency} {_grouped(value, decimals)}"


def format_pct(fraction: Decimal | float | None, decimals: int = 2, signed: bool = False) -> str:
    """Ex.: 0.1234 -> '12,34%'. None -> '-'.

    Com `signed=True`: 0.0544 -> '+5,44%', -0.0321 -> '-3,21%' (para
    rentabilidade, onde o sinal importa).
    """
    if fraction is None:
        return "—"
    value = float(fraction) * 100
    text = f"{abs(value):.{decimals}f}".replace(".", ",")
    if signed:
        sign = "+" if value > 0 else ("-" if value < 0 else "")
        return f"{sign}{text}%"
    sign = "-" if value < 0 else ""
    return f"{sign}{text}%"


def format_number(value: Decimal | float | int, decimals: int = 4) -> str:
    """Numero generico, padrao brasileiro, sem casas longas soltas."""
    return _grouped(value, decimals)


def format_quantity(
    value: Decimal | float | int,
    asset_class: str | None = None,
    currency: str | None = None,
    decimals: int | None = None,
) -> str:
    """Quantidade com casas decimais coerentes com o tipo de ativo.

    Cripto: ate 8 casas. Ativos fracionados em USD (ex.: acoes fracionarias
    dos EUA): ate 6 casas. Demais (acoes BR, FIIs, Tesouro): 2 casas.
    Pode ser sobrescrito explicitamente via `decimals`.
    """
    if decimals is None:
        if asset_class in _QUANTITY_DECIMALS_BY_CLASS:
            decimals = _QUANTITY_DECIMALS_BY_CLASS[asset_class]
        elif currency == "USD":
            decimals = _USD_QUANTITY_DECIMALS
        else:
            decimals = _DEFAULT_QUANTITY_DECIMALS
    return _grouped(value, decimals)
