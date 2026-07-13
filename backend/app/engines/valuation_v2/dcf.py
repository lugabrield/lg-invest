"""DCF simplificado (Sprint 26, Fase 2) — puro, sem I/O.

Modelo de 2 estágios: `DCF_PROJECTION_YEARS` anos de fluxo de caixa livre
crescendo a uma taxa constante, seguidos de valor terminal por
perpetuidade (Gordon growth), descontados a uma taxa via CAPM
simplificado (risk-free + beta x prêmio de risco de mercado). É
"simplificado" porque não modela mudanças de margem, capex ou estrutura
de capital ano a ano — mesma limitação de qualquer DCF didático, mantida
deliberadamente simples e auditável em vez de falsamente precisa.

Ausência de FCF positivo, de ações em circulação ou de taxa de desconto
que exceda o crescimento terminal nunca vira erro nem valor aproximado —
vira `(None, motivo)` (Volume 18 §8).
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.valuation_v2.constants import (
    DCF_PROJECTION_YEARS,
    DEFAULT_BETA,
    macro_assumptions,
)


def capm_discount_rate(beta: Decimal | None, currency: str) -> tuple[Decimal, bool]:
    """Taxa de desconto via CAPM simplificado: risk_free + beta x ERP.

    Devolve `(taxa, beta_foi_padrao)` — `beta_foi_padrao=True` quando o
    ativo não tem beta reportado e o beta de mercado (1.0) foi usado no
    lugar (nunca um beta "estimado" para a empresa específica)."""
    macro = macro_assumptions(currency)
    used_default = beta is None
    effective_beta = DEFAULT_BETA if beta is None else beta
    rate = macro["risk_free_rate"] + effective_beta * macro["equity_risk_premium"]
    return rate, used_default


def project_fcf(fcf0: Decimal, growth_rate: Decimal, years: int) -> list[Decimal]:
    """FCF projetado ano a ano, crescendo a `growth_rate` constante."""
    cash_flows: list[Decimal] = []
    value = fcf0
    for _ in range(years):
        value = value * (Decimal("1") + growth_rate)
        cash_flows.append(value)
    return cash_flows


def discount_cash_flows(cash_flows: list[Decimal], discount_rate_value: Decimal) -> Decimal:
    total = Decimal("0")
    for i, cf in enumerate(cash_flows, start=1):
        total += cf / ((Decimal("1") + discount_rate_value) ** i)
    return total


def terminal_value(
    last_fcf: Decimal, terminal_growth: Decimal, discount_rate_value: Decimal
) -> Decimal | None:
    """Valor terminal por perpetuidade (Gordon growth). `None` quando a
    taxa de desconto não excede o crescimento terminal (denominador não
    positivo — o modelo simplesmente não é aplicável nesse caso, nunca
    aproximamos com um denominador artificialmente ajustado)."""
    denom = discount_rate_value - terminal_growth
    if denom <= 0:
        return None
    return last_fcf * (Decimal("1") + terminal_growth) / denom


def dcf_fair_value_per_share(
    fcf0: Decimal,
    growth_rate: Decimal,
    discount_rate_value: Decimal,
    terminal_growth: Decimal,
    shares_outstanding: Decimal,
    net_debt: Decimal | None,
    years: int = DCF_PROJECTION_YEARS,
) -> tuple[Decimal | None, str | None]:
    """Valor justo por ação via DCF de 2 estágios. `net_debt=None` é
    tratado como dívida líquida neutra (nem soma nem subtrai — não
    inventamos um valor de dívida que não foi coletado), com o motivo
    disso ficando a cargo de quem chama sinalizar como aviso."""
    if fcf0 <= 0:
        return None, "fluxo de caixa livre inicial não positivo — DCF não é significativo"
    if shares_outstanding <= 0:
        return None, "quantidade de ações em circulação indisponível ou inválida"

    terminal_growth_capped = min(terminal_growth, discount_rate_value - Decimal("0.01"))

    cash_flows = project_fcf(fcf0, growth_rate, years)
    pv_explicit = discount_cash_flows(cash_flows, discount_rate_value)

    tv = terminal_value(cash_flows[-1], terminal_growth_capped, discount_rate_value)
    if tv is None:
        return None, (
            "taxa de desconto não excede o crescimento terminal — valor terminal indefinido "
            "nesse cenário"
        )
    pv_terminal = tv / ((Decimal("1") + discount_rate_value) ** years)

    enterprise_value = pv_explicit + pv_terminal
    equity_value = enterprise_value - (net_debt or Decimal("0"))
    if equity_value <= 0:
        return None, (
            "valor de equity implícito não positivo (dívida líquida elevada frente ao "
            "fluxo de caixa projetado)"
        )

    return equity_value / shares_outstanding, None
