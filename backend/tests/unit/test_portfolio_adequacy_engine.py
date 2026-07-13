"""Testes do PortfolioAdequacyEngine — orquestração pura (Sprint 26, Fase 5)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.portfolio_adequacy.engine import PortfolioAdequacyEngine
from backend.app.schemas.portfolio_adequacy import (
    ADEQUACY_STATUS_INDETERMINATE,
    EVALUATED_DIMENSION_ASSET,
    EVALUATED_DIMENSION_CLASS,
    VALUATION_NOT_APPLICABLE_MESSAGE,
)
from backend.app.schemas.target_allocation import AllocationRuleEvaluation

_ENGINE = PortfolioAdequacyEngine()


def _evaluation(**kwargs) -> AllocationRuleEvaluation:
    base = {
        "dimension_type": "asset",
        "dimension_key": "VOO",
        "current_weight": Decimal("0.10"),
        "target_weight": Decimal("0.10"),
        "min_weight": None,
        "max_weight": None,
        "gap_to_target": Decimal("0"),
        "gap_status": "neutral",
        "contribution_priority": 0,
        "rebalance_required": False,
        "extreme_overweight": False,
        "alert_message": None,
    }
    base.update(kwargs)
    return AllocationRuleEvaluation(**base)


def test_out_of_scope_asset_class_returns_reason():
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        asset_evaluation=None,
        class_evaluation=None,
    )
    assert result.reason is not None
    assert "fora do escopo" in result.reason
    assert result.valuation_applicable is False


def test_valuation_note_is_always_present_regardless_of_outcome():
    result = _ENGINE.evaluate(
        ticker="VOO", asset_class="etf", asset_evaluation=None, class_evaluation=None
    )
    assert result.valuation_note == VALUATION_NOT_APPLICABLE_MESSAGE
    assert result.valuation_applicable is False


def test_no_rules_at_all_is_indeterminate():
    result = _ENGINE.evaluate(
        ticker="VOO", asset_class="etf", asset_evaluation=None, class_evaluation=None
    )
    assert result.adequacy_status == ADEQUACY_STATUS_INDETERMINATE
    assert result.reason is not None
    assert "nenhuma regra" in result.reason


def test_asset_level_rule_takes_precedence_and_high_confidence():
    asset_eval = _evaluation(
        dimension_type="asset",
        dimension_key="VOO",
        current_weight=Decimal("0.08"),
        target_weight=Decimal("0.12"),
        gap_to_target=Decimal("-0.04"),
        gap_status="underweight",
        rebalance_required=True,
    )
    class_eval = _evaluation(
        dimension_type="class",
        dimension_key="etf",
        current_weight=Decimal("0.20"),
        target_weight=Decimal("0.15"),
        gap_to_target=Decimal("0.05"),
        gap_status="overweight",
    )
    result = _ENGINE.evaluate(
        ticker="VOO", asset_class="etf", asset_evaluation=asset_eval, class_evaluation=class_eval
    )
    assert result.evaluated_dimension == EVALUATED_DIMENSION_ASSET
    assert result.adequacy_status == "underweight"
    assert result.current_weight == Decimal("0.08")
    assert result.confidence == "alta"
    assert result.warnings == []
    # Contexto de classe fica disponível mesmo quando a regra efetiva é de ativo.
    assert result.class_current_weight == Decimal("0.20")
    assert result.class_target_weight == Decimal("0.15")


def test_falls_back_to_class_rule_with_medium_confidence_and_warning():
    class_eval = _evaluation(
        dimension_type="class",
        dimension_key="crypto",
        current_weight=Decimal("0.03"),
        target_weight=Decimal("0.05"),
        max_weight=Decimal("0.10"),
        gap_to_target=Decimal("-0.02"),
        gap_status="underweight",
    )
    result = _ENGINE.evaluate(
        ticker="BTC-USD", asset_class="crypto", asset_evaluation=None, class_evaluation=class_eval
    )
    assert result.evaluated_dimension == EVALUATED_DIMENSION_CLASS
    assert result.adequacy_status == "underweight"
    assert result.confidence == "média"
    assert len(result.warnings) == 1
    assert "BTC-USD" in result.warnings[0]


def test_blocked_status_and_alert_message_pass_through_unchanged():
    asset_eval = _evaluation(
        dimension_type="asset",
        dimension_key="BTC-USD",
        current_weight=Decimal("0.18"),
        target_weight=Decimal("0.05"),
        max_weight=Decimal("0.10"),
        gap_to_target=Decimal("0.13"),
        gap_status="blocked",
        rebalance_required=True,
        extreme_overweight=True,
        alert_message="asset=BTC-USD: peso atual ultrapassa o máximo configurado.",
    )
    result = _ENGINE.evaluate(
        ticker="BTC-USD", asset_class="crypto", asset_evaluation=asset_eval, class_evaluation=None
    )
    assert result.adequacy_status == "blocked"
    assert result.extreme_overweight is True
    assert result.alert_message == asset_eval.alert_message
    # Nunca reescreve o alerta como recomendação de venda — passa o texto
    # já pronto do Target Allocation Engine v2 (que nunca sugere vender).
    assert "vend" not in (result.alert_message or "").lower()


def test_methodology_always_cites_target_allocation_rule():
    asset_eval = _evaluation()
    result = _ENGINE.evaluate(
        ticker="VOO", asset_class="etf", asset_evaluation=asset_eval, class_evaluation=None
    )
    assert result.methodology == ["target_allocation_rule"]


def test_bond_asset_class_is_in_scope():
    asset_eval = _evaluation(dimension_type="asset", dimension_key="TESOURO-IPCA-2035")
    result = _ENGINE.evaluate(
        ticker="TESOURO-IPCA-2035",
        asset_class="bond",
        asset_evaluation=asset_eval,
        class_evaluation=None,
    )
    assert result.reason is None
    assert result.evaluated_dimension == EVALUATED_DIMENSION_ASSET
