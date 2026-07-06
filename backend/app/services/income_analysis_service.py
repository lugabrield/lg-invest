"""Serviço do Income Engine (Sprint 24, Fase 7).

Resolve os dois tipos de proventos já persistidos pela integração
Dividendos.me (`income_monthly_summaries` e `income_events`), converte
tudo para a moeda base (BRL, mesma conversão do Dashboard/Decision
Engine 3.0/Simulation Engine) e monta o `IncomeEngineInput` puro. Não
persiste nada — é uma análise sob demanda, como as demais engines das
fases anteriores.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.engines.income.engine import IncomeAnalysisResult, analyze_income
from backend.app.engines.income.inputs import (
    IncomeEngineInput,
    MonthlyIncomeTotal,
    TickerIncomeEvent,
)
from backend.app.infrastructure.repositories.income_event_repository import (
    IncomeEventRepository,
)
from backend.app.infrastructure.repositories.income_monthly_summary_repository import (
    IncomeMonthlySummaryRepository,
)
from backend.app.services import fx_settings_service
from backend.app.services.portfolio_service import PortfolioService

_ZERO = Decimal("0")


def _to_brl(amount: Decimal, currency: str, exchange_rate: Decimal) -> Decimal:
    if currency == "USD":
        return amount * exchange_rate
    return amount


class IncomeAnalysisService:
    def __init__(self, db: Session):
        self.db = db
        self.events = IncomeEventRepository(db)
        self.monthly_summaries = IncomeMonthlySummaryRepository(db)

    def build_input(
        self,
        portfolio_id: int,
        reference_date: date | None = None,
    ) -> IncomeEngineInput:
        """Monta os proventos já recebidos (dois tipos) e os custos de
        aquisição das posições atuais, tudo já convertido para BRL."""
        exchange_rate = fx_settings_service.get_usd_brl_rate()

        monthly_totals = tuple(
            MonthlyIncomeTotal(
                year=row.year,
                month=row.month,
                amount_total=_to_brl(row.amount_total, row.currency, exchange_rate),
            )
            for row in self.monthly_summaries.list_by_portfolio(portfolio_id)
        )

        ticker_events = tuple(
            TickerIncomeEvent(
                ticker=row.ticker,
                payment_date=row.payment_date,
                amount_total=_to_brl(row.amount_total, row.currency, exchange_rate),
            )
            for row in self.events.list_by_portfolio(portfolio_id)
            if row.ticker is not None and row.payment_date is not None
        )

        summary = PortfolioService(self.db).get_summary(portfolio_id)
        position_cost_basis = {
            position.ticker: _to_brl(
                position.quantity * position.average_price, position.currency, exchange_rate
            )
            for position in summary.positions
        }

        return IncomeEngineInput(
            reference_date=reference_date or date.today(),
            monthly_totals=monthly_totals,
            ticker_events=ticker_events,
            position_cost_basis=position_cost_basis,
        )

    def evaluate(
        self,
        portfolio_id: int,
        reference_date: date | None = None,
    ) -> IncomeAnalysisResult:
        """Monta os inputs a partir do banco e roda a análise de renda pura."""
        data = self.build_input(portfolio_id, reference_date=reference_date)
        return analyze_income(data)
