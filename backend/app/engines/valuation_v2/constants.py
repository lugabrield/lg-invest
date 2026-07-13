"""Premissas macro do Valuation Engine 2.0 (Sprint 26, Fase 2).

Estes números NÃO são dados do ativo (nunca violam a regra "nunca
inventar dado" — Volume 18 §8, que se refere a dados de EMPRESA/ativo,
como ROIC ou FCF ausentes). São premissas macroeconômicas ilustrativas,
do mesmo tipo que qualquer analista fundamentalista precisa declarar
explicitamente para rodar um DCF (Damodaran publica tabelas equivalentes
de risk-free rate e equity risk premium por país/moeda). Ficam isoladas
neste módulo, documentadas, para que:

1. Nunca sejam confundidas com dado real coletado do provider.
2. Sejam fáceis de revisar/atualizar sem tocar na lógica de cálculo.
3. Toda estimativa que as usa deixe isso explícito em `assumptions`
   (`schemas/valuation_v2.py::ValuationScenario`).

Não representam recomendação de alocação nem previsão do LG INVEST sobre
a economia — são um ponto de partida conservador e auditável.
"""

from __future__ import annotations

from decimal import Decimal

# --- Taxa livre de risco e prêmio de risco de mercado, por moeda -----------
# Proxies de longo prazo (não são cotações ao vivo). BRL usa uma taxa mais
# alta refletindo o prêmio estrutural de juros/inflação do Brasil; USD usa
# a média histórica de longo prazo do Treasury americano.
_MACRO_BY_CURRENCY = {
    "BRL": {"risk_free_rate": Decimal("0.10"), "equity_risk_premium": Decimal("0.055")},
    "USD": {"risk_free_rate": Decimal("0.045"), "equity_risk_premium": Decimal("0.05")},
}
_DEFAULT_CURRENCY = "USD"  # fallback conservador quando a moeda do ativo é desconhecida

# Crescimento de perpetuidade nunca pode superar um proxy de crescimento
# nominal de longo prazo da economia — evita terminal value inflado
# (armadilha clássica de DCF ingênuo).
_TERMINAL_GROWTH_CAP_BY_CURRENCY = {
    "BRL": Decimal("0.045"),
    "USD": Decimal("0.025"),
}

# Beta padrão (mercado) quando o ativo não tem beta reportado — nunca
# inventamos um beta "customizado" para a empresa, usamos o beta neutro
# de mercado (1.0) e sinalizamos isso explicitamente via warning.
DEFAULT_BETA = Decimal("1.0")

# Horizonte explícito de projeção do DCF simplificado (anos).
DCF_PROJECTION_YEARS = 5

# Variação de crescimento entre cenários pessimista/otimista em relação ao
# cenário base (pontos percentuais, em fração).
SCENARIO_GROWTH_SPREAD = Decimal("0.05")

# Variação de taxa de desconto entre cenários (pontos percentuais, em fração).
SCENARIO_DISCOUNT_SPREAD = Decimal("0.015")

# Limites de sanidade para a taxa de crescimento assumida no DCF — evita
# extrapolar um CAGR histórico extremo (ex.: recuperação pontual de
# lucro) para 5 anos de projeção sem qualquer correção.
GROWTH_RATE_SANE_MIN = Decimal("-0.30")
GROWTH_RATE_SANE_MAX = Decimal("0.40")

# Margem de segurança exigida, escalada pela qualidade do ativo (Volume —
# "margem de segurança deve ser proporcional à qualidade": ativos de alta
# qualidade exigem uma margem menor; ativos de qualidade baixa/indeterminada
# exigem uma margem maior, porque o risco de erro na estimativa é maior.
REQUIRED_MARGIN_OF_SAFETY_BY_QUALITY = {
    "alta": Decimal("0.15"),
    "média": Decimal("0.25"),
    "baixa": Decimal("0.35"),
    "indeterminado": Decimal("0.30"),
}
_DEFAULT_REQUIRED_MARGIN_OF_SAFETY = Decimal("0.30")

# Divergência entre o método de múltiplos e o DCF base acima da qual a
# confiança da estimativa é reduzida (metodologias discordando fortemente
# é, em si, um sinal de baixa confiança — não uma média que os concilia).
HIGH_DISPERSION_THRESHOLD = Decimal("0.40")

# Divergência entre o Graham Number (checagem de sanidade) e o valor base
# combinado acima da qual emitimos aviso — o Graham nunca corrige a
# estimativa, só sinaliza que vale a pena investigar o contexto.
GRAHAM_DIVERGENCE_WARNING_THRESHOLD = Decimal("0.40")


def macro_assumptions(currency: str) -> dict:
    return _MACRO_BY_CURRENCY.get(currency, _MACRO_BY_CURRENCY[_DEFAULT_CURRENCY])


def terminal_growth_cap(currency: str) -> Decimal:
    return _TERMINAL_GROWTH_CAP_BY_CURRENCY.get(
        currency, _TERMINAL_GROWTH_CAP_BY_CURRENCY[_DEFAULT_CURRENCY]
    )


def required_margin_of_safety(quality_classification: str | None) -> Decimal:
    if quality_classification is None:
        return _DEFAULT_REQUIRED_MARGIN_OF_SAFETY
    return REQUIRED_MARGIN_OF_SAFETY_BY_QUALITY.get(
        quality_classification, _DEFAULT_REQUIRED_MARGIN_OF_SAFETY
    )
