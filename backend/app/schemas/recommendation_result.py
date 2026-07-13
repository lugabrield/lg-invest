"""Schemas de saída do Decision Engine (Volume 7 §4; Volume 18 §10).

Estruturas serializáveis com a distribuição recomendada, justificativa
por ativo, score de compra, alertas, ativos ignorados, nível de
confiança e o log de auditoria completo.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

# Sprint 25, Parte 4 (explicabilidade do Aporte v3): mesmos rótulos de
# origem já usados por `engines/target_allocation/precedence.py` para o
# limite efetivo em Configurações — reaproveitados aqui para o motivo de
# bloqueio do Decision Engine ficar com o MESMO vocabulário em toda a
# aplicação, em vez de dois jeitos diferentes de dizer a mesma coisa.
BLOCK_SOURCE_MANUAL = "bloqueio_manual"
BLOCK_SOURCE_OVER_CONCENTRATION = "sobreconcentracao"
BLOCK_SOURCE_DETAILED_RULE = "regra_detalhada"
BLOCK_SOURCE_POLICY = "politica_geral"
BLOCK_SOURCES = (
    BLOCK_SOURCE_MANUAL,
    BLOCK_SOURCE_OVER_CONCENTRATION,
    BLOCK_SOURCE_DETAILED_RULE,
    BLOCK_SOURCE_POLICY,
)


class ScoreFactor(BaseModel):
    """Um componente (aditivo) do score de compra, para exibição
    estruturada (Sprint 25, Parte 4) — mesma conta que já compunha o texto
    livre em `reasons`, só que com peso/valor/contribuição explícitos em
    vez de escondidos dentro de uma frase. Nunca decide nada sozinho: é
    só a mesma aritmética já usada por `buy_score`, exposta.

    `weight` fica `None` na linha de ajuste por confiança do dado (v3) —
    ali o "fator" não soma ao score bruto, ele ESCALA o total; `contribution`
    nesse caso é o delta (raw_score -> score), podendo ser negativo."""

    label: str
    weight: Decimal | None = None
    value: Decimal
    contribution: Decimal


class RecommendationItem(BaseModel):
    ticker: str
    amount: Decimal
    weight: Decimal  # fração do aporte
    buy_score: Decimal  # 0..1
    lg_score: Decimal  # 0..100
    conviction_score: Decimal | None = None  # 0..100, só preenchido pelo Decision Engine 2.0
    item_confidence: Decimal | None = None  # 0..1 — confiança do dado usado neste ativo (Sprint 21)
    reasons: list[str]
    # Sprint 25, Parte 4: breakdown estruturado dos mesmos fatores de
    # `reasons` (label/peso/valor/contribuição) — soma das contribuições
    # é igual a `buy_score` (v1/v2) ou ao `raw_score` pré-confiança + o
    # delta da linha de confiança (v3). Vazio quando a versão do motor
    # ainda não popula breakdown (nunca inventado).
    score_breakdown: list[ScoreFactor] = []
    # Sprint 25, Parte 2.5: True quando este item veio da Watchlist/Radar
    # (ainda não é posição) e não do Portfolio Engine — a UI usa isto
    # para separar visualmente "Já tenho" de "Novo candidato".
    is_new_from_watchlist: bool = False
    # Sprint 25, Parte 4: explica por que um candidato novo da Watchlist
    # está nesta recomendação (teto reduzido, decisão de iniciar posição
    # sempre do usuário) — `None` para itens que já são posição existente.
    watchlist_reason: str | None = None


class CappedDimensionResult(BaseModel):
    """Uma dimensão (classe/moeda/país/ativo/exposição internacional) que
    teve o aporte cortado pelo Post-Allocation Constraints Engine
    (Sprint 29) porque o peso RESULTANTE pós-aporte ultrapassaria o
    máximo configurado — nunca detectado apenas pelo peso ANTES do
    aporte. Ver `engines/decision/post_allocation.py`."""

    dimension_type: str
    dimension_key: str
    label: str
    weight_before: Decimal
    weight_after: Decimal
    max_weight: Decimal
    source: str  # "regra_detalhada" | "politica_geral"


class IgnoredItem(BaseModel):
    ticker: str
    reason: str
    # Sprint 25, Parte 4: qual camada gerou o bloqueio — ver `BLOCK_SOURCES`
    # acima. `None` preserva compatibilidade com qualquer chamador antigo
    # que ainda não populava a origem.
    block_source: str | None = None


class DecisionAudit(BaseModel):
    """Log auditável da recomendação (Volume 18, seção 10)."""

    contribution_amount: Decimal
    eligible_tickers: list[str]
    blocked_tickers: list[str]
    model_version: str
    weights: dict[str, float]


class RecommendationResult(BaseModel):
    contribution_amount: Decimal
    allocated_amount: Decimal  # soma efetivamente distribuída (<= contribution_amount)
    items: list[RecommendationItem]
    ignored: list[IgnoredItem]
    alerts: list[str]
    confidence: Decimal  # 0..1
    confidence_label: str
    explanation: str  # resumo em linguagem natural
    audit: DecisionAudit
    # Sprint 29: dimensões (classe/moeda/país/ativo/exposição
    # internacional) que tiveram o aporte cortado pelo Post-Allocation
    # Constraints Engine para não ultrapassar o máximo configurado
    # DEPOIS do aporte — vazio quando `recommend_v3` roda sem
    # `portfolio_value_before` (nenhuma simulação pós-aporte disponível)
    # ou quando nenhuma dimensão bateu no limite.
    capped_dimensions: list[CappedDimensionResult] = []

    model_config = {"from_attributes": True}
