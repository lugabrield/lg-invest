"""Importação manual de fundamentos via CSV/Excel (Sprint 28, Fase 5).

Fallback para quando Yahoo Finance não cobre um ativo (ver
`docs/DATA_COVERAGE_REPORT.md`): o usuário baixa um modelo, preenche
com dados de outra fonte (RI da empresa, CVM, Status Invest etc.) e
importa aqui. Nunca cria `Asset` novo, nunca sobrescreve um snapshot
existente sem confirmação explícita, e sempre recomputa
valuation/traps/scores dos tickers efetivamente alterados — mesmo
padrão de recomputação de `DataRefreshService._recompute_analysis`
(reaproveitado, não duplicado).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.etl.importers.file_reader import read_rows
from backend.app.etl.validators.fundamentals_import_validators import (
    validate_fundamentals_import_rows,
)
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.schemas.fundamentals_import import (
    MANUAL_IMPORT_SOURCE,
    FundamentalsImportResult,
    FundamentalsImportRowError,
    FundamentalsImportRowOutcome,
)

logger = get_logger("lg_invest.import.fundamentals")


class FundamentalsImportService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.fundamentals = FundamentalsRepository(db)

    def import_file(
        self,
        file_path: str | Path,
        portfolio_id: int,
        confirm_overwrite: bool = False,
    ) -> FundamentalsImportResult:
        """Importa um arquivo CSV/Excel de fundamentos.

        Sem `confirm_overwrite`, linhas cujo `(ticker, period_end)` já
        tem um snapshot salvo ficam como
        `"conflict_pending_confirmation"` e NÃO são aplicadas — o
        chamador reexecuta com `confirm_overwrite=True` (normalmente
        depois de o usuário marcar uma caixa de confirmação na UI) para
        efetivamente sobrescrever. Linhas com período novo são sempre
        aplicadas, confirmação ou não.
        """
        errors: list[FundamentalsImportRowError] = []
        outcomes: list[FundamentalsImportRowOutcome] = []

        rows = read_rows(file_path)
        valid_rows = validate_fundamentals_import_rows(rows, errors)

        touched_tickers: set[str] = set()

        for row in valid_rows:
            asset = self.assets.get_by_ticker(row.ticker)
            if asset is None:
                errors.append(
                    FundamentalsImportRowError(
                        line=row.line,
                        field="ticker",
                        message=(
                            f"Ticker '{row.ticker}' não está cadastrado. A importação manual "
                            "de fundamentos não cria ativos novos — cadastre-o primeiro em "
                            "Ativos ou Carteira."
                        ),
                    )
                )
                continue

            if not row.fields:
                errors.append(
                    FundamentalsImportRowError(
                        line=row.line,
                        field=None,
                        message="Nenhum campo fundamentalista preenchido nesta linha.",
                    )
                )
                continue

            existing = self.fundamentals.get_by_asset_and_period(asset.id, row.period_end)
            if existing is not None and not confirm_overwrite:
                outcomes.append(
                    FundamentalsImportRowOutcome(
                        line=row.line,
                        ticker=row.ticker,
                        period_end=row.period_end,
                        status="conflict_pending_confirmation",
                        reported_source=row.reported_source,
                        message=(
                            f"Já existe um snapshot para {row.ticker} em "
                            f"{row.period_end.isoformat()} (fonte atual: '{existing.source}'). "
                            "Confirme a sobrescrita para aplicar esta linha."
                        ),
                    )
                )
                continue

            was_update = existing is not None
            self.fundamentals.upsert_fields(
                asset_id=asset.id,
                period_end=row.period_end,
                source=MANUAL_IMPORT_SOURCE,
                fields=row.fields,
            )
            touched_tickers.add(row.ticker)
            outcomes.append(
                FundamentalsImportRowOutcome(
                    line=row.line,
                    ticker=row.ticker,
                    period_end=row.period_end,
                    status="updated" if was_update else "imported",
                    fields_applied=sorted(row.fields.keys()),
                    reported_source=row.reported_source,
                    message=(
                        f"{len(row.fields)} campo(s) aplicado(s) — fonte reportada: "
                        f"{row.reported_source or 'não informada'}."
                    ),
                )
            )

        result = FundamentalsImportResult(
            total_rows=len(rows),
            outcomes=outcomes,
            errors=errors,
        )

        if touched_tickers:
            # Import local para evitar dependência circular
            # (`DataRefreshService` não depende deste módulo).
            from backend.app.services.data_refresh_service import DataRefreshService

            refresh_service = DataRefreshService(self.db)
            for ticker in sorted(touched_tickers):
                asset = self.assets.get_by_ticker(ticker)
                asset_class = asset.asset_class if asset else None
                valuation_done, traps_done, scores_done = refresh_service._recompute_analysis(
                    ticker, asset_class, portfolio_id
                )
                if valuation_done:
                    result.valuation_recalculated += 1
                if traps_done:
                    result.traps_recalculated += 1
                if scores_done:
                    result.scores_recalculated += 1
            result.tickers_recomputed = sorted(touched_tickers)

        logger.info(
            "Importação manual de fundamentos concluída: total=%s aplicadas=%s "
            "conflitos_pendentes=%s erros=%s tickers_recomputados=%s",
            result.total_rows,
            result.imported,
            result.conflicts_pending,
            len(result.errors),
            len(result.tickers_recomputed),
        )
        return result
