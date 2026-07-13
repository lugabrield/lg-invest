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

from backend.app.engines.data_coverage.thresholds import SCORE_PARTIAL, SCORE_SUFFICIENT
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
from backend.app.schemas.valuation_v2 import VALUATION_STATUS_OVERVALUED
from backend.app.services import fx_settings_service
from backend.app.services.conviction_score_service import ConvictionScoreService
from backend.app.services.dashboard_view_service import build_dashboard_view
from backend.app.services.data_coverage_service import DataCoverageService
from backend.app.services.investment_policy_service import InvestmentPolicyService
from backend.app.services.lg_score_service import LGScoreService
from backend.app.services.portfolio_service import PortfolioService
from backend.app.services.target_allocation_service import TargetAllocationService
from backend.app.services.trap_detection_service import TrapDetectionService
from backend.app.services.valuation_v2_service import ValuationServiceV2

_ZERO = Decimal("0")

# Sprint 28, Fase 6 — mesma ordem de grandeza das penalidades do Trap
# Detection Engine (`schemas/trap_detection.py::CONFIDENCE_PENALTY_BY_SEVERITY`,
# 0.05-0.20): cobertura de dados insuficiente para o Decision Engine
# pesa como um trap de severidade média; cobertura parcial, como severidade
# baixa. Nunca bloqueia nem recomenda venda — só reduz confiança, igual ao
# mecanismo já existente.
_COVERAGE_INSUFFICIENT_CONFIDENCE_PENALTY = Decimal("0.10")
_COVERAGE_PARTIAL_CONFIDENCE_PENALTY = Decimal("0.05")


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

    def _fundamental_signals_for_ticker(
        self, ticker: str, asset_class: str
    ) -> tuple[Decimal, tuple[str, ...]]:
        """Sinais do Trap Detection Engine (Sprint 26, Fase 3-4) e do
        Valuation Engine 2.0 (Fase 2) para um ticker — devolve
        `(confidence_penalty, warnings)`. Ambos os serviços já tratam
        classes fora de escopo (ETF/cripto/Tesouro) devolvendo penalidade
        0 e nenhum flag, então esta função não precisa filtrar por
        `asset_class` sozinha (nunca duplica a lista de classes aplicáveis
        que já mora nos engines).

        Nunca bloqueia nem recomenda venda: a penalidade só reduz
        `DecisionInput.confidence` (mecanismo já existente do v3 — Volume
        18, "confiança baixa reduz score"), e os avisos só viram texto em
        `reasons`."""
        warnings: list[str] = []
        confidence_penalty = Decimal("0")

        trap_result = TrapDetectionService(self.db).evaluate_ticker(ticker)
        if trap_result is not None:
            confidence_penalty = trap_result.confidence_penalty
            warnings.extend(
                f"{flag.label} (severidade {flag.severity})" for flag in trap_result.flags
            )

        if asset_class == "stock":
            valuation = ValuationServiceV2(self.db).evaluate_ticker(ticker)
            if valuation is not None and valuation.valuation_status == VALUATION_STATUS_OVERVALUED:
                warnings.append(
                    "Valuation Engine 2.0 classifica este ativo como sobrevalorizado "
                    "em relação à faixa de valor justo estimada."
                )

        # Sprint 28, Fase 6: o Decision Engine v3 não pode mais dizer só
        # "confiança baixa" — quando o Data Coverage Report (Sprint 28,
        # Fase 2) mostra que faltam dados fundamentais, isso vira um aviso
        # explícito com os campos exatos que faltam, e uma penalidade de
        # confiança REAL (não só cosmética) é aplicada, tornando a frase
        # "score reduzido por baixa cobertura de dados" literalmente
        # verdadeira, nunca apenas um rótulo.
        coverage = DataCoverageService(self.db).evaluate_ticker(ticker)
        if coverage is not None:
            de_score = coverage.decision_engine.score
            if de_score is not None and de_score < SCORE_SUFFICIENT:
                insufficient = de_score < SCORE_PARTIAL
                confidence_penalty += (
                    _COVERAGE_INSUFFICIENT_CONFIDENCE_PENALTY
                    if insufficient
                    else _COVERAGE_PARTIAL_CONFIDENCE_PENALTY
                )
                missing = coverage.valuation.missing_labels or coverage.missing_field_labels
                missing_txt = ", ".join(missing[:5]) if missing else "dados fundamentais"
                nivel = "insuficiente" if insufficient else "parcial"
                warnings.append(
                    f"{ticker} tem cobertura de dados fundamentais {nivel} "
                    f"({float(de_score):.0f}%) — faltam: {missing_txt}. "
                    "Score reduzido por baixa cobertura de dados."
                )

        return confidence_penalty, tuple(warnings)

    def _decision_input_for_ticker(
        self,
        ticker: str,
        asset_class: str,
        current_weight: Decimal,
        evaluation_by_key: dict[tuple[str, str], object],
        is_new_from_watchlist: bool = False,
    ) -> DecisionInput | None:
        """Monta um `DecisionInput` a partir de LG Score/Conviction Score +
        sinais do Target Allocation Rule Engine v2 — compartilhado entre
        posições existentes e candidatos novos da Watchlist/Radar (Sprint
        25, Parte 2.5). Retorna `None` quando nem o LG Score consegue ser
        calculado (nunca inventa dado)."""
        lg_service = LGScoreService(self.db)
        conviction_service = ConvictionScoreService(self.db)

        score = lg_service.score_ticker(ticker, current_weight=current_weight)
        if score is None:
            return None
        conviction = conviction_service.score_ticker(ticker, current_weight=current_weight)

        # Sprint 26, Fase 6: penalidade de confiança do Trap Detection
        # Engine é aplicada AQUI, na origem — assim ela se propaga
        # automaticamente por todo o Decision Engine 3.0 (score, alerta de
        # baixa confiança, confiança média da recomendação) sem precisar
        # duplicar a lógica em `scoring.py`.
        confidence_penalty, fundamental_warnings = self._fundamental_signals_for_ticker(
            ticker, asset_class
        )
        effective_confidence = max(Decimal("0"), score.confidence - confidence_penalty)

        asset = self.assets.get_by_ticker(ticker)
        country = asset.country if asset is not None else None
        currency = asset.currency if asset is not None else None
        is_international = country is not None and country != "BR"

        signals: list[AllocationRuleSignal] = []
        for dimension_type, dimension_key in (
            ("class", asset_class),
            ("currency", currency),
            ("country", country),
            ("asset", ticker),
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
                    dimension_key=evaluation.dimension_key,
                    current_weight=evaluation.current_weight,
                    max_weight=evaluation.max_weight,
                    alert_message=evaluation.alert_message,
                )
            )

        return DecisionInput(
            ticker=ticker,
            asset_class=asset_class,
            lg_score=score.lg_score,
            confidence=effective_confidence,
            current_weight=current_weight,
            target_weight=None,
            conviction_score=(conviction.conviction_score if conviction is not None else None),
            quality_score=conviction.quality if conviction is not None else None,
            valuation_score=conviction.valuation if conviction is not None else None,
            growth_score=conviction.growth if conviction is not None else None,
            risk_score=conviction.risk if conviction is not None else None,
            currency=currency,
            country=country,
            is_international=is_international,
            rule_signals=tuple(signals),
            is_new_from_watchlist=is_new_from_watchlist,
            fundamental_warnings=fundamental_warnings,
        )

    def build_inputs_v3(
        self, portfolio_id: int, allow_watchlist_candidates: bool = False
    ) -> list[DecisionInput]:
        """Monta os candidatos v3 (Sprint 24, Fase 4): Portfolio + LG Score +
        Conviction Score (com pilares individuais quality/valuation/growth/
        risk) + sinais do Target Allocation Rule Engine v2 (classe/moeda/
        país/ativo) + país/moeda para o bônus de internacionalização. Um
        ativo sem Conviction Score calculável ainda entra na lista (mesma
        regra do v2): a engine cai de volta no LG Score para esse ativo
        especificamente, nunca exclui um candidato por isso.

        `allow_watchlist_candidates` (Sprint 25, Parte 2.5): quando `True`,
        adiciona candidatos NOVOS (sem posição) que o Radar Engine já
        classificou como `"new_candidate"` — nunca inclui candidatos
        `monitor`/`avoid`/`blocked`/`insufficient_data`, e nunca um ativo
        que já é posição (esses continuam entrando pelo caminho normal
        acima, mesmo com `allow_watchlist_candidates=True`). O default
        `False` preserva o comportamento v3 exatamente como antes da
        Sprint 25."""
        summary = PortfolioService(self.db).get_summary(portfolio_id)

        rule_engine_evaluation = TargetAllocationService(self.db).evaluate_portfolio_rules(
            portfolio_id
        )
        evaluation_by_key = {
            (e.dimension_type, e.dimension_key): e for e in rule_engine_evaluation.evaluations
        }

        inputs: list[DecisionInput] = []
        holding_tickers: set[str] = set()
        for pos in summary.positions:
            holding_tickers.add(pos.ticker)
            decision_input = self._decision_input_for_ticker(
                pos.ticker, pos.asset_class, pos.weight, evaluation_by_key
            )
            if decision_input is not None:
                inputs.append(decision_input)

        if allow_watchlist_candidates:
            from backend.app.services.radar_service import RadarService

            radar = RadarService(self.db).evaluate(portfolio_id)
            for candidate in radar.by_classification("new_candidate"):
                if candidate.ticker in holding_tickers:
                    continue
                decision_input = self._decision_input_for_ticker(
                    candidate.ticker,
                    candidate.asset_class,
                    Decimal("0"),
                    evaluation_by_key,
                    is_new_from_watchlist=True,
                )
                if decision_input is not None:
                    inputs.append(decision_input)

        return inputs

    def _policy_limits_and_aggregates(
        self, portfolio_id: int
    ) -> tuple[PolicyLimits, PortfolioAggregates, Decimal]:
        """Resolve os limites da Investment Policy, os pesos agregados da
        carteira (cripto/FII/internacional) e o patrimônio atual em R$
        para o Decision Engine 3.0. Nunca inventa um limite: campos
        ausentes na política viram `None` em `PolicyLimits`, e a engine
        trata isso como "sem limite". O patrimônio (Sprint 29) alimenta o
        Post-Allocation Constraints Engine — sem ele, a simulação
        pós-aporte simplesmente não roda (nunca inventa um valor)."""
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
        return policy, aggregates, view.total_converted_brl

    def recommend_v3(
        self,
        portfolio_id: int,
        amount: Decimal,
        blocked: set[str] | None = None,
        config: DecisionConfig = DEFAULT_CONFIG,
        persist: bool = True,
        allow_watchlist_candidates: bool = False,
    ) -> RecommendationResult:
        """Gera (e opcionalmente persiste) a recomendação de aporte v3.

        `allow_watchlist_candidates=True` (Sprint 25, Parte 2.5) inclui
        candidatos novos da Watchlist/Radar já classificados como
        "new_candidate" — sempre com teto de alocação reduzido
        (`config.max_new_asset_weight`) e nunca substituindo o
        comportamento padrão para quem não habilitar isso explicitamente.
        """
        candidates = self.build_inputs_v3(
            portfolio_id, allow_watchlist_candidates=allow_watchlist_candidates
        )
        policy, aggregates, portfolio_value_before = self._policy_limits_and_aggregates(
            portfolio_id
        )
        result = recommend_v3(
            candidates,
            amount,
            blocked=blocked,
            config=config,
            policy=policy,
            aggregates=aggregates,
            portfolio_value_before=portfolio_value_before,
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
