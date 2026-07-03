"""Serviço do Decision Engine.

Fronteira banco↔engine:
- monta os DecisionInput a partir do Portfolio Engine (pesos atuais) e
  do LG Score Engine (score + confiança);
- chama a engine pura;
- persiste cada item da recomendação na tabela `recommendations`
  (auditabilidade, Volume 7/18), mantendo a engine sem efeitos colaterais.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.engines.decision.engine import (
    MODEL_VERSION,
    MODEL_VERSION_V2,
    recommend,
    recommend_v2,
)
from backend.app.engines.decision.inputs import DEFAULT_CONFIG, DecisionConfig, DecisionInput
from backend.app.infrastructure.database.models.recommendation import Recommendation
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.recommendation_repository import (
    RecommendationRepository,
)
from backend.app.schemas.recommendation_result import RecommendationResult
from backend.app.services.conviction_score_service import ConvictionScoreService
from backend.app.services.lg_score_service import LGScoreService
from backend.app.services.portfolio_service import PortfolioService
from backend.app.services.target_allocation_service import TargetAllocationService


class DecisionService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.recommendations = RecommendationRepository(db)

    def build_inputs(self, portfolio_id: int) -> list[DecisionInput]:
        """Monta os candidatos a partir de Portfolio + LG Score."""
        summary = PortfolioService(self.db).get_summary(portfolio_id)
        lg_service = LGScoreService(self.db)

        inputs: list[DecisionInput] = []
        for pos in summary.positions:
            score = lg_service.score_ticker(pos.ticker, current_weight=pos.weight)
            if score is None:
                continue
            inputs.append(
                DecisionInput(
                    ticker=pos.ticker,
                    asset_class=pos.asset_class,
                    lg_score=score.lg_score,
                    confidence=score.confidence,
                    current_weight=pos.weight,
                    target_weight=None,  # peso-alvo fora do MVP
                )
            )
        return inputs

    def recommend(
        self,
        portfolio_id: int,
        amount: Decimal,
        blocked: set[str] | None = None,
        config: DecisionConfig = DEFAULT_CONFIG,
        persist: bool = True,
    ) -> RecommendationResult:
        """Gera (e opcionalmente persiste) a recomendação de aporte."""
        candidates = self.build_inputs(portfolio_id)
        result = recommend(candidates, amount, blocked=blocked, config=config)

        if persist and result.items:
            self._persist(amount, result, MODEL_VERSION)

        return result

    def build_inputs_v2(self, portfolio_id: int) -> list[DecisionInput]:
        """Monta os candidatos v2: Portfolio + LG Score + Conviction Score

        (Sprint 17) + desvio de alocação por classe (Target Allocation
        Engine, Sprint 17). Um ativo sem Conviction Score calculável
        ainda entra na lista (com `conviction_score=None`): o Decision
        Engine 2.0 cai de volta no LG Score para esse ativo
        especificamente, nunca exclui um candidato por isso.
        """
        summary = PortfolioService(self.db).get_summary(portfolio_id)
        lg_service = LGScoreService(self.db)
        conviction_service = ConvictionScoreService(self.db)

        allocation_drift = TargetAllocationService(self.db).evaluate_portfolio(portfolio_id)
        drift_by_class = {c.asset_class: c.drift_pct for c in allocation_drift.classes}

        inputs: list[DecisionInput] = []
        for pos in summary.positions:
            score = lg_service.score_ticker(pos.ticker, current_weight=pos.weight)
            if score is None:
                continue
            conviction = conviction_service.score_ticker(pos.ticker, current_weight=pos.weight)
            inputs.append(
                DecisionInput(
                    ticker=pos.ticker,
                    asset_class=pos.asset_class,
                    lg_score=score.lg_score,
                    confidence=score.confidence,
                    current_weight=pos.weight,
                    target_weight=None,  # peso-alvo por ticker fora do MVP
                    conviction_score=(
                        conviction.conviction_score if conviction is not None else None
                    ),
                    class_drift_pct=drift_by_class.get(pos.asset_class),
                )
            )
        return inputs

    def recommend_v2(
        self,
        portfolio_id: int,
        amount: Decimal,
        blocked: set[str] | None = None,
        config: DecisionConfig = DEFAULT_CONFIG,
        persist: bool = True,
    ) -> RecommendationResult:
        """Gera (e opcionalmente persiste) a recomendação de aporte v2."""
        candidates = self.build_inputs_v2(portfolio_id)
        result = recommend_v2(candidates, amount, blocked=blocked, config=config)

        if persist and result.items:
            self._persist(amount, result, MODEL_VERSION_V2)

        return result

    def _persist(self, amount: Decimal, result: RecommendationResult, model_version: str) -> None:
        today = date.today()
        for item in result.items:
            asset = self.assets.get_by_ticker(item.ticker)
            if asset is None:
                continue
            self.recommendations.create(
                Recommendation(
                    date=today,
                    contribution_amount=amount,
                    asset_id=asset.id,
                    amount=item.amount,
                    reason=" | ".join(item.reasons),
                    algo_version=model_version,
                )
            )
