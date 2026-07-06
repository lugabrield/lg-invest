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

    # --- Sprint 24, Fase 4 (Decision Engine 3.0) --------------------------
    # Pilares individuais do LG Conviction Score (Sprints 14-16), já 0..100
    # e "maior é melhor" (inclusive risk: quanto maior, menor o risco).
    # Nenhum é recalculado aqui — só repassados do ConvictionScoreResult
    # para dar transparência por pilar na explicação do Decision Engine 3.0,
    # em vez de esconder tudo atrás de um único número (conviction_score).
    quality_score: Decimal | None = None
    valuation_score: Decimal | None = None
    growth_score: Decimal | None = None
    risk_score: Decimal | None = None

    currency: str | None = None
    country: str | None = None
    # True quando o ativo conta como exposição internacional (país != "BR")
    # para fins do bônus de internacionalização da Investment Policy.
    is_international: bool = False

    # Sinais já resolvidos do Target Allocation Rule Engine v2 (Sprint 24,
    # Fase 3) aplicáveis a este candidato (dimensões classe/moeda/país/ativo
    # que batem com este ticker). Resolvidos pelo serviço, não pela engine —
    # a engine só lê, nunca consulta banco.
    rule_signals: tuple[AllocationRuleSignal, ...] = ()


@dataclass(frozen=True)
class AllocationRuleSignal:
    """Espelho pontual de `AllocationRuleEvaluation` (Target Allocation Rule
    Engine v2) para uma dimensão aplicável a um candidato específico do
    Decision Engine 3.0 — usado para bônus de aporte e bloqueio, nunca para
    recomendar venda (ver `_gap_status`/regra de ouro em
    `engines/target_allocation/engine.py`)."""

    dimension_type: str
    gap_status: str  # underweight | neutral | overweight | blocked
    contribution_priority: int
    rebalance_required: bool
    extreme_overweight: bool


@dataclass(frozen=True)
class PolicyLimits:
    """Espelho pontual dos limites de `InvestmentPolicy` (Sprint 24, Fase 3)
    relevantes para bloqueio/bônus no Decision Engine 3.0. `None` em
    qualquer campo significa "sem limite configurado" — nunca inventa um
    limite default dentro da engine."""

    max_asset_weight: Decimal | None = None
    max_crypto_weight: Decimal | None = None
    target_fii_max: Decimal | None = None
    target_international_min: Decimal | None = None
    target_international_max: Decimal | None = None


@dataclass(frozen=True)
class PortfolioAggregates:
    """Pesos agregados da carteira inteira — necessários para checar
    limites da Investment Policy que não fazem sentido por ativo isolado
    (ex.: peso TOTAL em cripto vs. `max_crypto_weight`)."""

    crypto_weight: Decimal = Decimal("0")
    fii_weight: Decimal = Decimal("0")
    international_weight: Decimal = Decimal("0")


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
