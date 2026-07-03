"""Testes dos validadores de qualidade de preço (Volume 18, seção 7)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from backend.app.etl.contracts.price_data import PriceData
from backend.app.etl.validators.price_validators import validate_price


def _price(**kwargs) -> PriceData:
    base = {
        "ticker": "WEGE3.SA",
        "date": date(2026, 1, 2),
        "close": Decimal("40.00"),
        "currency": "BRL",
        "source_name": "test",
        "collected_at": datetime.now(UTC),
    }
    base.update(kwargs)
    return PriceData(**base)


def test_valid_price_passes():
    assert validate_price(_price(), today=date(2026, 1, 3)) is None


def test_non_positive_close_is_rejected():
    assert validate_price(_price(close=Decimal("0")), today=date(2026, 1, 3)) is not None


def test_future_date_is_rejected():
    reason = validate_price(_price(date=date(2026, 6, 1)), today=date(2026, 1, 3))
    assert reason == "data no futuro"


def test_high_less_than_low_is_rejected():
    reason = validate_price(_price(high=Decimal("30"), low=Decimal("35")), today=date(2026, 1, 3))
    assert reason == "high menor que low"


def test_negative_volume_is_rejected():
    reason = validate_price(_price(volume=Decimal("-10")), today=date(2026, 1, 3))
    assert reason == "volume negativo"
