"""Testes do fx_service (cadeia de fallback BCB -> Yahoo -> manual).

Providers fake controlados nos testes — nenhuma rede é acessada. O
arquivo de configurações é isolado via monkeypatch, mesmo padrão de
`test_fx_settings_service.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.app.etl.providers.fx_provider import FxRateProvider
from backend.app.schemas.market_data import FxQuote
from backend.app.services import fx_service, fx_settings_service


class _FakeProvider(FxRateProvider):
    def __init__(self, name, quote=None, raise_exc=False):
        self.name = name
        self._quote = quote
        self._raise = raise_exc
        self.calls = 0

    def get_latest(self, pair: str = "USDBRL"):
        self.calls += 1
        if self._raise:
            raise ConnectionError("boom")
        return self._quote

    def get_quote_on_or_before(self, target, pair: str = "USDBRL"):
        raise NotImplementedError


def _quote(rate, source) -> FxQuote:
    now = datetime.now(UTC)
    return FxQuote(
        pair="USDBRL", rate=Decimal(str(rate)), source=source, quote_date=now, fetched_at=now
    )


@pytest.fixture(autouse=True)
def _isolated_settings_file(tmp_path, monkeypatch):
    monkeypatch.setattr(fx_settings_service, "_SETTINGS_PATH", tmp_path / "app_settings.json")


def test_first_provider_success_persists_and_returns():
    bcb = _FakeProvider("bcb", quote=_quote(5.10, "bcb"))
    yahoo = _FakeProvider("yahoo", quote=_quote(5.20, "yahoo"))

    result = fx_service.update_usd_brl_rate(providers=[bcb, yahoo])

    assert result.source == "bcb"
    assert result.rate == Decimal("5.10")
    assert yahoo.calls == 0
    assert fx_settings_service.get_usd_brl_rate() == Decimal("5.10")


def test_falls_back_to_second_provider_on_failure():
    bcb = _FakeProvider("bcb", raise_exc=True)
    yahoo = _FakeProvider("yahoo", quote=_quote(5.20, "yahoo"))

    result = fx_service.update_usd_brl_rate(providers=[bcb, yahoo])

    assert result.source == "yahoo"
    assert result.rate == Decimal("5.20")


def test_falls_back_to_second_provider_when_first_returns_none():
    bcb = _FakeProvider("bcb", quote=None)
    yahoo = _FakeProvider("yahoo", quote=_quote(5.30, "yahoo"))

    result = fx_service.update_usd_brl_rate(providers=[bcb, yahoo])

    assert result.source == "yahoo"
    assert result.rate == Decimal("5.30")


def test_all_providers_fail_returns_last_saved_quote():
    fx_settings_service.set_usd_brl_rate(Decimal("5.00"))
    bcb = _FakeProvider("bcb", raise_exc=True)
    yahoo = _FakeProvider("yahoo", raise_exc=True)

    result = fx_service.update_usd_brl_rate(providers=[bcb, yahoo])

    assert result.rate == Decimal("5.00")
    assert result.source == "manual"


def test_all_providers_fail_and_no_saved_quote_raises():
    bcb = _FakeProvider("bcb", raise_exc=True)
    yahoo = _FakeProvider("yahoo", raise_exc=True)

    with pytest.raises(RuntimeError):
        fx_service.update_usd_brl_rate(providers=[bcb, yahoo])
