"""Valuation Engine 2.0 — orquestração pura (Sprint 26, Fase 2).

Combina DCF simplificado (3 cenários), múltiplos normalizados pelo
próprio histórico do ativo e Graham Number (checagem de sanidade) numa
`ValuationV2Result` com faixa de valor justo, margem de segurança
escalada pela qualidade, confiança e avisos. Nunca gera recomendação de
compra/venda. Nunca inventa dado: cada componente ausente vira um motivo
explícito, nunca um valor aproximado (Volume 18 §8).

Escopo desta fase: apenas ações (`asset_class == "stock"`, BR ou US).
FIIs/REITs, ETFs, cripto e renda fixa têm regras próprias em fases
futuras (Sprint 26, Fases 4-5) — aqui, essas classes sempre voltam
`indeterminado` com o motivo de estarem fora de escopo.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.valuation_v2.constants import (
    DCF_PROJECTION_YEARS,
    GRAHAM_DIVERGENCE_WARNING_THRESHOLD,
    GROWTH_RATE_SANE_MAX,
    GROWTH_RATE_SANE_MIN,
    HIGH_DISPERSION_THRESHOLD,
    SCENARIO_DISCOUNT_SPREAD,
    SCENARIO_GROWTH_SPREAD,
    macro_assumptions,
    required_margin_of_safety,
    terminal_growth_cap,
)
from backend.app.engines.valuation_v2.dcf import capm_discount_rate, dcf_fair_value_per_share
from backend.app.engines.valuation_v2.graham import graham_number
from backend.app.engines.valuation_v2.multiples import normalized_multiples_fair_value
from backend.app.engines.valuation_v2.reverse_dcf import implied_growth_rate
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.fundamentals_analysis import FundamentalsAnalysisResult
from backend.app.schemas.valuation_v2 import (
    INSUFFICIENT_DATA_MESSAGE,
    VALUATION_STATUS_FAIR,
    VALUATION_STATUS_INDETERMINATE,
    VALUATION_STATUS_OVERVALUED,
    VALUATION_STATUS_UNDERVALUED,
    FairValueRange,
    ValuationScenario,
    ValuationV2Result,
)

_APPLICABLE_ASSET_CLASSES = ("stock",)


def _average(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def _clamp(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    return max(low, min(high, value))


def _book_value_per_share(
    total_equity: Decimal | None, shares_outstanding: Decimal | None
) -> Decimal | None:
    if total_equity is None or shares_outstanding is None or shares_outstanding <= 0:
        return None
    return total_equity / shares_outstanding


def _growth_assumption(
    analysis: FundamentalsAnalysisResult | None,
) -> tuple[Decimal | None, str | None]:
    """Prioriza CAGR de FCF (mais direto para DCF), depois lucro líquido,
    depois receita — cada um só usado se o anterior estiver indisponível."""
    if analysis is None:
        return None, None
    if analysis.fcf_cagr is not None:
        return analysis.fcf_cagr, "FCF"
    if analysis.net_income_cagr is not None:
        return analysis.net_income_cagr, "lucro líquido"
    if analysis.revenue_cagr is not None:
        return analysis.revenue_cagr, "receita"
    return None, None


class ValuationEngineV2:
    """Estima faixa de valor justo de ações combinando múltiplos métodos."""

    def evaluate(
        self,
        ticker: str,
        asset_class: str,
        currency: str,
        current_price: Decimal | None,
        latest_snapshot: FundamentalSnapshotResult | None,
        history: list[FundamentalSnapshotResult],
        fundamentals_analysis: FundamentalsAnalysisResult | None,
        quality_classification: str | None,
    ) -> ValuationV2Result:
        if asset_class not in _APPLICABLE_ASSET_CLASSES:
            return ValuationV2Result(
                ticker=ticker,
                asset_class=asset_class,
                current_price=current_price,
                valuation_status=VALUATION_STATUS_INDETERMINATE,
                confidence="baixa",
                reason=(
                    f"classe '{asset_class}' fora do escopo desta fase do Valuation "
                    "Engine 2.0 (cobre apenas ações — Sprint 26, Fase 2)"
                ),
            )

        if latest_snapshot is None:
            return ValuationV2Result(
                ticker=ticker,
                asset_class=asset_class,
                current_price=current_price,
                valuation_status=VALUATION_STATUS_INDETERMINATE,
                confidence="baixa",
                reason=INSUFFICIENT_DATA_MESSAGE,
            )

        warnings: list[str] = []
        methodology: list[str] = []
        scenarios: list[ValuationScenario] = []

        fcf0 = latest_snapshot.free_cash_flow
        shares_outstanding = latest_snapshot.shares_outstanding
        net_debt = latest_snapshot.net_debt
        beta = latest_snapshot.beta
        eps = latest_snapshot.eps
        book_value_per_share = _book_value_per_share(
            latest_snapshot.total_equity, shares_outstanding
        )

        macro = macro_assumptions(currency)
        discount_base, beta_was_default = capm_discount_rate(beta, currency)
        if beta_was_default:
            warnings.append(
                "Beta indisponível — usando beta de mercado (1.0) como aproximação padrão."
            )
        discount_pess = discount_base + SCENARIO_DISCOUNT_SPREAD
        discount_opt = max(
            discount_base - SCENARIO_DISCOUNT_SPREAD, macro["risk_free_rate"] + Decimal("0.005")
        )
        t_growth_cap = terminal_growth_cap(currency)

        growth_base, growth_source = _growth_assumption(fundamentals_analysis)

        dcf_available = (
            fcf0 is not None
            and fcf0 > 0
            and shares_outstanding is not None
            and shares_outstanding > 0
            and growth_base is not None
        )

        if dcf_available:
            growth_clamped = _clamp(growth_base, GROWTH_RATE_SANE_MIN, GROWTH_RATE_SANE_MAX)
            if growth_clamped != growth_base:
                warnings.append(
                    f"Crescimento histórico de {growth_source} ({growth_base:.1%}) fora da "
                    f"faixa de sanidade — ajustado para {growth_clamped:.1%} na projeção."
                )
            growth_pess = max(growth_clamped - SCENARIO_GROWTH_SPREAD, t_growth_cap)
            growth_opt = min(growth_clamped + SCENARIO_GROWTH_SPREAD, GROWTH_RATE_SANE_MAX)

            for label, growth, discount in (
                ("DCF pessimista", growth_pess, discount_pess),
                ("DCF base", growth_clamped, discount_base),
                ("DCF otimista", growth_opt, discount_opt),
            ):
                value, dcf_reason = dcf_fair_value_per_share(
                    fcf0=fcf0,
                    growth_rate=growth,
                    discount_rate_value=discount,
                    terminal_growth=t_growth_cap,
                    shares_outstanding=shares_outstanding,
                    net_debt=net_debt,
                )
                assumptions = (
                    f"crescimento assumido {growth:.1%} a.a. ({growth_source}, "
                    f"{DCF_PROJECTION_YEARS} anos), taxa de desconto {discount:.1%}, "
                    f"crescimento terminal {t_growth_cap:.1%}"
                )
                scenarios.append(
                    ValuationScenario(
                        label=label, fair_value=value, assumptions=assumptions, reason=dcf_reason
                    )
                )
            if net_debt is None:
                warnings.append(
                    "Dívida líquida indisponível — DCF considera caixa/dívida neutra "
                    "(pode subestimar o efeito de alavancagem)."
                )
            if any(s.fair_value is not None for s in scenarios):
                methodology.append("dcf")
        else:
            if fcf0 is None or fcf0 <= 0:
                why = "fluxo de caixa livre indisponível ou não positivo"
            elif shares_outstanding is None or shares_outstanding <= 0:
                why = "quantidade de ações em circulação indisponível"
            else:
                why = "histórico insuficiente para estimar taxa de crescimento (CAGR)"
            scenarios.append(
                ValuationScenario(
                    label="DCF", fair_value=None, assumptions="não aplicado", reason=why
                )
            )

        multiples_value, multiples_reason = normalized_multiples_fair_value(
            history, eps, book_value_per_share
        )
        scenarios.append(
            ValuationScenario(
                label="Múltiplos (histórico próprio)",
                fair_value=multiples_value,
                assumptions=(
                    "média histórica de P/L e/ou P/VP do próprio ativo aplicada ao "
                    "EPS/valor patrimonial por ação mais recente"
                ),
                reason=multiples_reason,
            )
        )
        if multiples_value is not None:
            methodology.append("multiplos")

        graham_value, graham_reason = graham_number(eps, book_value_per_share)

        dcf_values = [
            s.fair_value
            for s in scenarios
            if s.label.startswith("DCF") and s.fair_value is not None
        ]
        dcf_base_value = next(
            (s.fair_value for s in scenarios if s.label == "DCF base" and s.fair_value is not None),
            None,
        )

        low_candidates: list[Decimal] = []
        high_candidates: list[Decimal] = []
        base_candidates: list[Decimal] = []
        if dcf_values:
            low_candidates.append(min(dcf_values))
            high_candidates.append(max(dcf_values))
        if dcf_base_value is not None:
            base_candidates.append(dcf_base_value)
        if multiples_value is not None:
            low_candidates.append(multiples_value)
            high_candidates.append(multiples_value)
            base_candidates.append(multiples_value)

        fair_value_range = FairValueRange(
            low=min(low_candidates) if low_candidates else None,
            base=_average(base_candidates) if base_candidates else None,
            high=max(high_candidates) if high_candidates else None,
        )

        if fair_value_range.base is None:
            return ValuationV2Result(
                ticker=ticker,
                asset_class=asset_class,
                current_price=current_price,
                valuation_status=VALUATION_STATUS_INDETERMINATE,
                fair_value_range=fair_value_range,
                scenarios=scenarios,
                graham_sanity_check=graham_value,
                graham_reason=graham_reason,
                confidence="baixa",
                warnings=warnings,
                methodology=methodology,
                reason=INSUFFICIENT_DATA_MESSAGE,
            )

        if graham_value is not None and fair_value_range.base > 0:
            divergence = abs(graham_value - fair_value_range.base) / fair_value_range.base
            if divergence > GRAHAM_DIVERGENCE_WARNING_THRESHOLD:
                warnings.append(
                    f"Graham Number (checagem de sanidade) diverge {divergence:.0%} da "
                    "estimativa combinada — vale investigar o contexto (ex.: lucro ou "
                    "valor patrimonial distorcidos por evento não recorrente)."
                )

        dispersion = None
        if (
            fair_value_range.low is not None
            and fair_value_range.high is not None
            and fair_value_range.base > 0
        ):
            dispersion = (fair_value_range.high - fair_value_range.low) / fair_value_range.base
            if dispersion > HIGH_DISPERSION_THRESHOLD:
                warnings.append(
                    f"Dispersão alta entre métodos de valuation ({dispersion:.0%} da "
                    "faixa em relação ao valor base) — confiança reduzida."
                )

        methods_count = len(set(methodology))
        periods_used = fundamentals_analysis.periods_used if fundamentals_analysis else 0
        if (
            methods_count >= 2
            and (dispersion is None or dispersion <= HIGH_DISPERSION_THRESHOLD)
            and periods_used >= 3
        ):
            confidence = "alta"
        elif methods_count >= 1:
            confidence = "média"
        else:
            confidence = "baixa"

        req_margin = required_margin_of_safety(quality_classification)
        if quality_classification is None or quality_classification == "indeterminado":
            warnings.append(
                "Qualidade do ativo indeterminada — margem de segurança conservadora aplicada."
            )

        margin_of_safety: Decimal | None = None
        if current_price is not None and current_price > 0:
            margin_of_safety = (fair_value_range.base - current_price) / fair_value_range.base
            if margin_of_safety >= req_margin:
                status = VALUATION_STATUS_UNDERVALUED
            elif margin_of_safety <= -req_margin:
                status = VALUATION_STATUS_OVERVALUED
            else:
                status = VALUATION_STATUS_FAIR
            reason_final = None
        else:
            status = VALUATION_STATUS_INDETERMINATE
            warnings.append(
                "Preço atual indisponível — não é possível calcular a margem de segurança."
            )
            reason_final = "preço atual indisponível para comparação com a faixa de valor justo"

        implied_expectation = None
        implied_growth_rate_value = None
        if dcf_available and current_price is not None and current_price > 0:
            implied_g, reverse_reason = implied_growth_rate(
                current_price=current_price,
                fcf0=fcf0,
                discount_rate_value=discount_base,
                terminal_growth=t_growth_cap,
                shares_outstanding=shares_outstanding,
                net_debt=net_debt,
                years=DCF_PROJECTION_YEARS,
                growth_low=GROWTH_RATE_SANE_MIN,
                growth_high=GROWTH_RATE_SANE_MAX,
            )
            if implied_g is not None:
                implied_growth_rate_value = implied_g
                implied_expectation = (
                    f"O preço atual embute uma expectativa de crescimento de fluxo de "
                    f"caixa de aproximadamente {implied_g:.1%} ao ano nos próximos "
                    f"{DCF_PROJECTION_YEARS} anos (taxa de desconto de {discount_base:.1%})."
                )
            elif reverse_reason:
                warnings.append(f"Reverse DCF: {reverse_reason}")

        return ValuationV2Result(
            ticker=ticker,
            asset_class=asset_class,
            current_price=current_price,
            valuation_status=status,
            fair_value_range=fair_value_range,
            scenarios=scenarios,
            margin_of_safety=margin_of_safety,
            required_margin_of_safety=req_margin,
            graham_sanity_check=graham_value,
            graham_reason=graham_reason,
            implied_expectation=implied_expectation,
            implied_growth_rate=implied_growth_rate_value,
            confidence=confidence,
            warnings=warnings,
            methodology=methodology,
            reason=reason_final,
        )
