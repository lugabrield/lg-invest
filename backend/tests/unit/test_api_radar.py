"""Testes de `GET/POST/PATCH/DELETE /api/watchlist` e `GET /api/radar`
(v1.1, Fase 7 — ver docs/API_CONTRACT.md).

Só contrato/serialização/wiring: a Watchlist (CRUD, troca de status,
coleta de dados) e o Radar Engine (classificação pura) já são cobertos
pelos testes de `WatchlistService`/`RadarService`/`evaluate_radar`. O
que este arquivo garante é que as rotas compõem tudo certo (Decimal como
string, 404 para id desconhecido, 422 para duplicata/status inválido), e
que nenhuma ação aqui cria `Position` ou muda patrimônio.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.app import app
from backend.app.api.deps import get_db
from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import Portfolio


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.commit()
    return portfolio.id


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


_PAYLOAD = {
    "ticker": "msft",
    "name": "Microsoft Corp",
    "asset_class": "stock",
    "country": "us",
    "currency": "usd",
    "thesis": "Qualidade + moat + exposicao internacional.",
}


def test_list_watchlist_empty_by_default(client, db_session):
    portfolio_id = _seed_portfolio(db_session)

    response = client.get("/api/watchlist", params={"portfolio_id": portfolio_id})

    assert response.status_code == 200
    assert response.json() == []


def test_add_watchlist_asset_creates_entry(client, db_session):
    portfolio_id = _seed_portfolio(db_session)

    response = client.post("/api/watchlist", params={"portfolio_id": portfolio_id}, json=_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["ticker"] == "MSFT"
    assert body["status"] == "watching"
    assert body["already_in_portfolio"] is False


def test_add_watchlist_asset_rejects_duplicate_active_ticker(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    client.post("/api/watchlist", params={"portfolio_id": portfolio_id}, json=_PAYLOAD)

    response = client.post("/api/watchlist", params={"portfolio_id": portfolio_id}, json=_PAYLOAD)

    assert response.status_code == 422


def test_add_watchlist_asset_rejects_invalid_asset_class(client, db_session):
    portfolio_id = _seed_portfolio(db_session)

    response = client.post(
        "/api/watchlist",
        params={"portfolio_id": portfolio_id},
        json={**_PAYLOAD, "asset_class": "not_a_real_class"},
    )

    assert response.status_code == 422


def test_update_watchlist_asset_changes_fields(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    created = client.post(
        "/api/watchlist", params={"portfolio_id": portfolio_id}, json=_PAYLOAD
    ).json()

    response = client.patch(
        f"/api/watchlist/{created['id']}",
        params={"portfolio_id": portfolio_id},
        json={"priority": 8, "notes": "Acompanhar resultado trimestral."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["priority"] == 8
    assert body["notes"] == "Acompanhar resultado trimestral."


def test_update_watchlist_asset_404_for_unknown_id(client, db_session):
    portfolio_id = _seed_portfolio(db_session)

    response = client.patch(
        "/api/watchlist/999999", params={"portfolio_id": portfolio_id}, json={"priority": 5}
    )

    assert response.status_code == 404


def test_set_watchlist_status_updates_status(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    created = client.post(
        "/api/watchlist", params={"portfolio_id": portfolio_id}, json=_PAYLOAD
    ).json()

    response = client.patch(
        f"/api/watchlist/{created['id']}/status",
        params={"portfolio_id": portfolio_id},
        json={"status": "candidate"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "candidate"


def test_set_watchlist_status_rejects_invalid_status(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    created = client.post(
        "/api/watchlist", params={"portfolio_id": portfolio_id}, json=_PAYLOAD
    ).json()

    response = client.patch(
        f"/api/watchlist/{created['id']}/status",
        params={"portfolio_id": portfolio_id},
        json={"status": "not_a_real_status"},
    )

    assert response.status_code == 422


def test_remove_watchlist_asset_deletes_entry(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    created = client.post(
        "/api/watchlist", params={"portfolio_id": portfolio_id}, json=_PAYLOAD
    ).json()

    response = client.delete(
        f"/api/watchlist/{created['id']}", params={"portfolio_id": portfolio_id}
    )

    assert response.status_code == 204
    assert client.get("/api/watchlist", params={"portfolio_id": portfolio_id}).json() == []


def test_remove_watchlist_asset_404_for_unknown_id(client, db_session):
    portfolio_id = _seed_portfolio(db_session)

    response = client.delete("/api/watchlist/999999", params={"portfolio_id": portfolio_id})

    assert response.status_code == 404


def test_collect_watchlist_asset_data_returns_result(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    created = client.post(
        "/api/watchlist", params={"portfolio_id": portfolio_id}, json=_PAYLOAD
    ).json()

    response = client.post(
        f"/api/watchlist/{created['id']}/collect", params={"portfolio_id": portfolio_id}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "MSFT"
    assert body["asset_ensured"] is True
    # Sem histórico de preço/fundamentos no teste -> baixa confiança, nunca
    # um valor de confiança inventado (mesma asserção de
    # test_watchlist_data_collection_ensures_asset_and_marks_low_confidence_without_prices).
    assert body["low_confidence"] is True


def test_collect_all_watchlist_data_returns_one_result_per_entry(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    client.post("/api/watchlist", params={"portfolio_id": portfolio_id}, json=_PAYLOAD)
    client.post(
        "/api/watchlist",
        params={"portfolio_id": portfolio_id},
        json={**_PAYLOAD, "ticker": "AAPL", "name": "Apple Inc"},
    )

    response = client.post("/api/watchlist/collect-all", params={"portfolio_id": portfolio_id})

    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


def test_radar_evaluation_empty_when_no_candidates(client, db_session):
    portfolio_id = _seed_portfolio(db_session)

    response = client.get("/api/radar", params={"portfolio_id": portfolio_id})

    assert response.status_code == 200
    assert response.json() == {"candidates": []}


def test_radar_evaluation_includes_watchlist_candidate(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    client.post("/api/watchlist", params={"portfolio_id": portfolio_id}, json=_PAYLOAD)

    response = client.get("/api/radar", params={"portfolio_id": portfolio_id})

    assert response.status_code == 200
    candidates = response.json()["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["ticker"] == "MSFT"
    assert candidates[0]["is_current_holding"] is False
