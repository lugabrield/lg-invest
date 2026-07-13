"""Testes do DecisionService v3 (Sprint 24, Fase 4) — wiring DB -> engines ->
Decision Engine 3.0 (Investment Policy + Target Allocation Rule Engine v2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.schemas.investment_policy import InvestmentPolicyUpdate
from backend.app.services.decision_service import DecisionService
from backend.app.services.investment_policy_service import InvestmentPolicyService
from backend.app.services.target_allocation_rule_service import TargetAllocationRuleService


def _seed_portfolio(db) -> tuple[int, int, int]:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    stock = Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    crypto = Asset(
        ticker="BTC-USD", name="Bitcoin", asset_class="crypto", country="US", currency="USD"
    )
    us_etf = Asset(
        ticker="VOO", name="Vanguard S&P 500", asset_class="etf", country="US", currency="USD"
    )
    db.add_all([stock, crypto, us_etf])
    db.flush()

    db.add_all(
        [
            Position(
                portfolio_id=portfolio.id,
                asset_id=stock.id,
                quantity=Decimal("100"),
                average_price=Decimal("38"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
            Position(
                portfolio_id=portfolio.id,
                asset_id=crypto.id,
                quantity=Decimal("0.01"),
                average_price=Decimal("60000"),
                currency="USD",
                opened_at=date(2025, 1, 1),
            ),
            Position(
                portfolio_id=portfolio.id,
                asset_id=us_etf.id,
                quantity=Decimal("2"),
                average_price=Decimal("400"),
                currency="USD",
                opened_at=date(2025, 1, 1),
            ),
        ]
    )
    db.add(Price(asset_id=stock.id, date=date(2026, 6, 27), close=Decimal("40")))
    db.add(Price(asset_id=crypto.id, date=date(2026, 6, 27), close=Decimal("63000")))
    db.add(Price(asset_id=us_etf.id, date=date(2026, 6, 27), close=Decimal("410")))
    db.commit()
    return portfolio.id, stock.id, crypto.id


def test_build_inputs_v3_fills_pillars_from_conviction_score(db_session):
    portfolio_id, _, _ = _seed_portfolio(db_session)
    inputs = DecisionService(db_session).build_inputs_v3(portfolio_id)
    for candidate in inputs:
        # Sem fundamentos coletados, o Conviction Score ainda cai para a
        # proxy de preço em cada pilar — nunca deve ficar totalmente None.
        assert (
            candidate.quality_score is not None
            or candidate.valuation_score is not None
            or candidate.conviction_score is not None
        )


def test_build_inputs_v3_marks_international_correctly(db_session):
    portfolio_id, _, _ = _seed_portfolio(db_session)
    inputs = DecisionService(db_session).build_inputs_v3(portfolio_id)

    wege = next(i for i in inputs if i.ticker == "WEGE3.SA")
    voo = next(i for i in inputs if i.ticker == "VOO")
    assert wege.is_international is False
    assert voo.is_international is True
    assert voo.currency == "USD"
    assert voo.country == "US"


def test_build_inputs_v3_attaches_rule_signals_when_rules_configured(db_session):
    portfolio_id, _, _ = _seed_portfolio(db_session)
    TargetAllocationRuleService(db_session).set_rule(
        portfolio_id,
        dimension_type="class",
        dimension_key="etf",
        target_weight=Decimal("0.40"),
    )

    inputs = DecisionService(db_session).build_inputs_v3(portfolio_id)
    voo = next(i for i in inputs if i.ticker == "VOO")
    assert any(s.dimension_type == "class" for s in voo.rule_signals)


def test_build_inputs_v3_no_signals_without_rules(db_session):
    portfolio_id, _, _ = _seed_portfolio(db_session)
    inputs = DecisionService(db_session).build_inputs_v3(portfolio_id)
    for candidate in inputs:
        assert candidate.rule_signals == ()


def test_policy_limits_and_aggregates_computes_crypto_weight(db_session):
    portfolio_id, _, _ = _seed_portfolio(db_session)
    policy, aggregates, portfolio_value_before = DecisionService(
        db_session
    )._policy_limits_and_aggregates(portfolio_id)
    assert aggregates.crypto_weight > Decimal("0")
    assert aggregates.international_weight > Decimal("0")
    assert portfolio_value_before > Decimal("0")


def test_recommend_v3_blocks_crypto_over_policy_limit(db_session):
    portfolio_id, _, _ = _seed_portfolio(db_session)
    InvestmentPolicyService(db_session).get_or_create(portfolio_id)
    InvestmentPolicyService(db_session).update(
        portfolio_id,
        InvestmentPolicyUpdate(max_crypto_weight=Decimal("0.01")),
    )

    result = DecisionService(db_session).recommend_v3(portfolio_id, Decimal("1000"), persist=False)
    assert result.audit.model_version == "decision_v3"
    ignored_tickers = [i.ticker for i in result.ignored]
    assert "BTC-USD" in ignored_tickers


def test_recommend_v3_end_to_end_totals_respect_amount(db_session):
    portfolio_id, _, _ = _seed_portfolio(db_session)
    result = DecisionService(db_session).recommend_v3(portfolio_id, Decimal("1000"), persist=False)
    total = sum((i.amount for i in result.items), start=Decimal("0"))
    assert total == result.allocated_amount
    assert total <= Decimal("1000")


def test_recommend_v3_never_mentions_selling(db_session):
    portfolio_id, _, _ = _seed_portfolio(db_session)
    InvestmentPolicyService(db_session).update(
        portfolio_id,
        InvestmentPolicyUpdate(
            max_crypto_weight=Decimal("0.001"), max_asset_weight=Decimal("0.01")
        ),
    )
    result = DecisionService(db_session).recommend_v3(portfolio_id, Decimal("1000"), persist=False)
    all_text = result.explanation + " ".join(result.alerts)
    for ignored in result.ignored:
        all_text += " " + ignored.reason
    assert "vender" not in all_text.lower()
