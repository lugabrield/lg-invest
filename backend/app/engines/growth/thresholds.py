"""Bandas de crescimento por CAGR (Sprint 16).

Heurística MVP própria, com faixas fixas — não ajustadas por setor,
tamanho ou ciclo de vida do ativo. Aplicável a qualquer classe com CAGR
calculável pelo Fundamentals Engine (na prática, hoje, `stock`, já que
é a classe com histórico de demonstrativos coletado).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class GrowthBand:
    field: str
    label: str
    strong_threshold: Decimal
    weak_threshold: Decimal

    def classify(self, value: Decimal) -> str:
        if value >= self.strong_threshold:
            return "forte"
        if value <= self.weak_threshold:
            return "fraca"
        return "moderada"


GROWTH_BANDS: tuple[GrowthBand, ...] = (
    GrowthBand(
        field="revenue_cagr",
        label="CAGR de receita",
        strong_threshold=Decimal("0.15"),
        weak_threshold=Decimal("0.05"),
    ),
    GrowthBand(
        field="net_income_cagr",
        label="CAGR de lucro líquido",
        strong_threshold=Decimal("0.15"),
        weak_threshold=Decimal("0.05"),
    ),
)
