"""Reverse DCF — crescimento implícito no preço atual (Sprint 26, Fase 2).

Em vez de estimar o valor justo a partir de premissas de crescimento,
inverte a pergunta: "que taxa de crescimento constante, no mesmo DCF
simplificado, faria o valor justo por ação coincidir com o preço atual de
mercado?". Não é uma previsão do LG INVEST — é uma leitura explícita da
expectativa que o mercado já está precificando, útil para avaliar se essa
expectativa é razoável frente ao histórico do próprio ativo.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.valuation_v2.dcf import dcf_fair_value_per_share

_MAX_ITERATIONS = 60
_TOLERANCE = Decimal("0.01")  # 1 centavo de convergência


def implied_growth_rate(
    current_price: Decimal,
    fcf0: Decimal,
    discount_rate_value: Decimal,
    terminal_growth: Decimal,
    shares_outstanding: Decimal,
    net_debt: Decimal | None,
    years: int,
    growth_low: Decimal,
    growth_high: Decimal,
) -> tuple[Decimal | None, str | None]:
    """Bisseção sobre a taxa de crescimento no mesmo DCF simplificado. A
    função valor-justo(g) é monotonicamente crescente em `g` dentro da
    faixa considerada (mais crescimento -> mais fluxo de caixa projetado
    -> valor maior), então bisseção converge sem precisar de derivadas."""

    def fair_value_at(g: Decimal) -> Decimal | None:
        value, _ = dcf_fair_value_per_share(
            fcf0=fcf0,
            growth_rate=g,
            discount_rate_value=discount_rate_value,
            terminal_growth=terminal_growth,
            shares_outstanding=shares_outstanding,
            net_debt=net_debt,
            years=years,
        )
        return value

    low, high = growth_low, growth_high
    value_low = fair_value_at(low)
    value_high = fair_value_at(high)

    if value_low is None or value_high is None:
        return None, "modelo de DCF não converge nos limites de crescimento considerados"

    if current_price <= value_low:
        return low, None
    if current_price >= value_high:
        return None, (
            "preço atual implica expectativa de crescimento acima do limite considerado "
            "pelo modelo simplificado — expectativa de mercado extremamente otimista"
        )

    mid = low
    for _ in range(_MAX_ITERATIONS):
        mid = (low + high) / 2
        value_mid = fair_value_at(mid)
        if value_mid is None:
            return None, "modelo de DCF não converge no ponto médio considerado"
        if abs(value_mid - current_price) <= _TOLERANCE:
            return mid, None
        if value_mid < current_price:
            low = mid
        else:
            high = mid

    return mid, None
