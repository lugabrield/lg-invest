"""Testes do allocation_projection_service (antes/depois do aporte).

Função pura: recebe `DashboardView` + `RecommendationResult` já prontos
(sem banco), então testado com objetos construídos na mão — igual aos
testes de engine.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.schemas.dashboard_view import ConvertedPosition, CurrencyExposure, DashboardView
from backend.app.schemas.recommendation_result import (
    DecisionAudit,
    RecommendationItem,
    RecommendationResult,
)
from backend.app.services.allocation_projection_service import build_allocation_projection

_ZERO = Decimal("0")


def _position(ticker, group_label, currency, value_brl) -> ConvertedPosition:
    return ConvertedPosition(
        ticker=ticker,
        asset_class="stock",
        currency=currency,
        quantity=Decimal("1"),
        average_price=Decimal("1"),
        current_price=Decimal("1"),
        position_value=value_brl,
        position_value_brl=value_brl,
        weight=_ZERO,  # recalculado abaixo em _view
        return_pct=Decimal("0"),
        is_price_estimated=False,
        group_label=group_label,
        price_source="yahoo",
        price_updated_at=None,
    )


def _view(positions: list[ConvertedPosition]) -> DashboardView:
    total = sum((p.position_value_brl for p in positions), _ZERO)
    positions = [p.model_copy(update={"weight": p.position_value_brl / total}) for p in positions]
    by_currency: dict[str, Decimal] = {}
    for p in positions:
        by_currency[p.currency] = by_currency.get(p.currency, _ZERO) + p.position_value_brl
    currency_exposure = [
        CurrencyExposure(currency=c, value_brl=v, weight=v / total) for c, v in by_currency.items()
    ]
    return DashboardView(
        exchange_rate=Decimal("5"),
        total_brl=total,
        total_usd=_ZERO,
        total_converted_brl=total,
        total_cost_brl=total,
        total_return_pct=None,
        is_multi_currency=len(by_currency) > 1,
        currency_exposure=currency_exposure,
        positions=positions,
        largest_position_ticker=max(positions, key=lambda p: p.weight).ticker,
        concentration_hhi=_ZERO,
        effective_number_of_assets=None,
        estimated_price_tickers=[],
        manual_price_tickers=[],
        unpriced_tickers=[],
    )


def _recommendation(items: list[RecommendationItem], contribution: Decimal) -> RecommendationResult:
    allocated = sum((i.amount for i in items), _ZERO)
    return RecommendationResult(
        contribution_amount=contribution,
        allocated_amount=allocated,
        items=items,
        ignored=[],
        alerts=[],
        confidence=Decimal("0.8"),
        confidence_label="alta",
        explanation="teste",
        audit=DecisionAudit(
            contribution_amount=contribution,
            eligible_tickers=[i.ticker for i in items],
            blocked_tickers=[],
            model_version="test",
            weights={},
        ),
    )


def test_totals_before_and_after():
    positions = [
        _position("WEGE3.SA", "Ações BR", "BRL", Decimal("4000")),
        _position("VOO", "ETFs", "USD", Decimal("6000")),
    ]
    view = _view(positions)
    items = [
        RecommendationItem(
            ticker="WEGE3.SA",
            amount=Decimal("1000"),
            weight=Decimal("1"),
            buy_score=Decimal("0.9"),
            lg_score=Decimal("80"),
            reasons=["bom preço"],
        )
    ]
    recommendation = _recommendation(items, Decimal("1000"))

    projection = build_allocation_projection(view, recommendation)
    assert projection.total_before_brl == Decimal("10000")
    assert projection.total_after_brl == Decimal("11000")


def test_group_weight_shifts_toward_recommended_ticker():
    positions = [
        _position("WEGE3.SA", "Ações BR", "BRL", Decimal("4000")),
        _position("VOO", "ETFs", "USD", Decimal("6000")),
    ]
    view = _view(positions)
    items = [
        RecommendationItem(
            ticker="WEGE3.SA",
            amount=Decimal("1000"),
            weight=Decimal("1"),
            buy_score=Decimal("0.9"),
            lg_score=Decimal("80"),
            reasons=[],
        )
    ]
    recommendation = _recommendation(items, Decimal("1000"))

    projection = build_allocation_projection(view, recommendation)
    by_group = {c.label: c for c in projection.by_group}

    assert by_group["Ações BR"].weight_before == Decimal("4000") / Decimal("10000")
    assert by_group["Ações BR"].weight_after == Decimal("5000") / Decimal("11000")
    assert by_group["Ações BR"].weight_after > by_group["Ações BR"].weight_before


def test_currency_weight_shifts_toward_brl_when_recommendation_is_brl_position():
    positions = [
        _position("WEGE3.SA", "Ações BR", "BRL", Decimal("4000")),
        _position("VOO", "ETFs", "USD", Decimal("6000")),
    ]
    view = _view(positions)
    items = [
        RecommendationItem(
            ticker="WEGE3.SA",
            amount=Decimal("1000"),
            weight=Decimal("1"),
            buy_score=Decimal("0.9"),
            lg_score=Decimal("80"),
            reasons=[],
        )
    ]
    recommendation = _recommendation(items, Decimal("1000"))

    projection = build_allocation_projection(view, recommendation)
    by_currency = {c.label: c for c in projection.by_currency}
    assert by_currency["BRL"].weight_after > by_currency["BRL"].weight_before
    assert by_currency["USD"].weight_after < by_currency["USD"].weight_before


def test_no_recommendation_items_keeps_weights_unchanged():
    positions = [
        _position("WEGE3.SA", "Ações BR", "BRL", Decimal("4000")),
        _position("VOO", "ETFs", "USD", Decimal("6000")),
    ]
    view = _view(positions)
    recommendation = _recommendation([], Decimal("1000"))

    projection = build_allocation_projection(view, recommendation)
    assert projection.total_after_brl == projection.total_before_brl
    for comparison in projection.by_group:
        assert comparison.weight_after == comparison.weight_before
