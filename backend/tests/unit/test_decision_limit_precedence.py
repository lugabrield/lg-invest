"""Precedência de limites entre a regra detalhada (Target Allocation Rule

Engine v2) e a Investment Policy no Decision Engine 3.0 (Sprint 25,
Parte 1).

Bug corrigido: quando existia uma regra detalhada (ex.: `class=fii`,
`max_weight=25%`) E a Investment Policy também tinha um limite genérico
para a mesma classe (ex.: `target_fii_max=15%`), o bloqueio usava, por
engano, o limite da política na mensagem exibida ao usuário — mesmo a
regra detalhada, mais específica, sendo a que de fato deveria mandar.
Reportado pelo usuário com uma carteira real: FIIs em 34.4% do
patrimônio (espalhados por mais de um ativo, nenhum individualmente
sobreconcentrado), regra detalhada `class=fii` com `max=25%`, política
com `target_fii_max=15%` — a tela Aporte mostrava "acima do limite
máximo da política (34.4% > 15.0%)" em vez de citar os 25% da regra
detalhada.

Nota sobre os pesos usados nos testes: o filtro v1 (`filter_eligible`,
chamado por `filter_eligible_v3` antes da lógica desta sprint) já
bloqueia qualquer candidato com peso INDIVIDUAL acima de
`over_concentration_limit` (30% por padrão) — um filtro totalmente
diferente e anterior a esta correção. Por isso os testes abaixo mantêm
o peso do candidato (ativo individual) abaixo de 30% e usam o campo
`current_weight` do `AllocationRuleSignal` (peso agregado da
dimensão/classe) para carregar o valor que de fato excede o limite —
exatamente como acontece na carteira real do usuário, com FIIs
espalhados por mais de um ticket.

Precedência esperada:
1. Regra detalhada (Target Allocation Rule Engine v2) — se tiver
   `max_weight`, é a fonte de verdade do limite.
2. Investment Policy — só usada como fallback quando não há regra
   detalhada com `max_weight` para aquela dimensão.
3. Sem nenhuma das duas: nenhum limite é inventado.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.engines.decision.eligibility import filter_eligible_v3
from backend.app.engines.decision.inputs import (
    DEFAULT_CONFIG,
    AllocationRuleSignal,
    DecisionInput,
    PolicyLimits,
    PortfolioAggregates,
)
from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.schemas.investment_policy import InvestmentPolicyUpdate
from backend.app.services.decision_service import DecisionService
from backend.app.services.investment_policy_service import InvestmentPolicyService
from backend.app.services.target_allocation_rule_service import TargetAllocationRuleService


def _candidate(**overrides) -> DecisionInput:
    base = dict(
        ticker="TEST3.SA",
        asset_class="stock",
        lg_score=Decimal("60"),
        confidence=Decimal("1"),
        current_weight=Decimal("0.05"),  # baixo o suficiente p/ não disparar sobreconcentração
    )
    base.update(overrides)
    return DecisionInput(**base)


def _blocked_signal(dimension_type, dimension_key, current_weight, max_weight) -> tuple:
    return (
        AllocationRuleSignal(
            dimension_type,
            "blocked",
            0,
            True,
            current_weight > max_weight * Decimal("1.5"),
            dimension_key=dimension_key,
            current_weight=current_weight,
            max_weight=max_weight,
        ),
    )


def _neutral_signal(dimension_type, dimension_key, current_weight, max_weight) -> tuple:
    return (
        AllocationRuleSignal(
            dimension_type,
            "neutral",
            0,
            False,
            False,
            dimension_key=dimension_key,
            current_weight=current_weight,
            max_weight=max_weight,
        ),
    )


# --- 1. Regra detalhada tem precedência sobre a política ---------------------


def test_detailed_rule_max_takes_precedence_over_policy_message():
    """FIIs a 34.4% (agregado), regra detalhada max=25%, política

    target_fii_max=15%: a mensagem deve citar 25.0%, nunca 15.0%."""
    candidate = _candidate(
        asset_class="fii",
        rule_signals=_blocked_signal("class", "fii", Decimal("0.344"), Decimal("0.25")),
    )
    policy = PolicyLimits(target_fii_max=Decimal("0.15"))
    aggregates = PortfolioAggregates(fii_weight=Decimal("0.344"))

    eligible, ignored = filter_eligible_v3(
        [candidate], set(), DEFAULT_CONFIG, policy=policy, aggregates=aggregates
    )
    assert eligible == []
    assert "25.0%" in ignored[0].reason
    assert "15.0%" not in ignored[0].reason
    assert "regra detalhada" in ignored[0].reason
    assert ignored[0].block_source == "regra_detalhada"


# --- 2. Sem regra detalhada, cai para a política ------------------------------


def test_falls_back_to_investment_policy_without_detailed_rule():
    candidate = _candidate(asset_class="fii")
    policy = PolicyLimits(target_fii_max=Decimal("0.15"))
    aggregates = PortfolioAggregates(fii_weight=Decimal("0.20"))

    eligible, ignored = filter_eligible_v3(
        [candidate], set(), DEFAULT_CONFIG, policy=policy, aggregates=aggregates
    )
    assert eligible == []
    assert "política geral" in ignored[0].reason
    assert "15.0%" in ignored[0].reason
    assert ignored[0].block_source == "politica_geral"


# --- 3. Mensagem mostra o limite/fonte corretos -------------------------------


def test_message_cites_detailed_rule_source_explicitly():
    candidate = _candidate(
        asset_class="crypto",
        rule_signals=_blocked_signal("class", "crypto", Decimal("0.12"), Decimal("0.10")),
    )
    _, ignored = filter_eligible_v3([candidate], set(), DEFAULT_CONFIG)
    assert "regra detalhada de alocação-alvo" in ignored[0].reason
    assert "10.0%" in ignored[0].reason


def test_message_cites_policy_source_explicitly_as_fallback():
    candidate = _candidate(asset_class="crypto")
    policy = PolicyLimits(max_crypto_weight=Decimal("0.05"))
    aggregates = PortfolioAggregates(crypto_weight=Decimal("0.06"))
    _, ignored = filter_eligible_v3(
        [candidate], set(), DEFAULT_CONFIG, policy=policy, aggregates=aggregates
    )
    assert "política geral" in ignored[0].reason
    assert "5.0%" in ignored[0].reason


# --- 4/5. FIIs acima/abaixo do máximo da regra detalhada ----------------------


def test_fii_34_4_pct_blocked_by_detailed_max_25():
    candidate = _candidate(
        asset_class="fii",
        rule_signals=_blocked_signal("class", "fii", Decimal("0.344"), Decimal("0.25")),
    )
    eligible, ignored = filter_eligible_v3([candidate], set(), DEFAULT_CONFIG)
    assert eligible == []
    assert ignored[0].ticker == candidate.ticker


def test_fii_22_pct_not_blocked_by_detailed_max_25():
    # 22% < 25%: a regra detalhada avaliaria como "neutral" (dentro do
    # alvo/máximo), não "blocked" — o candidato deve passar, mesmo com uma
    # política mais apertada (15%) configurada — a regra detalhada manda.
    candidate = _candidate(
        asset_class="fii",
        rule_signals=_neutral_signal("class", "fii", Decimal("0.22"), Decimal("0.25")),
    )
    policy = PolicyLimits(target_fii_max=Decimal("0.15"))
    aggregates = PortfolioAggregates(fii_weight=Decimal("0.22"))
    eligible, ignored = filter_eligible_v3(
        [candidate], set(), DEFAULT_CONFIG, policy=policy, aggregates=aggregates
    )
    assert eligible == [candidate]
    assert ignored == []


# --- 6. Removendo a regra detalhada, volta ao comportamento da política ------


def test_removing_detailed_rule_reverts_to_policy_behavior():
    policy = PolicyLimits(target_fii_max=Decimal("0.15"))
    aggregates = PortfolioAggregates(fii_weight=Decimal("0.22"))

    with_rule = _candidate(
        asset_class="fii",
        rule_signals=_neutral_signal("class", "fii", Decimal("0.22"), Decimal("0.25")),
    )
    eligible, _ = filter_eligible_v3(
        [with_rule], set(), DEFAULT_CONFIG, policy=policy, aggregates=aggregates
    )
    assert eligible == [with_rule]  # regra detalhada manda: 22% < 25%, elegível

    without_rule = _candidate(asset_class="fii")
    eligible2, ignored2 = filter_eligible_v3(
        [without_rule], set(), DEFAULT_CONFIG, policy=policy, aggregates=aggregates
    )
    assert eligible2 == []  # sem a regra, a política (15%) volta a valer: 22% > 15%
    assert "política geral" in ignored2[0].reason


# --- 7. Precedência funciona para todas as dimensões/classes -----------------


@pytest.mark.parametrize(
    "dimension_type,dimension_key,asset_class,candidate_weight,dimension_current,detailed_max",
    [
        ("class", "fii", "fii", Decimal("0.05"), Decimal("0.30"), Decimal("0.25")),
        ("class", "crypto", "crypto", Decimal("0.03"), Decimal("0.08"), Decimal("0.05")),
        ("class", "bond", "bond", Decimal("0.05"), Decimal("0.40"), Decimal("0.30")),
        ("class", "etf", "etf", Decimal("0.05"), Decimal("0.50"), Decimal("0.35")),
        ("class", "reit", "reit", Decimal("0.05"), Decimal("0.20"), Decimal("0.15")),
        ("class", "stock", "stock", Decimal("0.05"), Decimal("0.60"), Decimal("0.50")),
        ("currency", "USD", "etf", Decimal("0.05"), Decimal("0.45"), Decimal("0.40")),
        ("currency", "BRL", "stock", Decimal("0.05"), Decimal("0.70"), Decimal("0.60")),
        ("country", "BR", "stock", Decimal("0.05"), Decimal("0.70"), Decimal("0.60")),
        ("country", "US", "etf", Decimal("0.05"), Decimal("0.45"), Decimal("0.40")),
        ("asset", "BTC-USD", "crypto", Decimal("0.08"), Decimal("0.08"), Decimal("0.05")),
        ("asset", "VOO", "etf", Decimal("0.25"), Decimal("0.25"), Decimal("0.20")),
    ],
)
def test_detailed_rule_precedence_applies_to_every_dimension(
    dimension_type, dimension_key, asset_class, candidate_weight, dimension_current, detailed_max
):
    candidate = _candidate(
        ticker=dimension_key if dimension_type == "asset" else "TEST3.SA",
        asset_class=asset_class,
        current_weight=candidate_weight,
        rule_signals=_blocked_signal(
            dimension_type, dimension_key, dimension_current, detailed_max
        ),
    )
    # Política com um limite BEM mais apertado (metade do detalhado) — se a
    # precedência estivesse errada, a mensagem mostraria esse valor.
    wrong_policy_limit = detailed_max / 2
    policy = PolicyLimits(
        max_asset_weight=wrong_policy_limit,
        max_crypto_weight=wrong_policy_limit,
        target_fii_max=wrong_policy_limit,
    )
    aggregates = PortfolioAggregates(crypto_weight=dimension_current, fii_weight=dimension_current)

    eligible, ignored = filter_eligible_v3(
        [candidate], set(), DEFAULT_CONFIG, policy=policy, aggregates=aggregates
    )
    assert eligible == []
    assert f"{detailed_max * 100:.1f}%" in ignored[0].reason
    assert f"{wrong_policy_limit * 100:.1f}%" not in ignored[0].reason


# --- 8. Nenhum bloqueio gera recomendação de venda ---------------------------


def test_no_detailed_rule_block_ever_mentions_selling():
    candidate = _candidate(
        asset_class="fii",
        rule_signals=_blocked_signal("class", "fii", Decimal("0.344"), Decimal("0.25")),
    )
    _, ignored = filter_eligible_v3([candidate], set(), DEFAULT_CONFIG)
    assert "vender" not in ignored[0].reason.lower()
    assert "não é recomendação de venda" in ignored[0].reason


def test_no_policy_fallback_block_ever_mentions_selling():
    candidate = _candidate(asset_class="fii")
    policy = PolicyLimits(target_fii_max=Decimal("0.15"))
    aggregates = PortfolioAggregates(fii_weight=Decimal("0.20"))
    _, ignored = filter_eligible_v3(
        [candidate], set(), DEFAULT_CONFIG, policy=policy, aggregates=aggregates
    )
    assert "vender" not in ignored[0].reason.lower()
    assert "não é recomendação de venda" in ignored[0].reason


# --- Cenário real de ponta a ponta (reproduz o bug reportado) ---------------


def _seed_fii_heavy_portfolio(db) -> tuple[int, int, int]:
    """Carteira com FIIs somando ~34.4% do patrimônio, espalhados por DOIS

    tickers (nenhum sobreconcentrado individualmente, exatamente como na
    carteira real do usuário) — reproduz o cenário exato reportado: regra
    detalhada `class=fii` com `max=25%` E Investment Policy com
    `target_fii_max=15%` configuradas ao mesmo tempo."""
    portfolio = Portfolio(name="Carteira teste FII", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    fii_a = Asset(
        ticker="HGLG11.SA", name="CSHG Logística", asset_class="fii", country="BR", currency="BRL"
    )
    fii_b = Asset(
        ticker="MXRF11.SA", name="Maxi Renda", asset_class="fii", country="BR", currency="BRL"
    )
    stock = Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    db.add_all([fii_a, fii_b, stock])
    db.flush()

    db.add_all(
        [
            # HGLG11: 100 * 110 = 11.000 (~17,2%)
            Position(
                portfolio_id=portfolio.id,
                asset_id=fii_a.id,
                quantity=Decimal("100"),
                average_price=Decimal("100"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
            # MXRF11: 1100 * 10 = 11.000 (~17,2%) -> FIIs somam ~34,4%
            Position(
                portfolio_id=portfolio.id,
                asset_id=fii_b.id,
                quantity=Decimal("1100"),
                average_price=Decimal("9"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
            # WEGE3: 634.9 * 63 ~= 40.000 (~62,5%) -> total ~= 64.000
            Position(
                portfolio_id=portfolio.id,
                asset_id=stock.id,
                quantity=Decimal("634.92"),
                average_price=Decimal("38"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
        ]
    )
    db.add(Price(asset_id=fii_a.id, date=date(2026, 6, 27), close=Decimal("110")))
    db.add(Price(asset_id=fii_b.id, date=date(2026, 6, 27), close=Decimal("10")))
    db.add(Price(asset_id=stock.id, date=date(2026, 6, 27), close=Decimal("63")))
    db.commit()
    return portfolio.id, fii_a.id, fii_b.id


def test_recommend_v3_end_to_end_uses_detailed_rule_limit_not_policy(db_session):
    """Reproduz o bug relatado pelo usuário: com regra detalhada

    `class=fii max=25%` E Investment Policy `target_fii_max=15%`
    configuradas juntas, o bloqueio de FIIs deve citar 25%, nunca 15%."""
    portfolio_id, _, _ = _seed_fii_heavy_portfolio(db_session)

    InvestmentPolicyService(db_session).update(
        portfolio_id, InvestmentPolicyUpdate(target_fii_max=Decimal("0.15"))
    )
    TargetAllocationRuleService(db_session).set_rule(
        portfolio_id,
        dimension_type="class",
        dimension_key="fii",
        min_weight=Decimal("0.10"),
        target_weight=Decimal("0.20"),
        max_weight=Decimal("0.25"),
        priority=3,
    )

    result = DecisionService(db_session).recommend_v3(portfolio_id, Decimal("1000"), persist=False)
    fii_ignored = [i for i in result.ignored if i.ticker in ("HGLG11.SA", "MXRF11.SA")]
    assert fii_ignored, "FIIs deveriam estar bloqueados (classe acima do máximo)"
    for item in fii_ignored:
        assert "25.0%" in item.reason
        assert "15.0%" not in item.reason
        assert "regra detalhada" in item.reason
        assert "vender" not in item.reason.lower()


def test_recommend_v3_end_to_end_falls_back_to_policy_when_rule_removed(db_session):
    portfolio_id, _, _ = _seed_fii_heavy_portfolio(db_session)
    InvestmentPolicyService(db_session).update(
        portfolio_id, InvestmentPolicyUpdate(target_fii_max=Decimal("0.15"))
    )
    # Nenhuma regra detalhada configurada desta vez.
    result = DecisionService(db_session).recommend_v3(portfolio_id, Decimal("1000"), persist=False)
    fii_ignored = [i for i in result.ignored if i.ticker in ("HGLG11.SA", "MXRF11.SA")]
    assert fii_ignored, "FIIs deveriam estar bloqueados pela política (sem regra detalhada)"
    for item in fii_ignored:
        assert "15.0%" in item.reason
        assert "política geral" in item.reason
