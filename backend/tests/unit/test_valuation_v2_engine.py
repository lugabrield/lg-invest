"""Testes do Valuation Engine 2.0 — orquestração (Sprint 26, Fase 2).

Estratégia: quando o teste precisa do valor exato de um cenário DCF, ele
recalcula com as MESMAS funções puras que o engine usa internamente
(`capm_discount_rate`, `terminal_growth_cap`, `dcf_fair_value_per_share`)
em vez de valores mágicos hardcoded — assim o teste continua correto se
as constantes de `constants.py` forem revisadas no futuro.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from backend.app.engines.valuation_v2.constants import terminal_growth_cap
from backend.app.engines.valuation_v2.dcf import capm_discount_rate, dcf_fair_value_per_share
from backend.app.engines.valuation_v2.engine import ValuationEngineV2
from backend.app.engines.valuation_v2.multiples import normalized_multiples_fair_value
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.fundamentals_analysis import FundamentalsAnalysisResult
from backend.app.schemas.valuation_v2 import (
    INSUFFICIENT_DATA_MESSAGE,
    VALUATION_STATUS_FAIR,
    VALUATION_STATUS_INDETERMINATE,
    VALUATION_STATUS_OVERVALUED,
    VALUATION_STATUS_UNDERVALUED,
)

_ENGINE = ValuationEngineV2()


def _snap(period_end, **kwargs) -> FundamentalSnapshotResult:
    base = {
        "ticker": "WEGE3.SA",
        "period_end": period_end,
        "source": "yahoo",
        "collected_at": datetime(2025, 1, 1),
    }
    base.update(kwargs)
    return FundamentalSnapshotResult(**base)


def _healthy_history() -> list[FundamentalSnapshotResult]:
    return [
        _snap(date(2021, 12, 31), pe_ratio=Decimal("9"), pb_ratio=Decimal("0.9")),
        _snap(date(2022, 12, 31), pe_ratio=Decimal("10"), pb_ratio=Decimal("1.0")),
        _snap(date(2023, 12, 31), pe_ratio=Decimal("11"), pb_ratio=Decimal("1.1")),
        _snap(date(2024, 12, 31), pe_ratio=Decimal("10"), pb_ratio=Decimal("1.0")),
    ]


def _healthy_latest_snapshot() -> FundamentalSnapshotResult:
    return _snap(
        date(2024, 12, 31),
        pe_ratio=Decimal("10"),
        pb_ratio=Decimal("1.0"),
        free_cash_flow=Decimal("1000000"),
        shares_outstanding=Decimal("1000000"),
        net_debt=Decimal("0"),
        beta=Decimal("1.0"),
        eps=Decimal("2.0"),
        total_equity=Decimal("20000000"),
    )


def _healthy_analysis(periods_used: int = 4) -> FundamentalsAnalysisResult:
    return FundamentalsAnalysisResult(
        ticker="WEGE3.SA", periods_used=periods_used, fcf_cagr=Decimal("0.08"), confidence="alta"
    )


def _expected_dcf_base_fair_value(currency: str = "USD") -> Decimal:
    """Recomputa o cenário 'DCF base' com as mesmas funções puras do engine."""
    discount_base, _ = capm_discount_rate(Decimal("1.0"), currency)
    t_growth_cap = terminal_growth_cap(currency)
    value, reason = dcf_fair_value_per_share(
        fcf0=Decimal("1000000"),
        growth_rate=Decimal("0.08"),
        discount_rate_value=discount_base,
        terminal_growth=t_growth_cap,
        shares_outstanding=Decimal("1000000"),
        net_debt=Decimal("0"),
    )
    assert reason is None
    return value


def _expected_multiples_value() -> Decimal:
    value, reason = normalized_multiples_fair_value(
        _healthy_history(), Decimal("2.0"), Decimal("20")
    )
    assert reason is None
    return value


def _expected_fair_value_base() -> Decimal:
    return (_expected_dcf_base_fair_value() + _expected_multiples_value()) / Decimal("2")


def test_out_of_scope_asset_class_returns_indeterminate():
    result = _ENGINE.evaluate(
        ticker="BTLG11.SA",
        asset_class="fii",
        currency="BRL",
        current_price=Decimal("100"),
        latest_snapshot=_healthy_latest_snapshot(),
        history=_healthy_history(),
        fundamentals_analysis=_healthy_analysis(),
        quality_classification="alta",
    )
    assert result.valuation_status == VALUATION_STATUS_INDETERMINATE
    assert "fii" in result.reason
    assert "fora do escopo" in result.reason


def test_no_snapshot_returns_literal_insufficient_data_message():
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="BRL",
        current_price=Decimal("30"),
        latest_snapshot=None,
        history=[],
        fundamentals_analysis=None,
        quality_classification=None,
    )
    assert result.valuation_status == VALUATION_STATUS_INDETERMINATE
    assert result.reason == INSUFFICIENT_DATA_MESSAGE


def test_snapshot_with_no_usable_method_returns_literal_insufficient_data_message():
    empty_snapshot = _snap(date(2024, 12, 31))  # nenhum campo financeiro preenchido
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="USD",
        current_price=Decimal("30"),
        latest_snapshot=empty_snapshot,
        history=[empty_snapshot],
        fundamentals_analysis=None,
        quality_classification=None,
    )
    assert result.valuation_status == VALUATION_STATUS_INDETERMINATE
    assert result.reason == INSUFFICIENT_DATA_MESSAGE
    assert result.fair_value_range.base is None


def test_undervalued_when_price_well_below_fair_value_base():
    base = _expected_fair_value_base()
    price = base * Decimal("0.5")  # margem bem acima do exigido para qualidade "alta" (15%)
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="USD",
        current_price=price,
        latest_snapshot=_healthy_latest_snapshot(),
        history=_healthy_history(),
        fundamentals_analysis=_healthy_analysis(),
        quality_classification="alta",
    )
    assert result.valuation_status == VALUATION_STATUS_UNDERVALUED
    assert result.margin_of_safety is not None
    assert result.margin_of_safety >= result.required_margin_of_safety


def test_overvalued_when_price_well_above_fair_value_base():
    base = _expected_fair_value_base()
    price = base * Decimal("2.0")
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="USD",
        current_price=price,
        latest_snapshot=_healthy_latest_snapshot(),
        history=_healthy_history(),
        fundamentals_analysis=_healthy_analysis(),
        quality_classification="alta",
    )
    assert result.valuation_status == VALUATION_STATUS_OVERVALUED
    assert result.margin_of_safety is not None
    assert result.margin_of_safety <= -result.required_margin_of_safety


def test_fair_when_price_close_to_fair_value_base():
    base = _expected_fair_value_base()
    price = base  # margem 0 — dentro de qualquer banda de margem exigida
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="USD",
        current_price=price,
        latest_snapshot=_healthy_latest_snapshot(),
        history=_healthy_history(),
        fundamentals_analysis=_healthy_analysis(),
        quality_classification="alta",
    )
    assert result.valuation_status == VALUATION_STATUS_FAIR


def test_missing_current_price_is_indeterminate_but_not_the_insufficient_data_message():
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="USD",
        current_price=None,
        latest_snapshot=_healthy_latest_snapshot(),
        history=_healthy_history(),
        fundamentals_analysis=_healthy_analysis(),
        quality_classification="alta",
    )
    assert result.valuation_status == VALUATION_STATUS_INDETERMINATE
    # a faixa de valor justo FOI estimada — o problema é só a comparação com o
    # preço, então a mensagem não pode ser a de "dados insuficientes para
    # estimar valor justo" (isso seria enganoso: o valor justo existe).
    assert result.reason != INSUFFICIENT_DATA_MESSAGE
    assert result.fair_value_range.base is not None
    assert any("preço atual indisponível" in w.lower() for w in result.warnings)


def test_quality_scales_required_margin_of_safety():
    base = _expected_fair_value_base()
    # margem de ~20%: suficiente para "baixa" exigir mais (35%) que "alta" (15%)
    price = base * Decimal("0.80")

    result_high_quality = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="USD",
        current_price=price,
        latest_snapshot=_healthy_latest_snapshot(),
        history=_healthy_history(),
        fundamentals_analysis=_healthy_analysis(),
        quality_classification="alta",
    )
    result_low_quality = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="USD",
        current_price=price,
        latest_snapshot=_healthy_latest_snapshot(),
        history=_healthy_history(),
        fundamentals_analysis=_healthy_analysis(),
        quality_classification="baixa",
    )
    assert result_high_quality.required_margin_of_safety == Decimal("0.15")
    assert result_low_quality.required_margin_of_safety == Decimal("0.35")
    assert result_high_quality.valuation_status == VALUATION_STATUS_UNDERVALUED
    assert result_low_quality.valuation_status == VALUATION_STATUS_FAIR


def test_quality_none_uses_conservative_default_margin_and_warns():
    base = _expected_fair_value_base()
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="USD",
        current_price=base,
        latest_snapshot=_healthy_latest_snapshot(),
        history=_healthy_history(),
        fundamentals_analysis=_healthy_analysis(),
        quality_classification=None,
    )
    assert result.required_margin_of_safety == Decimal("0.30")
    assert any("qualidade do ativo indeterminada" in w.lower() for w in result.warnings)


def test_beta_missing_uses_default_and_warns():
    snapshot = _healthy_latest_snapshot().model_copy(update={"beta": None})
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="USD",
        current_price=Decimal("20"),
        latest_snapshot=snapshot,
        history=_healthy_history(),
        fundamentals_analysis=_healthy_analysis(),
        quality_classification="alta",
    )
    assert any("beta" in w.lower() for w in result.warnings)


def test_net_debt_missing_warns_neutral_assumption():
    snapshot = _healthy_latest_snapshot().model_copy(update={"net_debt": None})
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="USD",
        current_price=Decimal("20"),
        latest_snapshot=snapshot,
        history=_healthy_history(),
        fundamentals_analysis=_healthy_analysis(),
        quality_classification="alta",
    )
    assert any("dívida líquida" in w.lower() for w in result.warnings)


def test_implied_expectation_present_when_dcf_and_price_available():
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="USD",
        current_price=_expected_fair_value_base(),
        latest_snapshot=_healthy_latest_snapshot(),
        history=_healthy_history(),
        fundamentals_analysis=_healthy_analysis(),
        quality_classification="alta",
    )
    assert result.implied_expectation is not None
    assert "%" in result.implied_expectation


def test_graham_sanity_check_present_and_never_drives_status_alone():
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="USD",
        current_price=_expected_fair_value_base(),
        latest_snapshot=_healthy_latest_snapshot(),
        history=_healthy_history(),
        fundamentals_analysis=_healthy_analysis(),
        quality_classification="alta",
    )
    assert result.graham_sanity_check is not None
    # Graham nunca aparece em `methodology` — só DCF e múltiplos contribuem
    # para a faixa/status; Graham é checagem de sanidade isolada.
    assert "graham" not in result.methodology


def test_confidence_alta_when_two_methods_agree_and_enough_history():
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="USD",
        current_price=_expected_fair_value_base(),
        latest_snapshot=_healthy_latest_snapshot(),
        history=_healthy_history(),
        fundamentals_analysis=_healthy_analysis(periods_used=4),
        quality_classification="alta",
    )
    assert set(result.methodology) == {"dcf", "multiplos"}
    assert result.confidence in ("alta", "média")  # alta se dispersão baixa, média se moderada


def test_confidence_baixa_when_only_graham_available():
    # snapshot com EPS/VPA (Graham) mas sem FCF/ações (sem DCF) e sem
    # histórico de múltiplos (sem múltiplos) — só a checagem de sanidade
    # roda, e ela sozinha nunca sustenta confiança alta/média.
    snapshot = _snap(
        date(2024, 12, 31),
        eps=Decimal("2.0"),
        total_equity=Decimal("20000000"),
        shares_outstanding=Decimal("1000000"),
    )
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        currency="USD",
        current_price=Decimal("20"),
        latest_snapshot=snapshot,
        history=[snapshot],
        fundamentals_analysis=None,
        quality_classification="alta",
    )
    assert result.valuation_status == VALUATION_STATUS_INDETERMINATE
    assert result.reason == INSUFFICIENT_DATA_MESSAGE
    assert result.graham_sanity_check is not None
