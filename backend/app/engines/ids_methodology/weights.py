"""Pesos do LG Conviction Score (IDS Methodology, Sprint 12).

CONVICTION_SCORE = 0.30*Quality + 0.25*Valuation + 0.20*Growth
                  + 0.15*Risk + 0.10*CapitalReinvestment

Pesos-padrão para o perfil de investidor de longo prazo do projeto
(Buy & Hold, horizonte 50+ anos, foco em qualidade, crescimento
sustentável e reinvestimento de capital acima de renda imediata) —
ver docs/IDS_METHODOLOGY.md para a explicação completa e os créditos
conceituais. Não reproduzem a fórmula de nenhum investidor ou fundo
específico; são uma síntese própria inspirada em princípios gerais e
amplamente publicados de investimento em qualidade e valuation.

Parametrizável por classe de ativo (ver `profile.py`): FIIs, Renda
Fixa e Cripto usam perfis diferentes deste padrão.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IdsPillarWeights:
    quality: float = 0.30
    valuation: float = 0.25
    growth: float = 0.20
    risk: float = 0.15
    capital_reinvestment: float = 0.10

    def validate(self) -> None:
        total = self.quality + self.valuation + self.growth + self.risk + self.capital_reinvestment
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"Os pesos do LG Conviction Score devem somar 1.0 (atual: {total}).")


DEFAULT_WEIGHTS = IdsPillarWeights()
