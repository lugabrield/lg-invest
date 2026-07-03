"""Testes do BcbFxProvider sem conexão real.

`_fetch` (chamada HTTP real) é mockado; validamos apenas o parsing da
resposta e a lógica de seleção da cotação mais recente dentro da janela
consultada. Nenhuma rede é acessada (Volume 4, seção 17; Volume 20,
prompt 7).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.etl.providers.bcb_fx_provider import BcbFxProvider


def _payload(values: list[dict]) -> dict:
    return {"value": values}


def test_get_quote_on_or_before_uses_latest_value_in_window(monkeypatch):
    provider = BcbFxProvider()
    payload = _payload(
        [
            {
                "cotacaoCompra": 4.90,
                "cotacaoVenda": 4.92,
                "dataHoraCotacao": "2026-06-30 13:05:00.123",
            },
            {
                "cotacaoCompra": 5.00,
                "cotacaoVenda": 5.02,
                "dataHoraCotacao": "2026-07-01 13:05:00.123",
            },
        ]
    )
    monkeypatch.setattr(provider, "_fetch", lambda url: payload)

    quote = provider.get_quote_on_or_before(date(2026, 7, 1))

    assert quote is not None
    assert quote.pair == "USDBRL"
    assert quote.rate == Decimal("5.01")
    assert quote.source == "bcb"
    assert quote.quote_date.date() == date(2026, 7, 1)
    assert quote.is_override is False


def test_empty_window_returns_none(monkeypatch):
    provider = BcbFxProvider()
    monkeypatch.setattr(provider, "_fetch", lambda url: _payload([]))
    assert provider.get_quote_on_or_before(date(2026, 7, 1)) is None


def test_network_failure_returns_none(monkeypatch):
    provider = BcbFxProvider()

    def _raise(url):
        raise ConnectionError("boom")

    monkeypatch.setattr(provider, "_fetch", _raise)
    assert provider.get_quote_on_or_before(date(2026, 7, 1)) is None


def test_malformed_entry_returns_none(monkeypatch):
    provider = BcbFxProvider()
    monkeypatch.setattr(
        provider, "_fetch", lambda url: _payload([{"dataHoraCotacao": "2026-07-01 13:05:00"}])
    )
    assert provider.get_quote_on_or_before(date(2026, 7, 1)) is None


def test_unsupported_pair_raises():
    provider = BcbFxProvider()
    with pytest.raises(ValueError):
        provider.get_quote_on_or_before(date(2026, 7, 1), pair="EURBRL")


def test_get_latest_delegates_to_today(monkeypatch):
    provider = BcbFxProvider()
    payload = _payload(
        [{"cotacaoCompra": 5.00, "cotacaoVenda": 5.02, "dataHoraCotacao": "2026-07-01 13:05:00"}]
    )
    monkeypatch.setattr(provider, "_fetch", lambda url: payload)

    quote = provider.get_latest()

    assert quote is not None
    assert quote.rate == Decimal("5.01")
