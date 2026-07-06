"""Testes de RadarService (Sprint 25, Parte 2.4) — fronteira banco/engine.

Cobre: candidatos novos sem dado suficiente viram "insufficient_data",
entradas "discarded" da watchlist são ignoradas, posições existentes e
candidatos novos aparecem separadamente, e o bloqueio por limite de
classe (Target Allocation Rule Engine v2) se propaga tanto para a
posição existente quanto para um candidato novo da mesma classe.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.schemas.watchlist import WatchlistAssetCreate
from backend.app.services.radar_service import RadarService
from backend.app.services.target_allocation_rule_service import TargetAllocationRuleService
from backend.app.services.watchlist_service import WatchlistService


def _seed_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.commit()
    return portfolio.id


def _seed_position(db, portfolio_id: int, ticker: str, asset_class: str) -> None:
    asset = Asset(ticker=ticker, name=ticker, asset_class=asset_class, country="BR", currency="BRL")
    db.add(asset)
    db.commit()
    db.add(Price(asset_id=asset.id, date=date(2026, 1, 2), close=Decimal("100.00"), source="yahoo"))
    db.commit()
    db.add(
        Position(
            portfolio_id=portfolio_id,
            asset_id=asset.id,
            quantity=Decimal("100"),
            average_price=Decimal("90"),
            currency="BRL",
            opened_at=date(2025, 1, 1),
        )
    )
    db.commit()


def _watchlist_payload(**overrides) -> WatchlistAssetCreate:
    base = dict(
        ticker="MXRF11.SA",
        name="Maxi Renda FII",
        asset_class="fii",
        country="BR",
        currency="BRL",
    )
    base.update(overrides)
    return WatchlistAssetCreate(**base)


def test_radar_new_candidate_without_data_is_insufficient_data(db_session):
    portfolio_id = _seed_portfolio(db_session)
    WatchlistService(db_session).add_watchlist_asset(
        portfolio_id, _watchlist_payload(status="candidate")
    )

    evaluation = RadarService(db_session).evaluate(portfolio_id)

    assert len(evaluation.candidates) == 1
    candidate = evaluation.candidates[0]
    assert candidate.ticker == "MXRF11.SA"
    assert candidate.is_current_holding is False
    assert candidate.classification == "insufficient_data"


def test_radar_excludes_discarded_watchlist_entries(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)
    created = service.add_watchlist_asset(portfolio_id, _watchlist_payload())
    service.discard_asset(portfolio_id, created.id)

    evaluation = RadarService(db_session).evaluate(portfolio_id)

    assert evaluation.candidates == []


def test_radar_separates_current_holding_from_new_candidate(db_session):
    portfolio_id = _seed_portfolio(db_session)
    _seed_position(db_session, portfolio_id, "HGLG11.SA", "fii")
    WatchlistService(db_session).add_watchlist_asset(
        portfolio_id, _watchlist_payload(ticker="MXRF11.SA", status="candidate")
    )

    evaluation = RadarService(db_session).evaluate(portfolio_id)

    by_ticker = {c.ticker: c for c in evaluation.candidates}
    assert by_ticker["HGLG11.SA"].is_current_holding is True
    assert by_ticker["MXRF11.SA"].is_current_holding is False


def test_radar_blocks_class_dimension_for_both_holding_and_new_candidate(db_session):
    """Um limite de classe (regra detalhada) já ultrapassado bloqueia a
    dimensão inteira — tanto para quem já tem a posição quanto para um
    candidato novo da mesma classe. Nunca é uma recomendação de venda."""
    portfolio_id = _seed_portfolio(db_session)
    _seed_position(db_session, portfolio_id, "HGLG11.SA", "fii")
    TargetAllocationRuleService(db_session).set_rule(
        portfolio_id,
        dimension_type="class",
        dimension_key="fii",
        max_weight=Decimal("0.10"),
    )
    WatchlistService(db_session).add_watchlist_asset(
        portfolio_id, _watchlist_payload(ticker="MXRF11.SA", status="candidate")
    )

    evaluation = RadarService(db_session).evaluate(portfolio_id)

    by_ticker = {c.ticker: c for c in evaluation.candidates}
    assert by_ticker["HGLG11.SA"].classification == "blocked"
    assert by_ticker["MXRF11.SA"].classification == "blocked"
    for reason in by_ticker["MXRF11.SA"].reasons:
        assert "vender" not in reason.lower()


def test_radar_no_blocking_when_no_rule_configured(db_session):
    portfolio_id = _seed_portfolio(db_session)
    _seed_position(db_session, portfolio_id, "HGLG11.SA", "fii")

    evaluation = RadarService(db_session).evaluate(portfolio_id)

    by_ticker = {c.ticker: c for c in evaluation.candidates}
    assert by_ticker["HGLG11.SA"].classification != "blocked"
