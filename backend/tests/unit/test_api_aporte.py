"""Testes de `POST /api/aporte` e `GET /api/assets` (v1.1, Fase 3 — ver
docs/API_CONTRACT.md).

Só contrato/serialização/wiring: a lógica de recomendação em si (score,
elegibilidade, limites pós-aporte etc.) já é coberta por
`test_decision_service_v3.py` e pelos testes dos engines. O que este
arquivo garante é que a rota chama o `DecisionService` certo pela versão
pedida, devolve `RecommendationResult` + `AllocationProjection` no formato
certo (Decimal como string), respeita `persist`, e que `GET /api/assets`
lista o universo de ativos usado pelo seletor de bloqueados.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.app import app
from backend.app.api.deps import get_db
from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.infrastructure.database.models.recommendation import Recommendation


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


def test_simulate_aporte_v3_returns_result_and_projection(client, db_session):
    _seed_portfolio(db_session)

    response = client.post(
        "/api/aporte",
        params={"portfolio_id": 1},
        json={"amount": "1000", "persist": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"result", "projection"}
    assert body["result"]["audit"]["model_version"] == "decision_v3"
    assert isinstance(body["result"]["contribution_amount"], str)
    assert Decimal(body["result"]["contribution_amount"]) == Decimal("1000")
    if body["result"]["items"]:
        assert body["projection"] is not None
        assert isinstance(body["projection"]["total_before_brl"], str)


def test_simulate_aporte_respects_engine_version_v1(client, db_session):
    _seed_portfolio(db_session)

    response = client.post(
        "/api/aporte",
        params={"portfolio_id": 1},
        json={"amount": "1000", "engine_version": "v1", "persist": False},
    )

    assert response.status_code == 200
    assert response.json()["result"]["audit"]["model_version"] != "decision_v3"


def test_simulate_aporte_blocks_manually_blocked_ticker(client, db_session):
    _seed_portfolio(db_session)

    response = client.post(
        "/api/aporte",
        params={"portfolio_id": 1},
        json={"amount": "1000", "blocked": ["wege3.sa"], "persist": False},
    )

    body = response.json()
    ignored_tickers = {item["ticker"] for item in body["result"]["ignored"]}
    assert "WEGE3.SA" in ignored_tickers
    blocked_entry = next(i for i in body["result"]["ignored"] if i["ticker"] == "WEGE3.SA")
    assert blocked_entry["block_source"] == "bloqueio_manual"


def test_simulate_aporte_projection_is_null_when_nothing_allocated(client, db_session):
    _seed_portfolio(db_session)

    response = client.post(
        "/api/aporte",
        params={"portfolio_id": 1},
        json={
            "amount": "1000",
            "blocked": ["WEGE3.SA", "BTC-USD", "VOO"],
            "persist": False,
        },
    )

    body = response.json()
    assert body["result"]["items"] == []
    assert body["projection"] is None


def test_simulate_aporte_persist_true_writes_recommendation_rows(client, db_session):
    _seed_portfolio(db_session)

    response = client.post(
        "/api/aporte",
        params={"portfolio_id": 1},
        json={"amount": "1000", "persist": True},
    )

    assert response.status_code == 200
    saved = db_session.query(Recommendation).all()
    if response.json()["result"]["items"]:
        assert len(saved) > 0
    else:
        assert len(saved) == 0


def test_simulate_aporte_persist_false_writes_nothing(client, db_session):
    _seed_portfolio(db_session)

    client.post(
        "/api/aporte",
        params={"portfolio_id": 1},
        json={"amount": "1000", "persist": False},
    )

    assert db_session.query(Recommendation).count() == 0


def test_simulate_aporte_rejects_invalid_engine_version(client, db_session):
    _seed_portfolio(db_session)

    response = client.post(
        "/api/aporte",
        params={"portfolio_id": 1},
        json={"amount": "1000", "engine_version": "v9"},
    )

    assert response.status_code == 422


def test_list_assets_returns_seeded_universe(client, db_session):
    _seed_portfolio(db_session)

    response = client.get("/api/assets")

    assert response.status_code == 200
    tickers = {a["ticker"] for a in response.json()}
    assert tickers == {"WEGE3.SA", "BTC-USD", "VOO"}
