"""Rotas de Simulação — Monte Carlo Simulation Engine (v1.1, Fase 8 — ver
docs/API_CONTRACT.md).

Consome `SimulationService.run_portfolio_simulation()`, exatamente como
`frontend/streamlit_app/pages_impl/simulacao.py` já fazia: resolve o
valor atual da carteira e as premissas de retorno/volatilidade por
classe (editáveis em Configurações, ainda só no Streamlit), monta o
`SimulationInput` e roda a engine pura. Nenhum cálculo financeiro vive
aqui — só compõe o que `SimulationService`/`SimulationResult` já
devolvem. Isto é sempre uma projeção probabilística, nunca uma
previsão real de mercado nem recomendação financeira (ver
`docs/SIMULATION_ENGINE.md`); nada aqui persiste no banco.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_portfolio_id
from backend.app.schemas.simulation import SimulationResultView, SimulationRunRequest
from backend.app.services.simulation_service import SimulationService

router = APIRouter(tags=["simulacao"])

# Mesma seed fixa 42 usada por `pages_impl/simulacao.py` quando o
# checkbox "Usar semente fixa (resultado reproduzível)" está marcado —
# nunca um valor arbitrário vindo do cliente.
_REPRODUCIBLE_SEED = 42


@router.post("/simulacao", response_model=SimulationResultView)
def run_simulation(
    payload: SimulationRunRequest,
    portfolio_id: int = Depends(get_portfolio_id),
    db: Session = Depends(get_db),
) -> SimulationResultView:
    try:
        result = SimulationService(db).run_portfolio_simulation(
            portfolio_id,
            monthly_contribution=payload.monthly_contribution,
            horizon_years=payload.horizon_years,
            num_simulations=payload.num_simulations,
            seed=_REPRODUCIBLE_SEED if payload.reproducible else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SimulationResultView.model_validate(result)
