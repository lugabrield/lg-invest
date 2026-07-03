"""Testes de concentração: HHI e número efetivo de ativos (Volume 8, seção 9)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.engines.portfolio.concentration import (
    effective_number_of_assets,
    herfindahl_index,
)


def test_single_asset_hhi_is_one():
    assert herfindahl_index([Decimal("1")]) == Decimal("1")


def test_n_equal_assets_hhi_is_one_over_n():
    weights = [Decimal("0.25")] * 4
    assert herfindahl_index(weights) == pytest.approx(Decimal("0.25"))


def test_empty_weights_hhi_is_zero():
    assert herfindahl_index([]) == Decimal("0")


def test_effective_number_of_assets():
    # 4 ativos iguais => HHI 0.25 => número efetivo 4.
    hhi = herfindahl_index([Decimal("0.25")] * 4)
    assert effective_number_of_assets(hhi) == pytest.approx(Decimal("4"))


def test_effective_number_none_when_hhi_zero():
    assert effective_number_of_assets(Decimal("0")) is None
