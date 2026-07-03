"""Testes do fx_settings_service (câmbio USD/BRL manual, persistência em JSON).

Isola o arquivo real (`data/app_settings.json`) via monkeypatch, para não
gravar nada no ambiente de desenvolvimento durante os testes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.app.schemas.market_data import FxQuote
from backend.app.services import fx_settings_service


@pytest.fixture(autouse=True)
def _isolated_settings_file(tmp_path, monkeypatch):
    monkeypatch.setattr(fx_settings_service, "_SETTINGS_PATH", tmp_path / "app_settings.json")


def test_default_rate_when_no_file():
    assert fx_settings_service.get_usd_brl_rate() == fx_settings_service._DEFAULT_USD_BRL_RATE


def test_get_fx_quote_none_when_no_file():
    assert fx_settings_service.get_fx_quote() is None


def test_set_fx_quote_roundtrip():
    now = datetime.now(UTC)
    quote = FxQuote(
        pair="USDBRL", rate=Decimal("5.42"), source="bcb", quote_date=now, fetched_at=now
    )
    fx_settings_service.set_fx_quote(quote)

    saved = fx_settings_service.get_fx_quote()
    assert saved is not None
    assert saved.rate == Decimal("5.42")
    assert saved.source == "bcb"
    assert saved.is_override is False
    assert fx_settings_service.get_usd_brl_rate() == Decimal("5.42")


def test_set_usd_brl_rate_marks_source_manual_override():
    fx_settings_service.set_usd_brl_rate(Decimal("5.35"))
    quote = fx_settings_service.get_fx_quote()
    assert quote is not None
    assert quote.source == "manual"
    assert quote.is_override is True


def test_legacy_file_without_source_is_treated_as_manual(tmp_path):
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text('{"usd_brl_rate": "5.10"}', encoding="utf-8")
    quote = fx_settings_service.get_fx_quote()
    assert quote is not None
    assert quote.rate == Decimal("5.10")
    assert quote.source == "manual"


def test_set_and_get_rate_roundtrip():
    fx_settings_service.set_usd_brl_rate(Decimal("5.35"))
    assert fx_settings_service.get_usd_brl_rate() == Decimal("5.35")


def test_invalid_rate_raises():
    with pytest.raises(ValueError):
        fx_settings_service.set_usd_brl_rate(Decimal("0"))
    with pytest.raises(ValueError):
        fx_settings_service.set_usd_brl_rate(Decimal("-1"))


def test_corrupted_file_falls_back_to_default(tmp_path):
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text("{not valid json", encoding="utf-8")
    assert fx_settings_service.get_usd_brl_rate() == fx_settings_service._DEFAULT_USD_BRL_RATE


def test_set_rate_preserves_other_keys(tmp_path):
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text('{"other_key": "keep-me"}', encoding="utf-8")
    fx_settings_service.set_usd_brl_rate(Decimal("6.0"))
    data = fx_settings_service._read_all()
    assert data["other_key"] == "keep-me"
    assert data["usd_brl_rate"] == "6.0"
