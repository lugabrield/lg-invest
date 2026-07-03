"""Testes do engine de Diagnóstico da Carteira (Sprint 11).

Engine pura: constrói `DashboardView` na mão (sem banco) e verifica as
regras de `engines/portfolio_diagnostics`. Mesmo padrão dos outros
testes de engine do projeto (ex.: `test_portfolio_engine.py`).
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.portfolio_diagnostics import thresholds as t
from backend.app.engines.portfolio_diagnostics.engine import build_diagnostics
from backend.app.schemas.dashboard_view import ConvertedPosition, CurrencyExposure, DashboardView
from backend.app.schemas.portfolio_diagnostics import (
    SEVERITY_ALERT,
    SEVERITY_ATTENTION,
    SEVERITY_INFO,
    SEVERITY_POSITIVE,
)

_ZERO = Decimal("0")


def _position(
    ticker: str,
    group_label: str,
    currency: str,
    weight: Decimal,
    asset_class: str = "stock",
    return_pct: Decimal | None = Decimal("0"),
    is_estimated: bool = False,
    price_source: str = "yahoo",
) -> ConvertedPosition:
    value = weight * Decimal("100000")
    return ConvertedPosition(
        ticker=ticker,
        asset_class=asset_class,
        currency=currency,
        quantity=Decimal("1"),
        average_price=Decimal("1"),
        current_price=Decimal("1"),
        position_value=value,
        position_value_brl=value,
        weight=weight,
        return_pct=return_pct,
        is_price_estimated=is_estimated,
        group_label=group_label,
        price_source=price_source,
        price_updated_at=None,
    )


def _view(
    positions: list[ConvertedPosition],
    is_multi_currency: bool = False,
    effective_n: Decimal | None = Decimal("10"),
    estimated: list[str] | None = None,
    manual: list[str] | None = None,
) -> DashboardView:
    total = sum((p.position_value_brl for p in positions), _ZERO)
    by_currency: dict[str, Decimal] = {}
    for p in positions:
        by_currency[p.currency] = by_currency.get(p.currency, _ZERO) + p.position_value_brl
    currency_exposure = [
        CurrencyExposure(currency=c, value_brl=v, weight=(v / total if total > 0 else _ZERO))
        for c, v in by_currency.items()
    ]
    largest = max(positions, key=lambda p: p.weight).ticker if positions else None
    return DashboardView(
        exchange_rate=Decimal("5"),
        total_brl=total,
        total_usd=_ZERO,
        total_converted_brl=total,
        total_cost_brl=total,
        total_return_pct=None,
        is_multi_currency=is_multi_currency,
        currency_exposure=currency_exposure,
        positions=positions,
        largest_position_ticker=largest,
        concentration_hhi=_ZERO,
        effective_number_of_assets=effective_n,
        estimated_price_tickers=estimated or [],
        manual_price_tickers=manual or [],
        unpriced_tickers=[],
    )


def _insight(diagnostics, code: str):
    return next((i for i in diagnostics.insights if i.code == code), None)


def test_no_positions_returns_no_insights():
    diagnostics = build_diagnostics(_view([], effective_n=None))
    assert diagnostics.insights == []


def test_concentration_alert_above_threshold():
    positions = [
        _position("ITUB4.SA", "Ações BR", "BRL", Decimal("0.90")),
        _position("WEGE3.SA", "Ações BR", "BRL", Decimal("0.10")),
    ]
    diagnostics = build_diagnostics(_view(positions))
    insight = _insight(diagnostics, "concentration_single_asset")
    assert insight.severity == SEVERITY_ALERT
    assert "ITUB4.SA" in insight.message


def test_concentration_attention_between_thresholds():
    weight = (t.SINGLE_POSITION_WARN + t.SINGLE_POSITION_ALERT) / 2
    remaining = (Decimal("1") - weight) / 8
    positions = [_position("ITUB4.SA", "Ações BR", "BRL", weight)]
    positions += [_position(f"T{i}", "Ações BR", "BRL", remaining) for i in range(8)]
    diagnostics = build_diagnostics(_view(positions))
    insight = _insight(diagnostics, "concentration_single_asset")
    assert insight.severity == SEVERITY_ATTENTION
    assert "ITUB4.SA" in insight.message


def test_concentration_positive_case():
    positions = [_position(f"T{i}", "Ações BR", "BRL", Decimal("0.1")) for i in range(10)]
    diagnostics = build_diagnostics(_view(positions))
    insight = _insight(diagnostics, "concentration_single_asset")
    assert insight.severity == SEVERITY_POSITIVE


def test_dominant_group_attention_above_threshold():
    positions = [
        _position("A", "Ações BR", "BRL", Decimal("0.6")),
        _position("B", "FIIs", "BRL", Decimal("0.4")),
    ]
    diagnostics = build_diagnostics(_view(positions))
    insight = _insight(diagnostics, "dominant_group")
    assert insight.severity == SEVERITY_ATTENTION
    assert "Ações BR" in insight.message


def test_dominant_group_info_below_threshold():
    positions = [
        _position("A", "Ações BR", "BRL", Decimal("0.3")),
        _position("B", "FIIs", "BRL", Decimal("0.3")),
        _position("C", "Ações EUA", "USD", Decimal("0.4")),
    ]
    diagnostics = build_diagnostics(_view(positions))
    insight = _insight(diagnostics, "dominant_group")
    assert insight.severity == SEVERITY_INFO


def test_diversification_low():
    positions = [_position("A", "Ações BR", "BRL", Decimal("1"))]
    diagnostics = build_diagnostics(_view(positions, effective_n=Decimal("2")))
    insight = _insight(diagnostics, "diversification")
    assert insight.severity == SEVERITY_ATTENTION


def test_diversification_moderate():
    positions = [_position("A", "Ações BR", "BRL", Decimal("1"))]
    diagnostics = build_diagnostics(_view(positions, effective_n=Decimal("7")))
    insight = _insight(diagnostics, "diversification")
    assert insight.severity == SEVERITY_INFO


def test_diversification_good():
    positions = [_position("A", "Ações BR", "BRL", Decimal("1"))]
    diagnostics = build_diagnostics(_view(positions, effective_n=Decimal("15")))
    insight = _insight(diagnostics, "diversification")
    assert insight.severity == SEVERITY_POSITIVE


def test_diversification_skipped_when_none():
    positions = [_position("A", "Ações BR", "BRL", Decimal("1"))]
    diagnostics = build_diagnostics(_view(positions, effective_n=None))
    assert _insight(diagnostics, "diversification") is None


def test_international_exposure_attention_when_low():
    positions = [
        _position("A", "Ações BR", "BRL", Decimal("0.9")),
        _position("B", "Ações EUA", "USD", Decimal("0.1")),
    ]
    diagnostics = build_diagnostics(_view(positions))
    insight = _insight(diagnostics, "international_exposure")
    assert insight.severity == SEVERITY_ATTENTION
    assert "internacional" in insight.message.lower()


def test_international_exposure_info_when_adequate():
    positions = [
        _position("A", "Ações BR", "BRL", Decimal("0.5")),
        _position("B", "Ações EUA", "USD", Decimal("0.5")),
    ]
    diagnostics = build_diagnostics(_view(positions))
    insight = _insight(diagnostics, "international_exposure")
    assert insight.severity == SEVERITY_INFO


def test_fii_weight_attention_above_threshold():
    positions = [
        _position("A", "FIIs", "BRL", Decimal("0.4"), asset_class="fii"),
        _position("B", "Ações BR", "BRL", Decimal("0.6")),
    ]
    diagnostics = build_diagnostics(_view(positions))
    insight = _insight(diagnostics, "weight_fiis")
    assert insight.severity == SEVERITY_ATTENTION


def test_crypto_weight_attention_above_threshold():
    positions = [
        _position("BTC", "Cripto", "USD", Decimal("0.2"), asset_class="crypto"),
        _position("A", "Ações BR", "BRL", Decimal("0.8")),
    ]
    diagnostics = build_diagnostics(_view(positions))
    insight = _insight(diagnostics, "weight_crypto")
    assert insight.severity == SEVERITY_ATTENTION


def test_multi_currency_insight_present_only_when_flagged():
    positions = [_position("A", "Ações BR", "BRL", Decimal("1"))]
    diagnostics_multi = build_diagnostics(_view(positions, is_multi_currency=True))
    diagnostics_single = build_diagnostics(_view(positions, is_multi_currency=False))
    assert _insight(diagnostics_multi, "multi_currency") is not None
    assert _insight(diagnostics_single, "multi_currency") is None


def test_manual_and_estimated_prices_insight():
    positions = [_position("A", "Ações BR", "BRL", Decimal("1"))]
    diagnostics = build_diagnostics(
        _view(positions, estimated=["TESOURO-IPCA-2050"], manual=["OUTRO-ATIVO"])
    )
    insight = _insight(diagnostics, "manual_or_estimated_prices")
    assert insight is not None
    assert "TESOURO-IPCA-2050" in insight.message
    assert "OUTRO-ATIVO" in insight.message
    assert insight.severity == SEVERITY_ATTENTION


def test_no_manual_or_estimated_insight_when_all_automatic():
    positions = [_position("A", "Ações BR", "BRL", Decimal("1"))]
    diagnostics = build_diagnostics(_view(positions))
    assert _insight(diagnostics, "manual_or_estimated_prices") is None


def test_cash_position_insight_only_when_cash_class_present():
    positions_without_cash = [_position("A", "Ações BR", "BRL", Decimal("1"))]
    positions_with_cash = [
        _position("A", "Ações BR", "BRL", Decimal("0.9")),
        _position("CAIXA", "Renda Fixa", "BRL", Decimal("0.1"), asset_class="cash"),
    ]
    diagnostics_without = build_diagnostics(_view(positions_without_cash))
    diagnostics_with = build_diagnostics(_view(positions_with_cash))
    assert _insight(diagnostics_without, "cash_position") is None
    assert _insight(diagnostics_with, "cash_position") is not None
