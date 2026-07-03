"""CLI de importação de ativos a partir de um CSV.

Idempotente (Volume 4): se o ticker já existe, atualiza os dados
básicos; se não existe, cria; nunca duplica. Deve rodar ANTES da
importação de posições, pois posições exigem o ativo cadastrado.

Uso:
    python -m scripts.import_assets --file data/exports/assets_real.csv

Formato esperado do CSV:
    ticker,name,asset_class,country,currency,sector
"""

from __future__ import annotations

import argparse
import json

from backend.app.core.logging import configure_logging, get_logger
from backend.app.etl.importers.file_reader import read_rows
from backend.app.etl.importers.import_result import ImportResult
from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.database.session import get_session
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.schemas.import_row import AssetImportRow

logger = get_logger("lg_invest.cli.import_assets")

REQUIRED_COLUMNS = {"ticker", "name", "asset_class", "country", "currency"}


def import_assets(file_path: str) -> ImportResult:
    """Importa (upsert) ativos de um arquivo CSV/Excel."""
    result = ImportResult()
    rows = read_rows(file_path)

    with get_session() as db:
        repo = AssetRepository(db)
        for raw in rows:
            result.total_rows += 1

            missing = REQUIRED_COLUMNS - set(raw.data.keys())
            if missing:
                result.add_error(
                    raw.line, f"colunas obrigatórias ausentes: {', '.join(sorted(missing))}"
                )
                continue

            try:
                row = AssetImportRow(**raw.data)
            except Exception as exc:  # noqa: BLE001 - reporta erro por linha
                result.add_error(raw.line, str(exc), "schema")
                continue

            existing = repo.get_by_ticker(row.ticker)
            if existing is not None:
                # Atualiza dados básicos, preservando o ticker.
                existing.name = row.name
                existing.asset_class = row.asset_class
                existing.country = row.country
                existing.currency = row.currency
                existing.sector = row.sector
                db.commit()
                result.updated += 1
            else:
                repo.create(
                    Asset(
                        ticker=row.ticker,
                        name=row.name,
                        asset_class=row.asset_class,
                        country=row.country,
                        currency=row.currency,
                        sector=row.sector,
                    )
                )
                result.imported += 1

    logger.info(
        "Ativos: total=%s criados=%s atualizados=%s ignorados=%s",
        result.total_rows,
        result.imported,
        result.updated,
        result.skipped,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa ativos (idempotente) de um CSV.")
    parser.add_argument("--file", type=str, required=True)
    args = parser.parse_args()

    configure_logging()
    result = import_assets(args.file)
    print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
