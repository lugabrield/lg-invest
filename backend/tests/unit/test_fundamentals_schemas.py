"""Testes de FundamentalSnapshotResult (coverage_pct / missing_fields)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from backend.app.schemas.fundamentals import _RATIO_FIELDS, FundamentalSnapshotResult


def _result(**overrides) -> FundamentalSnapshotResult:
    base = {
        "ticker": "WEGE3.SA",
        "period_end": date(2026, 6, 30),
        "source": "yahoo",
        "collected_at": datetime(2026, 6, 30, 12, 0, 0),
    }
    base.update(overrides)
    return FundamentalSnapshotResult(**base)


def test_full_coverage_when_all_fields_present():
    values = {field: Decimal("1") for field in _RATIO_FIELDS}
    result = _result(**values)
    assert result.missing_fields == []
    assert result.coverage_pct == Decimal("1")


def test_zero_coverage_when_no_fields_present():
    result = _result()
    assert len(result.missing_fields) == len(_RATIO_FIELDS)
    assert result.coverage_pct == Decimal("0")


def test_partial_coverage():
    result = _result(roe=Decimal("0.2"), pe_ratio=Decimal("10"))
    assert set(result.missing_fields) == set(_RATIO_FIELDS) - {"roe", "pe_ratio"}
    assert result.coverage_pct == Decimal(2) / Decimal(len(_RATIO_FIELDS))
