"""Validadores de importação de carteira (Volume 4, seção 13).

Cada validador recebe linhas brutas e produz linhas válidas tipadas
(`PositionImportRow`) e erros estruturados, sem abortar o processo
quando uma linha individual falha.

Regras aplicadas, na ordem:
1. Schema/tipo (via Pydantic): campos obrigatórios e conversíveis.
2. Duplicidade no próprio arquivo: mesmo ticker repetido.
3. Existência do ticker em `assets` (resolução fica no importer, mas a
   regra "ticker desconhecido = rejeitar" é validada lá, com a sessão).
"""

from __future__ import annotations

from pydantic import ValidationError

from backend.app.etl.importers.file_reader import RawRow
from backend.app.etl.importers.import_result import ImportResult
from backend.app.schemas.import_row import PositionImportRow

REQUIRED_POSITION_COLUMNS = {"ticker", "quantity", "average_price", "currency", "opened_at"}


def validate_position_rows(
    rows: list[RawRow], result: ImportResult
) -> list[tuple[int, PositionImportRow]]:
    """Valida schema e duplicidade no arquivo.

    Retorna lista de (numero_da_linha, PositionImportRow) das linhas válidas.
    Registra erros em `result` para as linhas inválidas.
    """
    valid: list[tuple[int, PositionImportRow]] = []
    seen_tickers: set[str] = set()

    for raw in rows:
        result.total_rows += 1

        # 1. Schema: colunas obrigatórias presentes
        missing = REQUIRED_POSITION_COLUMNS - set(raw.data.keys())
        if missing:
            result.add_error(
                raw.line,
                f"colunas obrigatórias ausentes: {', '.join(sorted(missing))}",
            )
            continue

        # 2. Tipagem/validação via Pydantic
        try:
            row = PositionImportRow(**raw.data)
        except ValidationError as exc:
            first = exc.errors()[0]
            field_name = ".".join(str(p) for p in first.get("loc", [])) or None
            result.add_error(raw.line, first.get("msg", "linha inválida"), field_name)
            continue

        # 3. Duplicidade dentro do arquivo
        if row.ticker in seen_tickers:
            result.add_error(raw.line, f"ticker duplicado no arquivo: {row.ticker}", "ticker")
            continue
        seen_tickers.add(row.ticker)

        valid.append((raw.line, row))

    return valid
