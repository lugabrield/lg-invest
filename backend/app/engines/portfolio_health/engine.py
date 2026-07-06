"""Portfolio Health Score (Sprint 24, Fase 8) — o "capstone" que resume,
num único score (0..100, maior = mais saudável), 5 sinais já produzidos
por outras engines/serviços da plataforma:

1. Diversificação (Portfolio Engine — número efetivo de ativos).
2. Alinhamento de risco (Portfolio Risk Engine, Fase 6 — risco medido vs.
   tolerância declarada na Investment Policy, Fase 3).
3. Aderência à alocação-alvo (Target Allocation Rule Engine v2, Fase 3 —
   quantas dimensões estão dentro da meta vs. acima/bloqueadas).
4. Tendência de renda (Income Engine, Fase 7 — crescimento de proventos).
5. Confiança dos dados (Data Quality Layer, Sprint 21 — quão automático/
   completo é o dado usado pela plataforma).

Cada pilar é opcional: se o sinal de origem não estiver disponível (ex.:
nenhuma regra de alocação-alvo configurada, sem histórico de renda), o
pilar fica `available=False`, documentado em `warnings`, e os pesos dos
pilares restantes são renormalizados entre si — nunca inventa o pilar
ausente (mesmo padrão já usado no Portfolio Risk Engine, Fase 6).

Este é um relatório informativo — assim como as demais engines de
análise, nunca sugere uma ação de compra/venda.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.app.engines.portfolio_health import thresholds as t
from backend.app.engines.portfolio_health.inputs import (
    DEFAULT_CONFIG,
    PortfolioHealthConfig,
    PortfolioHealthInput,
)

MODEL_VERSION = "portfolio_health_v1"
_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


@dataclass
class HealthFactor:
    name: str
    available: bool
    raw_value: Decimal | None
    score: Decimal | None  # 0..100, maior = mais saudável
    weight_used: Decimal
    reason: str


@dataclass
class PortfolioHealthResult:
    model_version: str
    overall_score: Decimal
    overall_classification: str  # uma das HEALTH_LABELS
    factors: list[HealthFactor]
    reasons: list[str]
    warnings: list[str]


def _diversification_factor(data: PortfolioHealthInput) -> HealthFactor:
    n_eff = data.effective_number_of_assets
    if n_eff is None:
        return HealthFactor(
            name="diversificação",
            available=False,
            raw_value=None,
            score=None,
            weight_used=_ZERO,
            reason="número efetivo de ativos indisponível (carteira sem posições precificadas)",
        )
    high_n = t.DIVERSIFICATION_HIGH_N
    score = min(_HUNDRED, max(_ZERO, (n_eff - 1) / (high_n - 1) * _HUNDRED))
    return HealthFactor(
        name="diversificação",
        available=True,
        raw_value=n_eff,
        score=score,
        weight_used=_ZERO,
        reason=f"número efetivo de ativos: {float(n_eff):.1f} (saúde máxima a partir de {high_n}).",
    )


def _risk_alignment_factor(data: PortfolioHealthInput) -> HealthFactor:
    computed = data.risk_overall_classification
    declared = data.declared_risk_tolerance
    if (
        computed is None
        or declared is None
        or computed not in t.RISK_TOLERANCE_ORDER
        or declared not in t.RISK_TOLERANCE_ORDER
    ):
        return HealthFactor(
            name="alinhamento_de_risco",
            available=False,
            raw_value=None,
            score=None,
            weight_used=_ZERO,
            reason=(
                "risco medido ou tolerância declarada indisponível (rode o Portfolio Risk "
                "Engine e configure a Investment Policy)"
            ),
        )
    bands_above = max(
        0, t.RISK_TOLERANCE_ORDER.index(computed) - t.RISK_TOLERANCE_ORDER.index(declared)
    )
    score = max(_ZERO, _HUNDRED - Decimal(bands_above) * t.RISK_ALIGNMENT_PENALTY_PER_BAND)
    reason = (
        f"risco medido '{computed}' vs. tolerância declarada '{declared}' "
        f"({bands_above} faixa(s) acima)."
    )
    return HealthFactor(
        name="alinhamento_de_risco",
        available=True,
        raw_value=Decimal(bands_above),
        score=score,
        weight_used=_ZERO,
        reason=reason,
    )


def _allocation_alignment_factor(data: PortfolioHealthInput) -> HealthFactor:
    alignment = data.allocation_alignment
    if alignment is None or not alignment.has_rules or alignment.total_evaluations <= 0:
        return HealthFactor(
            name="aderência_alocação_alvo",
            available=False,
            raw_value=None,
            score=None,
            weight_used=_ZERO,
            reason="nenhuma regra de alocação-alvo configurada (Target Allocation Rule Engine v2)",
        )
    score = (
        Decimal(alignment.aligned_evaluations) / Decimal(alignment.total_evaluations)
    ) * _HUNDRED
    return HealthFactor(
        name="aderência_alocação_alvo",
        available=True,
        raw_value=score / _HUNDRED,
        score=score,
        weight_used=_ZERO,
        reason=(
            f"{alignment.aligned_evaluations} de {alignment.total_evaluations} dimensão(ões) "
            "dentro da meta de alocação (neutra ou underweight)."
        ),
    )


def _income_trend_factor(data: PortfolioHealthInput) -> HealthFactor:
    growth = data.income_growth_pct
    if growth is None:
        return HealthFactor(
            name="tendência_de_renda",
            available=False,
            raw_value=None,
            score=None,
            weight_used=_ZERO,
            reason="sem crescimento de renda calculável (histórico insuficiente no Income Engine)",
        )
    strong, severe = t.INCOME_GROWTH_STRONG, t.INCOME_GROWTH_DECLINE_SEVERE
    if growth >= strong:
        score = _HUNDRED
    elif growth <= severe:
        score = _ZERO
    else:
        score = (growth - severe) / (strong - severe) * _HUNDRED
    return HealthFactor(
        name="tendência_de_renda",
        available=True,
        raw_value=growth,
        score=score,
        weight_used=_ZERO,
        reason=f"crescimento de renda (TTM vs. período anterior): {growth * 100:.1f}%.",
    )


def _data_confidence_factor(data: PortfolioHealthInput) -> HealthFactor:
    pct = data.data_confidence_pct
    if pct is None:
        return HealthFactor(
            name="confiança_dos_dados",
            available=False,
            raw_value=None,
            score=None,
            weight_used=_ZERO,
            reason="resumo de qualidade de dado indisponível (Data Quality Layer)",
        )
    score = min(_HUNDRED, max(_ZERO, pct * _HUNDRED))
    return HealthFactor(
        name="confiança_dos_dados",
        available=True,
        raw_value=pct,
        score=score,
        weight_used=_ZERO,
        reason=f"{pct * 100:.1f}% do patrimônio com dado de qualidade (preço/fundamentos/valuation).",
    )


def evaluate_portfolio_health(
    data: PortfolioHealthInput,
    config: PortfolioHealthConfig = DEFAULT_CONFIG,
) -> PortfolioHealthResult:
    """Combina os 5 pilares em um score composto (pura, sem banco/rede)."""
    warnings: list[str] = []

    raw_factors = [
        (_diversification_factor(data), config.weight_diversification),
        (_risk_alignment_factor(data), config.weight_risk_alignment),
        (_allocation_alignment_factor(data), config.weight_allocation_alignment),
        (_income_trend_factor(data), config.weight_income_trend),
        (_data_confidence_factor(data), config.weight_data_confidence),
    ]

    available_weight_total = sum(w for factor, w in raw_factors if factor.available)
    factors: list[HealthFactor] = []
    composite_score = _ZERO
    reasons: list[str] = []

    for factor, weight in raw_factors:
        if not factor.available:
            warnings.append(f"pilar '{factor.name}' indisponível: {factor.reason}")
            factors.append(factor)
            continue
        effective_weight = (
            (weight / available_weight_total) if available_weight_total > 0 else _ZERO
        )
        factor.weight_used = effective_weight
        composite_score += effective_weight * factor.score
        reasons.append(factor.reason)
        factors.append(factor)

    if available_weight_total <= 0:
        overall_classification = "indeterminado"
        reasons.append("nenhum pilar pôde ser calculado — sem dado suficiente na carteira.")
    else:
        overall_classification = t.classify_health_score(composite_score)
        reasons.append(
            "score composto combina os pilares disponíveis com pesos renormalizados entre "
            "si — nunca inventa um pilar ausente. Relatório informativo, não é recomendação "
            "de compra ou venda."
        )

    return PortfolioHealthResult(
        model_version=MODEL_VERSION,
        overall_score=Decimal(str(round(float(composite_score), 2))),
        overall_classification=overall_classification,
        factors=factors,
        reasons=reasons,
        warnings=warnings,
    )
