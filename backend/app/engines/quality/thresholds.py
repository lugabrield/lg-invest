"""Bandas de qualidade por indicador e classe de ativo (Sprint 16).

Heurística MVP própria, com faixas fixas — um ponto de partida simples
e auditável, não uma recomendação. "Melhor" é sempre um ROE/margem
MAIOR ou uma dívida/EBITDA MENOR.

Escopo desta sprint: só ações (`stock`), onde ROE/margem/alavancagem
são indicadores padrão. FIIs, REITs e outras classes exigiriam
indicadores próprios (ex.: vacância, qualidade de inquilinos) fora do
escopo do MVP — recebem "indeterminado" com razão explícita.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

APPLICABLE_CLASSES = ("stock",)

HIGHER_IS_BETTER = "higher_is_better"
LOWER_IS_BETTER = "lower_is_better"


@dataclass(frozen=True)
class QualityBand:
    field: str
    label: str
    direction: str  # HIGHER_IS_BETTER | LOWER_IS_BETTER
    strong_threshold: Decimal
    weak_threshold: Decimal

    def classify(self, value: Decimal) -> str:
        if self.direction == HIGHER_IS_BETTER:
            if value >= self.strong_threshold:
                return "forte"
            if value <= self.weak_threshold:
                return "fraca"
            return "média"
        # LOWER_IS_BETTER
        if value <= self.strong_threshold:
            return "forte"
        if value >= self.weak_threshold:
            return "fraca"
        return "média"


QUALITY_BANDS: tuple[QualityBand, ...] = (
    QualityBand(
        field="roe",
        label="ROE",
        direction=HIGHER_IS_BETTER,
        strong_threshold=Decimal("0.15"),
        weak_threshold=Decimal("0.08"),
    ),
    QualityBand(
        field="net_margin",
        label="Margem líquida",
        direction=HIGHER_IS_BETTER,
        strong_threshold=Decimal("0.15"),
        weak_threshold=Decimal("0.05"),
    ),
    QualityBand(
        field="debt_to_ebitda",
        label="Dívida/EBITDA",
        direction=LOWER_IS_BETTER,
        strong_threshold=Decimal("2"),
        weak_threshold=Decimal("4"),
    ),
)
