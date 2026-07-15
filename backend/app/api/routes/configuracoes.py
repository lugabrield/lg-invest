"""Rotas de Configurações (v1.1, Fase 10 — ver docs/API_CONTRACT.md).

Composição fina sobre `backend/app/services/*` já existentes e
validados: `fx_settings_service`/`fx_service` (câmbio), `market_data_service`
(preços), `target_allocation_settings_service`/`allocation_presets_service`
(Camada 1 — alocação simples), `TargetAllocationRuleService` (Camada 2 —
regras detalhadas), `InvestmentPolicyService` (Camada 3 — política geral),
`allocation_overview_service` (precedência/conflitos entre as 3 camadas) e
`simulation_assumptions_service` (premissas do Monte Carlo). Nenhuma regra
de negócio nova vive aqui — mesmo escopo de
`frontend/streamlit_app/pages_impl/configuracoes.py`, só reorganizado em
endpoints REST-ful em vez de abas com botões.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_portfolio_id
from backend.app.core.config import settings
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.schemas.configuracoes_bundle import (
    AllocationPresetView,
    FxManualUpdateRequest,
    FxQuoteView,
    FxStatusView,
    SimpleAllocationUpdateRequest,
    SimpleAllocationView,
    SystemInfoView,
    TargetAllocationRuleUpsertRequest,
    TargetAllocationRuleView,
)
from backend.app.schemas.investment_policy import InvestmentPolicyUpdate, InvestmentPolicyView
from backend.app.schemas.market_data import BatchUpdateResult
from backend.app.schemas.simulation import (
    ClassAssumptionView,
    SimulationAssumptionsView,
    SimulationAssumptionUpdate,
)
from backend.app.schemas.target_allocation import AllocationOverview
from backend.app.services import (
    allocation_presets_service,
    fx_settings_service,
    simulation_assumptions_service,
    target_allocation_settings_service,
)
from backend.app.services.allocation_overview_service import build_allocation_overview
from backend.app.services.investment_policy_service import InvestmentPolicyService
from backend.app.services.target_allocation_rule_service import TargetAllocationRuleService

router = APIRouter(prefix="/configuracoes", tags=["configuracoes"])

# Mesma máscara de `_redact_database_url` do Streamlit — nunca expõe
# usuário:senha de uma URL de banco (ex.: Supabase) na resposta da API.
_DB_URL_CREDENTIALS_RE = re.compile(r"://([^:/@]+):([^@/]+)@")


def _redact_database_url(url: str) -> str:
    return _DB_URL_CREDENTIALS_RE.sub(r"://\1:***@", url)


# --- Sistema -----------------------------------------------------------


@router.get("/sistema", response_model=SystemInfoView)
def get_system_info(
    portfolio_id: int = Depends(get_portfolio_id), db: Session = Depends(get_db)
) -> SystemInfoView:
    assets_count = len(AssetRepository(db).list_all())
    return SystemInfoView(
        environment=settings.environment,
        database_url_redacted=_redact_database_url(settings.database_url),
        portfolio_id=portfolio_id,
        assets_count=assets_count,
    )


@router.get("/fx", response_model=FxStatusView)
def get_fx_status() -> FxStatusView:
    quote = fx_settings_service.get_fx_quote()
    return FxStatusView(
        current_rate=fx_settings_service.get_usd_brl_rate(),
        quote=(
            FxQuoteView.model_validate(
                {
                    "pair": quote.pair,
                    "rate": quote.rate,
                    "source": quote.source,
                    "fetched_at": quote.fetched_at.isoformat(),
                }
            )
            if quote is not None
            else None
        ),
    )


@router.post("/fx/refresh", response_model=FxQuoteView)
def refresh_fx_rate() -> FxQuoteView:
    from backend.app.services.fx_service import update_usd_brl_rate

    try:
        quote = update_usd_brl_rate()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return FxQuoteView.model_validate(
        {
            "pair": quote.pair,
            "rate": quote.rate,
            "source": quote.source,
            "fetched_at": quote.fetched_at.isoformat(),
        }
    )


@router.put("/fx", response_model=FxStatusView)
def set_fx_rate_manually(payload: FxManualUpdateRequest) -> FxStatusView:
    try:
        fx_settings_service.set_usd_brl_rate(payload.rate)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return get_fx_status()


@router.post("/precos/refresh", response_model=BatchUpdateResult)
def refresh_prices(db: Session = Depends(get_db)) -> BatchUpdateResult:
    from backend.app.etl.providers.yahoo_provider import YahooFinanceProvider
    from backend.app.services.market_data_service import MarketDataService

    try:
        service = MarketDataService(db, YahooFinanceProvider())
        return service.update_all_active()
    except Exception as exc:  # noqa: BLE001 - nunca vazar detalhe de exceção não prevista
        raise HTTPException(
            status_code=503,
            detail="Não foi possível atualizar os preços agora — sem internet ou fonte indisponível.",
        ) from exc


# --- Camada 1: alocação-alvo simples ------------------------------------


def _simple_allocation_view() -> SimpleAllocationView:
    allocation = target_allocation_settings_service.get_target_allocation()
    return SimpleAllocationView(allocation=allocation, has_target=bool(allocation))


@router.get("/alocacao-simples", response_model=SimpleAllocationView)
def get_simple_allocation() -> SimpleAllocationView:
    return _simple_allocation_view()


@router.put("/alocacao-simples", response_model=SimpleAllocationView)
def set_simple_allocation(payload: SimpleAllocationUpdateRequest) -> SimpleAllocationView:
    try:
        target_allocation_settings_service.set_target_allocation(payload.allocation)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _simple_allocation_view()


@router.delete("/alocacao-simples", status_code=204)
def clear_simple_allocation() -> None:
    target_allocation_settings_service.clear_target_allocation()


@router.get("/alocacao-presets", response_model=list[AllocationPresetView])
def list_allocation_presets() -> list[AllocationPresetView]:
    return [
        AllocationPresetView(
            key=p.key, label=p.label, description=p.description, allocation=p.allocation
        )
        for p in allocation_presets_service.list_presets()
    ]


@router.post("/alocacao-presets/{preset_key}/aplicar", response_model=SimpleAllocationView)
def apply_allocation_preset(preset_key: str) -> SimpleAllocationView:
    try:
        preset = allocation_presets_service.get_preset(preset_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if preset.allocation is None:
        raise HTTPException(
            status_code=422,
            detail=f"Preset '{preset_key}' não aplica nada — configure manualmente.",
        )
    target_allocation_settings_service.set_target_allocation(preset.allocation)
    return _simple_allocation_view()


# --- Camada 2: regras detalhadas ----------------------------------------


@router.get("/regras-alocacao", response_model=list[TargetAllocationRuleView])
def list_target_allocation_rules(
    portfolio_id: int = Depends(get_portfolio_id), db: Session = Depends(get_db)
) -> list[TargetAllocationRuleView]:
    rules = TargetAllocationRuleService(db).list_rules(portfolio_id)
    return [TargetAllocationRuleView.model_validate(r) for r in rules]


@router.put("/regras-alocacao", response_model=TargetAllocationRuleView, status_code=201)
def upsert_target_allocation_rule(
    payload: TargetAllocationRuleUpsertRequest,
    portfolio_id: int = Depends(get_portfolio_id),
    db: Session = Depends(get_db),
) -> TargetAllocationRuleView:
    try:
        rule = TargetAllocationRuleService(db).set_rule(
            portfolio_id,
            dimension_type=payload.dimension_type,
            dimension_key=payload.dimension_key,
            min_weight=payload.min_weight,
            target_weight=payload.target_weight,
            max_weight=payload.max_weight,
            priority=payload.priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TargetAllocationRuleView.model_validate(rule)


@router.delete("/regras-alocacao/{dimension_type}/{dimension_key}", status_code=204)
def delete_target_allocation_rule(
    dimension_type: str,
    dimension_key: str,
    portfolio_id: int = Depends(get_portfolio_id),
    db: Session = Depends(get_db),
) -> None:
    removed = TargetAllocationRuleService(db).delete_rule(
        portfolio_id, dimension_type, dimension_key
    )
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhuma regra encontrada para {dimension_type}={dimension_key}.",
        )


# --- Camada 3: política de investimento ---------------------------------


@router.get("/politica", response_model=InvestmentPolicyView)
def get_investment_policy(
    portfolio_id: int = Depends(get_portfolio_id), db: Session = Depends(get_db)
) -> InvestmentPolicyView:
    return InvestmentPolicyService(db).get_or_create(portfolio_id)


@router.patch("/politica", response_model=InvestmentPolicyView)
def update_investment_policy(
    payload: InvestmentPolicyUpdate,
    portfolio_id: int = Depends(get_portfolio_id),
    db: Session = Depends(get_db),
) -> InvestmentPolicyView:
    return InvestmentPolicyService(db).update(portfolio_id, payload)


# --- Visão geral (precedência e conflitos entre as 3 camadas) -----------


@router.get("/visao-geral", response_model=AllocationOverview)
def get_allocation_overview(
    portfolio_id: int = Depends(get_portfolio_id), db: Session = Depends(get_db)
) -> AllocationOverview:
    return build_allocation_overview(db, portfolio_id)


# --- Premissas do Monte Carlo Simulation Engine --------------------------


@router.get("/premissas-simulacao", response_model=SimulationAssumptionsView)
def get_simulation_assumptions() -> SimulationAssumptionsView:
    # `get_all_assumptions()` devolve `ClassAssumption` (dataclass da
    # engine pura, `backend/app/engines/simulation/inputs.py`), não o
    # schema Pydantic `ClassAssumptionView` — precisa de conversão
    # explícita (mesmo motivo de `SimulationResultView.model_validate`
    # na Fase 8, mas aqui o container é um dict, não um único objeto).
    assumptions = simulation_assumptions_service.get_all_assumptions()
    return SimulationAssumptionsView(
        assumptions=[
            ClassAssumptionView(
                asset_class=a.asset_class,
                expected_return=a.expected_return,
                volatility=a.volatility,
                source=a.source,
            )
            for a in assumptions.values()
        ],
        disclaimer=simulation_assumptions_service.DISCLAIMER,
    )


@router.put("/premissas-simulacao", response_model=SimulationAssumptionsView)
def set_simulation_assumption(payload: SimulationAssumptionUpdate) -> SimulationAssumptionsView:
    try:
        simulation_assumptions_service.set_assumption(
            payload.asset_class, payload.expected_return, payload.volatility
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return get_simulation_assumptions()


@router.delete("/premissas-simulacao/{asset_class}", response_model=SimulationAssumptionsView)
def reset_simulation_assumption(asset_class: str) -> SimulationAssumptionsView:
    simulation_assumptions_service.reset_assumption(asset_class)
    return get_simulation_assumptions()
