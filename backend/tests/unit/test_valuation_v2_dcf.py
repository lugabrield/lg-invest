"""Testes do DCF simplificado do Valuation Engine 2.0 (Sprint 26, Fase 2)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.valuation_v2.dcf import (
    capm_discount_rate,
    dcf_fair_value_per_share,
    discount_cash_flows,
    project_fcf,
    terminal_value,
)


def test_capm_discount_rate_uses_default_beta_when_missing():
    rate, used_default = capm_discount_rate(None, "USD")
    assert used_default is True
    # risk_free 4.5% + beta padrão 1.0 x ERP 5% = 9.5%
    assert rate == Decimal("0.045") + Decimal("1.0") * Decimal("0.05")


def test_capm_discount_rate_uses_provided_beta():
    rate, used_default = capm_discount_rate(Decimal("0.8"), "USD")
    assert used_default is False
    assert rate == Decimal("0.045") + Decimal("0.8") * Decimal("0.05")


def test_capm_discount_rate_brl_uses_brl_macro_assumptions():
    rate_brl, _ = capm_discount_rate(Decimal("1.0"), "BRL")
    rate_usd, _ = capm_discount_rate(Decimal("1.0"), "USD")
    assert rate_brl > rate_usd  # prêmio estrutural do Brasil é maior


def test_capm_discount_rate_unknown_currency_falls_back_to_usd():
    rate_unknown, _ = capm_discount_rate(Decimal("1.0"), "EUR")
    rate_usd, _ = capm_discount_rate(Decimal("1.0"), "USD")
    assert rate_unknown == rate_usd


def test_project_fcf_grows_at_constant_rate():
    cash_flows = project_fcf(Decimal("100"), Decimal("0.10"), 3)
    assert cash_flows == [Decimal("110.0"), Decimal("121.00"), Decimal("133.100")]


def test_project_fcf_zero_growth_stays_constant():
    cash_flows = project_fcf(Decimal("100"), Decimal("0"), 3)
    assert cash_flows == [Decimal("100"), Decimal("100"), Decimal("100")]


def test_discount_cash_flows_matches_manual_sum():
    cash_flows = [Decimal("100"), Decimal("100")]
    pv = discount_cash_flows(cash_flows, Decimal("0.10"))
    expected = Decimal("100") / Decimal("1.10") + Decimal("100") / (Decimal("1.10") ** 2)
    assert pv == expected


def test_terminal_value_none_when_discount_does_not_exceed_growth():
    assert terminal_value(Decimal("100"), Decimal("0.10"), Decimal("0.10")) is None
    assert terminal_value(Decimal("100"), Decimal("0.12"), Decimal("0.10")) is None


def test_terminal_value_gordon_growth_formula():
    tv = terminal_value(Decimal("100"), Decimal("0.02"), Decimal("0.10"))
    assert tv == Decimal("100") * Decimal("1.02") / Decimal("0.08")


def test_dcf_fair_value_per_share_happy_path_matches_manual_calc():
    value, reason = dcf_fair_value_per_share(
        fcf0=Decimal("100"),
        growth_rate=Decimal("0"),
        discount_rate_value=Decimal("0.10"),
        terminal_growth=Decimal("0.02"),
        shares_outstanding=Decimal("10"),
        net_debt=Decimal("0"),
        years=5,
    )
    assert reason is None
    assert value is not None
    # cálculo manual independente: PV de 5 anos de FCF=100 a 10% + valor
    # terminal (Gordon growth, g=2%) descontado — resultado ~117.08.
    assert Decimal("115") < value < Decimal("120")


def test_dcf_fair_value_none_when_fcf_not_positive():
    value, reason = dcf_fair_value_per_share(
        fcf0=Decimal("-10"),
        growth_rate=Decimal("0.05"),
        discount_rate_value=Decimal("0.10"),
        terminal_growth=Decimal("0.02"),
        shares_outstanding=Decimal("10"),
        net_debt=None,
    )
    assert value is None
    assert "fluxo de caixa livre" in reason


def test_dcf_fair_value_none_when_shares_outstanding_invalid():
    value, reason = dcf_fair_value_per_share(
        fcf0=Decimal("100"),
        growth_rate=Decimal("0.05"),
        discount_rate_value=Decimal("0.10"),
        terminal_growth=Decimal("0.02"),
        shares_outstanding=Decimal("0"),
        net_debt=None,
    )
    assert value is None
    assert "ações em circulação" in reason


def test_dcf_fair_value_none_when_equity_value_not_positive_due_to_heavy_debt():
    value, reason = dcf_fair_value_per_share(
        fcf0=Decimal("10"),
        growth_rate=Decimal("0"),
        discount_rate_value=Decimal("0.10"),
        terminal_growth=Decimal("0.02"),
        shares_outstanding=Decimal("10"),
        net_debt=Decimal("10_000_000"),
    )
    assert value is None
    assert "dívida líquida" in reason


def test_dcf_fair_value_net_debt_none_treated_as_neutral():
    value_none_debt, _ = dcf_fair_value_per_share(
        fcf0=Decimal("100"),
        growth_rate=Decimal("0"),
        discount_rate_value=Decimal("0.10"),
        terminal_growth=Decimal("0.02"),
        shares_outstanding=Decimal("10"),
        net_debt=None,
    )
    value_zero_debt, _ = dcf_fair_value_per_share(
        fcf0=Decimal("100"),
        growth_rate=Decimal("0"),
        discount_rate_value=Decimal("0.10"),
        terminal_growth=Decimal("0.02"),
        shares_outstanding=Decimal("10"),
        net_debt=Decimal("0"),
    )
    assert value_none_debt == value_zero_debt


def test_dcf_fair_value_higher_growth_yields_higher_value():
    low, _ = dcf_fair_value_per_share(
        fcf0=Decimal("100"),
        growth_rate=Decimal("0.02"),
        discount_rate_value=Decimal("0.10"),
        terminal_growth=Decimal("0.02"),
        shares_outstanding=Decimal("10"),
        net_debt=Decimal("0"),
    )
    high, _ = dcf_fair_value_per_share(
        fcf0=Decimal("100"),
        growth_rate=Decimal("0.08"),
        discount_rate_value=Decimal("0.10"),
        terminal_growth=Decimal("0.02"),
        shares_outstanding=Decimal("10"),
        net_debt=Decimal("0"),
    )
    assert high > low


def test_dcf_fair_value_terminal_growth_is_capped_below_discount_rate():
    # terminal_growth (0.30) > discount_rate (0.10): sem o cap interno em
    # `dcf_fair_value_per_share`, o valor terminal explodiria/ficaria negativo.
    value, reason = dcf_fair_value_per_share(
        fcf0=Decimal("100"),
        growth_rate=Decimal("0.05"),
        discount_rate_value=Decimal("0.10"),
        terminal_growth=Decimal("0.30"),
        shares_outstanding=Decimal("10"),
        net_debt=Decimal("0"),
    )
    assert reason is None
    assert value is not None
    assert value > 0
