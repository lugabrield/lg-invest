"""Serviço de fundamentos (Sprint 13 / Fase 2).

Orquestra o pipeline de fundamentos:
    provider -> upsert em fundamental_snapshots (por período)

Regras:
- Ativos `is_manual` e classes sem fundamentos de empresa aplicáveis
  (cripto, caixa, renda fixa) são pulados, com motivo explícito —
  nunca chamam o provider à toa.
- Falha em um ativo não derruba os demais (mesmo padrão do
  `MarketDataService`).
- Idempotência: snapshot de (asset_id, period_end) já existente é
  atualizado (só quando o novo valor não é None, para não regredir um
  dado bom para ausente), não duplicado.
- `get_latest` do provider grava um snapshot "TTM" (período = data mais
  recente disponível) com razões/múltiplos; `get_history` grava até 4
  snapshots anuais com receita/lucro/EBITDA/FCF/dívida — linhas
  distintas na mesma tabela, propositalmente.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.etl.contracts.fundamental_data import FundamentalData
from backend.app.etl.providers.fundamentals_provider import FundamentalsProvider
from backend.app.infrastructure.database.models.fundamental_snapshot import FundamentalSnapshot
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.schemas.fundamentals import BatchFundamentalsResult, FundamentalsCollectionResult

logger = get_logger("lg_invest.fundamentals")

# Classes sem fundamentos de empresa aplicáveis — nunca chamam o provider.
NOT_APPLICABLE_CLASSES = ("crypto", "cash", "bond")

_SNAPSHOT_FIELDS = (
    "roe",
    "roa",
    "net_margin",
    "ebitda_margin",
    "revenue",
    "net_income",
    "ebitda",
    "ebit",
    "free_cash_flow",
    "net_debt",
    "debt_to_ebitda",
    "pe_ratio",
    "pb_ratio",
    "ev_ebitda",
    "dividend_yield",
    "payout_ratio",
    "eps",
    "revenue_per_share",
    "beta",
    "market_cap",
    "enterprise_value",
    "forward_pe",
    "operating_margin",
    "total_debt",
    "total_cash",
    "operating_cash_flow",
    "gross_profit",
    "shares_outstanding",
)


class FundamentalsService:
    def __init__(self, db: Session, provider: FundamentalsProvider):
        self.db = db
        self.provider = provider
        self.assets = AssetRepository(db)
        self.fundamentals = FundamentalsRepository(db)

    def collect_for_asset(self, ticker: str) -> FundamentalsCollectionResult:
        """Coleta o snapshot mais recente e o histórico anual de um ativo."""
        asset = self.assets.get_by_ticker(ticker)
        if asset is None:
            logger.warning("collect_for_asset: %s não cadastrado.", ticker)
            return FundamentalsCollectionResult(
                ticker=ticker, collected=False, reason="ativo não cadastrado"
            )

        if asset.is_manual:
            return FundamentalsCollectionResult(
                ticker=ticker, collected=False, reason="ativo manual"
            )

        if asset.asset_class in NOT_APPLICABLE_CLASSES:
            return FundamentalsCollectionResult(
                ticker=ticker,
                collected=False,
                reason=f"classe '{asset.asset_class}' sem fundamentos de empresa aplicáveis",
            )

        try:
            latest = self.provider.get_latest(ticker)
        except Exception as exc:  # noqa: BLE001 - falha de fonte externa não derruba o batch
            logger.error("Erro coletando fundamentos de %s: %s", ticker, exc)
            return FundamentalsCollectionResult(
                ticker=ticker, collected=False, error=f"falha na coleta: {type(exc).__name__}"
            )

        if latest is None:
            return FundamentalsCollectionResult(
                ticker=ticker, collected=False, reason="sem dado do provider"
            )

        self._upsert(asset.id, latest)

        try:
            history = self.provider.get_history(ticker)
        except Exception as exc:  # noqa: BLE001 - histórico é complementar, não crítico
            logger.warning("Falha ao coletar histórico de fundamentos de %s: %s", ticker, exc)
            history = []

        for item in history:
            self._upsert(asset.id, item)

        logger.info(
            "Fundamentos de %s coletados: 1 snapshot atual + %s período(s) históricos.",
            ticker,
            len(history),
        )
        return FundamentalsCollectionResult(
            ticker=ticker, collected=True, period_end=latest.period_end
        )

    def _upsert(self, asset_id: int, data: FundamentalData) -> None:
        existing = self.fundamentals.get_by_asset_and_period(asset_id, data.period_end)
        if existing is not None:
            for field in _SNAPSHOT_FIELDS:
                value = getattr(data, field, None)
                if value is not None:
                    setattr(existing, field, value)
            existing.source = "yahoo"
            self.db.commit()
        else:
            snapshot = FundamentalSnapshot(
                asset_id=asset_id,
                period_end=data.period_end,
                source="yahoo",
                **{field: getattr(data, field, None) for field in _SNAPSHOT_FIELDS},
            )
            self.fundamentals.create(snapshot)

    def collect_all(self) -> BatchFundamentalsResult:
        """Coleta fundamentos de todos os ativos ativos e aplicáveis."""
        batch = BatchFundamentalsResult()
        for asset in self.assets.list_active():
            batch.results.append(self.collect_for_asset(asset.ticker))
        return batch
