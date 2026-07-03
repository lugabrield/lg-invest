"""Testes de frontend/streamlit_app/formatting.py (Sprint 11).

Segue o mesmo padrão de `test_streamlit_smoke.py`: testa módulos do
Streamlit a partir de `backend/tests`, sem precisar de um servidor
Streamlit rodando (são funções puras de formatação).
"""

from __future__ import annotations

from decimal import Decimal

from frontend.streamlit_app.formatting import (
    format_brl,
    format_money,
    format_number,
    format_pct,
    format_quantity,
    format_usd,
)


def test_format_brl_uses_brazilian_separators():
    assert format_brl(Decimal("24344.82")) == "R$ 24.344,82"


def test_format_brl_rounds_to_two_decimals():
    assert format_brl(Decimal("13888.7601")) == "R$ 13.888,76"


def test_format_usd_uses_brazilian_separators_too():
    assert format_usd(Decimal("1234.5")) == "US$ 1.234,50"


def test_format_money_dispatches_by_currency():
    assert format_money(Decimal("100"), "BRL") == "R$ 100,00"
    assert format_money(Decimal("100"), "USD") == "US$ 100,00"
    assert format_money(Decimal("100"), "EUR") == "EUR 100,00"


def test_format_pct_basic():
    assert format_pct(Decimal("0.1234")) == "12,34%"


def test_format_pct_none_returns_dash():
    assert format_pct(None) == "—"


def test_format_pct_signed_positive():
    assert format_pct(Decimal("0.0544"), signed=True) == "+5,44%"


def test_format_pct_signed_negative():
    assert format_pct(Decimal("-0.0321"), signed=True) == "-3,21%"


def test_format_pct_unsigned_negative_still_shows_minus():
    assert format_pct(Decimal("-0.0321")) == "-3,21%"


def test_format_number_generic():
    assert format_number(Decimal("13888.7601"), decimals=2) == "13.888,76"


def test_format_quantity_default_two_decimals():
    assert format_quantity(Decimal("100")) == "100,00"


def test_format_quantity_crypto_uses_eight_decimals():
    result = format_quantity(Decimal("0.00123456"), asset_class="crypto")
    assert result == "0,00123456"


def test_format_quantity_usd_fractional_uses_six_decimals():
    result = format_quantity(Decimal("1.5"), currency="USD")
    assert result == "1,500000"


def test_format_quantity_explicit_decimals_override():
    assert format_quantity(Decimal("1.23456"), asset_class="crypto", decimals=2) == "1,23"
