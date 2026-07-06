"""Contrato de entrada e configuração do Portfolio Risk Engine
(Sprint 24, Fase 6 — "Risk Engine 2.0").

Não confundir com `engines/risk/` (Sprint 16): aquele é o Risk Engine v1,
que classifica o risco de balanço/mercado de **um ativo individual** a
partir de indicadores fundamentalistas. Este pacote é uma segunda engine,
nova e complementar, que agrega risco no **nível da carteira inteira**:
volatilidade ponderada, concentração (HHI), risco estrutural por classe
(reaproveitando as classificações do Risk Engine v1, nunca recalculando),
e risco de cauda (probabilidade de perda, vinda do Monte Carlo Simulation
Engine da Fase 5). "2.0" aqui significa "segunda geração de risco na
plataforma" (agregado), não uma nova versão que substitui o v1 — os dois
convivem, cada um respondendo a uma pergunta diferente.

A engine é pura: não acessa banco nem rede. O `PortfolioRiskService`
resolve tudo isso e entrega esta estrutura pronta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class AssetRiskSignal:
    """Classificação de risco de um ativo (Risk Engine v1), com o peso
    dele na carteira — usada para o fator de risco estrutural agregado."""

    ticker: str
    asset_class: str
    weight: Decimal  # fração 0..1 do patrimônio
    classification: str  # "baixo" | "médio" | "alto" | "indeterminado"
    confidence: str  # "baixa" | "média" | "alta"


@dataclass(frozen=True)
class PortfolioRiskInput:
    """Estado atual da carteira, pronto para a agregação de risco."""

    concentration_hhi: Decimal  # Herfindahl-Hirschman, 0..1 (já calculado pelo Portfolio Engine)
    effective_number_of_assets: Decimal | None
    international_weight: Decimal  # fração 0..1 (moedas != BRL)
    class_weights: dict[str, Decimal] = field(default_factory=dict)  # fração 0..1 por classe
    class_volatilities: dict[str, Decimal] = field(
        default_factory=dict
    )  # volatilidade anual por classe (mesma fonte do Simulation Engine)
    asset_risk_signals: tuple[AssetRiskSignal, ...] = ()
    probability_of_loss: Decimal | None = None  # do Monte Carlo (Fase 5), opcional
    declared_risk_tolerance: str | None = None  # de InvestmentPolicy.risk_tolerance


@dataclass(frozen=True)
class PortfolioRiskConfig:
    """Pesos de combinação dos 4 fatores de risco (somam 1.0). Se um fator
    não puder ser calculado (dado ausente), os pesos restantes são
    renormalizados entre os fatores disponíveis — nunca inventa o fator
    ausente com um valor default."""

    weight_volatility: Decimal = Decimal("0.35")
    weight_concentration: Decimal = Decimal("0.25")
    weight_asset_class_risk: Decimal = Decimal("0.25")
    weight_drawdown: Decimal = Decimal("0.15")


DEFAULT_CONFIG = PortfolioRiskConfig()
