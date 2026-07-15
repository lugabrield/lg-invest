"""Testes de `/api/configuracoes/*` (v1.1, Fase 10 — ver docs/API_CONTRACT.md).

Só contrato/serialização/wiring: cada camada (câmbio, preços, alocação
simples/presets, regras detalhadas, política de investimento, visão
geral e premissas do Monte Carlo) já é coberta por testes de serviço
próprios (`test_fx_settings_service.py`, `test_target_allocation_*`,
`test_investment_policy_service.py`, `test_allocation_overview_service.py`,
`test_simulation_assumptions_service.py`). O que este arquivo garante é
que as rotas compõem tudo certo (404/422 nos lugares certos, isolamento
dos três arquivos JSON de configuração) — nunca toca a rede de verdade
(atualização automática de câmbio/preços é mockada).
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
from backend.app.schemas.market_data import BatchUpdateResult, FxQuote
from backend.app.services import (
    fx_settings_service,
    simulation_assumptions_service,
    target_allocation_settings_service,
)


@pytest.fixture(autouse=True)
def _isolated_settings_files(tmp_path, monkeypatch):
    # As três camadas persistidas em JSON (câmbio, alocação-alvo simples,
    # premissas do Monte Carlo) nunca devem tocar o arquivo real de
    # desenvolvimento durante os testes — mesmo padrão já usado nos
    # testes de serviço de cada uma.
    monkeypatch.setattr(fx_settings_service, "_SETTINGS_PATH", tmp_path / "app_settings.json")
    monkeypatch.setattr(
        target_allocation_settings_service, "_SETTINGS_PATH", tmp_path / "app_settings.json"
    )
    monkeypatch.setattr(
        simulation_assumptions_service, "_SETTINGS_PATH", tmp_path / "app_settings.json"
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


# --- Sistema -------------------------------------------------------------


def test_get_system_info_returns_environment_and_assets_count(client, db_session):
    _seed_portfolio(db_session)

    response = client.get("/api/configuracoes/sistema", params={"portfolio_id": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_id"] == 1
    assert body["assets_count"] == 0
    assert (
        "://" not in body["database_url_redacted"]
        or ":***@" in body["database_url_redacted"]
        or "@" not in body["database_url_redacted"]
    )


def test_get_fx_status_defaults_when_never_set(client):
    response = client.get("/api/configuracoes/fx")

    assert response.status_code == 200
    body = response.json()
    assert body["quote"] is None
    assert float(body["current_rate"]) > 0


def test_set_fx_rate_manually_updates_status(client):
    response = client.put("/api/configuracoes/fx", json={"rate": "5.35"})

    assert response.status_code == 200
    body = response.json()
    assert body["current_rate"] == "5.35"
    assert body["quote"]["source"] == "manual"


def test_set_fx_rate_rejects_non_positive(client):
    response = client.put("/api/configuracoes/fx", json={"rate": "0"})

    assert response.status_code == 422


def test_refresh_fx_rate_returns_quote_on_success(client, monkeypatch):
    from datetime import UTC, datetime

    import backend.app.services.fx_service as fx_service_module

    fake_quote = FxQuote(
        rate="5.42", source="bcb", quote_date=datetime.now(UTC), fetched_at=datetime.now(UTC)
    )
    monkeypatch.setattr(fx_service_module, "update_usd_brl_rate", lambda: fake_quote)

    response = client.post("/api/configuracoes/fx/refresh")

    assert response.status_code == 200
    assert response.json()["source"] == "bcb"


def test_refresh_fx_rate_returns_503_when_all_sources_fail(client, monkeypatch):
    import backend.app.services.fx_service as fx_service_module

    def _raise():
        raise RuntimeError("sem internet")

    monkeypatch.setattr(fx_service_module, "update_usd_brl_rate", _raise)

    response = client.post("/api/configuracoes/fx/refresh")

    assert response.status_code == 503


def test_refresh_prices_returns_batch_result(client, monkeypatch):
    import backend.app.services.market_data_service as market_data_service_module

    monkeypatch.setattr(
        market_data_service_module.MarketDataService,
        "update_all_active",
        lambda self: BatchUpdateResult(results=[]),
    )

    response = client.post("/api/configuracoes/precos/refresh")

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_refresh_prices_returns_503_on_unexpected_error(client, monkeypatch):
    import backend.app.services.market_data_service as market_data_service_module

    def _raise(self):
        raise RuntimeError("Yahoo indisponível")

    monkeypatch.setattr(market_data_service_module.MarketDataService, "update_all_active", _raise)

    response = client.post("/api/configuracoes/precos/refresh")

    assert response.status_code == 503


# --- Camada 1: alocação-alvo simples --------------------------------------


def test_get_simple_allocation_empty_by_default(client):
    response = client.get("/api/configuracoes/alocacao-simples")

    assert response.status_code == 200
    body = response.json()
    assert body["allocation"] == {}
    assert body["has_target"] is False


def test_set_simple_allocation_valid_sum(client):
    response = client.put(
        "/api/configuracoes/alocacao-simples",
        json={"allocation": {"stock": "0.6", "bond": "0.4"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_target"] is True
    assert body["allocation"]["stock"] == "0.6"


def test_set_simple_allocation_rejects_sum_not_100(client):
    response = client.put(
        "/api/configuracoes/alocacao-simples",
        json={"allocation": {"stock": "0.5", "bond": "0.2"}},
    )

    assert response.status_code == 422


def test_clear_simple_allocation_resets_to_empty(client):
    client.put(
        "/api/configuracoes/alocacao-simples",
        json={"allocation": {"stock": "1.0"}},
    )

    response = client.delete("/api/configuracoes/alocacao-simples")
    assert response.status_code == 204

    after = client.get("/api/configuracoes/alocacao-simples").json()
    assert after["allocation"] == {}


def test_list_allocation_presets_includes_personalizado(client):
    response = client.get("/api/configuracoes/alocacao-presets")

    assert response.status_code == 200
    keys = [p["key"] for p in response.json()]
    assert "personalizado" in keys
    assert "moderado" in keys


def test_apply_allocation_preset_sets_simple_allocation(client):
    response = client.post("/api/configuracoes/alocacao-presets/moderado/aplicar")

    assert response.status_code == 200
    body = response.json()
    assert body["has_target"] is True
    assert float(body["allocation"]["stock"]) == 0.3


def test_apply_allocation_preset_personalizado_returns_422(client):
    response = client.post("/api/configuracoes/alocacao-presets/personalizado/aplicar")

    assert response.status_code == 422


def test_apply_allocation_preset_unknown_returns_404(client):
    response = client.post("/api/configuracoes/alocacao-presets/nao_existe/aplicar")

    assert response.status_code == 404


# --- Camada 2: regras detalhadas ------------------------------------------


def test_list_target_allocation_rules_empty_by_default(client, db_session):
    _seed_portfolio(db_session)

    response = client.get("/api/configuracoes/regras-alocacao", params={"portfolio_id": 1})

    assert response.status_code == 200
    assert response.json() == []


def test_upsert_target_allocation_rule_creates_rule(client, db_session):
    _seed_portfolio(db_session)

    response = client.put(
        "/api/configuracoes/regras-alocacao",
        params={"portfolio_id": 1},
        json={"dimension_type": "class", "dimension_key": "fii", "target_weight": "0.2"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["dimension_type"] == "class"
    assert body["dimension_key"] == "fii"
    assert float(body["target_weight"]) == 0.2


def test_upsert_target_allocation_rule_rejects_min_greater_than_max(client, db_session):
    _seed_portfolio(db_session)

    response = client.put(
        "/api/configuracoes/regras-alocacao",
        params={"portfolio_id": 1},
        json={
            "dimension_type": "class",
            "dimension_key": "fii",
            "min_weight": "0.5",
            "max_weight": "0.2",
        },
    )

    assert response.status_code == 422


def test_upsert_target_allocation_rule_rejects_invalid_dimension_type(client, db_session):
    _seed_portfolio(db_session)

    response = client.put(
        "/api/configuracoes/regras-alocacao",
        params={"portfolio_id": 1},
        json={"dimension_type": "not_a_real_dimension", "dimension_key": "fii"},
    )

    assert response.status_code == 422


def test_delete_target_allocation_rule_removes_entry(client, db_session):
    _seed_portfolio(db_session)
    client.put(
        "/api/configuracoes/regras-alocacao",
        params={"portfolio_id": 1},
        json={"dimension_type": "currency", "dimension_key": "USD", "target_weight": "0.3"},
    )

    response = client.delete(
        "/api/configuracoes/regras-alocacao/currency/USD", params={"portfolio_id": 1}
    )

    assert response.status_code == 204
    assert client.get("/api/configuracoes/regras-alocacao", params={"portfolio_id": 1}).json() == []


def test_delete_target_allocation_rule_404_for_unknown(client, db_session):
    _seed_portfolio(db_session)

    response = client.delete(
        "/api/configuracoes/regras-alocacao/class/nao_existe", params={"portfolio_id": 1}
    )

    assert response.status_code == 404


# --- Camada 3: política de investimento -----------------------------------


def test_get_investment_policy_returns_defaults_on_first_read(client, db_session):
    _seed_portfolio(db_session)

    response = client.get("/api/configuracoes/politica", params={"portfolio_id": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["risk_tolerance"] == "moderado-alto"
    assert body["horizon_years"] == 50


def test_update_investment_policy_changes_only_sent_fields(client, db_session):
    _seed_portfolio(db_session)
    client.get("/api/configuracoes/politica", params={"portfolio_id": 1})

    response = client.patch(
        "/api/configuracoes/politica",
        params={"portfolio_id": 1},
        json={"horizon_years": 30},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["horizon_years"] == 30
    assert body["risk_tolerance"] == "moderado-alto"


# --- Visão geral (precedência e conflitos) --------------------------------


def test_get_allocation_overview_empty_when_nothing_configured(client, db_session):
    _seed_portfolio(db_session)

    response = client.get("/api/configuracoes/visao-geral", params={"portfolio_id": 1})

    assert response.status_code == 200
    body = response.json()
    assert "effective_limits" in body
    assert "conflicts" in body


# --- Premissas do Monte Carlo ---------------------------------------------


def test_get_simulation_assumptions_covers_all_asset_classes(client):
    response = client.get("/api/configuracoes/premissas-simulacao")

    assert response.status_code == 200
    body = response.json()
    assert len(body["assumptions"]) == 7
    assert all(a["source"] == "default do sistema" for a in body["assumptions"])


def test_set_simulation_assumption_marks_as_user_adjusted(client):
    response = client.put(
        "/api/configuracoes/premissas-simulacao",
        json={"asset_class": "stock", "expected_return": "0.13", "volatility": "0.28"},
    )

    assert response.status_code == 200
    stock = next(a for a in response.json()["assumptions"] if a["asset_class"] == "stock")
    assert stock["source"] == "ajustado pelo usuário"
    assert stock["expected_return"] == "0.13"


def test_set_simulation_assumption_rejects_unknown_asset_class(client):
    response = client.put(
        "/api/configuracoes/premissas-simulacao",
        json={"asset_class": "nao_existe", "expected_return": "0.1", "volatility": "0.1"},
    )

    assert response.status_code == 422


def test_reset_simulation_assumption_restores_default(client):
    client.put(
        "/api/configuracoes/premissas-simulacao",
        json={"asset_class": "stock", "expected_return": "0.13", "volatility": "0.28"},
    )

    response = client.delete("/api/configuracoes/premissas-simulacao/stock")

    assert response.status_code == 200
    stock = next(a for a in response.json()["assumptions"] if a["asset_class"] == "stock")
    assert stock["source"] == "default do sistema"
