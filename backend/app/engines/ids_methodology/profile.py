"""Perfil do investidor e pesos por classe de ativo (IDS Methodology, Sprint 12).

Codifica de forma explícita e parametrizável — não apenas em texto solto
no Journal — o perfil de investidor de longo prazo descrito no projeto:
Buy & Hold, horizonte superior a 50 anos, foco em construção de
patrimônio e independência financeira, aceitação de volatilidade, busca
por maior exposição internacional ao longo do tempo e preferência por
maximização de patrimônio sobre renda imediata.

Cada perfil por classe de ativo é um conjunto de pesos
(`IdsPillarWeights`) que reflete o que importa mais para aquela classe
dentro dessa filosofia: ações e ETFs pesam mais Growth/Capital
Reinvestment (juros compostos de longo prazo); FIIs, Renda Fixa e Cripto
pesam mais Risco (previsibilidade ou volatilidade, conforme o caso).
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.engines.ids_methodology.weights import DEFAULT_WEIGHTS, IdsPillarWeights


@dataclass(frozen=True)
class InvestorProfile:
    """Perfil de investidor codificado (parâmetros, não texto solto).

    Hoje é metadado de referência (documentação viva do perfil por trás
    dos pesos); consumido por futuras engines de valuation/fundamentos
    para ajustar premissas de longo prazo (ex.: taxa de desconto,
    horizonte de projeção).
    """

    strategy: str = "buy_and_hold"
    horizon_years: int = 50
    accepts_high_volatility: bool = True
    prioritizes_growth_over_income: bool = True
    international_exposure_target: float = 0.40  # meta de longo prazo, não um limite rígido


DEFAULT_INVESTOR_PROFILE = InvestorProfile()

# Perfis de peso por classe de ativo. Cada um deve somar 1.0
# (`IdsPillarWeights.validate()` garante isso quando o engine calcula).
ASSET_CLASS_PROFILES: dict[str, IdsPillarWeights] = {
    "stock": IdsPillarWeights(
        quality=0.30, valuation=0.25, growth=0.25, risk=0.10, capital_reinvestment=0.10
    ),
    "etf": IdsPillarWeights(
        quality=0.30, valuation=0.20, growth=0.25, risk=0.15, capital_reinvestment=0.10
    ),
    "fii": IdsPillarWeights(
        quality=0.35, valuation=0.25, growth=0.10, risk=0.25, capital_reinvestment=0.05
    ),
    "reit": IdsPillarWeights(
        quality=0.35, valuation=0.25, growth=0.10, risk=0.25, capital_reinvestment=0.05
    ),
    "crypto": IdsPillarWeights(
        quality=0.20, valuation=0.15, growth=0.20, risk=0.40, capital_reinvestment=0.05
    ),
    "bond": IdsPillarWeights(
        quality=0.40, valuation=0.15, growth=0.05, risk=0.35, capital_reinvestment=0.05
    ),
    "cash": IdsPillarWeights(
        quality=0.50, valuation=0.10, growth=0.05, risk=0.30, capital_reinvestment=0.05
    ),
}


def weights_for_asset_class(asset_class: str) -> IdsPillarWeights:
    """Devolve os pesos do perfil da classe, ou o padrão se a classe for desconhecida."""
    return ASSET_CLASS_PROFILES.get(asset_class, DEFAULT_WEIGHTS)
