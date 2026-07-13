"""Testes do reverse DCF (Sprint 26, Fase 2)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.valuation_v2.dcf import dcf_fair_value_per_share
from backend.app.engines.valuation_v2.reverse_dcf import implied_growth_rate

_COMMON_KWARGS = dict(
    fcf0=Decimal("100"),
    discount_rate_value=Decimal("0.10"),
    terminal_growth=Decimal("0.02"),
    shares_outstanding=Decimal("10"),
    net_debt=Decimal("0"),
    years=5,
)


def test_implied_growth_rate_recovers_known_growth():
    known_growth = Decimal("0.05")
    price_at_known_growth, reason = dcf_fair_value_per_share(
        growth_rate=known_growth, **_COMMON_KWARGS
    )
    assert reason is None
    assert price_at_known_growth is not None

    implied, implied_reason = implied_growth_rate(
        current_price=price_at_known_growth,
        growth_low=Decimal("-0.10"),
        growth_high=Decimal("0.20"),
        **_COMMON_KWARGS,
    )
    assert implied_reason is None
    assert implied is not None
    assert abs(implied - known_growth) < Decimal("0.001")


def test_implied_growth_rate_returns_lower_bound_when_price_below_pessimistic():
    value_at_low, _ = dcf_fair_value_per_share(growth_rate=Decimal("-0.10"), **_COMMON_KWARGS)
    implied, reason = implied_growth_rate(
        current_price=value_at_low - Decimal("1"),
        growth_low=Decimal("-0.10"),
        growth_high=Decimal("0.20"),
        **_COMMON_KWARGS,
    )
    assert reason is None
    assert implied == Decimal("-0.10")


def test_implied_growth_rate_none_when_price_above_optimistic_bound():
    value_at_high, _ = dcf_fair_value_per_share(growth_rate=Decimal("0.20"), **_COMMON_KWARGS)
    implied, reason = implied_growth_rate(
        current_price=value_at_high + Decimal("1000"),
        growth_low=Decimal("-0.10"),
        growth_high=Decimal("0.20"),
        **_COMMON_KWARGS,
    )
    assert implied is None
    assert "extremamente otimista" in reason


def test_implied_growth_rate_none_when_dcf_never_converges():
    # fcf0 não positivo faz o DCF nunca convergir em nenhum extremo.
    kwargs = dict(_COMMON_KWARGS)
    kwargs["fcf0"] = Decimal("-10")
    implied, reason = implied_growth_rate(
        current_price=Decimal("50"),
        growth_low=Decimal("-0.10"),
        growth_high=Decimal("0.20"),
        **kwargs,
    )
    assert implied is None
    assert "não converge" in reason
