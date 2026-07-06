"""Serviço do painel de Inteligência (Sprint 19: Advanced Dashboard Intelligence).

Fronteira banco↔engine: para cada posição da carteira (Portfolio
Engine), busca o LG Conviction Score v2 (`ConvictionScoreService`,
Sprint 17) e o desvio de alocação por classe (`TargetAllocationService`,
Sprint 17), e monta um único `IntelligenceDashboardView` para a tela.

Nenhuma regra nova é decidida aqui — apenas composição e agregações de
apresentação (média, contagem por classificação, destaques). Um ativo
sem Conviction Score calculável (ex.: sem histórico de preço) entra na
lista com `has_conviction_score=False` e um motivo explícito — nunca é
omitido nem recebe um valor inventado.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.schemas.intelligence_dashboard import AssetIntelligence, IntelligenceDashboardView
from backend.app.services.conviction_score_service import ConvictionScoreService
from backend.app.services.portfolio_service import PortfolioService
from backend.app.services.target_allocation_service import TargetAllocationService

_ZERO = Decimal("0")


def _to_asset_intelligence(
    ticker: str, asset_class: str, weight: Decimal, conviction
) -> AssetIntelligence:
    if conviction is None:
        return AssetIntelligence(
            ticker=ticker,
            asset_class=asset_class,
            current_weight=weight,
            has_conviction_score=False,
            unavailable_reason=(
                "Conviction Score indisponível: ativo sem histórico de preço suficiente."
            ),
        )
    return AssetIntelligence(
        ticker=ticker,
        asset_class=asset_class,
        current_weight=weight,
        has_conviction_score=True,
        conviction_score=conviction.conviction_score,
        classification=conviction.classification,
        confidence=conviction.confidence,
        confidence_label=conviction.confidence_label,
        quality=conviction.quality,
        valuation=conviction.valuation,
        growth=conviction.growth,
        risk=conviction.risk,
        capital_reinvestment=conviction.capital_reinvestment,
        recommendation_hint=conviction.recommendation_hint,
        explanation=conviction.explanation,
    )


def build_intelligence_dashboard(db: Session, portfolio_id: int) -> IntelligenceDashboardView:
    """Monta o painel de Inteligência para uma carteira."""
    summary = PortfolioService(db).get_summary(portfolio_id)
    conviction_service = ConvictionScoreService(db)

    assets: list[AssetIntelligence] = []
    for pos in summary.positions:
        conviction = conviction_service.score_ticker(pos.ticker, current_weight=pos.weight)
        assets.append(_to_asset_intelligence(pos.ticker, pos.asset_class, pos.weight, conviction))

    scored = [a for a in assets if a.has_conviction_score]
    if scored:
        average_conviction_score = sum((a.conviction_score for a in scored), start=_ZERO) / Decimal(
            len(scored)
        )
        most_convicted = max(scored, key=lambda a: a.conviction_score)
        least_convicted = min(scored, key=lambda a: a.conviction_score)
    else:
        average_conviction_score = None
        most_convicted = None
        least_convicted = None

    coverage_pct = sum((a.current_weight for a in scored), start=_ZERO)

    classification_counts: dict[str, int] = {}
    for a in scored:
        classification_counts[a.classification] = classification_counts.get(a.classification, 0) + 1

    allocation_drift = TargetAllocationService(db).evaluate_portfolio(portfolio_id)

    return IntelligenceDashboardView(
        assets=assets,
        average_conviction_score=average_conviction_score,
        coverage_pct=coverage_pct,
        classification_counts=classification_counts,
        most_convicted=most_convicted,
        least_convicted=least_convicted,
        allocation_drift=allocation_drift,
    )
