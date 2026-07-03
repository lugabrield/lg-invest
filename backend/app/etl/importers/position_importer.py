"""Importer de posições consolidadas (Volume 17 / Volume 4, seção 11).

Recebe linhas já validadas por schema e, para cada uma:
- resolve o ticker para um Asset existente (ticker desconhecido = rejeita);
- faz upsert da posição por (portfolio_id, asset_id), tornando a
  importação reprocessável sem duplicar linhas.

Não busca dados externos e não calcula nada financeiro.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.etl.importers.import_result import ImportResult
from backend.app.infrastructure.database.models.position import Position
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.position_repository import PositionRepository
from backend.app.schemas.import_row import PositionImportRow


class PositionImporter:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.positions = PositionRepository(db)

    def import_rows(
        self,
        portfolio_id: int,
        valid_rows: list[tuple[int, PositionImportRow]],
        result: ImportResult,
    ) -> ImportResult:
        """Persiste as posições válidas, fazendo upsert por (portfolio, asset)."""
        for line, row in valid_rows:
            asset = self.assets.get_by_ticker(row.ticker)
            if asset is None:
                result.add_error(line, f"ativo não cadastrado: {row.ticker}", "ticker")
                continue

            existing = self.positions.get_by_portfolio_and_asset(portfolio_id, asset.id)
            if existing is not None:
                existing.quantity = row.quantity
                existing.average_price = row.average_price
                existing.currency = row.currency
                existing.opened_at = row.opened_at
                self.db.commit()
                result.updated += 1
            else:
                self.positions.create(
                    Position(
                        portfolio_id=portfolio_id,
                        asset_id=asset.id,
                        quantity=row.quantity,
                        average_price=row.average_price,
                        currency=row.currency,
                        opened_at=row.opened_at,
                    )
                )
                result.imported += 1

        return result
