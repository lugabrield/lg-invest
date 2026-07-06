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
    MODEL_VERSION_V3,
    recommend,
    recommend_v2,
    recommend_v3,
)
from backend.app.engines.decision.inputs import (
    DEFAULT_CONFIG,
    AllocationRuleSignal,
    DecisionConfig,
    DecisionInput,
    PolicyLimits,
    PortfolioAggregates,
)
from backend.app.infrastructure.database.models.recommendation import Recommendation
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.recommendation_repository import (
    RecommendationRepository,
)
from backend.app.schemas.recommendation_result import RecommendationResult
from backend.app.services import fx_settings_service
from backend.app.services.conviction_score_service import ConvictionScoreService
from backend.app.services.dashboard_view_service import build_dashboard_view
from backend.app.services.investment_policy_service import InvestmentPolicyService
from backend.app.services.lg_score_service import LGScoreService
from backend.app.services.portfolio_service import PortfolioService
from backend.app.services.target_allocation_service import TargetAllocationService

_ZERO = Decimal("0")


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

    def build_inputs_v3(self, portfolio_id: int) -> list[DecisionInput]:
        """Monta os candidatos v3 (Sprint 24, Fase 4): Portfolio + LG Score +
        Conviction Score (com pilares individuais quality/valuation/growth/
        risk) + sinais do Target Allocation Rule Engine v2 (classe/moeda/
        país/ativo) + país/moeda para o bônus de internacionalização. Um
        ativo sem Conviction Score calculável ainda entra na lista (mesma
        regra do v2): a engine cai de volta no LG Score para esse ativo
        especificamente, nunca exclui um candidato por isso."""
        summary = PortfolioService(self.db).get_summary(portfolio_id)
        lg_service = LGScoreService(self.db)
        conviction_service = ConvictionScoreService(self.db)

        rule_engine_evaluation = TargetAllocationService(self.db).evaluate_portfolio_rules(
            portfolio_id
        )
        evaluation_by_key = {
            (e.dimension_type, e.dimension_key): e for e in rule_engine_evaluation.evaluations
        }

        inputs: list[DecisionInput] = []
        for pos in summary.positions:
            score = lg_service.score_ticker(pos.ticker, current_weight=pos.weight)
            if score is None:
                continue
            conviction = conviction_service.score_ticker(pos.ticker, current_weight=pos.weight)

            asset = self.assets.get_by_ticker(pos.ticker)
            country = asset.country if asset is not None else None
            currency = asset.currency if asset is not None else None
            is_international = country is not None and country != "BR"

            signals: list[AllocationRuleSignal] = []
            for dimension_type, dimension_key in (
                ("class", pos.asset_class),
                ("currency", currency),
                ("country", country),
                ("asset", pos.ticker),
            ):
                if dimension_key is None:
                    continue
                evaluation = evaluation_by_key.get((dimension_type, dimension_key))
                if evaluation is None:
                    continue
                signals.append(
                    AllocationRuleSignal(
                        dimension_type=dimension_type,
                        gap_status=evaluation.gap_status,
                        contribution_priority=evaluation.contribution_priority,
                        rebalance_required=evaluation.rebalance_required,
                        extreme_overweight=evaluation.extreme_overweight,
                    )
                )

            inputs.append(
                DecisionInput(
                    ticker=pos.ticker,
                    asset_class=pos.asset_class,
                    lg_score=score.lg_score,
                    confidence=score.confidence,
                    current_weight=pos.weight,
                    target_weight=None,
                    conviction_score=(
                        conviction.conviction_score if conviction is not None else None
                    ),
                    quality_score=conviction.quality if conviction is not None else None,
                    valuation_score=conviction.valuation if conviction is not None else None,
                    growth_score=conviction.growth if conviction is not None else None,
                    risk_score=conviction.risk if conviction is not None else None,
                    currency=currency,
                    country=country,
                    is_international=is_international,
                    rule_signals=tuple(signals),
                )
            )

        return inputs

    def _policy_limits_and_aggregates(
        self, portfolio_id: int
    ) -> tuple[PolicyLimits, PortfolioAggregates]:
        """Resolve os limites da Investment Policy e os pesos agregados da
        carteira (cripto/FII/internacional) para o Decision Engine 3.0.
        Nunca inventa um limite: campos ausentes na política viram `None`
        em `PolicyLimits`, e a engine trata isso como "sem limite"."""
        policy_view = InvestmentPolicyService(self.db).get_or_create(portfolio_id)
        policy = PolicyLimits(
            max_asset_weight=policy_view.max_asset_weight,
            max_crypto_weight=policy_view.max_crypto_weight,
            target_fii_max=policy_view.target_fii_max,
            target_international_min=policy_view.target_international_min,
            target_international_max=policy_view.target_international_max,
        )

        exchange_rate = fx_settings_service.get_usd_brl_rate()
        view = build_dashboard_view(self.db, portfolio_id, exchange_rate=exchange_rate)

        crypto_weight = _ZERO
        fii_weight = _ZERO
        international_weight = _ZERO
        for position in view.positions:
            if position.asset_class == "crypto":
                crypto_weight += position.weight
            if position.asset_class == "fii":
                fii_weight += position.weight
            asset = self.assets.get_by_ticker(position.ticker)
            if asset is not None and asset.country is not None and asset.country != "BR":
                international_weight += position.weight

        aggregates = PortfolioAggregates(
            crypto_weight=crypto_weight,
            fii_weight=fii_weight,
            international_weight=international_weight,
        )
        return policy, aggregates

    def recommend_v3(
        self,
        portfolio_id: int,
        amount: Decimal,
        blocked: set[str] | None = None,
        config: DecisionConfig = DEFAULT_CONFIG,
        persist: bool = True,
    ) -> RecommendationResult:
        """Gera (e opcionalmente persiste) a recomendação de aporte v3."""
        candidates = self.build_inputs_v3(portfolio_id)
        policy, aggregates = self._policy_limits_and_aggregates(portfolio_id)
        result = recommend_v3(
            candidates, amount, blocked=blocked, config=config, policy=policy, aggregates=aggregates
        )

        if persist and result.items:
            self._persist(amount, result, MODEL_VERSION_V3)

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
