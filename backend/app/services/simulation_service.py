"""Serviço do Monte Carlo Simulation Engine (Sprint 24, Fase 5).

Resolve o valor atual da carteira e os pesos por classe (via
`build_dashboard_view`, com conversão de câmbio) e as premissas de
retorno/volatilidade (`simulation_assumptions_service`), monta o
`SimulationInput` puro e chama a engine. Não persiste nada — assim como
`TargetAllocationService.evaluate_portfolio_rules`, é uma projeção sob
demanda, não um registro de auditoria (não há "recomendação" para
guardar, só uma faixa de cenários possíveis).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.engines.simulation.engine import SimulationResult, run_simulation
from backend.app.engines.simulation.inputs import SimulationConfig, SimulationInput
from backend.app.services import fx_settings_service, simulation_assumptions_service
from backend.app.services.dashboard_view_service import build_dashboard_view

_ZERO = Decimal("0")


class SimulationService:
    def __init__(self, db: Session):
        self.db = db

    def build_input(
        self,
        portfolio_id: int,
        monthly_contribution: Decimal,
        horizon_years: int,
    ) -> SimulationInput:
        """Monta o estado atual da carteira (valor + pesos por classe) e as
        premissas de retorno/volatilidade, sem tocar na engine."""
        exchange_rate = fx_settings_service.get_usd_brl_rate()
        view = build_dashboard_view(self.db, portfolio_id, exchange_rate=exchange_rate)

        class_values: dict[str, Decimal] = {}
        for position in view.positions:
            class_values[position.asset_class] = (
                class_values.get(position.asset_class, _ZERO) + position.position_value_brl
            )

        total_value = view.total_converted_brl
        class_weights = (
            {asset_class: value / total_value for asset_class, value in class_values.items()}
            if total_value > 0
            else {}
        )

        assumptions = simulation_assumptions_service.get_all_assumptions()

        return SimulationInput(
            initial_value=total_value,
            monthly_contribution=monthly_contribution,
            horizon_years=horizon_years,
            class_weights=class_weights,
            class_assumptions=assumptions,
        )

    def run_portfolio_simulation(
        self,
        portfolio_id: int,
        monthly_contribution: Decimal,
        horizon_years: int,
        num_simulations: int = 2000,
        seed: int | None = None,
    ) -> SimulationResult:
        """Monta os inputs a partir do banco e roda a simulação Monte Carlo pura."""
        data = self.build_input(portfolio_id, monthly_contribution, horizon_years)
        config = SimulationConfig(num_simulations=num_simulations, random_seed=seed)
        return run_simulation(data, config)
