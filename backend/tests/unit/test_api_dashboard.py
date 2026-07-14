"""Testes do `GET /api/dashboard` (v1.1, Fase 2 — ver docs/API_CONTRACT.md).

Só contrato/serialização: nenhum teste aqui recalcula regra de negócio —
isso já é coberto pelos testes de cada service (`test_dashboard_view_service.py`,
`test_portfolio_health_service.py`, `test_portfolio_risk_service.py` etc.).
O que este arquivo garante é que a API compõe os 7 pedaços certos, no
formato certo (Decimal como string, nunca float), sem duplicar cálculo.
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


def _seed_simple_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    wege = Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    db.add(wege)
    db.flush()

    db.add(
        Position(
            portfolio_id=portfolio.id,
            asset_id=wege.id,
            quantity=Decimal("100"),
            average_price=Decimal("38"),
            currency="BRL",
            opened_at=date(2025, 1, 1),
        )
    )
    db.add(Price(asset_id=wege.id, date=date(2026, 6, 27), close=Decimal("40")))
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


def test_dashboard_returns_all_seven_pieces(client, db_session):
    _seed_simple_portfolio(db_session)

    response = client.get("/api/dashboard", params={"portfolio_id": 1})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "view",
        "diagnostics",
        "intelligence",
        "data_quality",
        "health",
        "risk",
        "data_refresh_status",
    }


def test_dashboard_view_matches_seeded_position(client, db_session):
    _seed_simple_portfolio(db_session)

    body = client.get("/api/dashboard", params={"portfolio_id": 1}).json()

    positions = body["view"]["positions"]
    assert len(positions) == 1
    assert positions[0]["ticker"] == "WEGE3.SA"
    assert isinstance(positions[0]["current_price"], str)
    assert Decimal(positions[0]["current_price"]) == Decimal("40")


def test_dashboard_health_and_risk_are_populated(client, db_session):
    _seed_simple_portfolio(db_session)

    body = client.get("/api/dashboard", params={"portfolio_id": 1}).json()

    assert "overall_score" in body["health"]
    assert "overall_classification" in body["health"]
    assert isinstance(body["health"]["overall_score"], str)

    assert "overall_score" in body["risk"]
    assert "overall_classification" in body["risk"]
    assert isinstance(body["risk"]["overall_score"], str)


def test_dashboard_defaults_to_portfolio_1_when_no_query_param(client, db_session):
    _seed_simple_portfolio(db_session)

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    assert len(response.json()["view"]["positions"]) == 1


def test_dashboard_empty_portfolio_returns_empty_positions(client, db_session):
    portfolio = Portfolio(name="Vazia", base_currency="BRL")
    db_session.add(portfolio)
    db_session.commit()

    response = client.get("/api/dashboard", params={"portfolio_id": portfolio.id})

    assert response.status_code == 200
    assert response.json()["view"]["positions"] == []


def test_system_status_reports_database_ok(client):
    response = client.get("/api/system/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database_ok"] is True
    assert "environment" in body


def test_cors_configured_for_default_frontend_origin():
    from backend.app.core.config import settings

    assert "http://localhost:3000" in settings.api_cors_origins_list
