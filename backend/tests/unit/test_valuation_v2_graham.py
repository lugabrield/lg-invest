"""Testes do Graham Number — checagem de sanidade (Sprint 26, Fase 2)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.valuation_v2.graham import graham_number


def test_graham_number_happy_path():
    # sqrt(22.5 x 5 x 20) = sqrt(2250) ≈ 47.4342
    value, reason = graham_number(Decimal("5"), Decimal("20"))
    assert reason is None
    assert value is not None
    assert abs(value - Decimal("47.4342")) < Decimal("0.001")


def test_graham_number_none_when_eps_missing():
    value, reason = graham_number(None, Decimal("20"))
    assert value is None
    assert "indisponível" in reason


def test_graham_number_none_when_book_value_missing():
    value, reason = graham_number(Decimal("5"), None)
    assert value is None
    assert "indisponível" in reason


def test_graham_number_none_when_eps_negative():
    value, reason = graham_number(Decimal("-2"), Decimal("20"))
    assert value is None
    assert "não positivo" in reason


def test_graham_number_none_when_book_value_negative():
    value, reason = graham_number(Decimal("5"), Decimal("-1"))
    assert value is None
    assert "não positivo" in reason


def test_graham_number_none_when_both_zero():
    value, reason = graham_number(Decimal("0"), Decimal("0"))
    assert value is None
    assert "não positivo" in reason
