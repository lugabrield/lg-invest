"""Testes de `GET/POST /api/journal`, `/api/theses` e
`/api/theses/{id}/reviews` (v1.1, Fase 9 — ver docs/API_CONTRACT.md).

Só contrato/serialização/wiring: as regras de diário e de ciclo de vida
de tese (criação sempre "open", revisão atualiza status conforme
classificação, histórico nunca é apagado) já são cobertas por
`test_thesis_service.py` e pelos testes de `JournalService`. O que este
arquivo garante é que as rotas resolvem o `ticker` certo, devolvem 404
para ticker/tese desconhecidos, e 422 para action/classification
inválidas.
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
from backend.app.infrastructure.database.models import Asset


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


def _seed_asset(db) -> Asset:
    asset = Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    db.add(asset)
    db.commit()
    db.refresh(asset)
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


def test_list_journal_entries_empty_by_default(client, db_session):
    response = client.get("/api/journal")

    assert response.status_code == 200
    assert response.json() == []


def test_create_journal_entry_resolves_ticker(client, db_session):
    _seed_asset(db_session)

    response = client.post(
        "/api/journal",
        json={
            "ticker": "wege3.sa",
            "action": "buy",
            "date": "2026-07-14",
            "thesis": "Reforço de posição após resultado trimestral.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["ticker"] == "WEGE3.SA"
    assert body["action"] == "buy"
    assert body["expected_outcome"] is None


def test_create_journal_entry_404_for_unknown_ticker(client, db_session):
    response = client.post(
        "/api/journal",
        json={
            "ticker": "DESCONHECIDO",
            "action": "buy",
            "date": "2026-07-14",
            "thesis": "x",
        },
    )

    assert response.status_code == 404


def test_create_journal_entry_rejects_invalid_action(client, db_session):
    _seed_asset(db_session)

    response = client.post(
        "/api/journal",
        json={
            "ticker": "WEGE3.SA",
            "action": "not_a_real_action",
            "date": "2026-07-14",
            "thesis": "x",
        },
    )

    assert response.status_code == 422


def test_list_theses_empty_by_default(client, db_session):
    response = client.get("/api/theses")

    assert response.status_code == 200
    assert response.json() == []


def test_create_thesis_starts_open_and_resolves_ticker(client, db_session):
    _seed_asset(db_session)

    response = client.post(
        "/api/theses",
        json={
            "ticker": "wege3.sa",
            "thesis_date": "2026-07-14",
            "hypothesis": "Qualidade, crescimento e moat consistente no setor industrial.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["ticker"] == "WEGE3.SA"
    assert body["status"] == "open"


def test_create_thesis_404_for_unknown_ticker(client, db_session):
    response = client.post(
        "/api/theses",
        json={
            "ticker": "DESCONHECIDO",
            "thesis_date": "2026-07-14",
            "hypothesis": "x",
        },
    )

    assert response.status_code == 404


def test_create_thesis_review_updates_thesis_status(client, db_session):
    _seed_asset(db_session)
    created = client.post(
        "/api/theses",
        json={"ticker": "WEGE3.SA", "thesis_date": "2026-07-14", "hypothesis": "x"},
    ).json()

    response = client.post(
        f"/api/theses/{created['id']}/reviews",
        json={
            "review_date": "2026-08-01",
            "classification": "confirmed",
            "notes": "Resultado trimestral confirmou a tese.",
        },
    )

    assert response.status_code == 201
    assert response.json()["classification"] == "confirmed"

    theses_after = client.get("/api/theses").json()
    assert theses_after[0]["status"] == "confirmed"


def test_create_thesis_review_404_for_unknown_thesis(client, db_session):
    response = client.post(
        "/api/theses/999999/reviews",
        json={"review_date": "2026-08-01", "classification": "confirmed"},
    )

    assert response.status_code == 404


def test_create_thesis_review_rejects_invalid_classification(client, db_session):
    _seed_asset(db_session)
    created = client.post(
        "/api/theses",
        json={"ticker": "WEGE3.SA", "thesis_date": "2026-07-14", "hypothesis": "x"},
    ).json()

    response = client.post(
        f"/api/theses/{created['id']}/reviews",
        json={"review_date": "2026-08-01", "classification": "not_a_real_classification"},
    )

    assert response.status_code == 422
