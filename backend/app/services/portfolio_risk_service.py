"""Serviço do Portfolio Risk Engine (Sprint 24, Fase 6 — "Risk Engine 2.0").

Resolve concentração/número efetivo de ativos (`PortfolioService`), pesos
por classe e exposição internacional (`build_dashboard_view`),
volatilidade por classe (`simulation_assumptions_service`, mesma fonte do
Monte Carlo Simulation Engine), classificação de risco por ativo
(`RiskService`, Risk Engine v1) e a tolerância a risco declarada
(`InvestmentPolicyService`). Monta o `PortfolioRiskInput` puro e chama a
engine. Não persiste nada — é um relatório sob demanda, como o Monte
Carlo Simulation Engine e o Target Allocation Rule Engine v2.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.engines.portfolio_risk.engine import (
    PortfolioRiskResult,
    evaluate_portfolio_risk,
)
from backend.app.engines.portfolio_risk.inputs import AssetRiskSignal, PortfolioRiskInput
from backend.app.services import fx_settings_service, simulation_assumptions_service
from backend.app.services.dashboard_view_service import build_dashboard_view
from backend.app.services.investment_policy_service import InvestmentPolicyService
from backend.app.services.portfolio_service import PortfolioService
from backend.app.services.risk_service import RiskService

_ZERO = Decimal("0")


class PortfolioRiskService:
    def __init__(self, db: Session):
        self.db = db
        self.risk_service = RiskService(db)

    def build_input(
        self,
        portfolio_id: int,
        probability_of_loss: Decimal | None = None,
    ) -> PortfolioRiskInput:
        """Monta o estado atual da carteira necessário para a agregação de
        risco, sem tocar na engine."""
        summary = PortfolioService(self.db).get_summary(portfolio_id)

        exchange_rate = fx_settings_service.get_usd_brl_rate()
        view = build_dashboard_view(self.db, portfolio_id, exchange_rate=exchange_rate)

        class_weights: dict[str, Decimal] = {}
        international_weight = _ZERO
        for position in view.positions:
            class_weights[position.asset_class] = (
                class_weights.get(position.asset_class, _ZERO) + position.weight
            )
            if position.currency != "BRL":
                international_weight += position.weight

        class_volatilities = {
            asset_class: assumption.volatility
            for asset_class, assumption in simulation_assumptions_service.get_all_assumptions().items()
        }

        asset_risk_signals = []
        for position in view.positions:
            risk_result = self.risk_service.evaluate_ticker(position.ticker)
            if risk_result is None:
                continue
            asset_risk_signals.append(
                AssetRiskSignal(
                    ticker=position.ticker,
                    asset_class=position.asset_class,
                    weight=position.weight,
                    classification=risk_result.classification,
                    confidence=risk_result.confidence,
                )
            )

        policy_view = InvestmentPolicyService(self.db).get_or_create(portfolio_id)

        return PortfolioRiskInput(
            concentration_hhi=summary.concentration_hhi,
            effective_number_of_assets=summary.effective_number_of_assets,
            international_weight=international_weight,
            class_weights=class_weights,
            class_volatilities=class_volatilities,
            asset_risk_signals=tuple(asset_risk_signals),
            probability_of_loss=probability_of_loss,
            declared_risk_tolerance=policy_view.risk_tolerance,
        )

    def evaluate(
        self,
        portfolio_id: int,
        probability_of_loss: Decimal | None = None,
    ) -> PortfolioRiskResult:
        """Monta os inputs a partir do banco e roda a agregação de risco pura."""
        data = self.build_input(portfolio_id, probability_of_loss=probability_of_loss)
        return evaluate_portfolio_risk(data)
