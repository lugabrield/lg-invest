"""Testes do Portfolio Health Score (Sprint 24, Fase 8) — engine pura, sem
banco."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.portfolio_health.engine import evaluate_portfolio_health
from backend.app.engines.portfolio_health.inputs import (
    AllocationAlignmentInput,
    PortfolioHealthInput,
)


def _data(**overrides) -> PortfolioHealthInput:
    base = dict(
        effective_number_of_assets=Decimal("10"),
        risk_overall_classification="moderado",
        declared_risk_tolerance="moderado",
        allocation_alignment=AllocationAlignmentInput(
            has_rules=True, total_evaluations=4, aligned_evaluations=4
        ),
        income_growth_pct=Decimal("0.05"),
        data_confidence_pct=Decimal("0.9"),
    )
    base.update(overrides)
    return PortfolioHealthInput(**base)


def test_all_five_factors_available_when_fully_configured():
    result = evaluate_portfolio_health(_data())
    assert len(result.factors) == 5
    assert all(f.available for f in result.factors)
    total_weight = sum(f.weight_used for f in result.factors)
    assert abs(total_weight - Decimal("1")) < Decimal("0.001")


def test_perfect_inputs_yield_high_score_and_excelente_classification():
    result = evaluate_portfolio_health(_data())
    assert result.overall_score > Decimal("80")
    assert result.overall_classification in ("boa", "excelente")


def test_higher_diversification_increases_score():
    low = evaluate_portfolio_health(_data(effective_number_of_assets=Decimal("2")))
    high = evaluate_portfolio_health(_data(effective_number_of_assets=Decimal("15")))
    assert high.overall_score > low.overall_score


def test_risk_above_tolerance_penalizes_score():
    aligned = evaluate_portfolio_health(
        _data(risk_overall_classification="moderado", declared_risk_tolerance="moderado")
    )
    misaligned = evaluate_portfolio_health(
        _data(risk_overall_classification="alto", declared_risk_tolerance="baixo")
    )
    assert misaligned.overall_score < aligned.overall_score


def test_missing_risk_data_marks_factor_unavailable_and_renormalizes():
    result = evaluate_portfolio_health(
        _data(risk_overall_classification=None, declared_risk_tolerance=None)
    )
    factor = next(f for f in result.factors if f.name == "alinhamento_de_risco")
    assert factor.available is False
    assert factor.weight_used == Decimal("0")
    other_weights = sum(f.weight_used for f in result.factors if f.available)
    assert abs(other_weights - Decimal("1")) < Decimal("0.001")
    assert any("alinhamento_de_risco" in w for w in result.warnings)


def test_no_allocation_rules_marks_factor_unavailable():
    result = evaluate_portfolio_health(_data(allocation_alignment=None))
    factor = next(f for f in result.factors if f.name == "aderência_alocação_alvo")
    assert factor.available is False


def test_missing_income_growth_marks_factor_unavailable():
    result = evaluate_portfolio_health(_data(income_growth_pct=None))
    factor = next(f for f in result.factors if f.name == "tendência_de_renda")
    assert factor.available is False


def test_negative_income_growth_reduces_score():
    positive = evaluate_portfolio_health(_data(income_growth_pct=Decimal("0.05")))
    negative = evaluate_portfolio_health(_data(income_growth_pct=Decimal("-0.15")))
    assert negative.overall_score < positive.overall_score


def test_missing_data_confidence_marks_factor_unavailable():
    result = evaluate_portfolio_health(_data(data_confidence_pct=None))
    factor = next(f for f in result.factors if f.name == "confiança_dos_dados")
    assert factor.available is False


def test_all_factors_unavailable_yields_indeterminado():
    data = PortfolioHealthInput(
        effective_number_of_assets=None,
        risk_overall_classification=None,
        declared_risk_tolerance=None,
        allocation_alignment=None,
        income_growth_pct=None,
        data_confidence_pct=None,
    )
    result = evaluate_portfolio_health(data)
    assert result.overall_classification == "indeterminado"
    assert result.overall_score == Decimal("0")


def test_overall_classification_matches_health_labels_scale():
    result = evaluate_portfolio_health(_data())
    assert result.overall_classification in ("crítica", "atenção", "boa", "excelente")


def test_model_version_is_stable():
    result = evaluate_portfolio_health(_data())
    assert result.model_version == "portfolio_health_v1"
