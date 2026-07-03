"""Serviço de market data (Volume 20, prompt 7 / Sprint 12).

Orquestra o pipeline de preços:
    provider -> validator -> upsert incremental em `prices`

Regras:
- Coleta incremental: busca apenas a partir do dia seguinte à última
  data já registrada para o ativo.
- Idempotência: preço de (asset_id, date) já existente é atualizado,
  não duplicado.
- Tratamento de falhas: erro em um ativo não derruba os demais.
- Ativos marcados como `is_manual` (ex.: Tesouro Direto) são pulados no
  update em lote — nunca chamam o provider, o preço é sempre cadastrado
  manualmente na tela Ativos (Sprint 12).
- O serviço recebe o provider por injeção, então os testes usam mocks
  e nunca dependem de conexão real.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.etl.providers.base import MarketDataProvider
from backend.app.etl.validators.price_validators import validate_price
from backend.app.infrastructure.database.models.price import Price
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.price_repository import PriceRepository
from backend.app.schemas.market_data import BatchUpdateResult, UpdateResult

logger = get_logger("lg_invest.market_data")


class MarketDataService:
    def __init__(self, db: Session, provider: MarketDataProvider):
        self.db = db
        self.provider = provider
        self.assets = AssetRepository(db)
        self.prices = PriceRepository(db)

    def update_asset_prices(self, ticker: str) -> UpdateResult:
        """Atualiza o histórico de preços de um único ativo (incremental)."""
        asset = self.assets.get_by_ticker(ticker)
        if asset is None:
            logger.warning("update_asset_prices: %s não cadastrado.", ticker)
            return UpdateResult(ticker=ticker, error="ativo não cadastrado")

        if asset.is_manual:
            logger.info("update_asset_prices: %s é manual, coleta pulada.", ticker)
            return UpdateResult(ticker=ticker, skipped_manual=True)

        latest = self.prices.get_latest(asset.id)
        start = (latest.date + timedelta(days=1)) if latest else None

        try:
            history = self.provider.get_history(asset.ticker, asset.currency, start=start)
        except Exception as exc:  # noqa: BLE001 - falha de fonte externa não derruba o batch
            logger.error("Erro coletando %s: %s", ticker, exc)
            return UpdateResult(ticker=ticker, error=f"falha na coleta: {type(exc).__name__}")

        inserted = 0
        updated = 0
        rejected = 0
        for price_data in history:
            reason = validate_price(price_data)
            if reason is not None:
                rejected += 1
                logger.warning("Preço rejeitado %s %s: %s", ticker, price_data.date, reason)
                continue

            existing = self.prices.get_by_asset_and_date(asset.id, price_data.date)
            if existing is not None:
                existing.open = price_data.open
                existing.high = price_data.high
                existing.low = price_data.low
                existing.close = price_data.close
                existing.adjusted_close = price_data.adjusted_close
                existing.volume = price_data.volume
                existing.source = "yahoo"
                self.db.commit()
                updated += 1
            else:
                self.prices.create(
                    Price(
                        asset_id=asset.id,
                        date=price_data.date,
                        open=price_data.open,
                        high=price_data.high,
                        low=price_data.low,
                        close=price_data.close,
                        adjusted_close=price_data.adjusted_close,
                        volume=price_data.volume,
                        source="yahoo",
                    )
                )
                inserted += 1

        logger.info(
            "Preços %s: +%s inseridos, %s atualizados, %s rejeitados.",
            ticker,
            inserted,
            updated,
            rejected,
        )
        return UpdateResult(ticker=ticker, inserted=inserted, updated=updated, rejected=rejected)

    def update_all_active(self) -> BatchUpdateResult:
        """Atualiza os preços de todos os ativos ativos e não-manuais cadastrados."""
        batch = BatchUpdateResult()
        for asset in self.assets.list_active():
            batch.results.append(self.update_asset_prices(asset.ticker))
        return batch
