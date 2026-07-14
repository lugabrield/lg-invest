"""Testes de `POST /api/simulacao` (v1.1, Fase 8 — ver docs/API_CONTRACT.md).

Só contrato/serialização/wiring: o Monte Carlo Simulation Engine em si
(percentis, probabilidade de perda, reasons/warnings) já é coberto por
`test_simulation_engine.py` e `test_simulation_service.py`. O que este
arquivo garante é que a rota compõe tudo certo (Decimal como string,
defaults iguais aos do Streamlit, validação 422 de horizonte/nº de
simulações/aporte negativo, semente fixa quando `reproducible=true`), e
que nenhuma chamada aqui persiste nada no banco.
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
from backend.app.services import simulation_assumptions_service as assumptions_svc


@pytest.fixture(autouse=True)
def _isolated_settings_file(tmp_path, monkeypatch):
    # Mesmo isolamento de `test_simulation_service.py`: a rota lê
    # premissas via `simulation_assumptions_service`, que persiste em
    # `data/app_settings.json` — nunca deve tocar o arquivo real de
    # desenvolvimento durante os testes.
    settings_path = tmp_path / "app_settings.json"
    monkeypatch.setattr(assumptions_svc, "_SETTINGS_PATH", settings_path)
    yield settings_path


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


def test_run_simulation_uses_defaults_when_payload_is_empty(client, db_session):
    portfolio_id = _seed_portfolio(db_session)

    response = client.post("/api/simulacao", params={"portfolio_id": portfolio_id}, json={})

    assert response.status_code == 200
    body = response.json()
    assert body["model_version"] == "simulation_v1"
    assert body["horizon_years"] == 20
    assert body["num_simulations"] == 2000
    assert body["monthly_contribution"] == "1000"


def test_run_simulation_returns_result_for_empty_portfolio(client, db_session):
    portfolio_id = _seed_portfolio(db_session)

    response = client.post(
        "/api/simulacao",
        params={"portfolio_id": portfolio_id},
        json={"monthly_contribution": "500", "horizon_years": 10, "num_simulations": 100},
    )

    assert response.status_code == 200
    body = response.json()
    # Sem posições: nenhum componente de mercado é inventado, só
    # acumula os aportes futuros (mesma regra de
    # test_run_portfolio_simulation_handles_empty_portfolio).
    expected = 500 * 12 * 10
    assert abs(float(body["median_final_value"]) - expected) < 1
    assert set(body["percentiles"].keys()) == {"p10", "p25", "p50", "p75", "p90"}
    assert len(body["reasons"]) > 0


def test_run_simulation_reproducible_seed_is_deterministic(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    payload = {
        "monthly_contribution": "1000",
        "horizon_years": 15,
        "num_simulations": 200,
        "reproducible": True,
    }

    first = client.post("/api/simulacao", params={"portfolio_id": portfolio_id}, json=payload)
    second = client.post("/api/simulacao", params={"portfolio_id": portfolio_id}, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["percentiles"] == second.json()["percentiles"]


def test_run_simulation_rejects_horizon_out_of_range(client, db_session):
    portfolio_id = _seed_portfolio(db_session)

    response = client.post(
        "/api/simulacao", params={"portfolio_id": portfolio_id}, json={"horizon_years": 0}
    )

    assert response.status_code == 422


def test_run_simulation_rejects_horizon_above_max(client, db_session):
    portfolio_id = _seed_portfolio(db_session)

    response = client.post(
        "/api/simulacao", params={"portfolio_id": portfolio_id}, json={"horizon_years": 101}
    )

    assert response.status_code == 422


def test_run_simulation_rejects_num_simulations_below_min(client, db_session):
    portfolio_id = _seed_portfolio(db_session)

    response = client.post(
        "/api/simulacao", params={"portfolio_id": portfolio_id}, json={"num_simulations": 50}
    )

    assert response.status_code == 422


def test_run_simulation_rejects_num_simulations_above_max(client, db_session):
    portfolio_id = _seed_portfolio(db_session)

    response = client.post(
        "/api/simulacao", params={"portfolio_id": portfolio_id}, json={"num_simulations": 20001}
    )

    assert response.status_code == 422


def test_run_simulation_rejects_negative_contribution(client, db_session):
    portfolio_id = _seed_portfolio(db_session)

    response = client.post(
        "/api/simulacao",
        params={"portfolio_id": portfolio_id},
        json={"monthly_contribution": "-100"},
    )

    assert response.status_code == 422
