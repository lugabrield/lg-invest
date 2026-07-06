"""Serviço de alocação-alvo (Sprint 17 / Fase 2; v2 na Sprint 24 / Fase 3).

Ponte entre o Portfolio Engine (alocação atual), a configuração de
meta (`target_allocation_settings_service.py` v1 por classe;
`TargetAllocationRuleRepository` v2 por classe/moeda/país/ativo) e o
Target Allocation Engine (puro). Nenhum cálculo mora aqui — só
orquestração.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.engines.target_allocation.engine import (
    AllocationRuleInput,
    TargetAllocationEngine,
    TargetAllocationRuleEngine,
)
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.target_allocation_rule_repository import (
    TargetAllocationRuleRepository,
)
from backend.app.schemas.target_allocation import (
    TargetAllocationEvaluation,
    TargetAllocationResult,
)
from backend.app.services import fx_settings_service, target_allocation_settings_service
from backend.app.services.dashboard_view_service import build_dashboard_view
from backend.app.services.portfolio_service import PortfolioService

_ZERO = Decimal("0")


class TargetAllocationService:
    def __init__(self, db: Session):
        self.db = db
        self.portfolio_service = PortfolioService(db)
        self.engine = TargetAllocationEngine()
        self.rule_engine = TargetAllocationRuleEngine()

    def evaluate_portfolio(self, portfolio_id: int) -> TargetAllocationResult:
        summary = self.portfolio_service.get_summary(portfolio_id)
        current_allocation: dict[str, Decimal] = {
            slice_.label: slice_.weight for slice_ in summary.allocation_by_class
        }
        target_allocation = target_allocation_settings_service.get_target_allocation()
        return self.engine.compare(current_allocation, target_allocation)

    def evaluate_portfolio_rules(self, portfolio_id: int) -> TargetAllocationEvaluation:
        """Avaliação v2 (Sprint 24, Fase 3): usa `target_allocation_rules`
        (banco) em vez do JSON por classe da v1, cobrindo classe, moeda,
        país e ativo individual na mesma chamada."""
        rules = TargetAllocationRuleRepository(self.db).list_by_portfolio(portfolio_id)
        rule_inputs = [
            AllocationRuleInput(
                dimension_type=r.dimension_type,
                dimension_key=r.dimension_key,
                min_weight=r.min_weight,
                target_weight=r.target_weight,
                max_weight=r.max_weight,
                priority=r.priority,
            )
            for r in rules
        ]
        current_weights = self._current_weights_by_dimension(portfolio_id)
        return self.rule_engine.evaluate(current_weights, rule_inputs)

    def _current_weights_by_dimension(self, portfolio_id: int) -> dict[tuple[str, str], Decimal]:
        exchange_rate = fx_settings_service.get_usd_brl_rate()
        view = build_dashboard_view(self.db, portfolio_id, exchange_rate=exchange_rate)
        asset_repo = AssetRepository(self.db)

        weights: dict[tuple[str, str], Decimal] = {}
        for position in view.positions:
            weights[("class", position.asset_class)] = (
                weights.get(("class", position.asset_class), _ZERO) + position.weight
            )
            weights[("asset", position.ticker)] = position.weight

            asset = asset_repo.get_by_ticker(position.ticker)
            country = asset.country if asset is not None else None
            if country:
                weights[("country", country)] = (
                    weights.get(("country", country), _ZERO) + position.weight
                )

        for exposure in view.currency_exposure:
            weights[("currency", exposure.currency)] = exposure.weight

        return weights
