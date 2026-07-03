"""Testes do fluxo de importação de posições (Sprint 3)."""

from __future__ import annotations

from pathlib import Path

from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.database.models.portfolio import Portfolio
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.portfolio_repository import PortfolioRepository
from backend.app.services.portfolio_import_service import PortfolioImportService

FIXTURES = Path(__file__).parent / "fixtures"


def _seed_assets_and_portfolio(db_session) -> Portfolio:
    """Cadastra WEGE3.SA, VOO, ITUB4.SA e uma carteira (ZZZZ9 fica de fora de propósito)."""
    assets = AssetRepository(db_session)
    assets.create(
        Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    )
    assets.create(
        Asset(
            ticker="VOO",
            name="Vanguard S&P 500 ETF",
            asset_class="etf",
            country="US",
            currency="USD",
        )
    )
    assets.create(
        Asset(
            ticker="ITUB4.SA",
            name="Itaú Unibanco",
            asset_class="stock",
            country="BR",
            currency="BRL",
        )
    )
    return PortfolioRepository(db_session).create(Portfolio(name="Carteira Teste"))


def test_import_valid_csv(db_session):
    portfolio = _seed_assets_and_portfolio(db_session)
    service = PortfolioImportService(db_session)
    result = service.import_positions(portfolio.id, FIXTURES / "positions_valid.csv")

    assert result.imported == 2
    assert result.updated == 0
    assert not result.has_errors


def test_import_is_idempotent(db_session):
    portfolio = _seed_assets_and_portfolio(db_session)
    service = PortfolioImportService(db_session)

    first = service.import_positions(portfolio.id, FIXTURES / "positions_valid.csv")
    assert first.imported == 2

    second = service.import_positions(portfolio.id, FIXTURES / "positions_valid.csv")
    assert second.imported == 0
    assert second.updated == 2  # mesmas posições, agora atualizadas via upsert


def test_import_with_errors_keeps_valid_rows(db_session):
    portfolio = _seed_assets_and_portfolio(db_session)
    service = PortfolioImportService(db_session)
    result = service.import_positions(portfolio.id, FIXTURES / "positions_with_errors.csv")

    # Linha 1 (WEGE3.SA) é válida e entra. As demais falham por motivos distintos:
    # ZZZZ9 (ativo não cadastrado), VOO -3 (quantidade negativa),
    # WEGE3.SA repetido (duplicidade), ITUB4.SA (data inválida).
    assert result.imported == 1
    assert result.has_errors
    assert result.skipped == 4


def test_import_excel(db_session, tmp_path):
    from openpyxl import Workbook

    portfolio = _seed_assets_and_portfolio(db_session)

    wb = Workbook()
    ws = wb.active
    ws.append(["ticker", "quantity", "average_price", "currency", "opened_at"])
    ws.append(["WEGE3.SA", 100, 38.20, "BRL", "2025-06-01"])
    ws.append(["VOO", 10, 420.50, "USD", "2025-03-15"])
    xlsx_path = tmp_path / "positions.xlsx"
    wb.save(xlsx_path)

    service = PortfolioImportService(db_session)
    result = service.import_positions(portfolio.id, xlsx_path)

    assert result.imported == 2
    assert not result.has_errors
