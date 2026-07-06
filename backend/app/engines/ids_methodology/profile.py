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

# Perfis de peso por classe de ativo (Sprint 12; revisado Sprint 21).
# Cada um deve somar 1.0 (`IdsPillarWeights.validate()` garante isso
# quando o engine calcula).
#
# Sprint 21 revisou os pesos para refletir a ênfase pedida por classe,
# mas manteve os MESMOS 5 pilares (Quality/Valuation/Growth/Risk/Capital
# Reinvestment) para todas as classes — em vez de criar pilares
# conceitualmente diferentes por classe (ex.: "Diversificação" para ETF,
# "Custo/Liquidez" para ETF, "Papel na carteira" para Renda Fixa). Isso é
# uma decisão deliberada: pilares novos exigiriam dados que a
# plataforma não coleta hoje (nº de holdings do ETF, expense ratio,
# tracking error, rating de crédito do título) — inventar esses números
# violaria o princípio de não fabricar dados (Volume 18 §8). Onde a
# metodologia original pedia uma dimensão sem pilar equivalente, ela foi
# dobrada dentro do pilar mais próximo, documentado abaixo. Ver
# docs/IDS_METHODOLOGY.md para o racional completo por classe.
ASSET_CLASS_PROFILES: dict[str, IdsPillarWeights] = {
    # Ações: pesos-padrão do perfil de longo prazo (igual a DEFAULT_WEIGHTS).
    "stock": IdsPillarWeights(
        quality=0.30, valuation=0.25, growth=0.20, risk=0.15, capital_reinvestment=0.10
    ),
    # ETF: Quality/Valuation tradicionais quase sempre "indeterminado" (sem
    # múltiplos de empresa aplicáveis) — Risk carrega o peso maior como
    # proxy de diversificação/volatilidade; Growth e Reinvestment ainda
    # contam quando o ETF é de acumulação com fundamentos parciais.
    "etf": IdsPillarWeights(
        quality=0.15, valuation=0.10, growth=0.20, risk=0.35, capital_reinvestment=0.20
    ),
    # FII: "Income/Yield" da metodologia original é capturado pelo pilar de
    # Valuation (dividend yield já é uma das duas métricas de valuation
    # usadas para FII/REIT, ver engines/valuation/thresholds.py) — por
    # isso Valuation concentra peso maior. Growth quase sempre
    # indeterminado (FII não reporta CAGR de receita/lucro) e Capital
    # Reinvestment não aplicável (obrigação regulatória de distribuir).
    "fii": IdsPillarWeights(
        quality=0.30, valuation=0.40, growth=0.05, risk=0.20, capital_reinvestment=0.05
    ),
    # REIT: mesmo racional do FII, mas Growth é mantido em peso real
    # porque REITs americanos costumam reportar CAGR de receita/lucro
    # (US GAAP) — diferente de FII brasileiro.
    "reit": IdsPillarWeights(
        quality=0.30, valuation=0.35, growth=0.15, risk=0.15, capital_reinvestment=0.05
    ),
    # Cripto: Risk concentra a maior parte do peso (risco de balanço
    # tradicional não existe; a plataforma classifica risco "alto" por
    # política, não por indicador — ver engines/risk/engine.py — o que
    # também cobre a noção de "limite de exposição" da metodologia
    # original). Growth = proxy de momentum de preço (fallback v1, já
    # que não há CAGR de receita/lucro). Quality/Valuation = proxies de
    # preço v1 (estabilidade/caro-barato), lidas como "tese
    # macro"/"confiança de dado" da metodologia original.
    "crypto": IdsPillarWeights(
        quality=0.10, valuation=0.10, growth=0.10, risk=0.65, capital_reinvestment=0.05
    ),
    # Renda fixa (Tesouro Direto etc.): taxa real/duration + risco de
    # crédito/emissor + liquidez da metodologia original são todos
    # dimensões de risco — concentradas no pilar Risk. "Papel na
    # carteira" (função de proteção/estabilidade) é lido no pilar
    # Quality. Growth e Capital Reinvestment não se aplicam a título de
    # renda fixa.
    "bond": IdsPillarWeights(
        quality=0.20, valuation=0.10, growth=0.00, risk=0.70, capital_reinvestment=0.00
    ),
    "cash": IdsPillarWeights(
        quality=0.50, valuation=0.10, growth=0.05, risk=0.30, capital_reinvestment=0.05
    ),
}


def weights_for_asset_class(asset_class: str) -> IdsPillarWeights:
    """Devolve os pesos do perfil da classe, ou o padrão se a classe for desconhecida."""
    return ASSET_CLASS_PROFILES.get(asset_class, DEFAULT_WEIGHTS)
