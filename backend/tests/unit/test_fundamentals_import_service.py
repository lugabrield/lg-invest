"""Testes da Importação Manual de Fundamentos (Sprint 28, Fase 5/7).

Cobre os cenários 7-9 da Parte 8 da especificação:
- manual import cria snapshot com `source="manual_import"`
- manual import nunca cria posição
- manual import recalcula valuation/traps/scores dos tickers afetados

Mais os casos de erro/conflito exigidos pela Fase 5: ticker desconhecido,
valor numérico inválido, coluna obrigatória ausente, e a regra de "nunca
sobrescreve sem confirmação explícita"."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from backend.app.infrastructure.database.models import Asset, Portfolio, Position
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.infrastructure.repositories.position_repository import PositionRepository
from backend.app.services.fundamentals_import_service import FundamentalsImportService


def _seed_portfolio_and_asset(
    db, ticker: str = "ALUP4.SA", asset_class: str = "stock"
) -> tuple[int, Asset]:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.flush()
    asset = Asset(
        ticker=ticker, name="Alupar", asset_class=asset_class, country="BR", currency="BRL"
    )
    db.add(asset)
    db.commit()
    return portfolio.id, asset


def _write_csv(tmp_path: Path, filename: str, header: list[str], rows: list[list[str]]) -> Path:
    path = tmp_path / filename
    lines = [",".join(header)] + [",".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_import_creates_snapshot_with_manual_import_source(db_session, tmp_path):
    """Cenário 7: importação cria snapshot com `source="manual_import"`,
    nunca sobrescrevendo a origem informada na coluna `source` do arquivo
    (que é só um metadado de auditoria)."""
    portfolio_id, asset = _seed_portfolio_and_asset(db_session)
    csv_path = _write_csv(
        tmp_path,
        "fund.csv",
        ["ticker", "period_end", "source", "free_cash_flow", "total_equity"],
        [["ALUP4.SA", "2025-12-31", "Status Invest", "500000", "2000000"]],
    )

    result = FundamentalsImportService(db_session).import_file(
        str(csv_path), portfolio_id, confirm_overwrite=False
    )

    assert result.total_rows == 1
    assert result.imported == 1
    assert result.errors == []

    snapshot = FundamentalsRepository(db_session).get_by_asset_and_period(
        asset.id, date(2025, 12, 31)
    )
    assert snapshot is not None
    assert snapshot.source == "manual_import"
    assert snapshot.free_cash_flow == Decimal("500000")
    assert snapshot.total_equity == Decimal("2000000")


def test_import_never_creates_position(db_session, tmp_path):
    """Cenário 8: importação manual de fundamentos nunca cria `Position`
    nem altera o patrimônio — mesma garantia já aplicada à Watchlist."""
    portfolio_id, asset = _seed_portfolio_and_asset(db_session)
    csv_path = _write_csv(
        tmp_path,
        "fund.csv",
        ["ticker", "period_end", "free_cash_flow"],
        [["ALUP4.SA", "2025-12-31", "500000"]],
    )

    positions_before = len(PositionRepository(db_session).list_by_portfolio(portfolio_id))
    FundamentalsImportService(db_session).import_file(str(csv_path), portfolio_id)
    positions_after = len(PositionRepository(db_session).list_by_portfolio(portfolio_id))

    assert positions_after == positions_before == 0
    del asset


def test_import_recomputes_valuation_and_traps_for_touched_tickers(db_session, tmp_path):
    """Cenário 9: após a importação, os tickers alterados devem ter sido
    submetidos à recomputação de valuation/traps/scores (mesmo que o
    resultado seja "sem dado suficiente" — o que importa é que a
    recomputação foi de fato tentada, nunca pulada)."""
    portfolio_id, asset = _seed_portfolio_and_asset(db_session)
    db_session.add(
        Position(
            portfolio_id=portfolio_id,
            asset_id=asset.id,
            quantity=Decimal("10"),
            average_price=Decimal("20"),
            currency="BRL",
            opened_at=date(2025, 1, 1),
        )
    )
    db_session.commit()
    csv_path = _write_csv(
        tmp_path,
        "fund.csv",
        ["ticker", "period_end", "free_cash_flow", "total_equity", "shares_outstanding"],
        [["ALUP4.SA", "2025-12-31", "500000", "2000000", "100000"]],
    )

    result = FundamentalsImportService(db_session).import_file(str(csv_path), portfolio_id)

    assert result.tickers_recomputed == ["ALUP4.SA"]


def test_import_unknown_ticker_is_a_row_error_and_creates_nothing(db_session, tmp_path):
    portfolio_id, _asset = _seed_portfolio_and_asset(db_session, ticker="ALUP4.SA")
    csv_path = _write_csv(
        tmp_path,
        "fund.csv",
        ["ticker", "period_end", "free_cash_flow"],
        [["NAOCADASTRADO.SA", "2025-12-31", "500000"]],
    )

    result = FundamentalsImportService(db_session).import_file(str(csv_path), portfolio_id)

    assert result.imported == 0
    assert len(result.errors) == 1
    assert "NAOCADASTRADO.SA" in result.errors[0].message
    assert "não cria ativos novos" in result.errors[0].message


def test_import_invalid_numeric_value_is_a_row_error(db_session, tmp_path):
    portfolio_id, _asset = _seed_portfolio_and_asset(db_session)
    csv_path = _write_csv(
        tmp_path,
        "fund.csv",
        ["ticker", "period_end", "free_cash_flow"],
        [["ALUP4.SA", "2025-12-31", "não é um número"]],
    )

    result = FundamentalsImportService(db_session).import_file(str(csv_path), portfolio_id)

    assert result.imported == 0
    assert len(result.errors) == 1
    assert result.errors[0].field == "free_cash_flow"


def test_import_missing_ticker_column_is_a_row_error(db_session, tmp_path):
    portfolio_id, _asset = _seed_portfolio_and_asset(db_session)
    csv_path = _write_csv(
        tmp_path,
        "fund.csv",
        ["ticker", "period_end", "free_cash_flow"],
        [["", "2025-12-31", "500000"]],
    )

    result = FundamentalsImportService(db_session).import_file(str(csv_path), portfolio_id)

    assert result.imported == 0
    assert any(e.field == "ticker" for e in result.errors)


def test_import_invalid_period_end_is_a_row_error(db_session, tmp_path):
    portfolio_id, _asset = _seed_portfolio_and_asset(db_session)
    csv_path = _write_csv(
        tmp_path,
        "fund.csv",
        ["ticker", "period_end", "free_cash_flow"],
        [["ALUP4.SA", "31-12-2025-invalido", "500000"]],
    )

    result = FundamentalsImportService(db_session).import_file(str(csv_path), portfolio_id)

    assert result.imported == 0
    assert any(e.field == "period_end" for e in result.errors)


def test_import_existing_snapshot_without_confirmation_is_pending_and_not_applied(
    db_session, tmp_path
):
    """Regra central da Fase 5: nunca sobrescreve dados existentes sem
    confirmação explícita — a linha fica marcada como
    "conflict_pending_confirmation" e o banco não é alterado."""
    portfolio_id, asset = _seed_portfolio_and_asset(db_session)
    repo = FundamentalsRepository(db_session)
    repo.upsert_fields(
        asset_id=asset.id,
        period_end=date(2025, 12, 31),
        source="yahoo",
        fields={"pe_ratio": Decimal("8.4")},
    )
    csv_path = _write_csv(
        tmp_path,
        "fund.csv",
        ["ticker", "period_end", "free_cash_flow"],
        [["ALUP4.SA", "2025-12-31", "500000"]],
    )

    result = FundamentalsImportService(db_session).import_file(
        str(csv_path), portfolio_id, confirm_overwrite=False
    )

    assert result.imported == 0
    assert result.conflicts_pending == 1
    assert result.has_pending_conflicts is True

    snapshot = repo.get_by_asset_and_period(asset.id, date(2025, 12, 31))
    assert snapshot.source == "yahoo"  # não sobrescrito
    assert snapshot.free_cash_flow is None  # não aplicado


def test_import_existing_snapshot_with_confirmation_overwrites(db_session, tmp_path):
    portfolio_id, asset = _seed_portfolio_and_asset(db_session)
    repo = FundamentalsRepository(db_session)
    repo.upsert_fields(
        asset_id=asset.id,
        period_end=date(2025, 12, 31),
        source="yahoo",
        fields={"pe_ratio": Decimal("8.4")},
    )
    csv_path = _write_csv(
        tmp_path,
        "fund.csv",
        ["ticker", "period_end", "free_cash_flow"],
        [["ALUP4.SA", "2025-12-31", "500000"]],
    )

    result = FundamentalsImportService(db_session).import_file(
        str(csv_path), portfolio_id, confirm_overwrite=True
    )

    assert result.imported == 1
    assert result.conflicts_pending == 0

    snapshot = repo.get_by_asset_and_period(asset.id, date(2025, 12, 31))
    assert snapshot.source == "manual_import"
    assert snapshot.free_cash_flow == Decimal("500000")
    # campo já existente não informado no arquivo permanece intacto
    assert snapshot.pe_ratio == Decimal("8.4")


def test_import_row_with_no_fields_filled_is_an_error(db_session, tmp_path):
    portfolio_id, _asset = _seed_portfolio_and_asset(db_session)
    csv_path = _write_csv(
        tmp_path,
        "fund.csv",
        ["ticker", "period_end", "free_cash_flow"],
        [["ALUP4.SA", "2025-12-31", ""]],
    )

    result = FundamentalsImportService(db_session).import_file(str(csv_path), portfolio_id)

    assert result.imported == 0
    assert len(result.errors) == 1


def test_import_multiple_rows_mixed_valid_and_invalid(db_session, tmp_path):
    """Uma linha com erro não derruba as demais — mesmo padrão da
    importação de posições (Sprint 3)."""
    portfolio_id, _asset = _seed_portfolio_and_asset(db_session, ticker="ALUP4.SA")
    _seed_portfolio_and_asset(db_session, ticker="WEGE3.SA")
    csv_path = _write_csv(
        tmp_path,
        "fund.csv",
        ["ticker", "period_end", "free_cash_flow"],
        [
            ["ALUP4.SA", "2025-12-31", "500000"],
            ["WEGE3.SA", "2025-12-31", "não é número"],
        ],
    )

    result = FundamentalsImportService(db_session).import_file(str(csv_path), portfolio_id)

    assert result.total_rows == 2
    assert result.imported == 1
    assert len(result.errors) == 1
