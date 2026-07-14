"""Testes de `POST /api/portfolio/import` (v1.1, Fase 4 — ver
docs/API_CONTRACT.md).

Só contrato/wiring HTTP: a lógica de parsing/validação de linha já é
coberta por `test_position_importer.py` e `test_import_validators.py`.
O que este arquivo garante é que a rota aceita o upload, cria a carteira
se ainda não existir (mesmo comportamento de `_ensure_portfolio` na tela
Streamlit), devolve o resumo no formato certo, e rejeita extensão não
suportada sem quebrar.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.app import app
from backend.app.api.deps import get_db
from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import Asset, Portfolio

VALID_CSV = b"ticker,quantity,average_price,currency,opened_at\nWEGE3.SA,100,38.20,BRL,2025-06-01\n"
CSV_WITH_UNKNOWN_TICKER = (
    b"ticker,quantity,average_price,currency,opened_at\nZZZZ9,10,1.00,BRL,2025-06-01\n"
)


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


def _seed_asset(db) -> None:
    db.add(Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL"))
    db.commit()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_import_valid_csv_creates_position(client, db_session):
    _seed_asset(db_session)

    response = client.post(
        "/api/portfolio/import",
        params={"portfolio_id": 1},
        files={"file": ("positions.csv", io.BytesIO(VALID_CSV), "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 1
    assert body["updated"] == 0
    assert body["skipped"] == 0
    assert body["errors"] == []


def test_import_creates_portfolio_if_missing(client, db_session):
    _seed_asset(db_session)
    assert db_session.query(Portfolio).count() == 0

    response = client.post(
        "/api/portfolio/import",
        params={"portfolio_id": 1},
        files={"file": ("positions.csv", io.BytesIO(VALID_CSV), "text/csv")},
    )

    assert response.status_code == 200
    assert db_session.query(Portfolio).count() == 1


def test_import_is_idempotent_via_api(client, db_session):
    _seed_asset(db_session)

    first = client.post(
        "/api/portfolio/import",
        params={"portfolio_id": 1},
        files={"file": ("positions.csv", io.BytesIO(VALID_CSV), "text/csv")},
    )
    second = client.post(
        "/api/portfolio/import",
        params={"portfolio_id": 1},
        files={"file": ("positions.csv", io.BytesIO(VALID_CSV), "text/csv")},
    )

    assert first.json()["imported"] == 1
    assert second.json()["imported"] == 0
    assert second.json()["updated"] == 1


def test_import_unknown_ticker_reports_error_without_500(client, db_session):
    response = client.post(
        "/api/portfolio/import",
        params={"portfolio_id": 1},
        files={"file": ("positions.csv", io.BytesIO(CSV_WITH_UNKNOWN_TICKER), "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 0
    assert len(body["errors"]) == 1
    assert body["errors"][0]["line"] == 2  # linha 1 é o cabeçalho


def test_import_rejects_unsupported_extension(client, db_session):
    response = client.post(
        "/api/portfolio/import",
        params={"portfolio_id": 1},
        files={"file": ("positions.txt", io.BytesIO(b"not a real file"), "text/plain")},
    )

    assert response.status_code == 422
