"""Testes do Portfolio Engine v1 com valores conhecidos (Volume 20, prompt 8).

A engine é pura: estes testes não tocam banco nem rede.

Carteira de referência (tudo em BRL para o caso base):
    WEGE3: 100 x 40,00 (avg 38,00) -> valor 4.000, ret  +5,263%
    ITUB4: 200 x 30,00 (avg 28,00) -> valor 6.000, ret  +7,143%  (maior posição)
    VOO:    10 x 400,00 (avg 420,00) -> valor 4.000, ret -4,762%
    total_value = 14.000 ; total_cost = 13.600 ; ret total = +2,941%
    HHI = (4/14)^2 + (6/14)^2 + (4/14)^2 = 68/196 = 0,346938...
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.engines.portfolio.engine import build_summary
from backend.app.engines.portfolio.inputs import PositionInput


def _base_portfolio() -> list[PositionInput]:
    return [
        PositionInput("WEGE3.SA", "stock", "BRL", Decimal("100"), Decimal("38"), Decimal("40")),
        PositionInput("ITUB4.SA", "stock", "BRL", Decimal("200"), Decimal("28"), Decimal("30")),
        PositionInput("VOO", "etf", "BRL", Decimal("10"), Decimal("420"), Decimal("400")),
    ]


def test_total_value():
    s = build_summary(_base_portfolio())
    assert s.total_value == Decimal("14000")


def test_total_cost_and_return():
    s = build_summary(_base_portfolio())
    assert s.total_cost == Decimal("13600")
    assert s.total_return_pct == pytest.approx(Decimal("400") / Decimal("13600"))


def test_weights_sum_to_one():
    s = build_summary(_base_portfolio())
    total_weight = sum(p.weight for p in s.positions)
    assert total_weight == pytest.approx(Decimal("1"))


def test_position_returns():
    s = build_summary(_base_portfolio())
    by_ticker = {p.ticker: p for p in s.positions}
    assert by_ticker["WEGE3.SA"].return_pct == pytest.approx(Decimal("2") / Decimal("38"))
    assert by_ticker["ITUB4.SA"].return_pct == pytest.approx(Decimal("2") / Decimal("28"))
    assert by_ticker["VOO"].return_pct == pytest.approx(Decimal("-20") / Decimal("420"))


def test_largest_position():
    s = build_summary(_base_portfolio())
    assert s.largest_position_ticker == "ITUB4.SA"


def test_concentration_hhi():
    s = build_summary(_base_portfolio())
    assert s.concentration_hhi == pytest.approx(Decimal("68") / Decimal("196"))


def test_allocation_by_class():
    s = build_summary(_base_portfolio())
    by_class = {a.label: a for a in s.allocation_by_class}
    assert by_class["stock"].value == Decimal("10000")  # WEGE + ITUB
    assert by_class["etf"].value == Decimal("4000")
    assert by_class["stock"].weight == pytest.approx(Decimal("10000") / Decimal("14000"))


def test_single_currency_not_flagged():
    s = build_summary(_base_portfolio())
    assert s.is_multi_currency is False
    assert len(s.allocation_by_currency) == 1


def test_multi_currency_is_flagged():
    positions = [
        PositionInput("WEGE3.SA", "stock", "BRL", Decimal("100"), Decimal("38"), Decimal("40")),
        PositionInput("VOO", "etf", "USD", Decimal("10"), Decimal("400"), Decimal("420")),
    ]
    s = build_summary(positions)
    assert s.is_multi_currency is True
    assert len(s.allocation_by_currency) == 2


def test_unpriced_position_excluded_from_totals():
    positions = [
        PositionInput("WEGE3.SA", "stock", "BRL", Decimal("100"), Decimal("38"), Decimal("40")),
        PositionInput("NOPE9", "stock", "BRL", Decimal("50"), Decimal("10"), None),
    ]
    s = build_summary(positions)
    assert s.total_value == Decimal("4000")  # só WEGE entra
    assert "NOPE9" in s.unpriced_tickers
    assert len(s.positions) == 1


def test_zero_average_price_returns_none():
    positions = [
        PositionInput("FREE", "stock", "BRL", Decimal("10"), Decimal("0"), Decimal("5")),
    ]
    s = build_summary(positions)
    assert s.positions[0].return_pct is None


def test_empty_portfolio():
    s = build_summary([])
    assert s.total_value == Decimal("0")
    assert s.largest_position_ticker is None
    assert s.positions == []
    assert s.concentration_hhi == Decimal("0")
