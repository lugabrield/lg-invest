"""Decision Engine v1 (Volume 7 / Volume 17 §10 / Volume 20 prompt 10).

Engine PURA: recebe os candidatos já tratados e o valor do aporte e
devolve um `RecommendationResult` com a distribuição, justificativas,
alertas, nível de confiança e o log de auditoria.

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
from backend.app.engines.decision.post_allocation import apply_post_allocation_constraints
from backend.app.engines.decision.scoring import (
    compute_buy_score,
    compute_buy_score_v2,
    compute_buy_score_v3,
)
from backend.app.schemas.recommendation_result import (
    CappedDimensionResult,
    DecisionAudit,
    IgnoredItem,
    RecommendationItem,
    RecommendationResult,
    ScoreFactor,
)

# Sprint 29: limiares do alerta de "aporte grande demais em relação ao
# patrimônio" — pedido explícito do usuário após um aporte de R$ 1 milhão
# numa carteira de R$ 40 mil ter estourado o limite máximo de exposição
# em USD (97,23% quando o máximo configurado era 60%). O corte em si é
# feito pelo Post-Allocation Constraints Engine; este alerta só avisa
# ANTES de o usuário ler a distribuição que a simulação é extrema.
_LARGE_CONTRIBUTION_RATIO = Decimal("0.25")
_EXTREME_CONTRIBUTION_RATIO = Decimal("1.0")

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


def _score_breakdown(score) -> list[ScoreFactor]:
    """Converte `BuyScore.factors` (dataclass puro da engine) para o
    schema `ScoreFactor` (Sprint 25, Parte 4) — mesma conversão nos três
    motores, sem duplicar a lista comprehension em cada `recommend*`."""
    return [
        ScoreFactor(label=f.label, weight=f.weight, value=f.value, contribution=f.contribution)
        for f in score.factors
    ]


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
                score_breakdown=_score_breakdown(s),
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
        ignored=[
            IgnoredItem(ticker=i.ticker, reason=i.reason, block_source=i.block_source)
            for i in ignored
        ],
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
                score_breakdown=_score_breakdown(s),
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
        ignored=[
            IgnoredItem(ticker=i.ticker, reason=i.reason, block_source=i.block_source)
            for i in ignored
        ],
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
    portfolio_value_before: Decimal | None = None,
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

    `portfolio_value_before` (Sprint 29): patrimônio real da carteira em
    R$, necessário para o Post-Allocation Constraints Engine simular o
    peso de cada dimensão DEPOIS do aporte e cortar qualquer dimensão
    que ultrapassaria seu máximo configurado — correção do bug em que um
    aporte muito maior que o patrimônio atual conseguia estourar um
    limite máximo (ex.: 97% de exposição em USD com máximo configurado
    de 60%). Quando `None` (chamador não tem esse dado), a simulação
    pós-aporte é pulada — nunca inventa um patrimônio para simular.
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

    # Sprint 29: Post-Allocation Constraints — corta a distribuição acima
    # se alguma dimensão (classe/moeda/país/ativo/exposição internacional)
    # ultrapassaria seu máximo configurado DEPOIS do aporte.
    capped_dimensions: list[CappedDimensionResult] = []
    post_allocation_reasons: list[str] = []
    if portfolio_value_before is not None:
        pa_result = apply_post_allocation_constraints(
            allocations,
            input_by_ticker,
            portfolio_value_before,
            amount,
            policy=policy,
            aggregates=aggregates,
        )
        allocations = pa_result.allocations
        post_allocation_reasons = pa_result.reasons
        capped_dimensions = [
            CappedDimensionResult(
                dimension_type=cd.dimension_type,
                dimension_key=cd.dimension_key,
                label=cd.label,
                weight_before=cd.weight_before,
                weight_after=cd.weight_after,
                max_weight=cd.max_weight,
                source=cd.source,
            )
            for cd in pa_result.capped_dimensions
        ]

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
                score_breakdown=_score_breakdown(s),
                is_new_from_watchlist=c.is_new_from_watchlist,
                watchlist_reason=(_watchlist_reason(config) if c.is_new_from_watchlist else None),
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
    # Sprint 29: dimensões cortadas pelo Post-Allocation Constraints Engine
    # (nunca um bloqueio silencioso — o motivo explícito de cada corte
    # sempre vira alerta, mesma disciplina do resto do Decision Engine).
    alerts.extend(post_allocation_reasons)
    if portfolio_value_before is not None and portfolio_value_before > 0:
        contribution_ratio = amount / portfolio_value_before
        if contribution_ratio > _EXTREME_CONTRIBUTION_RATIO:
            alerts.append(
                "Aporte maior que a carteira atual. A simulação muda drasticamente a "
                "alocação e pode exigir uma estratégia de entrada gradual."
            )
        elif contribution_ratio > _LARGE_CONTRIBUTION_RATIO:
            alerts.append(
                "Este aporte é grande em relação ao patrimônio atual. A recomendação foi "
                "limitada por regras de alocação pós-aporte."
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
        ignored=[
            IgnoredItem(ticker=i.ticker, reason=i.reason, block_source=i.block_source)
            for i in ignored
        ],
        alerts=alerts,
        confidence=confidence,
        confidence_label=_confidence_label(confidence),
        explanation=explanation,
        audit=audit,
        capped_dimensions=capped_dimensions,
    )


def _watchlist_reason(config: DecisionConfig) -> str:
    """Explica por que um candidato novo da Watchlist/Radar está nesta
    recomendação (Sprint 25, Parte 4) — mesma regra já aplicada em
    `select_and_distribute` (teto `max_new_asset_weight`), só que
    exposta por item em vez de só num alerta agregado."""
    return (
        "Candidato novo do Watchlist/Radar — ainda não é posição na sua carteira. "
        f"Por isso a alocação inicial é limitada a {config.max_new_asset_weight * 100:.0f}% "
        "do aporte, mesmo com score alto. Nada aqui inicia a posição sozinho: iniciar (e "
        "quando) continua sendo sua decisão."
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
