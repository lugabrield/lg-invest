"""Testes do Target Allocation Engine (Sprint 17) — puro, sem banco/rede."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.target_allocation.engine import TargetAllocationEngine


def test_no_target_returns_has_target_false():
    engine = TargetAllocationEngine()
    result = engine.compare({"stock": Decimal("1.0")}, {})
    assert result.has_target is False
    assert result.reason is not None
    assert result.classes == []


def test_within_tolerance_is_dentro():
    engine = TargetAllocationEngine()
    result = engine.compare(
        {"stock": Decimal("0.31")},
        {"stock": Decimal("0.30")},
    )
    stock = next(c for c in result.classes if c.asset_class == "stock")
    assert stock.status == "dentro"


def test_underweight_is_abaixo():
    engine = TargetAllocationEngine()
    result = engine.compare(
        {"stock": Decimal("0.10")},
        {"stock": Decimal("0.30")},
    )
    stock = next(c for c in result.classes if c.asset_class == "stock")
    assert stock.status == "abaixo"
    assert stock.drift_pct == Decimal("-0.20")


def test_overweight_is_acima():
    engine = TargetAllocationEngine()
    result = engine.compare(
        {"stock": Decimal("0.50")},
        {"stock": Decimal("0.30")},
    )
    stock = next(c for c in result.classes if c.asset_class == "stock")
    assert stock.status == "acima"


def test_class_missing_from_current_is_fully_underweight():
    engine = TargetAllocationEngine()
    result = engine.compare(
        {"stock": Decimal("1.0")},
        {"stock": Decimal("0.70"), "fii": Decimal("0.30")},
    )
    fii = next(c for c in result.classes if c.asset_class == "fii")
    assert fii.current_pct == Decimal("0")
    assert fii.status == "abaixo"


def test_most_underweight_class_is_identified():
    engine = TargetAllocationEngine()
    result = engine.compare(
        {"stock": Decimal("0.60"), "fii": Decimal("0.40")},
        {"stock": Decimal("0.50"), "fii": Decimal("0.30"), "crypto": Decimal("0.20")},
    )
    assert result.most_underweight_class == "crypto"


def test_no_underweight_class_when_all_within_or_over():
    engine = TargetAllocationEngine()
    result = engine.compare(
        {"stock": Decimal("0.50")},
        {"stock": Decimal("0.30")},
    )
    assert result.most_underweight_class is None
