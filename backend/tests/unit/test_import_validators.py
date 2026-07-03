"""Testes dos validadores de importação (Volume 4, seção 13)."""

from __future__ import annotations

from backend.app.etl.importers.file_reader import RawRow
from backend.app.etl.importers.import_result import ImportResult
from backend.app.etl.validators.portfolio_validators import validate_position_rows


def _row(line: int, **kwargs) -> RawRow:
    base = {
        "ticker": "WEGE3.SA",
        "quantity": "100",
        "average_price": "38.20",
        "currency": "BRL",
        "opened_at": "2025-06-01",
    }
    base.update(kwargs)
    return RawRow(line=line, data=base)


def test_valid_row_passes():
    result = ImportResult()
    valid = validate_position_rows([_row(2)], result)
    assert len(valid) == 1
    assert not result.has_errors


def test_missing_required_column_is_rejected():
    result = ImportResult()
    bad = RawRow(line=2, data={"ticker": "WEGE3.SA", "quantity": "100"})
    valid = validate_position_rows([bad], result)
    assert len(valid) == 0
    assert result.has_errors


def test_negative_quantity_is_rejected():
    result = ImportResult()
    valid = validate_position_rows([_row(2, quantity="-5")], result)
    assert len(valid) == 0
    assert result.skipped == 1


def test_invalid_date_is_rejected():
    result = ImportResult()
    valid = validate_position_rows([_row(2, opened_at="not-a-date")], result)
    assert len(valid) == 0
    assert result.has_errors


def test_duplicate_ticker_in_file_is_rejected():
    result = ImportResult()
    rows = [_row(2), _row(3)]  # mesmo ticker WEGE3.SA
    valid = validate_position_rows(rows, result)
    assert len(valid) == 1  # apenas a primeira passa
    assert any("duplicado" in e.message for e in result.errors)


def test_ticker_is_uppercased():
    result = ImportResult()
    valid = validate_position_rows([_row(2, ticker="wege3.sa")], result)
    assert valid[0][1].ticker == "WEGE3.SA"
