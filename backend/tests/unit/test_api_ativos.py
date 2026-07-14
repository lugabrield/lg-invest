"""Testes de `GET/PATCH/POST /api/ativos/*` (v1.1, Fase 6 — ver
docs/API_CONTRACT.md).

Só contrato/serialização/wiring: LG Score, Conviction Score, valuation,
fundamentos, trap detection etc. já são cobertos pelos testes de cada
service/engine. O que este arquivo garante é que as rotas compõem tudo
certo (Decimal como string, 404 para ticker desconhecido), e que as
ações de escrita (flag manual, preço manual, refresh de preço/
fundamentos para ativos manuais — sem precisar de rede) funcionam.
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
from backend.app.infrastructure.database.models import Asset, Price


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


def _seed_stock(db, *, is_manual: bool = False) -> Asset:
    asset = Asset(
        ticker="WEGE3.SA",
        name="WEG",
        asset_class="stock",
        country="BR",
        currency="BRL",
        is_manual=is_manual,
    )
    db.add(asset)
    db.flush()
    db.add(Price(asset_id=asset.id, date=date(2026, 6, 27), close=Decimal("40"), source="yahoo"))
    db.commit()
    return asset


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_list_ativos_returns_seeded_asset(client, db_session):
    _seed_stock(db_session)

    response = client.get("/api/ativos")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    row = body[0]
    assert row["ticker"] == "WEGE3.SA"
    assert row["price_status"] == "automatic"
    assert Decimal(row["price"]) == Decimal("40")


def test_list_ativos_manual_asset_status(client, db_session):
    _seed_stock(db_session, is_manual=True)

    response = client.get("/api/ativos")

    assert response.json()[0]["price_status"] == "manual"


def test_get_ativo_detail_returns_bundle(client, db_session):
    _seed_stock(db_session)

    response = client.get("/api/ativos/WEGE3.SA", params={"portfolio_id": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "WEGE3.SA"
    assert body["asset_class"] == "stock"
    # Ação: valuation_v2 é o bloco aplicável, income_real_estate/adequacy ficam None.
    assert body["income_real_estate"] is None
    assert body["adequacy"] is None


def test_get_ativo_detail_404_for_unknown_ticker(client, db_session):
    response = client.get("/api/ativos/ZZZZ9")

    assert response.status_code == 404


def test_set_manual_flag_toggles_asset(client, db_session):
    _seed_stock(db_session)

    response = client.patch("/api/ativos/WEGE3.SA/manual-flag", json={"is_manual": True})

    assert response.status_code == 200
    assert response.json() == {"ticker": "WEGE3.SA", "is_manual": True}


def test_set_manual_flag_404_for_unknown_ticker(client, db_session):
    response = client.patch("/api/ativos/ZZZZ9/manual-flag", json={"is_manual": True})

    assert response.status_code == 404


def test_set_manual_price_creates_price(client, db_session):
    _seed_stock(db_session, is_manual=True)

    response = client.post("/api/ativos/WEGE3.SA/manual-price", json={"price": "42.50"})

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "WEGE3.SA"
    assert Decimal(body["price"]) == Decimal("42.50")
    assert body["source"] == "manual"


def test_set_manual_price_rejects_non_positive(client, db_session):
    _seed_stock(db_session, is_manual=True)

    response = client.post("/api/ativos/WEGE3.SA/manual-price", json={"price": "0"})

    assert response.status_code == 422


def test_refresh_price_skips_manual_asset_without_network(client, db_session):
    _seed_stock(db_session, is_manual=True)

    response = client.post("/api/ativos/WEGE3.SA/refresh-price")

    assert response.status_code == 200
    assert response.json()["result"]["skipped_manual"] is True


def test_collect_fundamentals_skips_manual_asset_without_network(client, db_session):
    _seed_stock(db_session, is_manual=True)

    response = client.post("/api/ativos/WEGE3.SA/collect-fundamentals")

    assert response.status_code == 200
    body = response.json()["result"]
    assert body["collected"] is False
    assert body["reason"] == "ativo manual"


def test_import_fundamentals_rejects_unsupported_extension(client, db_session):
    import io

    response = client.post(
        "/api/ativos/fundamentals-import",
        params={"portfolio_id": 1},
        files={"file": ("fundamentos.txt", io.BytesIO(b"not a real file"), "text/plain")},
    )

    assert response.status_code == 422
