"""Testes do Trap Detection Engine — orquestração (Sprint 26, Fases 3-4)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from backend.app.engines.trap_detection.engine import TrapDetectionEngine
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.fundamentals_analysis import FundamentalsAnalysisResult
from backend.app.schemas.income_real_estate import IncomeRealEstateAnalysisResult
from backend.app.schemas.trap_detection import (
    TRAP_TYPE_FII_YIELD,
    TRAP_TYPE_HIGH_DY,
    TRAP_TYPE_LEVERAGE,
    TRAP_TYPE_LOW_PE,
)
from backend.app.schemas.valuation_v2 import ValuationV2Result

_ENGINE = TrapDetectionEngine()


def _snap(**kwargs) -> FundamentalSnapshotResult:
    base = {
        "ticker": "WEGE3.SA",
        "period_end": date(2024, 12, 31),
        "source": "yahoo",
        "collected_at": datetime(2025, 1, 1),
    }
    base.update(kwargs)
    return FundamentalSnapshotResult(**base)


def test_out_of_scope_asset_class_returns_no_flags_with_reason():
    result = _ENGINE.evaluate(
        ticker="BOVA11.SA",
        asset_class="etf",
        latest_snapshot=_snap(),
        fundamentals_analysis=None,
        valuation=None,
    )
    assert result.flags == []
    assert result.confidence_penalty == Decimal("0")
    assert "etf" in result.reason
    assert "fora do escopo" in result.reason


def test_no_snapshot_returns_no_flags_with_reason():
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        latest_snapshot=None,
        fundamentals_analysis=None,
        valuation=None,
    )
    assert result.flags == []
    assert result.reason is not None


def test_clean_asset_has_no_flags():
    # Preenche fundamentos suficientes para não disparar o data_quality_trap
    # por baixa cobertura (>= 50% dos campos de `_RATIO_FIELDS`).
    snapshot = _snap(
        pe_ratio=Decimal("15"),
        pb_ratio=Decimal("2.0"),
        roe=Decimal("0.18"),
        roa=Decimal("0.10"),
        net_margin=Decimal("0.15"),
        ebitda_margin=Decimal("0.25"),
        revenue=Decimal("1000000"),
        net_income=Decimal("150000"),
        ebitda=Decimal("250000"),
        ebit=Decimal("200000"),
        free_cash_flow=Decimal("120000"),
        net_debt=Decimal("100000"),
        debt_to_ebitda=Decimal("1.5"),
        interest_coverage=Decimal("10"),
        eps=Decimal("3.0"),
        beta=Decimal("0.9"),
        shares_outstanding=Decimal("50000"),
        total_equity=Decimal("800000"),
    )
    analysis = FundamentalsAnalysisResult(
        ticker="WEGE3.SA",
        periods_used=4,
        net_income_cagr=Decimal("0.10"),
        margin_trend="estável",
        confidence="alta",
    )
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        latest_snapshot=snapshot,
        fundamentals_analysis=analysis,
        valuation=None,
    )
    assert result.flags == []
    assert result.confidence_penalty == Decimal("0")
    assert result.has_traps is False


def test_multiple_traps_accumulate_confidence_penalty():
    snapshot = _snap(
        pe_ratio=Decimal("6"),  # baixo
        pb_ratio=Decimal("2.0"),
        roe=Decimal("0.18"),
        debt_to_ebitda=Decimal("7"),  # alavancagem muito alta
        interest_coverage=Decimal("10"),
    )
    analysis = FundamentalsAnalysisResult(
        ticker="WEGE3.SA",
        periods_used=4,
        net_income_cagr=Decimal("-0.10"),  # lucro em queda -> ativa low_pe_trap
        margin_trend="estável",
        confidence="média",
    )
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        latest_snapshot=snapshot,
        fundamentals_analysis=analysis,
        valuation=None,
    )
    trap_types = {flag.trap_type for flag in result.flags}
    assert TRAP_TYPE_LOW_PE in trap_types
    assert TRAP_TYPE_LEVERAGE in trap_types
    assert result.confidence_penalty == sum(
        (flag.confidence_penalty for flag in result.flags), Decimal("0")
    )
    assert result.has_traps is True


def test_confidence_penalty_is_capped_at_one():
    # cenário artificial com todos os 5 detectores disparando em alta
    # severidade — a soma bruta seria 1.0, e o cap deve segurar nesse valor.
    snapshot = _snap(
        pe_ratio=Decimal("5"),
        pb_ratio=Decimal("0.5"),
        roe=Decimal("-0.10"),
        debt_to_ebitda=Decimal("8"),
        interest_coverage=Decimal("0.5"),
    )
    analysis = FundamentalsAnalysisResult(
        ticker="WEGE3.SA",
        periods_used=1,  # dispara data_quality_trap
        net_income_cagr=Decimal("-0.20"),
        margin_trend="piorando",
        confidence="baixa",
    )
    valuation = ValuationV2Result(
        ticker="WEGE3.SA",
        asset_class="stock",
        implied_growth_rate=Decimal("0.40"),
    )
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        latest_snapshot=snapshot,
        fundamentals_analysis=analysis,
        valuation=valuation,
    )
    assert result.confidence_penalty <= Decimal("1.0")
    assert len(result.flags) == 5


def test_growth_overpriced_trap_uses_valuation_implied_growth():
    snapshot = _snap(pe_ratio=Decimal("20"), pb_ratio=Decimal("3"), roe=Decimal("0.20"))
    analysis = FundamentalsAnalysisResult(
        ticker="WEGE3.SA", periods_used=4, fcf_cagr=Decimal("0.05"), confidence="alta"
    )
    valuation = ValuationV2Result(
        ticker="WEGE3.SA", asset_class="stock", implied_growth_rate=Decimal("0.25")
    )
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        latest_snapshot=snapshot,
        fundamentals_analysis=analysis,
        valuation=valuation,
    )
    trap_types = {flag.trap_type for flag in result.flags}
    assert "growth_overpriced_trap" in trap_types


def test_no_valuation_means_no_growth_overpriced_trap():
    snapshot = _snap(pe_ratio=Decimal("20"), pb_ratio=Decimal("3"), roe=Decimal("0.20"))
    analysis = FundamentalsAnalysisResult(
        ticker="WEGE3.SA", periods_used=4, fcf_cagr=Decimal("0.05"), confidence="alta"
    )
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        latest_snapshot=snapshot,
        fundamentals_analysis=analysis,
        valuation=None,
    )
    trap_types = {flag.trap_type for flag in result.flags}
    assert "growth_overpriced_trap" not in trap_types


# --- FIIs/REITs (Sprint 26, Fase 4) --------------------------------------


def _fii_snap(**kwargs) -> FundamentalSnapshotResult:
    base = {
        "ticker": "BTLG11.SA",
        "period_end": date(2024, 12, 31),
        "source": "yahoo",
        "collected_at": datetime(2025, 1, 1),
    }
    base.update(kwargs)
    return FundamentalSnapshotResult(**base)


def test_fii_asset_class_is_in_scope_and_uses_income_real_estate_detectors():
    snapshot = _fii_snap(dividend_yield=Decimal("0.07"))
    result = _ENGINE.evaluate(
        ticker="BTLG11.SA",
        asset_class="fii",
        latest_snapshot=snapshot,
        fundamentals_analysis=None,
        valuation=None,
        income_real_estate=None,
    )
    assert result.reason is None
    assert result.flags == []


def test_reit_high_dy_trap_fires_without_income_real_estate_result():
    snapshot = _fii_snap(dividend_yield=Decimal("0.20"))
    result = _ENGINE.evaluate(
        ticker="O",
        asset_class="reit",
        latest_snapshot=snapshot,
        fundamentals_analysis=None,
        valuation=None,
        income_real_estate=None,
    )
    trap_types = {flag.trap_type for flag in result.flags}
    assert TRAP_TYPE_HIGH_DY in trap_types
    assert TRAP_TYPE_FII_YIELD not in trap_types  # sem histórico, não dá pra comparar


def test_fii_yield_trap_fires_when_income_real_estate_history_available():
    snapshot = _fii_snap(dividend_yield=Decimal("0.13"))
    income_real_estate = IncomeRealEstateAnalysisResult(
        ticker="BTLG11.SA",
        asset_class="fii",
        dy_own_history_average=Decimal("0.07"),
    )
    result = _ENGINE.evaluate(
        ticker="BTLG11.SA",
        asset_class="fii",
        latest_snapshot=snapshot,
        fundamentals_analysis=None,
        valuation=None,
        income_real_estate=income_real_estate,
    )
    trap_types = {flag.trap_type for flag in result.flags}
    assert TRAP_TYPE_HIGH_DY in trap_types
    assert TRAP_TYPE_FII_YIELD in trap_types


def test_fii_low_dy_has_no_flags():
    snapshot = _fii_snap(dividend_yield=Decimal("0.06"))
    income_real_estate = IncomeRealEstateAnalysisResult(
        ticker="BTLG11.SA",
        asset_class="fii",
        dy_own_history_average=Decimal("0.055"),
    )
    result = _ENGINE.evaluate(
        ticker="BTLG11.SA",
        asset_class="fii",
        latest_snapshot=snapshot,
        fundamentals_analysis=None,
        valuation=None,
        income_real_estate=income_real_estate,
    )
    assert result.flags == []
    assert result.has_traps is False


def test_stock_only_tests_still_pass_unchanged_scope():
    # Ações continuam usando exclusivamente os 5 detectores da Fase 3 —
    # nenhum flag de FII/REIT deve aparecer mesmo passando income_real_estate.
    snapshot = _snap(pe_ratio=Decimal("15"), pb_ratio=Decimal("2.0"), roe=Decimal("0.18"))
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        latest_snapshot=snapshot,
        fundamentals_analysis=None,
        valuation=None,
    )
    trap_types = {flag.trap_type for flag in result.flags}
    assert TRAP_TYPE_HIGH_DY not in trap_types
    assert TRAP_TYPE_FII_YIELD not in trap_types
