"""Serviço de alocação-alvo (Sprint 17 / Fase 2).

Ponte entre o Portfolio Engine (alocação atual), a configuração de
meta (`target_allocation_settings_service.py`) e o Target Allocation
Engine (puro). Nenhum cálculo mora aqui — só orquestração.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.engines.target_allocation.engine import TargetAllocationEngine
from backend.app.schemas.target_allocation import TargetAllocationResult
from backend.app.services import target_allocation_settings_service
from backend.app.services.portfolio_service import PortfolioService


class TargetAllocationService:
    def __init__(self, db: Session):
        self.db = db
        self.portfolio_service = PortfolioService(db)
        self.engine = TargetAllocationEngine()

    def evaluate_portfolio(self, portfolio_id: int) -> TargetAllocationResult:
        summary = self.portfolio_service.get_summary(portfolio_id)
        current_allocation: dict[str, Decimal] = {
            slice_.label: slice_.weight for slice_ in summary.allocation_by_class
        }
        target_allocation = target_allocation_settings_service.get_target_allocation()
        return self.engine.compare(current_allocation, target_allocation)
