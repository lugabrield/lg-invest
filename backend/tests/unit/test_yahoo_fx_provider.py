"""Testes do YahooFxProvider sem conexão real.

O yfinance é mockado com um objeto mínimo compatível com `.empty`,
`.iloc[-1]` e `.index[-1]` — nenhuma rede é acessada (Volume 4, seção
17; Volume 20, prompt 7).
"""

from __future__ import annotations

import sys
import types
from datetime import date, datetime
from decimal import Decimal

from backend.app.etl.providers.yahoo_fx_provider import YahooFxProvider


class _FakeIloc:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def __getitem__(self, idx):
        return self._rows[idx]


class _FakeHistory:
    def __init__(self, rows: list[tuple[datetime, dict]]):
        self._rows = rows
        self.empty = len(rows) == 0
        self.index = [r[0] for r in rows]
        self.iloc = _FakeIloc([r[1] for r in rows])


class _FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol

    def history(self, **kwargs):
        return _FakeHistory(
            [
                (datetime(2026, 6, 30), {"Close": 4.98}),
                (datetime(2026, 7, 1), {"Close": 5.02}),
            ]
        )


def _install_fake_yfinance(monkeypatch, ticker_cls=_FakeTicker):
    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = ticker_cls  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)


def test_get_quote_on_or_before_returns_last_bar(monkeypatch):
    _install_fake_yfinance(monkeypatch)
    provider = YahooFxProvider()

    quote = provider.get_quote_on_or_before(date(2026, 7, 1))

    assert quote is not None
    assert quote.rate == Decimal("5.02")
    assert quote.source == "yahoo"
    assert quote.pair == "USDBRL"
    assert quote.is_override is False


def test_get_latest_delegates_to_today(monkeypatch):
    _install_fake_yfinance(monkeypatch)
    provider = YahooFxProvider()

    quote = provider.get_latest()

    assert quote is not None
    assert quote.rate == Decimal("5.02")


def test_empty_history_returns_none(monkeypatch):
    class _EmptyTicker:
        def __init__(self, symbol):
            pass

        def history(self, **kwargs):
            return _FakeHistory([])

    _install_fake_yfinance(monkeypatch, _EmptyTicker)
    provider = YahooFxProvider()

    assert provider.get_quote_on_or_before(date(2026, 7, 1)) is None


def test_unsupported_pair_raises(monkeypatch):
    _install_fake_yfinance(monkeypatch)
    provider = YahooFxProvider()

    import pytest

    with pytest.raises(ValueError):
        provider.get_quote_on_or_before(date(2026, 7, 1), pair="EURBRL")
