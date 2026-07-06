"""Repositório de WatchlistAsset (Sprint 25, Parte 2.1).

Mesmo padrão dos demais repositórios do projeto: classe simples, sem
base/abstract class, sessão injetada, sem lógica de negócio (validação
e orquestração ficam no `WatchlistService`).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.watchlist_asset import WatchlistAsset


class WatchlistAssetRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_portfolio(self, portfolio_id: int) -> list[WatchlistAsset]:
        return (
            self.db.query(WatchlistAsset)
            .filter(WatchlistAsset.portfolio_id == portfolio_id)
            .order_by(WatchlistAsset.priority.desc(), WatchlistAsset.ticker)
            .all()
        )

    def get_by_id(self, watchlist_asset_id: int) -> WatchlistAsset | None:
        return self.db.get(WatchlistAsset, watchlist_asset_id)

    def get_by_ticker(self, portfolio_id: int, ticker: str) -> WatchlistAsset | None:
        return (
            self.db.query(WatchlistAsset)
            .filter(
                WatchlistAsset.portfolio_id == portfolio_id,
                WatchlistAsset.ticker == ticker.upper(),
            )
            .one_or_none()
        )

    def create(self, watchlist_asset: WatchlistAsset) -> WatchlistAsset:
        self.db.add(watchlist_asset)
        self.db.commit()
        self.db.refresh(watchlist_asset)
        return watchlist_asset

    def update(self, watchlist_asset: WatchlistAsset) -> WatchlistAsset:
        self.db.commit()
        self.db.refresh(watchlist_asset)
        return watchlist_asset

    def delete(self, watchlist_asset: WatchlistAsset) -> None:
        self.db.delete(watchlist_asset)
        self.db.commit()
