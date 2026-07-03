"""Contrato de entrada e configuração do Decision Engine (Volume 7).

`DecisionInput` é o dado já tratado por ativo (LG Score, pesos,
confiança). `DecisionConfig` reúne os limites de alocação do Volume 7
§7, parametrizáveis mas com defaults do MVP.

A engine é pura: não acessa banco nem rede. O serviço resolve os
inputs (Portfolio Engine + LG Score Engine) e entrega esta estrutura.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DecisionInput:
    """Dados de um ativo candidato a receber aporte.

    `conviction_score`/`class_drift_pct` são usados apenas pelo Decision
    Engine 2.0 (`recommend_v2`, Sprint 18) — permanecem `None` por padrão
    para não afetar o `recommend()` v1, que continua usando só `lg_score`.
    """

    ticker: str
    asset_class: str
    lg_score: Decimal  # 0..100
    confidence: Decimal  # 0..1
    current_weight: Decimal  # fração 0..1 (peso atual na carteira)
    target_weight: Decimal | None = None  # fração 0..1, se houver política

    # Sprint 18 (Decision Engine 2.0):
    conviction_score: Decimal | None = None  # 0..100, LG Conviction Score v2 (Sprint 17)
    # peso atual do ativo menos peso-alvo da CLASSE do ativo (Target Allocation
    # Engine, Sprint 17); negativo = classe subalocada. None = sem meta configurada.
    class_drift_pct: Decimal | None = None


@dataclass(frozen=True)
class DecisionConfig:
    """Limites de alocação do aporte (Volume 7, seção 7)."""

    max_single_weight: Decimal = Decimal("0.50")  # máx. 50% do aporte em um ativo
    min_single_weight: Decimal = Decimal("0.10")  # mín. 10% por ativo selecionado
    # Limite de concentração: ativo com peso atual acima disto não recebe aporte.
    over_concentration_limit: Decimal = Decimal("0.30")

    def assets_for_amount(self, amount: Decimal) -> int:
        """Nº máximo de ativos conforme a faixa do aporte (Volume 7, seção 7)."""
        if amount <= Decimal("500"):
            return 2
        if amount <= Decimal("1000"):
            return 4
        if amount <= Decimal("3000"):
            return 6
        return 8


DEFAULT_CONFIG = DecisionConfig()
