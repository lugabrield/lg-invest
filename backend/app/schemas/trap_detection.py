"""Schema de saída do Trap Detection Engine (Sprint 26, Fase 3).

Um "flag" nunca é uma recomendação de compra/venda — é um sinal de que
uma leitura ingênua de um único múltiplo (P/L baixo = barato, P/VP baixo
= barato, etc.) pode estar enganosa neste ativo específico, dado o resto
do quadro fundamentalista. Cada flag documenta o que foi observado
(`affected_metric`, `explanation`), o quão sério é (`severity`), como
isso deveria pesar na leitura do score/confiança (`impact_on_score`) e o
que vale a pena investigar (`recommended_interpretation` — sempre em
termos de "investigar", nunca "vender"/"comprar").
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

TRAP_SEVERITY_LOW = "baixa"
TRAP_SEVERITY_MEDIUM = "média"
TRAP_SEVERITY_HIGH = "alta"
TRAP_SEVERITIES = (TRAP_SEVERITY_LOW, TRAP_SEVERITY_MEDIUM, TRAP_SEVERITY_HIGH)

# Os 7 flags nomeados do Trap Detection Engine (Sprint 26). Os 5 primeiros
# se aplicam a ações (Fase 3); os 2 últimos (High DY Trap, FII Yield Trap)
# são específicos de FIIs/REITs (Fase 4) — cada um só roda para a classe
# de ativo correspondente (`engines/trap_detection/engine.py` decide isso).
TRAP_TYPE_LOW_PE = "low_pe_trap"
TRAP_TYPE_LOW_PB = "low_pb_trap"
TRAP_TYPE_GROWTH_OVERPRICED = "growth_overpriced_trap"
TRAP_TYPE_LEVERAGE = "leverage_trap"
TRAP_TYPE_DATA_QUALITY = "data_quality_trap"
TRAP_TYPE_HIGH_DY = "high_dy_trap"
TRAP_TYPE_FII_YIELD = "fii_yield_trap"
TRAP_TYPES = (
    TRAP_TYPE_LOW_PE,
    TRAP_TYPE_LOW_PB,
    TRAP_TYPE_GROWTH_OVERPRICED,
    TRAP_TYPE_LEVERAGE,
    TRAP_TYPE_DATA_QUALITY,
    TRAP_TYPE_HIGH_DY,
    TRAP_TYPE_FII_YIELD,
)

# Penalidade de confiança (fração, 0..1) aplicada por severidade — usada
# pelo engine para computar `confidence_penalty` de forma consistente e
# auditável (nunca inventada por flag; sempre a mesma tabela).
CONFIDENCE_PENALTY_BY_SEVERITY = {
    TRAP_SEVERITY_LOW: Decimal("0.05"),
    TRAP_SEVERITY_MEDIUM: Decimal("0.10"),
    TRAP_SEVERITY_HIGH: Decimal("0.20"),
}


class TrapFlag(BaseModel):
    """Um sinal de possível armadilha de valuation — nunca uma recomendação."""

    trap_type: str  # ver TRAP_TYPES
    label: str  # nome legível, ex.: "Armadilha do P/L baixo"
    severity: str  # ver TRAP_SEVERITIES
    affected_metric: str  # campo de fundamentos que disparou o flag, ex.: "pe_ratio"
    explanation: str  # por que foi disparado, com os números observados
    impact_on_score: str  # como isso deveria pesar na leitura do score/confiança
    recommended_interpretation: str  # o que investigar — nunca "vender"/"comprar"
    confidence_penalty: Decimal  # ver CONFIDENCE_PENALTY_BY_SEVERITY


class TrapDetectionResult(BaseModel):
    """Resultado da varredura de armadilhas de valuation de um ativo.

    `confidence_penalty` é a soma das penalidades de cada flag (capada em
    1.0) — quem consome este resultado (ex.: Decision Engine v3, Fase 6)
    deve SUBTRAIR essa fração da confiança existente, nunca usar os flags
    para bloquear ou recomendar uma ação diretamente (Volume — "flags
    reduzem score/confiança, nunca disparam compra/venda")."""

    ticker: str
    asset_class: str
    flags: list[TrapFlag] = []
    confidence_penalty: Decimal = Decimal("0")
    reason: str | None = None  # motivo geral quando fora de escopo

    @property
    def has_traps(self) -> bool:
        return len(self.flags) > 0
