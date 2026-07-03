"""Testes do YahooFinanceProvider sem conexão real.

O yfinance é mockado: validamos apenas que o provider converte o
payload (DataFrame-like) em objetos PriceData corretos. Nenhuma rede
é acessada (Volume 4, seção 17; Volume 20, prompt 7).
"""

from __future__ import annotations

import sys
import types
from datetime import date
from decimal import Decimal

from backend.app.etl.providers.yahoo_provider import YahooFinanceProvider


class _FakeRow:
    """Imita uma linha de DataFrame com .get(coluna)."""

    def __init__(self, data: dict):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


class _FakeHistory:
    """Imita o DataFrame retornado por yfinance .history()."""

    def __init__(self, rows: list[tuple[date, dict]]):
        self._rows = rows
        self.empty = len(rows) == 0

    def iterrows(self):
        for d, values in self._rows:
            yield d, _FakeRow(values)


class _FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol

    def history(self, **kwargs):
        return _FakeHistory(
            [
                (
                    date(2026, 1, 2),
                    {
                        "Open": 39.0,
                        "High": 41.0,
                        "Low": 38.5,
                        "Close": 40.5,
                        "Adj Close": 40.2,
                        "Volume": 1_000_000,
                    },
                ),
                (
                    date(2026, 1, 3),
                    {
                        "Open": 40.5,
                        "High": 42.0,
                        "Low": 40.0,
                        "Close": 41.8,
                        "Adj Close": 41.5,
                        "Volume": 1_200_000,
                    },
                ),
            ]
        )


def _install_fake_yfinance(monkeypatch):
    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = _FakeTicker  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)


def test_get_history_parses_payload(monkeypatch):
    _install_fake_yfinance(monkeypatch)
    provider = YahooFinanceProvider()
    history = provider.get_history("WEGE3.SA", "BRL")

    assert len(history) == 2
    first = history[0]
    assert first.ticker == "WEGE3.SA"
    assert first.date == date(2026, 1, 2)
    assert first.close == Decimal("40.5")
    assert first.currency == "BRL"
    assert first.source_name == "yahoo_finance"


def test_get_latest_returns_last_bar(monkeypatch):
    _install_fake_yfinance(monkeypatch)
    provider = YahooFinanceProvider()
    latest = provider.get_latest("WEGE3.SA", "BRL")
    assert latest is not None
    assert latest.date == date(2026, 1, 3)
    assert latest.close == Decimal("41.8")


def test_empty_history_returns_empty_list(monkeypatch):
    fake_yf = types.ModuleType("yfinance")

    class _EmptyTicker:
        def __init__(self, symbol):
            pass

        def history(self, **kwargs):
            return _FakeHistory([])

    fake_yf.Ticker = _EmptyTicker  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

    provider = YahooFinanceProvider()
    assert provider.get_history("NOPE9.SA", "BRL") == []
