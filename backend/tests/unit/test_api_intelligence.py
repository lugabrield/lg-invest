"""Testes de `GET /api/intelligence` (v1.1, Fase 5 — ver docs/API_CONTRACT.md).

Só contrato/serialização/wiring: o Conviction Score v2 em si já é coberto
por `test_conviction_score_service.py`/`test_ids_methodology_engine.py`, e
a análise de renda por `test_income_analysis_service.py`. O que este
arquivo garante é que a rota compõe os dois corretamente, devolve
Decimal como string, e não quebra com carteira vazia (sem posição
nenhuma, sem proventos).
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


def _seed_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    stock = Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    db.add(stock)
    db.flush()

    db.add(
        Position(
            portfolio_id=portfolio.id,
            asset_id=stock.id,
            quantity=Decimal("100"),
            average_price=Decimal("38"),
            currency="BRL",
            opened_at=date(2025, 1, 1),
        )
    )
    db.add(Price(asset_id=stock.id, date=date(2026, 6, 27), close=Decimal("40")))
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


def test_get_intelligence_returns_view_and_income(client, db_session):
    _seed_portfolio(db_session)

    response = client.get("/api/intelligence", params={"portfolio_id": 1})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"view", "income"}
    assert len(body["view"]["assets"]) == 1
    asset = body["view"]["assets"][0]
    assert asset["ticker"] == "WEGE3.SA"
    assert isinstance(asset["current_weight"], str)
    assert isinstance(body["income"]["trend"]["ttm_total"], str)
    assert isinstance(body["income"]["breakdown"]["rows"], list)


def test_get_intelligence_empty_portfolio_does_not_error(client, db_session):
    portfolio = Portfolio(name="Carteira vazia", base_currency="BRL")
    db_session.add(portfolio)
    db_session.commit()

    response = client.get("/api/intelligence", params={"portfolio_id": portfolio.id})

    assert response.status_code == 200
    body = response.json()
    assert body["view"]["assets"] == []
    assert body["view"]["average_conviction_score"] is None
    assert body["income"]["breakdown"]["rows"] == []


def test_get_intelligence_default_portfolio_id(client, db_session):
    _seed_portfolio(db_session)

    response = client.get("/api/intelligence")

    assert response.status_code == 200
    assert len(response.json()["view"]["assets"]) == 1
