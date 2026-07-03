"""Serviço de importação de carteira.

Orquestra o fluxo do Sprint 3:
    arquivo -> leitura -> validação -> importação de posições -> resultado

Registra logs de início/fim e do resumo (Volume 4, seção 14), sem
expor mais dados sensíveis do que o necessário.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.etl.importers.file_reader import read_rows
from backend.app.etl.importers.import_result import ImportResult
from backend.app.etl.importers.position_importer import PositionImporter
from backend.app.etl.validators.portfolio_validators import validate_position_rows

logger = get_logger("lg_invest.import.portfolio")


class PortfolioImportService:
    def __init__(self, db: Session):
        self.db = db

    def import_positions(self, portfolio_id: int, file_path: str | Path) -> ImportResult:
        """Importa posições de um arquivo CSV/Excel para uma carteira."""
        result = ImportResult()
        logger.info(
            "Importação iniciada: carteira=%s arquivo=%s", portfolio_id, Path(file_path).name
        )

        rows = read_rows(file_path)
        valid_rows = validate_position_rows(rows, result)

        importer = PositionImporter(self.db)
        importer.import_rows(portfolio_id, valid_rows, result)

        logger.info(
            "Importação concluída: total=%s importadas=%s atualizadas=%s ignoradas=%s",
            result.total_rows,
            result.imported,
            result.updated,
            result.skipped,
        )
        if result.has_errors:
            logger.warning("Importação com %s erro(s) de linha.", len(result.errors))

        return result
