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
            "bookValue": 10.0,
            "sharesOutstanding": 50_000,
        }
        self.income_stmt = _FakeFrame(
            {
                "Total Revenue": {date(2024, 12, 31): 1_000_000, date(2023, 12, 31): 900_000},
                "Net Income": {date(2024, 12, 31): 180_000, date(2023, 12, 31): 150_000},
                "EBITDA": {date(2024, 12, 31): 300_000, date(2023, 12, 31): 260_000},
                "EBIT": {date(2024, 12, 31): 220_000, date(2023, 12, 31): 190_000},
                "Tax Provision": {date(2024, 12, 31): 40_000, date(2023, 12, 31): 38_000},
                "Pretax Income": {date(2024, 12, 31): 200_000, date(2023, 12, 31): 190_000},
                "Interest Expense": {date(2024, 12, 31): 20_000, date(2023, 12, 31): 19_000},
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
                "Stockholders Equity": {
                    date(2024, 12, 31): 500_000,
                    date(2023, 12, 31): 450_000,
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


# --- ROIC / cobertura de juros / total_equity (Sprint 26, Fase 1) ----------


def test_get_latest_computes_total_equity_from_book_value_and_shares(monkeypatch):
    """total_equity = bookValue (por ação) x sharesOutstanding — mesma base
    já usada pelo próprio priceToBook publicado pelo yfinance, não um valor
    inventado. Não é calculado em get_latest: roic/interest_coverage exigem
    dado de demonstrativo que `.info` não expõe com confiança."""
    _install_fake_yfinance(monkeypatch)
    provider = YahooFundamentalsProvider()
    data = provider.get_latest("WEGE3.SA")

    assert data is not None
    assert data.total_equity == Decimal("10.0") * Decimal("50000")
    assert data.roic is None
    assert data.interest_coverage is None


def test_get_latest_total_equity_none_without_book_value(monkeypatch):
    class _NoBookValueTicker:
        def __init__(self, symbol):
            self.info = {"returnOnEquity": 0.28, "mostRecentQuarter": 1735689600}

    _install_fake_yfinance(monkeypatch, _NoBookValueTicker)
    provider = YahooFundamentalsProvider()
    data = provider.get_latest("WEGE3.SA")

    assert data is not None
    assert data.total_equity is None


def test_get_history_computes_roic_and_interest_coverage_from_statements(monkeypatch):
    """ROIC = NOPAT / capital investido; NOPAT = EBIT x (1 - alíquota
    efetiva). Com EBIT=220000, Tax Provision=40000, Pretax Income=200000
    (alíquota=20%), Total Debt=400000, Stockholders Equity=500000,
    Cash=100000: invested_capital=800000, NOPAT=176000, roic=0.22.
    interest_coverage = EBIT / |Interest Expense| = 220000/20000 = 11."""
    _install_fake_yfinance(monkeypatch)
    provider = YahooFundamentalsProvider()
    history = provider.get_history("WEGE3.SA")

    first = history[0]
    assert first.period_end == date(2024, 12, 31)
    assert first.total_equity == Decimal("500000")
    assert first.roic == Decimal("0.22")
    assert first.interest_coverage == Decimal("11")


def test_get_history_roic_none_when_tax_rate_outside_sane_range(monkeypatch):
    """Alíquota efetiva fora de [0, 1] (ex.: crédito fiscal pontual gerando
    provisão negativa) não deve virar um ROIC inventado/distorcido — fica
    None, nunca aproximado."""

    class _WeirdTaxTicker:
        def __init__(self, symbol):
            self.info = {}
            self.income_stmt = _FakeFrame(
                {
                    "Total Revenue": {date(2024, 12, 31): 1_000_000},
                    "Net Income": {date(2024, 12, 31): 180_000},
                    "EBIT": {date(2024, 12, 31): 220_000},
                    "Tax Provision": {date(2024, 12, 31): -50_000},  # crédito fiscal
                    "Pretax Income": {date(2024, 12, 31): 200_000},
                },
                columns=[date(2024, 12, 31)],
            )
            self.balance_sheet = _FakeFrame(
                {
                    "Total Debt": {date(2024, 12, 31): 400_000},
                    "Cash And Cash Equivalents": {date(2024, 12, 31): 100_000},
                    "Stockholders Equity": {date(2024, 12, 31): 500_000},
                },
                columns=[date(2024, 12, 31)],
            )
            self.cashflow = _FakeFrame({}, columns=[date(2024, 12, 31)])

    _install_fake_yfinance(monkeypatch, _WeirdTaxTicker)
    provider = YahooFundamentalsProvider()
    history = provider.get_history("WEIRD3.SA")

    assert history[0].roic is None
    assert history[0].total_equity == Decimal("500000")  # componente independente segue disponível


def test_get_history_interest_coverage_none_without_interest_expense_row(monkeypatch):
    class _NoInterestExpenseTicker:
        def __init__(self, symbol):
            self.info = {}
            self.income_stmt = _FakeFrame(
                {
                    "Total Revenue": {date(2024, 12, 31): 1_000_000},
                    "Net Income": {date(2024, 12, 31): 180_000},
                    "EBIT": {date(2024, 12, 31): 220_000},
                },
                columns=[date(2024, 12, 31)],
            )
            self.balance_sheet = _FakeFrame({}, columns=[date(2024, 12, 31)])
            self.cashflow = _FakeFrame({}, columns=[date(2024, 12, 31)])

    _install_fake_yfinance(monkeypatch, _NoInterestExpenseTicker)
    provider = YahooFundamentalsProvider()
    history = provider.get_history("NOINT3.SA")

    assert history[0].interest_coverage is None
    assert history[0].roic is None  # sem total_equity/tax data disponível tampouco


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
