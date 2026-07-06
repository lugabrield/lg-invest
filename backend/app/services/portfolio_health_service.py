"""Serviço do Portfolio Health Score (Sprint 24, Fase 8).

Compõe sinais já produzidos por 4 serviços existentes — nunca recalcula
a lógica deles:
- `PortfolioService`: número efetivo de ativos (diversificação).
- `PortfolioRiskService` (Fase 6): risco medido da carteira.
- `TargetAllocationService.evaluate_portfolio_rules` (Fase 3): aderência
  à alocação-alvo.
- `IncomeAnalysisService` (Fase 7): tendência de renda.
- `DataQualityService` (Sprint 21): confiança dos dados usados.

Monta o `PortfolioHealthInput` puro e chama a engine. Não persiste nada
— relatório sob demanda, como as demais engines de análise das fases
anteriores.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.engines.portfolio_health.engine import (
    PortfolioHealthResult,
    evaluate_portfolio_health,
)
from backend.app.engines.portfolio_health.inputs import (
    AllocationAlignmentInput,
    PortfolioHealthInput,
)
from backend.app.services.data_quality_service import DataQualityService
from backend.app.services.income_analysis_service import IncomeAnalysisService
from backend.app.services.portfolio_risk_service import PortfolioRiskService
from backend.app.services.portfolio_service import PortfolioService
from backend.app.services.target_allocation_service import TargetAllocationService

_ALIGNED_GAP_STATUSES = ("neutral", "underweight")
_ZERO = Decimal("0")
_TWO = Decimal("2")


class PortfolioHealthService:
    def __init__(self, db: Session):
        self.db = db

    def build_input(self, portfolio_id: int) -> PortfolioHealthInput:
        summary = PortfolioService(self.db).get_summary(portfolio_id)

        risk_result = PortfolioRiskService(self.db).evaluate(portfolio_id)
        risk_classification = (
            risk_result.overall_classification
            if risk_result.overall_classification != "indeterminado"
            else None
        )

        allocation_eval = TargetAllocationService(self.db).evaluate_portfolio_rules(portfolio_id)
        allocation_alignment = None
        if allocation_eval.has_rules and allocation_eval.evaluations:
            aligned = sum(
                1 for e in allocation_eval.evaluations if e.gap_status in _ALIGNED_GAP_STATUSES
            )
            allocation_alignment = AllocationAlignmentInput(
                has_rules=True,
                total_evaluations=len(allocation_eval.evaluations),
                aligned_evaluations=aligned,
            )

        income_result = IncomeAnalysisService(self.db).evaluate(portfolio_id)

        data_quality = DataQualityService(self.db).evaluate_portfolio(portfolio_id)
        data_confidence_pct = (
            (data_quality.pct_fundamentals_available + data_quality.pct_valuation_available) / _TWO
            if data_quality.total_assets > 0
            else None
        )

        return PortfolioHealthInput(
            effective_number_of_assets=summary.effective_number_of_assets,
            risk_overall_classification=risk_classification,
            declared_risk_tolerance=risk_result.declared_risk_tolerance,
            allocation_alignment=allocation_alignment,
            income_growth_pct=income_result.trend.growth_pct,
            data_confidence_pct=data_confidence_pct,
        )

    def evaluate(self, portfolio_id: int) -> PortfolioHealthResult:
        """Monta os inputs a partir dos 4 serviços e roda a agregação pura."""
        data = self.build_input(portfolio_id)
        return evaluate_portfolio_health(data)
