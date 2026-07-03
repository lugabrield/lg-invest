"""Pesos do LG Score (Volume 6, seção 4).

LG_SCORE = 0.35*Q + 0.25*V + 0.20*G + 0.10*R + 0.10*A

Parametrizável por design (perfis futuros: conservador, agressivo,
renda, crescimento...), mas fixo no MVP. A soma deve ser 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LGScoreWeights:
    quality: float = 0.35
    valuation: float = 0.25
    growth: float = 0.20
    risk: float = 0.10
    allocation: float = 0.10

    def validate(self) -> None:
        total = self.quality + self.valuation + self.growth + self.risk + self.allocation
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"Os pesos do LG Score devem somar 1.0 (atual: {total}).")


DEFAULT_WEIGHTS = LGScoreWeights()
