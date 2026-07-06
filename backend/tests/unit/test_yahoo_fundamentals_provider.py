"""Testes do YahooFundamentalsProvider sem conexão real.

O yfinance é mockado com um objeto mínimo compatível com `.info` e com
DataFrames de demonstrativos (`.income_stmt`/`.balance_sheet`/`.cashflow`)
suportando `.empty`, `.index`, `.columns` e `.loc[row, col]`. Nenhuma
rede é acessada (Volume 4, seção 17; Volume 20, prompt 7).
"""

from __future__ import annotations

import sys
import types
from datetime import date
from decimal import Decimal

from backend.app.etl.providers.yahoo_fundamentals_provider import (
    YahooFundamentalsProvider,
    _normalize_percentage,
)


class _FakeLoc:
    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key):
        row, col = key
        return self._data[row][col]


class _FakeFrame:
    def __init__(self, data: dict, columns: list):
        self._data = data
        self.columns = columns
        self.index = list(data.keys())
        self.empty = len(columns) == 0
        self.loc = _FakeLoc(data)


class _FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.info = {
            "returnOnEquity": 0.28,
            "returnOnAssets": 0.10,
            "profitMargins": 0.18,
            "ebitdaMargins": 0.30,
            "totalRevenue": 1_000_000,
            "netIncomeToCommon": 180_000,
            "ebitda": 300_000,
            "freeCashflow": 150_000,
            "totalDebt": 400_000,
            "totalCash": 100_000,
            "trailingPE": 15.5,
            "priceToBook": 3.2,
            "enterpriseToEbitda": 9.1,
            "dividendYield": 0.03,
            "payoutRatio": 0.4,
            "trailingEps": 5.2,
            "revenuePerShare": 28.0,
            "beta": 0.9,
            "mostRecentQuarter": 1735689600,
        }
        self.income_stmt = _FakeFrame(
            {
                "Total Revenue": {date(2024, 12, 31): 1_000_000, date(2023, 12, 31): 900_000},
                "Net Income": {date(2024, 12, 31): 180_000, date(2023, 12, 31): 150_000},
                "EBITDA": {date(2024, 12, 31): 300_000, date(2023, 12, 31): 260_000},
            },
            columns=[date(2024, 12, 31), date(2023, 12, 31)],
        )
        self.balance_sheet = _FakeFrame(
            {
                "Total Debt": {date(2024, 12, 31): 400_000, date(2023, 12, 31): 380_000},
                "Cash And Cash Equivalents": {
                    date(2024, 12, 31): 100_000,
                    date(2023, 12, 31): 90_000,
                },
            },
            columns=[date(2024, 12, 31), date(2023, 12, 31)],
        )
        self.cashflow = _FakeFrame(
            {"Free Cash Flow": {date(2024, 12, 31): 150_000, date(2023, 12, 31): 120_000}},
            columns=[date(2024, 12, 31), date(2023, 12, 31)],
        )


def _install_fake_yfinance(monkeypatch, ticker_cls=_FakeTicker):
    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = ticker_cls  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)


def test_get_latest_parses_info(monkeypatch):
    _install_fake_yfinance(monkeypatch)
    provider = YahooFundamentalsProvider()
    data = provider.get_latest("WEGE3.SA")

    assert data is not None
    assert data.roe == Decimal("0.28")
    assert data.net_margin == Decimal("0.18")
    assert data.pe_ratio == Decimal("15.5")
    assert data.net_debt == Decimal("300000")
    assert data.debt_to_ebitda == Decimal("400000") / Decimal("300000")
    assert data.source_name == "yahoo_fundamentals"


def test_get_latest_returns_none_when_info_empty(monkeypatch):
    class _EmptyTicker:
        def __init__(self, symbol):
            self.info = {}

    _install_fake_yfinance(monkeypatch, _EmptyTicker)
    provider = YahooFundamentalsProvider()
    assert provider.get_latest("NOPE9.SA") is None


def test_get_history_parses_statements(monkeypatch):
    _install_fake_yfinance(monkeypatch)
    provider = YahooFundamentalsProvider()
    history = provider.get_history("WEGE3.SA")

    assert len(history) == 2
    first = history[0]
    assert first.period_end == date(2024, 12, 31)
    assert first.revenue == Decimal("1000000")
    assert first.net_income == Decimal("180000")
    assert first.net_margin == Decimal("180000") / Decimal("1000000")
    assert first.free_cash_flow == Decimal("150000")
    assert first.net_debt == Decimal("300000")


def test_get_history_empty_when_no_income_statement(monkeypatch):
    class _NoFinancialsTicker:
        def __init__(self, symbol):
            self.income_stmt = _FakeFrame({}, columns=[])

    _install_fake_yfinance(monkeypatch, _NoFinancialsTicker)
    provider = YahooFundamentalsProvider()
    assert provider.get_history("NOPE9.SA") == []


# --- Normalização de percentuais (Sprint 22 — BTLG11 exibindo Dividend Yield de 950%) ---


def test_normalize_percentage_passes_through_fraction_scale():
    assert _normalize_percentage(Decimal("0.095")) == Decimal("0.095")


def test_normalize_percentage_divides_percentage_scale_value():
    assert _normalize_percentage(Decimal("9.5")) == Decimal("0.095")


def test_normalize_percentage_none_stays_none():
    assert _normalize_percentage(None) is None


def test_normalize_percentage_boundary_at_one_is_not_divided():
    # Exatamente 100% (fração 1) é o limite: continua tratado como fração já correta.
    assert _normalize_percentage(Decimal("1")) == Decimal("1")


def test_normalize_percentage_handles_negative_values():
    assert _normalize_percentage(Decimal("-9.5")) == Decimal("-0.095")


def test_get_latest_normalizes_percentage_scale_dividend_yield(monkeypatch):
    """Reproduz o bug real do Sprint 22: BTLG11 (FII) com dividendYield=9.5 do
    yfinance (já em escala percentual) deve virar fração 0,095 (9,5%), não 9,5 (950%)."""

    class _PercentScaleTicker:
        def __init__(self, symbol):
            self.info = {
                "dividendYield": 9.5,
                "payoutRatio": 0.4,
                "returnOnEquity": 0.28,
                "mostRecentQuarter": 1735689600,
            }

    _install_fake_yfinance(monkeypatch, _PercentScaleTicker)
    provider = YahooFundamentalsProvider()
    data = provider.get_latest("BTLG11.SA")

    assert data is not None
    assert data.dividend_yield == Decimal("0.095")
    # Campos já em fração não devem ser distorcidos pela normalização.
    assert data.payout_ratio == Decimal("0.4")
    assert data.roe == Decimal("0.28")


def test_get_latest_does_not_distort_fraction_scale_margins(monkeypatch):
    _install_fake_yfinance(monkeypatch)
    provider = YahooFundamentalsProvider()
    data = provider.get_latest("WEGE3.SA")

    assert data is not None
    assert data.net_margin == Decimal("0.18")
    assert data.ebitda_margin == Decimal("0.30")
    assert data.dividend_yield == Decimal("0.03")
