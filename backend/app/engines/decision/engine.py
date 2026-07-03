"""Decision Engine v1 (Volume 7 / Volume 17 §10 / Volume 20 prompt 10).

Engine PURA: recebe os candidatos já tratados e o valor do aporte e
devolve um `RecommendationResult` com a distribuição, justificativas,
alertas, nível de confiança e log de auditoria.

Fluxo (Volume 7, seção 5):
    filtrar elegíveis -> pontuar -> distribuir -> explicar -> auditar
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.decision.allocation import select_and_distribute
from backend.app.engines.decision.eligibility import filter_eligible
from backend.app.engines.decision.inputs import (
    DEFAULT_CONFIG,
    DecisionConfig,
    DecisionInput,
)
from backend.app.engines.decision.scoring import compute_buy_score, compute_buy_score_v2
from backend.app.schemas.recommendation_result import (
    DecisionAudit,
    IgnoredItem,
    RecommendationItem,
    RecommendationResult,
)

MODEL_VERSION = "decision_v1"
MODEL_VERSION_V2 = "decision_v2"
_LOW_CONFIDENCE = Decimal("0.6")


def _confidence_label(confidence: Decimal) -> str:
    pct = confidence * Decimal("100")
    if pct > Decimal("80"):
        return "Alta"
    if pct >= Decimal("60"):
        return "Média"
    return "Baixa"


def recommend(
    candidates: list[DecisionInput],
    amount: Decimal,
    blocked: set[str] | None = None,
    config: DecisionConfig = DEFAULT_CONFIG,
) -> RecommendationResult:
    """Gera a recomendação de aporte para um valor informado."""
    if amount <= 0:
        raise ValueError("O valor do aporte deve ser positivo.")

    blocked = blocked or set()

    eligible, ignored = filter_eligible(candidates, blocked, config)
    scores = [compute_buy_score(c) for c in eligible]
    score_by_ticker = {s.ticker: s for s in scores}
    input_by_ticker = {c.ticker: c for c in eligible}

    allocations = select_and_distribute(scores, amount, config)
    allocated_total = sum((a.amount for a in allocations), start=Decimal("0"))

    items: list[RecommendationItem] = []
    for a in allocations:
        c = input_by_ticker[a.ticker]
        s = score_by_ticker[a.ticker]
        weight = (a.amount / amount) if amount > 0 else Decimal("0")
        items.append(
            RecommendationItem(
                ticker=a.ticker,
                amount=a.amount,
                weight=weight,
                buy_score=a.buy_score,
                lg_score=c.lg_score,
                reasons=s.reasons,
            )
        )

    # Confiança = média das confianças dos LG Scores dos ativos escolhidos.
    chosen = [input_by_ticker[a.ticker] for a in allocations]
    if chosen:
        confidence = sum((c.confidence for c in chosen), start=Decimal("0")) / Decimal(len(chosen))
    else:
        confidence = Decimal("0")

    alerts = _build_alerts(items, ignored, confidence, allocated_total, amount)
    explanation = _build_explanation(items, amount, allocated_total)

    audit = DecisionAudit(
        contribution_amount=amount,
        eligible_tickers=[c.ticker for c in eligible],
        blocked_tickers=sorted(blocked),
        model_version=MODEL_VERSION,
        weights={"lg_score": 0.50, "allocation_gap": 0.30, "concentration_inverted": 0.20},
    )

    return RecommendationResult(
        contribution_amount=amount,
        allocated_amount=allocated_total,
        items=items,
        ignored=[IgnoredItem(ticker=i.ticker, reason=i.reason) for i in ignored],
        alerts=alerts,
        confidence=confidence,
        confidence_label=_confidence_label(confidence),
        explanation=explanation,
        audit=audit,
    )


def recommend_v2(
    candidates: list[DecisionInput],
    amount: Decimal,
    blocked: set[str] | None = None,
    config: DecisionConfig = DEFAULT_CONFIG,
) -> RecommendationResult:
    """Gera a recomendação de aporte v2: Conviction Score + alocação-alvo.

    Mesmo fluxo do v1 (filtrar elegíveis -> pontuar -> distribuir ->
    explicar -> auditar), mas com `compute_buy_score_v2` — LG Conviction
    Score (Sprint 17) no lugar do LG Score puro quando disponível, e
    bônus de classe subalocada no lugar do gap de alocação por ativo
    (que nunca era usado de verdade: `target_weight` por ticker nunca
    foi implementado no MVP).
    """
    if amount <= 0:
        raise ValueError("O valor do aporte deve ser positivo.")

    blocked = blocked or set()

    eligible, ignored = filter_eligible(candidates, blocked, config)
    scores = [compute_buy_score_v2(c) for c in eligible]
    score_by_ticker = {s.ticker: s for s in scores}
    input_by_ticker = {c.ticker: c for c in eligible}

    allocations = select_and_distribute(scores, amount, config)
    allocated_total = sum((a.amount for a in allocations), start=Decimal("0"))

    items: list[RecommendationItem] = []
    for a in allocations:
        c = input_by_ticker[a.ticker]
        s = score_by_ticker[a.ticker]
        weight = (a.amount / amount) if amount > 0 else Decimal("0")
        items.append(
            RecommendationItem(
                ticker=a.ticker,
                amount=a.amount,
                weight=weight,
                buy_score=a.buy_score,
                lg_score=c.lg_score,
                conviction_score=c.conviction_score,
                reasons=s.reasons,
            )
        )

    chosen = [input_by_ticker[a.ticker] for a in allocations]
    if chosen:
        confidence = sum((c.confidence for c in chosen), start=Decimal("0")) / Decimal(len(chosen))
    else:
        confidence = Decimal("0")

    alerts = _build_alerts(items, ignored, confidence, allocated_total, amount)
    explanation = _build_explanation_v2(items, amount, allocated_total)

    audit = DecisionAudit(
        contribution_amount=amount,
        eligible_tickers=[c.ticker for c in eligible],
        blocked_tickers=sorted(blocked),
        model_version=MODEL_VERSION_V2,
        weights={
            "conviction_score_or_lg_score": 0.40,
            "class_underweight_bonus": 0.30,
            "concentration_inverted": 0.30,
        },
    )

    return RecommendationResult(
        contribution_amount=amount,
        allocated_amount=allocated_total,
        items=items,
        ignored=[IgnoredItem(ticker=i.ticker, reason=i.reason) for i in ignored],
        alerts=alerts,
        confidence=confidence,
        confidence_label=_confidence_label(confidence),
        explanation=explanation,
        audit=audit,
    )


def _build_explanation_v2(items, amount, allocated) -> str:
    if not items:
        return "Não houve recomendação de aporte para os critérios atuais."
    partes = [f"{i.ticker}: R$ {i.amount:.2f}" for i in items]
    return (
        f"Aporte de R$ {amount:.2f}: distribuídos R$ {allocated:.2f} entre "
        f"{len(items)} ativo(s) — " + "; ".join(partes) + ". "
        "Prioridade para ativos com melhor Conviction Score e classes subalocadas "
        "em relação à meta de alocação configurada."
    )


def _build_alerts(items, ignored, confidence, allocated, amount) -> list[str]:
    alerts: list[str] = []
    if not items:
        alerts.append("Nenhum ativo elegível para aporte: verifique bloqueios e concentração.")
    if confidence < _LOW_CONFIDENCE and items:
        alerts.append(
            "Confiança baixa: recomendação baseada em dados limitados; revise antes de aportar."
        )
    if allocated < amount and items:
        resto = amount - allocated
        alerts.append(f"Restou R$ {resto:.2f} não alocado por restrições de mínimo/limites.")
    return alerts


def _build_explanation(items, amount, allocated) -> str:
    if not items:
        return "Não houve recomendação de aporte para os critérios atuais."
    partes = [f"{i.ticker}: R$ {i.amount:.2f}" for i in items]
    return (
        f"Aporte de R$ {amount:.2f}: distribuídos R$ {allocated:.2f} entre "
        f"{len(items)} ativo(s) — " + "; ".join(partes) + ". "
        "Prioridade para ativos com melhor LG Score e menor concentração."
    )
