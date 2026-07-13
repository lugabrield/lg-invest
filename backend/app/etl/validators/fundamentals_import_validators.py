"""Validação de linhas do arquivo de importação manual de fundamentos
(Sprint 28, Fase 5).

Converte `RawRow` (strings brutas) em valores tipados prontos para
`FundamentalsRepository.upsert_fields`, coletando erro por linha sem
abortar o arquivo inteiro — mesmo padrão de
`etl/validators/portfolio_validators.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from backend.app.etl.importers.file_reader import RawRow
from backend.app.schemas.fundamentals_import import (
    FUNDAMENTALS_IMPORT_NUMERIC_FIELDS,
    FUNDAMENTALS_IMPORT_REQUIRED_COLUMNS,
    FundamentalsImportRowError,
)


@dataclass
class ValidFundamentalsRow:
    line: int
    ticker: str
    period_end: date
    reported_source: str | None
    fields: dict[str, Decimal]  # só campos numéricos presentes e válidos


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(raw: str) -> Decimal | None:
    raw = raw.strip().replace(",", ".")
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def validate_fundamentals_import_rows(
    rows: list[RawRow], errors: list[FundamentalsImportRowError]
) -> list[ValidFundamentalsRow]:
    """Valida todas as linhas, devolvendo só as válidas.

    Linhas com `ticker`/`period_end` ausentes ou inválidos, ou com
    algum campo numérico não conversível, viram erro (`errors`) e são
    excluídas — nunca aplicadas parcialmente com valor adivinhado."""
    valid_rows: list[ValidFundamentalsRow] = []

    for row in rows:
        line = row.line
        row_ok = True

        ticker = (row.data.get("ticker") or "").strip().upper()
        if not ticker:
            errors.append(
                FundamentalsImportRowError(line=line, field="ticker", message="Ticker ausente.")
            )
            row_ok = False

        period_raw = (row.data.get("period_end") or "").strip()
        period_end = _parse_date(period_raw) if period_raw else None
        if not period_raw:
            errors.append(
                FundamentalsImportRowError(
                    line=line, field="period_end", message="period_end ausente."
                )
            )
            row_ok = False
        elif period_end is None:
            errors.append(
                FundamentalsImportRowError(
                    line=line,
                    field="period_end",
                    message=f"period_end inválido: '{period_raw}'. Use AAAA-MM-DD.",
                )
            )
            row_ok = False

        fields: dict[str, Decimal] = {}
        for column in FUNDAMENTALS_IMPORT_NUMERIC_FIELDS:
            raw_value = (row.data.get(column) or "").strip()
            if not raw_value:
                continue  # coluna ausente/vazia — normal, nunca inventado
            parsed = _parse_decimal(raw_value)
            if parsed is None:
                errors.append(
                    FundamentalsImportRowError(
                        line=line,
                        field=column,
                        message=f"Valor numérico inválido em '{column}': '{raw_value}'.",
                    )
                )
                row_ok = False
                continue
            fields[column] = parsed

        if not row_ok:
            continue

        assert period_end is not None  # garantido pelas checagens acima
        valid_rows.append(
            ValidFundamentalsRow(
                line=line,
                ticker=ticker,
                period_end=period_end,
                reported_source=(row.data.get("source") or "").strip() or None,
                fields=fields,
            )
        )

    return valid_rows


__all__ = [
    "FUNDAMENTALS_IMPORT_REQUIRED_COLUMNS",
    "ValidFundamentalsRow",
    "validate_fundamentals_import_rows",
]
