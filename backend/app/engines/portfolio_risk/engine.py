"""Portfolio Risk Engine (Sprint 24, Fase 6 — "Risk Engine 2.0").

Agrega 4 fatores de risco independentes em um score composto (0..100,
maior = mais arriscado), classificado nas mesmas 4 faixas de
`RISK_TOLERANCES` da Investment Policy (Fase 3) — permitindo comparar
diretamente o risco medido da carteira com a tolerância declarada pelo
usuário.

Os 4 fatores:
1. Volatilidade ponderada da carteira (mesmas premissas do Monte Carlo
   Simulation Engine, Fase 5) — risco de mercado.
2. Concentração (HHI, já calculado pelo Portfolio Engine) — risco de
   concentração.
3. Risco estrutural por classe (reaproveita as classificações do Risk
   Engine v1 por ativo, Sprint 16 — nunca recalcula indicadores
   fundamentalistas aqui).
4. Risco de cauda (probabilidade de perda do Monte Carlo, Fase 5,
   opcional — se nenhuma simulação foi rodada, este fator fica
   "indisponível" e os pesos dos outros 3 são renormalizados).

Nenhum fator ausente é inventado: se não há dado suficiente para
calculá-lo, ele é marcado `available=False`, os pesos dos fatores
restantes são renormalizados (nunca silenciosamente ignorado sem
registro), e isso fica em `warnings`.

Este é um relatório informativo, não uma recomendação de compra/venda —
se o risco medido divergir da tolerância declarada, a engine apenas
sinaliza isso em `tolerance_alert`, nunca sugere uma ação.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.app.engines.portfolio_risk import thresholds as t
from backend.app.engines.portfolio_risk.inputs import (
    DEFAULT_CONFIG,
    PortfolioRiskConfig,
    PortfolioRiskInput,
)

MODEL_VERSION = "portfolio_risk_v1"

_RISK_TOLERANCE_ORDER = ("baixo", "moderado", "moderado-alto", "alto")
_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


@dataclass
class RiskFactor:
    name: str
    available: bool
    raw_value: Decimal | None  # valor bruto do fator (volatilidade, HHI, etc.)
    score: Decimal | None  # 0..100, maior = mais arriscado
    classification: str | None  # "baixo" | "médio" | "alto"
    weight_used: Decimal  # peso efetivamente usado no composto (já renormalizado)
    reason: str


@dataclass
class PortfolioRiskResult:
    model_version: str
    overall_score: Decimal  # 0..100
    overall_classification: str  # uma das RISK_TOLERANCES
    factors: list[RiskFactor]
    declared_risk_tolerance: str | None
    tolerance_alert: str | None
    reasons: list[str]
    warnings: list[str]


def _volatility_factor(data: PortfolioRiskInput) -> RiskFactor:
    known_weight = _ZERO
    weighted_vol = _ZERO
    missing_classes: list[str] = []
    for asset_class, weight in data.class_weights.items():
        if weight <= 0:
            continue
        vol = data.class_volatilities.get(asset_class)
        if vol is None:
            missing_classes.append(asset_class)
            continue
        known_weight += weight
        weighted_vol += weight * vol

    if known_weight <= 0:
        return RiskFactor(
            name="volatilidade",
            available=False,
            raw_value=None,
            score=None,
            classification=None,
            weight_used=_ZERO,
            reason="nenhuma classe da carteira tem volatilidade configurada",
        )

    portfolio_vol = weighted_vol / known_weight
    score = min(_HUNDRED, (portfolio_vol / t.VOLATILITY_HIGH) * _HUNDRED)
    classification = t.classify_by_bands(portfolio_vol, t.VOLATILITY_LOW, t.VOLATILITY_HIGH)
    reason = (
        f"volatilidade anual ponderada da carteira: {portfolio_vol * 100:.1f}% "
        f"(classificação '{classification}')"
    )
    if missing_classes:
        reason += (
            f" — calculada só com as classes com premissa configurada "
            f"(sem dado para {sorted(missing_classes)}, peso desconsiderado)"
        )
    return RiskFactor(
        name="volatilidade",
        available=True,
        raw_value=portfolio_vol,
        score=score,
        classification=classification,
        weight_used=_ZERO,  # preenchido depois da renormalização
        reason=reason,
    )


def _concentration_factor(data: PortfolioRiskInput) -> RiskFactor:
    hhi = data.concentration_hhi
    score = min(_HUNDRED, (hhi / t.HHI_HIGH) * _HUNDRED)
    classification = t.classify_by_bands(hhi, t.HHI_LOW, t.HHI_HIGH)
    n_eff = (
        f", nº efetivo de ativos {float(data.effective_number_of_assets):.1f}"
        if data.effective_number_of_assets is not None
        else ""
    )
    return RiskFactor(
        name="concentração",
        available=True,
        raw_value=hhi,
        score=score,
        classification=classification,
        weight_used=_ZERO,
        reason=f"HHI da carteira: {hhi:.3f}{n_eff} (classificação '{classification}')",
    )


def _asset_class_risk_factor(data: PortfolioRiskInput) -> RiskFactor:
    known_weight = _ZERO
    weighted_score = _ZERO
    excluded_weight = _ZERO
    for signal in data.asset_risk_signals:
        points = t.ASSET_CLASS_RISK_SCORE.get(signal.classification)
        if points is None:
            excluded_weight += signal.weight
            continue
        known_weight += signal.weight
        weighted_score += signal.weight * points

    if known_weight <= 0:
        return RiskFactor(
            name="risco_estrutural_por_ativo",
            available=False,
            raw_value=None,
            score=None,
            classification=None,
            weight_used=_ZERO,
            reason="nenhum ativo da carteira tem classificação de risco (Risk Engine v1) disponível",
        )

    avg_points = weighted_score / known_weight  # escala 1..3
    score = min(_HUNDRED, max(_ZERO, ((avg_points - 1) / 2) * _HUNDRED))
    classification = t.classify_by_bands(
        avg_points, t.ASSET_CLASS_RISK_LOW, t.ASSET_CLASS_RISK_HIGH
    )
    reason = (
        f"risco estrutural médio ponderado dos ativos (Risk Engine v1): "
        f"{avg_points:.2f} em escala 1 (baixo) a 3 (alto) (classificação '{classification}')"
    )
    if excluded_weight > 0:
        reason += (
            f" — {excluded_weight * 100:.1f}% do patrimônio ficou de fora por não ter "
            "classificação de risco disponível (indeterminado)"
        )
    return RiskFactor(
        name="risco_estrutural_por_ativo",
        available=True,
        raw_value=avg_points,
        score=score,
        classification=classification,
        weight_used=_ZERO,
        reason=reason,
    )


def _drawdown_factor(data: PortfolioRiskInput) -> RiskFactor:
    if data.probability_of_loss is None:
        return RiskFactor(
            name="risco_de_cauda",
            available=False,
            raw_value=None,
            score=None,
            classification=None,
            weight_used=_ZERO,
            reason=(
                "nenhuma simulação Monte Carlo foi informada — rode uma simulação "
                "(Fase 5) para incluir risco de cauda no score composto"
            ),
        )
    prob = data.probability_of_loss
    score = min(_HUNDRED, (prob / t.DRAWDOWN_HIGH) * _HUNDRED)
    classification = t.classify_by_bands(prob, t.DRAWDOWN_LOW, t.DRAWDOWN_HIGH)
    return RiskFactor(
        name="risco_de_cauda",
        available=True,
        raw_value=prob,
        score=score,
        classification=classification,
        weight_used=_ZERO,
        reason=(
            f"probabilidade simulada de terminar abaixo do total aportado: "
            f"{prob * 100:.1f}% (classificação '{classification}')"
        ),
    )


def _tolerance_alert(declared: str | None, computed: str) -> str | None:
    if declared is None or declared not in _RISK_TOLERANCE_ORDER:
        return None
    if computed not in _RISK_TOLERANCE_ORDER:
        return None
    declared_idx = _RISK_TOLERANCE_ORDER.index(declared)
    computed_idx = _RISK_TOLERANCE_ORDER.index(computed)
    if computed_idx > declared_idx:
        return (
            f"o risco medido da carteira ('{computed}') está acima da sua tolerância "
            f"declarada ('{declared}') — isto é apenas informativo, não é uma "
            "recomendação de compra ou venda."
        )
    if computed_idx < declared_idx:
        return (
            f"o risco medido da carteira ('{computed}') está abaixo da sua tolerância "
            f"declarada ('{declared}') — sua carteira está mais conservadora do que "
            "você declarou tolerar."
        )
    return None


def evaluate_portfolio_risk(
    data: PortfolioRiskInput,
    config: PortfolioRiskConfig = DEFAULT_CONFIG,
) -> PortfolioRiskResult:
    """Agrega os 4 fatores de risco em um score composto (pura, sem banco/rede)."""
    reasons: list[str] = []
    warnings: list[str] = []

    raw_factors = [
        (_volatility_factor(data), config.weight_volatility),
        (_concentration_factor(data), config.weight_concentration),
        (_asset_class_risk_factor(data), config.weight_asset_class_risk),
        (_drawdown_factor(data), config.weight_drawdown),
    ]

    available_weight_total = sum(w for factor, w in raw_factors if factor.available)
    factors: list[RiskFactor] = []
    composite_score = _ZERO

    for factor, weight in raw_factors:
        if not factor.available:
            warnings.append(f"fator '{factor.name}' indisponível: {factor.reason}")
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
        reasons.append(
            "nenhum fator de risco pôde ser calculado — sem dado suficiente na carteira."
        )
    else:
        overall_classification = t.classify_composite_score(composite_score)
        reasons.append(
            "score composto combina os fatores disponíveis com pesos renormalizados "
            "entre si — nunca inventa um fator ausente."
        )

    tolerance_alert = (
        _tolerance_alert(data.declared_risk_tolerance, overall_classification)
        if overall_classification != "indeterminado"
        else None
    )

    return PortfolioRiskResult(
        model_version=MODEL_VERSION,
        overall_score=Decimal(str(round(float(composite_score), 2))),
        overall_classification=overall_classification,
        factors=factors,
        declared_risk_tolerance=data.declared_risk_tolerance,
        tolerance_alert=tolerance_alert,
        reasons=reasons,
        warnings=warnings,
    )
