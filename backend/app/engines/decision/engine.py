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
from backend.app.engines.decision.eligibility import filter_eligible, filter_eligible_v3
from backend.app.engines.decision.inputs import (
    DEFAULT_CONFIG,
    DecisionConfig,
    DecisionInput,
    PolicyLimits,
    PortfolioAggregates,
)
from backend.app.engines.decision.scoring import (
    compute_buy_score,
    compute_buy_score_v2,
    compute_buy_score_v3,
)
from backend.app.schemas.recommendation_result import (
    DecisionAudit,
    IgnoredItem,
    RecommendationItem,
    RecommendationResult,
)

MODEL_VERSION = "decision_v1"
MODEL_VERSION_V2 = "decision_v2"
MODEL_VERSION_V3 = "decision_v3"
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
                item_confidence=c.confidence,
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
                item_confidence=c.confidence,
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
    """Monta os alertas da recomendação — nunca sugere aporte com dado ruim sem avisar
    (pedido explícito do usuário no Sprint 21). Alertas de confiança são específicos por
    ativo quando possível, não só um aviso genérico no fim."""
    alerts: list[str] = []
    if not items:
        alerts.append("Nenhum ativo elegível para aporte: verifique bloqueios e concentração.")

    low_confidence_items = [
        i for i in items if i.item_confidence is not None and i.item_confidence < _LOW_CONFIDENCE
    ]
    if low_confidence_items:
        tickers = ", ".join(i.ticker for i in low_confidence_items)
        alerts.append(
            f"Recomendação com baixa confiança por falta de fundamentos/valuation em: "
            f"{tickers}. O sistema ainda inclui esses ativos na distribuição (não bloqueia "
            "por confiança baixa), mas o motivo está registrado — revise antes de aportar."
        )
    elif confidence < _LOW_CONFIDENCE and items:
        alerts.append(
            "Recomendação com baixa confiança por falta de fundamentos/valuation; revise "
            "antes de aportar."
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


def recommend_v3(
    candidates: list[DecisionInput],
    amount: Decimal,
    blocked: set[str] | None = None,
    config: DecisionConfig = DEFAULT_CONFIG,
    policy: PolicyLimits | None = None,
    aggregates: PortfolioAggregates | None = None,
) -> RecommendationResult:
    """Gera a recomendação de aporte v3 (Sprint 24, Fase 4): score
    multi-fator (fundamentos/quality/valuation/growth/risk + alocação-alvo
    multi-dimensão + concentração + internacionalização, escalado pela
    confiança do dado) e bloqueio adicional por Investment Policy e por
    Target Allocation Rule Engine v2 — sempre pausando aporte, nunca
    recomendando venda.

    Mesmo fluxo das versões anteriores (filtrar elegíveis -> pontuar ->
    distribuir -> explicar -> auditar); `policy`/`aggregates` ausentes
    (`None`) fazem o v3 se comportar como se não houvesse política
    configurada — nunca inventa limites.
    """
    if amount <= 0:
        raise ValueError("O valor do aporte deve ser positivo.")

    blocked = blocked or set()

    eligible, ignored = filter_eligible_v3(
        candidates, blocked, config, policy=policy, aggregates=aggregates
    )
    scores = [compute_buy_score_v3(c, policy=policy, aggregates=aggregates) for c in eligible]
    score_by_ticker = {s.ticker: s for s in scores}
    input_by_ticker = {c.ticker: c for c in eligible}

    # Sprint 25, Parte 2.5: tickers novos da Watchlist/Radar (sem posição
    # existente) recebem o teto reduzido `max_new_asset_weight` em vez do
    # teto padrão — nunca 100% do aporte em um ativo ainda não possuído.
    new_asset_tickers = frozenset(c.ticker for c in eligible if c.is_new_from_watchlist)

    allocations = select_and_distribute(scores, amount, config, new_asset_tickers=new_asset_tickers)
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
                item_confidence=c.confidence,
                reasons=s.reasons,
                is_new_from_watchlist=c.is_new_from_watchlist,
            )
        )

    chosen = [input_by_ticker[a.ticker] for a in allocations]
    if chosen:
        confidence = sum((c.confidence for c in chosen), start=Decimal("0")) / Decimal(len(chosen))
    else:
        confidence = Decimal("0")

    alerts = _build_alerts(items, ignored, confidence, allocated_total, amount)
    if any(i.is_new_from_watchlist for i in items):
        novos = ", ".join(i.ticker for i in items if i.is_new_from_watchlist)
        alerts.append(
            f"Candidato(s) novo(s) da Watchlist nesta recomendação: {novos}. Considere "
            "iniciar uma posição pequena (nunca definido automaticamente) — a alocação "
            f"inicial está limitada a {config.max_new_asset_weight * 100:.0f}% do aporte "
            "para ativos que você ainda não possui."
        )
    explanation = _build_explanation_v3(items, amount, allocated_total)

    audit = DecisionAudit(
        contribution_amount=amount,
        eligible_tickers=[c.ticker for c in eligible],
        blocked_tickers=sorted(blocked),
        model_version=MODEL_VERSION_V3,
        weights={
            "fundamentals": 0.40,
            "allocation_bonus_multi_dimension": 0.25,
            "concentration_inverted": 0.20,
            "international_bonus": 0.15,
            "confidence_scaling": 1.0,
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


def _build_explanation_v3(items, amount, allocated) -> str:
    if not items:
        return "Não houve recomendação de aporte para os critérios atuais."
    partes = [f"{i.ticker}: R$ {i.amount:.2f}" for i in items]
    return (
        f"Aporte de R$ {amount:.2f}: distribuídos R$ {allocated:.2f} entre "
        f"{len(items)} ativo(s) — " + "; ".join(partes) + ". "
        "Prioridade combinando fundamentos (quality/valuation/growth/risk), gap de "
        "alocação-alvo (classe/moeda/país/ativo), concentração e exposição "
        "internacional em relação à política de investimento, com o score ajustado "
        "pela confiança do dado disponível."
    )
