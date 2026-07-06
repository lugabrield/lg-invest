"""Testes de WatchlistAssetRepository e WatchlistService (Sprint 25, Parte 2).

Cobre: cadastro, bloqueio de duplicata ativa, edição de status
(watching/candidate/blocked/discarded/bought), remoção, e a garantia
central da Watchlist — nunca cria `Position` nem altera o patrimônio
calculado pelo Portfolio Engine, mesmo depois de marcar um ativo como
"bought".
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.infrastructure.database.models import Asset, Portfolio, Position
from backend.app.schemas.watchlist import WatchlistAssetCreate, WatchlistAssetUpdate
from backend.app.services.portfolio_service import PortfolioService
from backend.app.services.watchlist_service import WatchlistService


def _seed_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.commit()
    return portfolio.id


def _create_payload(**overrides) -> WatchlistAssetCreate:
    base = dict(
        ticker="MSFT",
        name="Microsoft Corp",
        asset_class="stock",
        country="US",
        currency="USD",
        thesis="Qualidade + moat + exposição internacional.",
    )
    base.update(overrides)
    return WatchlistAssetCreate(**base)


def test_add_watchlist_asset_creates_entry(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)

    view = service.add_watchlist_asset(portfolio_id, _create_payload())

    assert view.ticker == "MSFT"
    assert view.status == "watching"
    assert view.already_in_portfolio is False


def test_add_watchlist_asset_rejects_duplicate_active_ticker(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)
    service.add_watchlist_asset(portfolio_id, _create_payload())

    with pytest.raises(ValueError):
        service.add_watchlist_asset(portfolio_id, _create_payload())


def test_add_watchlist_asset_allows_recreate_after_discarded(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)
    created = service.add_watchlist_asset(portfolio_id, _create_payload())
    service.discard_asset(portfolio_id, created.id)

    view = service.add_watchlist_asset(portfolio_id, _create_payload(status="watching"))

    assert view.ticker == "MSFT"
    assert view.status == "watching"
    assert len(service.list_watchlist_assets(portfolio_id)) == 1


def test_list_watchlist_assets_empty_by_default(db_session):
    portfolio_id = _seed_portfolio(db_session)
    assert WatchlistService(db_session).list_watchlist_assets(portfolio_id) == []


def test_get_watchlist_asset_by_ticker(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)
    service.add_watchlist_asset(portfolio_id, _create_payload())

    view = service.get_watchlist_asset_by_ticker(portfolio_id, "MSFT")
    assert view is not None
    assert view.ticker == "MSFT"

    assert service.get_watchlist_asset_by_ticker(portfolio_id, "NOPE") is None


def test_update_watchlist_asset_changes_only_sent_fields(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)
    created = service.add_watchlist_asset(portfolio_id, _create_payload())

    updated = service.update_watchlist_asset(
        portfolio_id, created.id, WatchlistAssetUpdate(priority=7)
    )

    assert updated.priority == 7
    assert updated.name == "Microsoft Corp"


def test_set_status_moves_through_all_statuses(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)
    created = service.add_watchlist_asset(portfolio_id, _create_payload())

    for status in ("candidate", "watching", "blocked", "discarded", "bought"):
        view = service.set_status(portfolio_id, created.id, status)
        assert view.status == status


def test_set_status_rejects_invalid_status(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)
    created = service.add_watchlist_asset(portfolio_id, _create_payload())

    with pytest.raises(ValueError):
        service.set_status(portfolio_id, created.id, "invalid_status")


def test_block_asset_sets_blocked_status(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)
    created = service.add_watchlist_asset(portfolio_id, _create_payload())

    view = service.block_asset(portfolio_id, created.id)
    assert view.status == "blocked"


def test_discard_asset_sets_discarded_status(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)
    created = service.add_watchlist_asset(portfolio_id, _create_payload())

    view = service.discard_asset(portfolio_id, created.id)
    assert view.status == "discarded"


def test_mark_as_bought_sets_bought_status(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)
    created = service.add_watchlist_asset(portfolio_id, _create_payload())

    view = service.mark_as_bought(portfolio_id, created.id)
    assert view.status == "bought"


def test_remove_watchlist_asset(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)
    created = service.add_watchlist_asset(portfolio_id, _create_payload())

    assert service.remove_watchlist_asset(portfolio_id, created.id) is True
    assert service.list_watchlist_assets(portfolio_id) == []


def test_remove_watchlist_asset_returns_false_when_not_found(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)

    assert service.remove_watchlist_asset(portfolio_id, 999) is False


def test_watchlist_never_creates_position_or_changes_patrimonio(db_session):
    """Garantia central: cadastrar, editar, marcar 'bought' ou remover um
    item da watchlist nunca cria uma Position nem muda o patrimônio."""
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)

    summary_before = PortfolioService(db_session).get_summary(portfolio_id)
    assert summary_before.total_value == Decimal("0")

    created = service.add_watchlist_asset(portfolio_id, _create_payload())
    service.set_status(portfolio_id, created.id, "candidate")
    service.mark_as_bought(portfolio_id, created.id)

    assert db_session.query(Position).count() == 0
    summary_after = PortfolioService(db_session).get_summary(portfolio_id)
    assert summary_after.total_value == Decimal("0")


def test_watchlist_flags_already_in_portfolio(db_session):
    """Se o ticker já tem posição real na carteira, a view sinaliza isso —
    mas a watchlist continua sem alterar a Position existente."""
    portfolio_id = _seed_portfolio(db_session)
    asset = Asset(
        ticker="MSFT", name="Microsoft Corp", asset_class="stock", country="US", currency="USD"
    )
    db_session.add(asset)
    db_session.commit()
    position = Position(
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        quantity=Decimal("10"),
        average_price=Decimal("300"),
        currency="USD",
        opened_at=date(2024, 1, 1),
    )
    db_session.add(position)
    db_session.commit()

    service = WatchlistService(db_session)
    view = service.add_watchlist_asset(portfolio_id, _create_payload())

    assert view.already_in_portfolio is True
    assert db_session.query(Position).count() == 1


def test_watchlist_data_collection_ensures_asset_and_marks_low_confidence_without_prices(
    db_session,
):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)
    created = service.add_watchlist_asset(portfolio_id, _create_payload())

    result = service.collect_data_for_asset(portfolio_id, created.id)

    assert result.ticker == "MSFT"
    assert result.asset_ensured is True
    assert result.low_confidence is True
    assert result.confidence is not None and result.confidence < Decimal("0.5")
    assert db_session.query(Asset).filter(Asset.ticker == "MSFT").count() == 1


def test_watchlist_data_collection_raises_for_unknown_id(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)

    with pytest.raises(ValueError):
        service.collect_data_for_asset(portfolio_id, 999)
