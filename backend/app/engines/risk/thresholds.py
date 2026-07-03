"""Bandas de risco por indicador e classe de ativo (Sprint 16).

Heurística MVP própria, com faixas fixas. Em ambos os indicadores,
"menor" é "menos arriscado" — não há inversão de direção aqui, ao
contrário do Valuation Engine (onde dividend yield mais alto é mais
barato).

Escopo desta sprint: dívida/EBITDA (ações, FIIs e REITs) e beta
(apenas ações — FIIs/REITs raramente têm beta confiável no yfinance).
Cripto, caixa e Tesouro Direto ficam fora: risco desses ativos exige
metodologia própria, fora do escopo do MVP.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

NOT_APPLICABLE_CLASSES = ("crypto", "cash", "bond")


@dataclass(frozen=True)
class RiskBand:
    field: str
    label: str
    low_threshold: Decimal
    high_threshold: Decimal
    applicable_classes: tuple[str, ...]

    def classify(self, value: Decimal) -> str:
        if value <= self.low_threshold:
            return "baixo"
        if value >= self.high_threshold:
            return "alto"
        return "médio"


_LEVERAGE_CLASSES = ("stock", "fii", "reit")
_MARKET_RISK_CLASSES = ("stock",)

RISK_BANDS: tuple[RiskBand, ...] = (
    RiskBand(
        field="debt_to_ebitda",
        label="Dívida/EBITDA",
        low_threshold=Decimal("2"),
        high_threshold=Decimal("4"),
        applicable_classes=_LEVERAGE_CLASSES,
    ),
    RiskBand(
        field="beta",
        label="Beta",
        low_threshold=Decimal("0.8"),
        high_threshold=Decimal("1.2"),
        applicable_classes=_MARKET_RISK_CLASSES,
    ),
)


def bands_for_asset_class(asset_class: str) -> tuple[RiskBand, ...]:
    return tuple(band for band in RISK_BANDS if asset_class in band.applicable_classes)
