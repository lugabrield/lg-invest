"""Testes de integração ponta-a-ponta do Post-Allocation Constraints Engine
(Sprint 29) via DecisionService.recommend_v3 — cobre os cenários da
especificação do usuário que dependem do pipeline completo (Portfolio +
LG Score + Target Allocation Rule Engine + Investment Policy + Decision
Engine v3), complementando os testes de engine pura em
`test_post_allocation_constraints.py`.

Como o valor exato de cada peso depende do câmbio USD/BRL configurado e
do LG Score calculado a partir do histórico de preços (não mockado),
estes testes verificam INVARIANTES (nunca ultrapassar o limite, nunca
sugerir venda, sempre explicar um corte) em vez de números exatos — os
números exatos já são cobertos pelos testes de engine pura.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.engines.decision.inputs import DecisionConfig
from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.schemas.investment_policy import InvestmentPolicyUpdate
from backend.app.services.decision_service import DecisionService
from backend.app.services.investment_policy_service import InvestmentPolicyService
from backend.app.services.target_allocation_rule_service import TargetAllocationRuleService

# Cenários 3/10/11 usam um limite de sobreconcentração e um teto por ativo
# mais permissivos (`over_concentration_limit`/`max_asset_weight` padrão são
# 30%/15% — pensados para carteiras com muitos ativos) só para isolar o que
# está sendo testado: o corte por dimensão MOEDA do Post-Allocation
# Constraints Engine, não os bloqueios pré-existentes de sobreconcentração
# por ativo (que já têm cobertura própria no cenário 9 e nos testes de
# `eligibility.py`).
_PERMISSIVE_CONFIG = DecisionConfig(over_concentration_limit=Decimal("0.50"))


def _seed_diversified_portfolio(db) -> int:
    """Carteira majoritariamente BRL com uma posição minoritária em USD
    (VOO) — reproduz o cenário do bug relatado (moeda estrangeira
    sub-representada em relação a uma meta configurada)."""
    portfolio = Portfolio(name="Carteira Sprint 29", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    stock = Asset(
        ticker="TAEE11.SA", name="Taesa", asset_class="stock", country="BR", currency="BRL"
    )
    us_etf = Asset(
        ticker="VOO", name="Vanguard S&P 500", asset_class="etf", country="US", currency="USD"
    )
    db.add_all([stock, us_etf])
    db.flush()

    db.add_all(
        [
            Position(
                portfolio_id=portfolio.id,
                asset_id=stock.id,
                quantity=Decimal("1000"),
                average_price=Decimal("25"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
            Position(
                portfolio_id=portfolio.id,
                asset_id=us_etf.id,
                quantity=Decimal("1"),
                average_price=Decimal("400"),
                currency="USD",
                opened_at=date(2025, 1, 1),
            ),
        ]
    )
    db.add(Price(asset_id=stock.id, date=date(2026, 6, 27), close=Decimal("28")))
    db.add(Price(asset_id=us_etf.id, date=date(2026, 6, 27), close=Decimal("410")))
    db.commit()
    return portfolio.id


def _seed_dual_usd_portfolio(db) -> int:
    """Carteira com DUAS posições em USD (VOO + QQQ) — necessário para
    forçar o corte por dimensão MOEDA de verdade: um único ativo nunca
    sozinho ultrapassa o teto de moeda quando o teto de moeda (ex.: 60%)
    é maior que o teto por ativo do aporte (`max_single_weight`, 50%,
    Volume 7) — só o conjunto de vários ativos na MESMA dimensão pode
    ultrapassar o teto agregado, que é exatamente o corte que o
    Post-Allocation Constraints Engine faz por GRUPO."""
    portfolio = Portfolio(name="Carteira USD duplo Sprint 29", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    stock = Asset(
        ticker="TAEE11.SA", name="Taesa", asset_class="stock", country="BR", currency="BRL"
    )
    voo = Asset(
        ticker="VOO", name="Vanguard S&P 500", asset_class="etf", country="US", currency="USD"
    )
    qqq = Asset(
        ticker="QQQ", name="Invesco QQQ Trust", asset_class="etf", country="US", currency="USD"
    )
    db.add_all([stock, voo, qqq])
    db.flush()

    db.add_all(
        [
            Position(
                portfolio_id=portfolio.id,
                asset_id=stock.id,
                quantity=Decimal("800"),
                average_price=Decimal("25"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
            Position(
                portfolio_id=portfolio.id,
                asset_id=voo.id,
                quantity=Decimal("4"),
                average_price=Decimal("400"),
                currency="USD",
                opened_at=date(2025, 1, 1),
            ),
            Position(
                portfolio_id=portfolio.id,
                asset_id=qqq.id,
                quantity=Decimal("4"),
                average_price=Decimal("350"),
                currency="USD",
                opened_at=date(2025, 1, 1),
            ),
        ]
    )
    db.add(Price(asset_id=stock.id, date=date(2026, 6, 27), close=Decimal("25")))
    db.add(Price(asset_id=voo.id, date=date(2026, 6, 27), close=Decimal("410")))
    db.add(Price(asset_id=qqq.id, date=date(2026, 6, 27), close=Decimal("360")))
    db.commit()
    return portfolio.id


def _seed_fii_over_limit_portfolio(db) -> int:
    """Carteira com FII já bem representado — usada para o cenário 9
    (bloqueio pré-existente por sobreconcentração de classe continua
    funcionando mesmo com o Post-Allocation Constraints Engine ativo)."""
    portfolio = Portfolio(name="Carteira FII Sprint 29", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    stock = Asset(
        ticker="TAEE11.SA", name="Taesa", asset_class="stock", country="BR", currency="BRL"
    )
    fii = Asset(
        ticker="HGLG11.SA", name="CSHG Logística", asset_class="fii", country="BR", currency="BRL"
    )
    db.add_all([stock, fii])
    db.flush()

    db.add_all(
        [
            Position(
                portfolio_id=portfolio.id,
                asset_id=stock.id,
                quantity=Decimal("100"),
                average_price=Decimal("25"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
            Position(
                portfolio_id=portfolio.id,
                asset_id=fii.id,
                quantity=Decimal("500"),
                average_price=Decimal("100"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
        ]
    )
    db.add(Price(asset_id=stock.id, date=date(2026, 6, 27), close=Decimal("28")))
    db.add(Price(asset_id=fii.id, date=date(2026, 6, 27), close=Decimal("110")))
    db.commit()
    return portfolio.id


def test_scenario_01_small_contribution_keeps_working_normally(db_session):
    """Cenário 1: um aporte pequeno continua funcionando normalmente —
    nenhuma dimensão bate no limite, nenhum saldo fica sem alocar por
    causa do Post-Allocation Constraints Engine (regressão)."""
    portfolio_id = _seed_diversified_portfolio(db_session)
    result = DecisionService(db_session).recommend_v3(portfolio_id, Decimal("100"), persist=False)

    assert result.items
    assert Decimal("0") < result.allocated_amount <= Decimal("100")
    assert result.capped_dimensions == []


def test_scenario_02_small_contribution_can_prioritize_underweight_currency(db_session):
    """Cenário 2: com uma meta de alocação-alvo configurada para USD e um
    aporte pequeno (R$ 1.000) em relação ao patrimônio, o motor ainda
    consegue direcionar aporte para o ativo em USD sub-representado —
    nada aqui é bloqueado pelo Post-Allocation Constraints Engine (o
    aporte é pequeno demais para sequer chegar perto do limite)."""
    portfolio_id = _seed_diversified_portfolio(db_session)
    TargetAllocationRuleService(db_session).set_rule(
        portfolio_id,
        dimension_type="currency",
        dimension_key="USD",
        min_weight=Decimal("0.20"),
        target_weight=Decimal("0.45"),
        max_weight=Decimal("0.60"),
    )

    result = DecisionService(db_session).recommend_v3(portfolio_id, Decimal("1000"), persist=False)

    assert any(i.ticker == "VOO" for i in result.items)
    assert result.capped_dimensions == []


def test_scenario_03_extreme_contribution_end_to_end_respects_currency_max(db_session):
    """Cenário 3 (ponta-a-ponta): o mesmo bug relatado pelo usuário —
    aporte de R$ 1.000.000 numa carteira pequena, com máximo de USD
    configurado em 60% — não pode mais resultar em ~97% de exposição em
    USD. Testado via DecisionService completo, não só a engine pura.
    Precisa de DOIS ativos em USD (ver `_seed_dual_usd_portfolio`): um só
    ativo nunca sozinho ultrapassa 60% de moeda quando o teto por ativo
    do aporte já é 50%."""
    portfolio_id = _seed_dual_usd_portfolio(db_session)
    TargetAllocationRuleService(db_session).set_rule(
        portfolio_id,
        dimension_type="currency",
        dimension_key="USD",
        min_weight=Decimal("0.20"),
        target_weight=Decimal("0.45"),
        max_weight=Decimal("0.60"),
    )
    InvestmentPolicyService(db_session).get_or_create(portfolio_id)
    InvestmentPolicyService(db_session).update(
        portfolio_id, InvestmentPolicyUpdate(max_asset_weight=Decimal("0.50"))
    )

    result = DecisionService(db_session).recommend_v3(
        portfolio_id, Decimal("1000000"), config=_PERMISSIVE_CONFIG, persist=False
    )

    assert result.capped_dimensions, "esperava ao menos uma dimensão cortada pelo aporte extremo"
    usd_capped = [
        cd
        for cd in result.capped_dimensions
        if cd.dimension_type == "currency" and cd.dimension_key == "USD"
    ]
    assert usd_capped, "esperava a dimensão moeda=USD entre as cortadas"
    for cd in usd_capped:
        assert cd.weight_after <= cd.max_weight
        # O bug relatado batia em 97,23% de exposição em USD — nunca mais.
        assert cd.weight_after < Decimal("0.70")
    assert result.allocated_amount < result.contribution_amount


def test_scenario_09_fii_already_over_limit_stays_blocked(db_session):
    """Cenário 9: um FII já sobreconcentrado ANTES do aporte (acima do
    limite máximo de classe da política) continua bloqueado, exatamente
    como antes da Sprint 29 — o Post-Allocation Constraints Engine é uma
    camada ADICIONAL, nunca substitui o bloqueio pré-existente por
    sobreconcentração já detectada em `eligibility.py`."""
    portfolio_id = _seed_fii_over_limit_portfolio(db_session)
    InvestmentPolicyService(db_session).get_or_create(portfolio_id)
    InvestmentPolicyService(db_session).update(
        portfolio_id,
        InvestmentPolicyUpdate(target_fii_max=Decimal("0.05")),
    )

    result = DecisionService(db_session).recommend_v3(portfolio_id, Decimal("1000"), persist=False)

    ignored_tickers = [i.ticker for i in result.ignored]
    assert "HGLG11.SA" in ignored_tickers


def test_scenario_10_no_recommendation_ever_suggests_selling(db_session):
    """Cenário 10: mesmo sob o aporte mais extremo (R$ 1.000.000, que
    força o Post-Allocation Constraints Engine a cortar e deixar saldo
    sem alocar), nenhum texto da recomendação sugere venda — é sempre
    'aporte pausado', nunca 'vender'."""
    portfolio_id = _seed_dual_usd_portfolio(db_session)
    TargetAllocationRuleService(db_session).set_rule(
        portfolio_id,
        dimension_type="currency",
        dimension_key="USD",
        min_weight=Decimal("0.20"),
        target_weight=Decimal("0.45"),
        max_weight=Decimal("0.60"),
    )
    InvestmentPolicyService(db_session).get_or_create(portfolio_id)
    InvestmentPolicyService(db_session).update(
        portfolio_id, InvestmentPolicyUpdate(max_asset_weight=Decimal("0.50"))
    )

    result = DecisionService(db_session).recommend_v3(
        portfolio_id, Decimal("1000000"), config=_PERMISSIVE_CONFIG, persist=False
    )

    all_text = result.explanation + " ".join(result.alerts)
    for ignored in result.ignored:
        all_text += " " + ignored.reason
    assert "vender" not in all_text.lower()


def test_scenario_11_capped_dimensions_never_exceed_configured_max(db_session):
    """Cenário 11: a seção 'Como a carteira ficaria depois' (a UI constrói
    a tabela a partir de `result.capped_dimensions`) nunca pode mostrar um
    peso resultante acima do limite máximo configurado — testa o mesmo
    contrato de dados que a UI consome em `pages_impl/aporte.py`."""
    portfolio_id = _seed_dual_usd_portfolio(db_session)
    TargetAllocationRuleService(db_session).set_rule(
        portfolio_id,
        dimension_type="currency",
        dimension_key="USD",
        min_weight=Decimal("0.20"),
        target_weight=Decimal("0.45"),
        max_weight=Decimal("0.60"),
    )
    InvestmentPolicyService(db_session).get_or_create(portfolio_id)
    InvestmentPolicyService(db_session).update(
        portfolio_id, InvestmentPolicyUpdate(max_asset_weight=Decimal("0.50"))
    )

    result = DecisionService(db_session).recommend_v3(
        portfolio_id, Decimal("1000000"), config=_PERMISSIVE_CONFIG, persist=False
    )

    assert result.capped_dimensions
    for cd in result.capped_dimensions:
        assert cd.weight_after <= cd.max_weight


def test_scenario_12_large_and_extreme_contribution_alerts(db_session):
    """Cenário 12: aportes grandes/extremos em relação ao patrimônio geram
    um alerta específico ANTES de o usuário ler a distribuição — textos
    exatos pedidos pelo usuário (limiares de 25% e 100% do patrimônio)."""
    portfolio_id = _seed_diversified_portfolio(db_session)

    _, _, portfolio_value_before = DecisionService(db_session)._policy_limits_and_aggregates(
        portfolio_id
    )

    large_amount = (portfolio_value_before * Decimal("0.5")).quantize(Decimal("1"))
    result_large = DecisionService(db_session).recommend_v3(
        portfolio_id, large_amount, persist=False
    )
    assert any("grande em relação ao patrimônio atual" in alert for alert in result_large.alerts)

    extreme_amount = (portfolio_value_before * Decimal("2")).quantize(Decimal("1"))
    result_extreme = DecisionService(db_session).recommend_v3(
        portfolio_id, extreme_amount, persist=False
    )
    assert any("maior que a carteira atual" in alert for alert in result_extreme.alerts)
