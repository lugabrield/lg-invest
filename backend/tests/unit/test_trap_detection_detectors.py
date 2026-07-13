"""Testes dos detectores puros de armadilha (Sprint 26, Fases 3-4)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.trap_detection.detectors import (
    detect_data_quality_trap,
    detect_fii_yield_trap,
    detect_growth_overpriced_trap,
    detect_high_dy_trap,
    detect_leverage_trap,
    detect_low_pb_trap,
    detect_low_pe_trap,
)
from backend.app.schemas.trap_detection import (
    TRAP_SEVERITY_HIGH,
    TRAP_SEVERITY_MEDIUM,
    TRAP_TYPE_DATA_QUALITY,
    TRAP_TYPE_FII_YIELD,
    TRAP_TYPE_GROWTH_OVERPRICED,
    TRAP_TYPE_HIGH_DY,
    TRAP_TYPE_LEVERAGE,
    TRAP_TYPE_LOW_PB,
    TRAP_TYPE_LOW_PE,
)

# --- Low P/E Trap ------------------------------------------------------


def test_low_pe_alone_is_not_a_trap():
    assert (
        detect_low_pe_trap(pe_ratio=Decimal("6"), net_income_cagr=None, margin_trend=None) is None
    )


def test_low_pe_with_declining_earnings_is_a_trap():
    flag = detect_low_pe_trap(
        pe_ratio=Decimal("6"), net_income_cagr=Decimal("-0.10"), margin_trend=None
    )
    assert flag is not None
    assert flag.trap_type == TRAP_TYPE_LOW_PE
    assert flag.severity == TRAP_SEVERITY_MEDIUM
    assert flag.confidence_penalty == Decimal("0.10")


def test_low_pe_with_worsening_margin_is_a_trap():
    flag = detect_low_pe_trap(pe_ratio=Decimal("6"), net_income_cagr=None, margin_trend="piorando")
    assert flag is not None
    assert flag.severity == TRAP_SEVERITY_MEDIUM


def test_low_pe_with_both_signals_is_high_severity():
    flag = detect_low_pe_trap(
        pe_ratio=Decimal("6"), net_income_cagr=Decimal("-0.10"), margin_trend="piorando"
    )
    assert flag is not None
    assert flag.severity == TRAP_SEVERITY_HIGH
    assert flag.confidence_penalty == Decimal("0.20")


def test_pe_above_threshold_never_triggers():
    flag = detect_low_pe_trap(
        pe_ratio=Decimal("20"), net_income_cagr=Decimal("-0.10"), margin_trend="piorando"
    )
    assert flag is None


def test_pe_none_never_triggers():
    assert (
        detect_low_pe_trap(pe_ratio=None, net_income_cagr=Decimal("-0.10"), margin_trend=None)
        is None
    )


# --- Low P/B Trap --------------------------------------------------------


def test_low_pb_alone_is_not_a_trap():
    assert detect_low_pb_trap(pb_ratio=Decimal("0.8"), roe=None) is None
    assert detect_low_pb_trap(pb_ratio=Decimal("0.8"), roe=Decimal("0.20")) is None


def test_low_pb_with_low_roe_is_a_trap():
    flag = detect_low_pb_trap(pb_ratio=Decimal("0.8"), roe=Decimal("0.02"))
    assert flag is not None
    assert flag.trap_type == TRAP_TYPE_LOW_PB
    assert flag.severity == TRAP_SEVERITY_MEDIUM


def test_low_pb_with_negative_roe_is_high_severity():
    flag = detect_low_pb_trap(pb_ratio=Decimal("0.8"), roe=Decimal("-0.05"))
    assert flag is not None
    assert flag.severity == TRAP_SEVERITY_HIGH


def test_pb_above_threshold_never_triggers():
    assert detect_low_pb_trap(pb_ratio=Decimal("2.0"), roe=Decimal("-0.05")) is None


# --- Growth Overpriced Trap ---------------------------------------------


def test_growth_gap_below_threshold_is_not_a_trap():
    flag = detect_growth_overpriced_trap(
        implied_growth_rate=Decimal("0.10"),
        historical_growth_rate=Decimal("0.08"),
        growth_source="FCF",
    )
    assert flag is None


def test_growth_gap_medium_triggers_medium_severity():
    flag = detect_growth_overpriced_trap(
        implied_growth_rate=Decimal("0.18"),
        historical_growth_rate=Decimal("0.08"),
        growth_source="FCF",
    )
    assert flag is not None
    assert flag.trap_type == TRAP_TYPE_GROWTH_OVERPRICED
    assert flag.severity == TRAP_SEVERITY_MEDIUM


def test_growth_gap_high_triggers_high_severity():
    flag = detect_growth_overpriced_trap(
        implied_growth_rate=Decimal("0.30"),
        historical_growth_rate=Decimal("0.08"),
        growth_source="FCF",
    )
    assert flag is not None
    assert flag.severity == TRAP_SEVERITY_HIGH


def test_growth_trap_none_without_both_rates():
    assert (
        detect_growth_overpriced_trap(
            implied_growth_rate=None, historical_growth_rate=Decimal("0.08"), growth_source="FCF"
        )
        is None
    )
    assert (
        detect_growth_overpriced_trap(
            implied_growth_rate=Decimal("0.30"), historical_growth_rate=None, growth_source=None
        )
        is None
    )


# --- Leverage Trap ---------------------------------------------------


def test_leverage_trap_none_when_both_healthy():
    assert detect_leverage_trap(debt_to_ebitda=Decimal("2"), interest_coverage=Decimal("8")) is None


def test_leverage_trap_high_debt_alone_triggers_medium():
    flag = detect_leverage_trap(debt_to_ebitda=Decimal("5"), interest_coverage=Decimal("8"))
    assert flag is not None
    assert flag.trap_type == TRAP_TYPE_LEVERAGE
    assert flag.severity == TRAP_SEVERITY_MEDIUM


def test_leverage_trap_low_coverage_alone_triggers_medium():
    flag = detect_leverage_trap(debt_to_ebitda=Decimal("2"), interest_coverage=Decimal("1.5"))
    assert flag is not None
    assert flag.severity == TRAP_SEVERITY_MEDIUM


def test_leverage_trap_both_signals_trigger_high():
    flag = detect_leverage_trap(debt_to_ebitda=Decimal("5"), interest_coverage=Decimal("1.5"))
    assert flag is not None
    assert flag.severity == TRAP_SEVERITY_HIGH


def test_leverage_trap_very_high_debt_alone_triggers_high():
    flag = detect_leverage_trap(debt_to_ebitda=Decimal("7"), interest_coverage=Decimal("8"))
    assert flag is not None
    assert flag.severity == TRAP_SEVERITY_HIGH


# --- Data Quality Trap -------------------------------------------------


def test_data_quality_trap_none_with_good_coverage_and_history():
    assert detect_data_quality_trap(coverage_pct=Decimal("0.9"), periods_used=4) is None


def test_data_quality_trap_low_coverage_triggers_medium():
    flag = detect_data_quality_trap(coverage_pct=Decimal("0.45"), periods_used=4)
    assert flag is not None
    assert flag.trap_type == TRAP_TYPE_DATA_QUALITY
    assert flag.severity == TRAP_SEVERITY_MEDIUM


def test_data_quality_trap_very_low_coverage_triggers_high():
    flag = detect_data_quality_trap(coverage_pct=Decimal("0.2"), periods_used=4)
    assert flag is not None
    assert flag.severity == TRAP_SEVERITY_HIGH


def test_data_quality_trap_short_history_triggers():
    flag = detect_data_quality_trap(coverage_pct=Decimal("0.9"), periods_used=1)
    assert flag is not None
    assert flag.severity == TRAP_SEVERITY_MEDIUM


# --- High DY Trap (FIIs/REITs, Sprint 26 Fase 4) -------------------------


def test_high_dy_trap_below_threshold_never_triggers():
    assert detect_high_dy_trap(dividend_yield=Decimal("0.08")) is None


def test_high_dy_trap_none_input_never_triggers():
    assert detect_high_dy_trap(dividend_yield=None) is None


def test_high_dy_trap_at_threshold_triggers_medium():
    flag = detect_high_dy_trap(dividend_yield=Decimal("0.12"))
    assert flag is not None
    assert flag.trap_type == TRAP_TYPE_HIGH_DY
    assert flag.severity == TRAP_SEVERITY_MEDIUM
    assert flag.confidence_penalty == Decimal("0.10")


def test_high_dy_trap_above_medium_below_very_high_is_medium():
    flag = detect_high_dy_trap(dividend_yield=Decimal("0.15"))
    assert flag is not None
    assert flag.severity == TRAP_SEVERITY_MEDIUM


def test_high_dy_trap_at_very_high_threshold_triggers_high():
    flag = detect_high_dy_trap(dividend_yield=Decimal("0.18"))
    assert flag is not None
    assert flag.severity == TRAP_SEVERITY_HIGH
    assert flag.confidence_penalty == Decimal("0.20")


def test_high_dy_trap_well_above_very_high_is_high():
    flag = detect_high_dy_trap(dividend_yield=Decimal("0.25"))
    assert flag is not None
    assert flag.severity == TRAP_SEVERITY_HIGH


# --- FII Yield Trap (FIIs/REITs, Sprint 26 Fase 4) -----------------------


def test_fii_yield_trap_ratio_below_threshold_never_triggers():
    assert (
        detect_fii_yield_trap(
            dividend_yield=Decimal("0.08"), dy_own_history_average=Decimal("0.07")
        )
        is None
    )


def test_fii_yield_trap_none_inputs_never_trigger():
    assert (
        detect_fii_yield_trap(dividend_yield=None, dy_own_history_average=Decimal("0.07")) is None
    )
    assert (
        detect_fii_yield_trap(dividend_yield=Decimal("0.10"), dy_own_history_average=None) is None
    )
    assert (
        detect_fii_yield_trap(dividend_yield=Decimal("0.10"), dy_own_history_average=Decimal("0"))
        is None
    )


def test_fii_yield_trap_at_medium_ratio_triggers_medium():
    flag = detect_fii_yield_trap(
        dividend_yield=Decimal("0.14"), dy_own_history_average=Decimal("0.10")
    )
    assert flag is not None
    assert flag.trap_type == TRAP_TYPE_FII_YIELD
    assert flag.severity == TRAP_SEVERITY_MEDIUM
    assert flag.confidence_penalty == Decimal("0.10")


def test_fii_yield_trap_at_high_ratio_triggers_high():
    flag = detect_fii_yield_trap(
        dividend_yield=Decimal("0.18"), dy_own_history_average=Decimal("0.10")
    )
    assert flag is not None
    assert flag.severity == TRAP_SEVERITY_HIGH
    assert flag.confidence_penalty == Decimal("0.20")
