"""Smoke tests da camada Streamlit (Sprint 8).

Não renderizam a UI (isso exige um servidor Streamlit), mas garantem
que todos os módulos de página importam sem erro e expõem `render`,
e que o JournalService funciona sobre o banco.
"""

from __future__ import annotations

import importlib

import pytest

PAGE_MODULES = [
    "frontend.streamlit_app.pages_impl.dashboard",
    "frontend.streamlit_app.pages_impl.carteira",
    "frontend.streamlit_app.pages_impl.ativos",
    "frontend.streamlit_app.pages_impl.inteligencia",
    "frontend.streamlit_app.pages_impl.aporte",
    "frontend.streamlit_app.pages_impl.simulacao",
    "frontend.streamlit_app.pages_impl.radar",
    "frontend.streamlit_app.pages_impl.journal",
    "frontend.streamlit_app.pages_impl.configuracoes",
    "frontend.streamlit_app.pages_impl.sincronizar_dividendos_me",
]


@pytest.mark.parametrize("module_path", PAGE_MODULES)
def test_page_module_imports_and_has_render(module_path):
    module = importlib.import_module(module_path)
    assert hasattr(module, "render"), f"{module_path} deve expor render()"


def test_app_module_imports():
    module = importlib.import_module("frontend.streamlit_app.app")
    assert hasattr(module, "main")


def test_journal_service_add_and_list(db_session):
    from datetime import date

    from backend.app.infrastructure.database.models.asset import Asset
    from backend.app.infrastructure.repositories.asset_repository import AssetRepository
    from backend.app.services.journal_service import JournalService

    AssetRepository(db_session).create(
        Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    )
    service = JournalService(db_session)
    entry = service.add_by_ticker(
        ticker="WEGE3.SA",
        action="buy",
        thesis="Empresa de qualidade, posição inicial.",
        entry_date=date(2026, 1, 5),
    )
    assert entry is not None
    assert len(service.list_all()) == 1


def test_journal_service_unknown_ticker_returns_none(db_session):
    from datetime import date

    from backend.app.services.journal_service import JournalService

    result = JournalService(db_session).add_by_ticker(
        ticker="NOPE9",
        action="buy",
        thesis="x",
        entry_date=date(2026, 1, 5),
    )
    assert result is None
