"""Bandas de valuation por múltiplo e classe de ativo (Sprint 15).

Heurística MVP própria, com faixas fixas (não ajustadas por setor,
crescimento nem ciclo econômico) — um ponto de partida simples e
auditável, não uma recomendação. Direção importa: para P/L, P/VP e
EV/EBITDA, "mais barato" é um número MENOR; para Dividend Yield de
FII/REIT, "mais barato" (mais atrativo) é um número MAIOR.

Uma sprint futura pode substituir bandas fixas por comparação com a
própria série histórica do ativo ou com pares do mesmo setor — fora do
escopo aqui.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# Classes de ativo sem múltiplos de empresa aplicáveis — mesma lista do
# Fundamentals Service (Sprint 13), reafirmada aqui deliberadamente para
# o Valuation Engine não depender de símbolo de outra camada.
NOT_APPLICABLE_CLASSES = ("crypto", "cash", "bond", "etf")

# Forma positiva de NOT_APPLICABLE_CLASSES — usada pela tela Inteligência
# (Sprint 22) para excluir cripto/renda fixa/caixa/ETF dos rankings de
# valuation ("mais baratos"/"mais caros"), já que para essas classes o
# valor exibido é o proxy de preço v1 (fallback do pilar), não uma
# classificação real de múltiplos.
APPLICABLE_CLASSES = ("stock", "fii", "reit")

LOWER_IS_CHEAPER = "lower_is_cheaper"
HIGHER_IS_CHEAPER = "higher_is_cheaper"


@dataclass(frozen=True)
class MetricBand:
    field: str
    label: str
    direction: str  # LOWER_IS_CHEAPER | HIGHER_IS_CHEAPER
    cheap_threshold: Decimal
    expensive_threshold: Decimal
    applicable_classes: tuple[str, ...]

    def classify(self, value: Decimal) -> str:
        if self.direction == LOWER_IS_CHEAPER:
            if value <= self.cheap_threshold:
                return "barato"
            if value >= self.expensive_threshold:
                return "caro"
            return "neutro"
        # HIGHER_IS_CHEAPER
        if value >= self.cheap_threshold:
            return "barato"
        if value <= self.expensive_threshold:
            return "caro"
        return "neutro"


# Ações brasileiras/americanas (stock)
_STOCK_CLASSES = ("stock",)
# FIIs e REITs — mesma lógica, dividend yield "puxa" o veredito
_INCOME_REAL_ESTATE_CLASSES = ("fii", "reit")

METRIC_BANDS: tuple[MetricBand, ...] = (
    MetricBand(
        field="pe_ratio",
        label="P/L",
        direction=LOWER_IS_CHEAPER,
        cheap_threshold=Decimal("12"),
        expensive_threshold=Decimal("20"),
        applicable_classes=_STOCK_CLASSES,
    ),
    MetricBand(
        field="pb_ratio",
        label="P/VP",
        direction=LOWER_IS_CHEAPER,
        cheap_threshold=Decimal("1.5"),
        expensive_threshold=Decimal("3"),
        applicable_classes=_STOCK_CLASSES,
    ),
    MetricBand(
        field="ev_ebitda",
        label="EV/EBITDA",
        direction=LOWER_IS_CHEAPER,
        cheap_threshold=Decimal("8"),
        expensive_threshold=Decimal("14"),
        applicable_classes=_STOCK_CLASSES,
    ),
    MetricBand(
        field="pb_ratio",
        label="P/VP",
        direction=LOWER_IS_CHEAPER,
        cheap_threshold=Decimal("0.9"),
        expensive_threshold=Decimal("1.1"),
        applicable_classes=_INCOME_REAL_ESTATE_CLASSES,
    ),
    MetricBand(
        field="dividend_yield",
        label="Dividend Yield",
        direction=HIGHER_IS_CHEAPER,
        cheap_threshold=Decimal("0.09"),
        expensive_threshold=Decimal("0.06"),
        applicable_classes=_INCOME_REAL_ESTATE_CLASSES,
    ),
)


def bands_for_asset_class(asset_class: str) -> tuple[MetricBand, ...]:
    return tuple(band for band in METRIC_BANDS if asset_class in band.applicable_classes)
