"""Schemas de apresentação da tela Configurações (v1.1, Fase 10).

A maioria das camadas já tinha schema Pydantic 1:1 (`InvestmentPolicyView`/
`InvestmentPolicyUpdate` em `investment_policy.py`, `AllocationOverview` em
`target_allocation.py`, `SimulationAssumptionsView`/`SimulationAssumptionUpdate`
em `simulation.py`, `FxQuote`/`BatchUpdateResult` em `market_data.py`). Este
módulo só acrescenta o que faltava: informações do ambiente, o status da
alocação-alvo simples (JSON), os presets prontos, e a leitura/escrita de
`TargetAllocationRule` (que só tinha o schema de AVALIAÇÃO da regra, não
um espelho 1:1 da regra em si).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, field_validator

from backend.app.infrastructure.database.models.target_allocation_rule import (
    TARGET_ALLOCATION_DIMENSIONS,
)


class SystemInfoView(BaseModel):
    """Espelha a seção "Ambiente" da aba Sistema — nunca expõe a URL do
    banco crua (credenciais são mascaradas antes de chegar aqui, mesma
    regra do Streamlit — ver `_redact_database_url` na rota)."""

    environment: str
    database_url_redacted: str
    portfolio_id: int
    assets_count: int


class FxQuoteView(BaseModel):
    pair: str
    rate: Decimal
    source: str
    fetched_at: str

    model_config = {"from_attributes": True}


class FxStatusView(BaseModel):
    """Câmbio USD/BRL em uso — mesma leitura de `_render_system_section`:
    se nunca houve cotação salva, `quote` é `None` e `current_rate` é o
    default do sistema (nunca inventa uma cotação)."""

    current_rate: Decimal
    quote: FxQuoteView | None = None


class FxManualUpdateRequest(BaseModel):
    rate: Decimal

    @field_validator("rate")
    @classmethod
    def rate_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Câmbio USD/BRL deve ser maior que zero.")
        return value


class SimpleAllocationView(BaseModel):
    """Alocação-alvo simples por classe (Camada 1) — `allocation` vazio
    significa "nenhuma meta configurada ainda", nunca um default oculto."""

    allocation: dict[str, Decimal]
    has_target: bool


class SimpleAllocationUpdateRequest(BaseModel):
    allocation: dict[str, Decimal]


class AllocationPresetView(BaseModel):
    """Um modelo pronto de alocação — `allocation=None` para o preset
    "Personalizado" (não aplica nada sozinho)."""

    key: str
    label: str
    description: str
    allocation: dict[str, Decimal] | None


class TargetAllocationRuleView(BaseModel):
    """Espelho 1:1 de `TargetAllocationRule` (Camada 2) — o schema de
    avaliação (`AllocationRuleEvaluation`) já existia, mas nenhum
    espelhava a regra CRUA como cadastrada."""

    id: int
    portfolio_id: int
    dimension_type: str
    dimension_key: str
    min_weight: Decimal | None
    target_weight: Decimal | None
    max_weight: Decimal | None
    priority: int

    model_config = {"from_attributes": True}


class TargetAllocationRuleUpsertRequest(BaseModel):
    dimension_type: str
    dimension_key: str
    min_weight: Decimal | None = None
    target_weight: Decimal | None = None
    max_weight: Decimal | None = None
    priority: int = 0

    @field_validator("dimension_type")
    @classmethod
    def dimension_type_valid(cls, value: str) -> str:
        if value not in TARGET_ALLOCATION_DIMENSIONS:
            raise ValueError(
                f"dimension_type deve ser um de: {', '.join(TARGET_ALLOCATION_DIMENSIONS)}"
            )
        return value
