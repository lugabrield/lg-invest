"""Testes de `/api/dividendos-me/*` (v1.1, Fase 11 — ver docs/API_CONTRACT.md).

Só contrato/wiring/segurança: a lógica de extração/diff/bloqueio já é
coberta por `test_dividendos_me_service.py`/`test_dividendos_me_income_service.py`.
O que este arquivo garante é que as rotas: (1) compõem tudo certo
(404/401/422/503 nos lugares certos), (2) nunca tocam Playwright/rede de
verdade (usa `_FakeClient`, monkeypatchado no lugar de `DividendosMeClient`
importado pelo módulo de rotas) e (3) respeitam as regras de segurança
de `docs/SECURITY_NOTES.md`: e-mail/senha nunca aparecem em nenhuma
resposta (sucesso ou erro), mesmo quando uma exceção simulada os
contém na mensagem.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.api.routes.dividendos_me as dividendos_me_routes
from backend.app.api.app import app
from backend.app.api.deps import get_db
from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import Asset, Portfolio, Position
from backend.app.integrations.dividendos_me.auth import DividendosMeAuthError
from backend.app.integrations.dividendos_me.client import DividendosMeScrapingError
from backend.app.integrations.dividendos_me.income_parser import (
    NormalizedIncomeEvent,
    NormalizedMonthlySummary,
)
from backend.app.integrations.dividendos_me.schemas import (
    ORIGIN_B3,
    ExtractedPosition,
)

_EMAIL = "investidor@example.com"
_PASSWORD = "senha-super-secreta-123"


def _extracted(
    ticker,
    *,
    quantity="10",
    average_price="100.00",
    current_value="1000.00",
    origin=ORIGIN_B3,
    asset_class="stock",
    currency="BRL",
    country="BR",
    review_required=False,
    review_reason=None,
    section="brasil",
) -> ExtractedPosition:
    return ExtractedPosition(
        raw_ticker=ticker,
        ticker=ticker,
        asset_class=asset_class,
        country=country,
        currency=currency,
        review_required=review_required,
        review_reason=review_reason,
        section=section,
        quantity=Decimal(quantity),
        average_price=Decimal(average_price) if average_price is not None else None,
        current_value=Decimal(current_value) if current_value is not None else None,
        origin=origin,
        synced_at=datetime.now(UTC),
    )


def _income_event(ticker="PETR4") -> NormalizedIncomeEvent:
    return NormalizedIncomeEvent(
        ticker=ticker,
        source="dividendos_me:calendar",
        event_type="dividend",
        status="scheduled",
        payment_date=date(2026, 8, 10),
        amount_total=Decimal("50.00"),
        currency="BRL",
        raw_payload={},
    )


def _monthly_summary(wallet="Carteira (B3)") -> NormalizedMonthlySummary:
    return NormalizedMonthlySummary(
        wallet_name=wallet,
        year=2026,
        month=6,
        amount_total=Decimal("300.00"),
        currency="BRL",
        source="dividendos_me:monthly",
        status="closed",
        annual_total=Decimal("1800.00"),
        annual_average=Decimal("300.00"),
        raw_payload={},
    )


class _FakeClient:
    """Substitui `DividendosMeClient` nos testes — nunca toca Playwright/rede."""

    behavior = "ok"
    positions: list[ExtractedPosition] = []
    failed_sections: list[str] = []
    income_events: list[NormalizedIncomeEvent] = []
    income_failed_sections: list[str] = []
    monthly_summaries: list[NormalizedMonthlySummary] = []
    monthly_failed_sections: list[str] = []

    def __init__(self, email: str, password: str, *, headless: bool = True):
        self.email = email
        self.password = password

    def _maybe_raise(self):
        if self.behavior == "auth_error":
            raise DividendosMeAuthError("Falha ao autenticar no Dividendos.me.")
        if self.behavior == "scraping_error":
            raise DividendosMeScrapingError("Playwright não está instalado neste ambiente.")
        if self.behavior == "unexpected":
            raise RuntimeError("boom")
        if self.behavior == "leak_password":
            raise DividendosMeAuthError(f"falha inesperada com senha {self.password}")

    def test_login(self) -> bool:
        self._maybe_raise()
        return True

    def fetch_portfolio(self):
        self._maybe_raise()
        return self.positions, self.failed_sections, []

    def fetch_income_events(self):
        self._maybe_raise()
        return self.income_events, self.income_failed_sections, []

    def fetch_income_monthly_summaries(self, *, debug=False, debug_dir=None):
        self._maybe_raise()
        return self.monthly_summaries, self.monthly_failed_sections, []


@pytest.fixture(autouse=True)
def _fake_client(monkeypatch):
    _FakeClient.behavior = "ok"
    _FakeClient.positions = []
    _FakeClient.failed_sections = []
    _FakeClient.income_events = []
    _FakeClient.income_failed_sections = []
    _FakeClient.monthly_summaries = []
    _FakeClient.monthly_failed_sections = []
    monkeypatch.setattr(dividendos_me_routes, "DividendosMeClient", _FakeClient)
    yield


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
        app.dependency_overrides.clear()


def _creds(**extra):
    return {"email": _EMAIL, "password": _PASSWORD, **extra}


# --- status --------------------------------------------------------------


def test_status_no_prior_sync(client, db_session, monkeypatch):
    _seed_portfolio(db_session)
    monkeypatch.setattr(dividendos_me_routes, "is_playwright_available", lambda: False)
    response = client.get("/api/dividendos-me/status")
    assert response.status_code == 200
    body = response.json()
    assert body["playwright_available"] is False
    assert body["last_sync_at"] is None
    assert body["last_sync_status"] is None


def test_status_reflects_playwright_available(client, db_session, monkeypatch):
    _seed_portfolio(db_session)
    monkeypatch.setattr(dividendos_me_routes, "is_playwright_available", lambda: True)
    response = client.get("/api/dividendos-me/status")
    assert response.json()["playwright_available"] is True


# --- test-login ------------------------------------------------------------


def test_test_login_success(client, db_session):
    _seed_portfolio(db_session)
    response = client.post("/api/dividendos-me/test-login", json=_creds())
    assert response.status_code == 200
    assert response.json() == {"success": True}


def test_test_login_blank_password_rejected(client, db_session):
    _seed_portfolio(db_session)
    response = client.post("/api/dividendos-me/test-login", json=_creds(password="  "))
    assert response.status_code == 422


def test_test_login_auth_error_returns_401(client, db_session):
    _seed_portfolio(db_session)
    _FakeClient.behavior = "auth_error"
    response = client.post("/api/dividendos-me/test-login", json=_creds())
    assert response.status_code == 401
    assert _PASSWORD not in response.text
    assert _EMAIL not in response.text


def test_test_login_scraping_error_returns_503(client, db_session):
    _seed_portfolio(db_session)
    _FakeClient.behavior = "scraping_error"
    response = client.post("/api/dividendos-me/test-login", json=_creds())
    assert response.status_code == 503


def test_test_login_unexpected_error_returns_generic_500(client, db_session):
    _seed_portfolio(db_session)
    _FakeClient.behavior = "unexpected"
    response = client.post("/api/dividendos-me/test-login", json=_creds())
    assert response.status_code == 500
    assert "boom" not in response.text


def test_test_login_never_leaks_password_even_when_exception_contains_it(client, db_session):
    _seed_portfolio(db_session)
    _FakeClient.behavior = "leak_password"
    response = client.post("/api/dividendos-me/test-login", json=_creds())
    assert response.status_code == 401
    assert _PASSWORD not in response.text


# --- dry-run -----------------------------------------------------------


def test_dry_run_success_returns_preview_and_blocking_reasons(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    _FakeClient.positions = [_extracted("PETR4"), _extracted("VALE3")]
    response = client.post("/api/dividendos-me/dry-run", json=_creds(portfolio_id=portfolio_id))
    assert response.status_code == 200
    body = response.json()
    assert body["preview"]["total_assets"] == 2
    assert body["preview"]["status"] == "success"
    assert body["blocking_reasons_replace"] == []
    assert body["blocking_reasons_update"] == []
    assert body["strong_alert_sections"] == []


def test_dry_run_portfolio_not_found_returns_404(client, db_session):
    response = client.post("/api/dividendos-me/dry-run", json=_creds(portfolio_id=999))
    assert response.status_code == 404


def test_dry_run_protected_btc_missing_blocks_replace(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    asset = Asset(
        ticker="BTC-USD", name="Bitcoin", asset_class="crypto", country="US", currency="USD"
    )
    db_session.add(asset)
    db_session.commit()
    db_session.add(
        Position(
            portfolio_id=portfolio_id,
            asset_id=asset.id,
            quantity=Decimal("1"),
            average_price=Decimal("50000"),
            currency="USD",
            opened_at=date.today(),
            source="manual",
        )
    )
    db_session.commit()

    # Extração não traz nada de criptomoedas desta vez — BTC-USD é
    # ticker sempre-protegido (Sprint 23.2), então replace é bloqueado.
    _FakeClient.positions = [_extracted("PETR4"), _extracted("VALE3")]
    response = client.post("/api/dividendos-me/dry-run", json=_creds(portfolio_id=portfolio_id))
    assert response.status_code == 200
    body = response.json()
    assert body["blocking_reasons_replace"], "esperava bloqueio por BTC-USD ausente"
    assert body["blocking_reasons_update"] == []


def test_dry_run_unexpected_error_returns_generic_500(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    _FakeClient.behavior = "unexpected"
    response = client.post("/api/dividendos-me/dry-run", json=_creds(portfolio_id=portfolio_id))
    assert response.status_code == 500
    assert "boom" not in response.text


# --- sync-update ---------------------------------------------------------


def test_sync_update_requires_confirm_true(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    response = client.post(
        "/api/dividendos-me/sync-update",
        json=_creds(portfolio_id=portfolio_id, confirm=False),
    )
    assert response.status_code == 422


def test_sync_update_success_creates_positions(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    _FakeClient.positions = [_extracted("PETR4"), _extracted("VALE3")]
    response = client.post(
        "/api/dividendos-me/sync-update",
        json=_creds(portfolio_id=portfolio_id, confirm=True),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["positions_created"] == 2
    assert _PASSWORD not in response.text


def test_sync_update_blocked_extraction_returns_422(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    # Extração quebrada: única posição, ticker vazio.
    _FakeClient.positions = [_extracted("", review_required=True, review_reason="ticker vazio")]
    response = client.post(
        "/api/dividendos-me/sync-update",
        json=_creds(portfolio_id=portfolio_id, confirm=True),
    )
    assert response.status_code == 422


# --- sync-replace --------------------------------------------------------


def test_sync_replace_requires_exact_phrase(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    response = client.post(
        "/api/dividendos-me/sync-replace",
        json=_creds(portfolio_id=portfolio_id, confirmation_phrase="substituir"),
    )
    assert response.status_code == 422


def test_sync_replace_success(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    _FakeClient.positions = [_extracted("PETR4"), _extracted("VALE3")]
    response = client.post(
        "/api/dividendos-me/sync-replace",
        json=_creds(portfolio_id=portfolio_id, confirmation_phrase="SUBSTITUIR"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["positions_created"] == 2


def test_sync_replace_blocked_when_removing_majority_of_portfolio(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    # Carteira atual tem 3 ativos; extração só traz 1 -> > 50% removido -> bloqueado.
    for ticker in ("AAAA3", "BBBB3", "CCCC3"):
        asset = Asset(ticker=ticker, name=ticker, asset_class="stock", country="BR", currency="BRL")
        db_session.add(asset)
        db_session.commit()
        db_session.add(
            Position(
                portfolio_id=portfolio_id,
                asset_id=asset.id,
                quantity=Decimal("10"),
                average_price=Decimal("10"),
                currency="BRL",
                opened_at=date.today(),
                source="manual",
            )
        )
        db_session.commit()

    _FakeClient.positions = [_extracted("AAAA3"), _extracted("PETR4")]
    response = client.post(
        "/api/dividendos-me/sync-replace",
        json=_creds(portfolio_id=portfolio_id, confirmation_phrase="SUBSTITUIR"),
    )
    assert response.status_code == 422


# --- proventos: histórico mensal -----------------------------------------


def test_income_monthly_preview_success(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    _FakeClient.monthly_summaries = [_monthly_summary()]
    response = client.post(
        "/api/dividendos-me/income/monthly/preview", json=_creds(portfolio_id=portfolio_id)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["summaries_valid"] == 1
    assert body["wallets_found"] == ["Carteira (B3)"]


def test_income_monthly_import_creates_summary(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    _FakeClient.monthly_summaries = [_monthly_summary()]
    response = client.post(
        "/api/dividendos-me/income/monthly/import", json=_creds(portfolio_id=portfolio_id)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["summaries_created"] == 1
    assert body["summaries_skipped_duplicate"] == 0

    # Segunda importação idêntica -> dedup, nada novo criado.
    response2 = client.post(
        "/api/dividendos-me/income/monthly/import", json=_creds(portfolio_id=portfolio_id)
    )
    body2 = response2.json()
    assert body2["summaries_created"] == 0
    assert body2["summaries_skipped_duplicate"] == 1


# --- proventos: calendário futuro -----------------------------------------


def test_income_calendar_preview_success(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    _FakeClient.income_events = [_income_event()]
    response = client.post(
        "/api/dividendos-me/income/calendar/preview", json=_creds(portfolio_id=portfolio_id)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["events_valid"] == 1


def test_income_calendar_import_creates_event(client, db_session):
    portfolio_id = _seed_portfolio(db_session)
    _FakeClient.income_events = [_income_event()]
    response = client.post(
        "/api/dividendos-me/income/calendar/import", json=_creds(portfolio_id=portfolio_id)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["events_created"] == 1
    assert _PASSWORD not in response.text


def test_income_calendar_portfolio_not_found_returns_404(client, db_session):
    response = client.post(
        "/api/dividendos-me/income/calendar/preview", json=_creds(portfolio_id=999)
    )
    assert response.status_code == 404
