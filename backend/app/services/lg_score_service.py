"""Serviço do LG Score Engine.

Fronteira banco↔engine: lê asset, histórico de preços e (quando há)
peso atual da carteira, monta o `ScoreInput` e chama a engine pura.
Pode pontuar um único ativo ou gerar o ranking de uma carteira.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.engines.lg_score.engine import calculate_lg_score
from backend.app.engines.lg_score.inputs import ScoreInput
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.price_repository import PriceRepository
from backend.app.schemas.lg_score import LGScoreResult
from backend.app.services.portfolio_service import PortfolioService


class LGScoreService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.prices = PriceRepository(db)

    def _price_history(self, asset_id: int) -> list:
        return [p.close for p in self.prices.list_by_asset(asset_id)]

    def score_ticker(
        self,
        ticker: str,
        current_weight=None,
        target_weight=None,
    ) -> LGScoreResult | None:
        asset = self.assets.get_by_ticker(ticker)
        if asset is None:
            return None
        data = ScoreInput(
            ticker=asset.ticker,
            asset_class=asset.asset_class,
            price_history=self._price_history(asset.id),
            current_weight=current_weight,
            target_weight=target_weight,
        )
        return calculate_lg_score(data)

    def rank_portfolio(self, portfolio_id: int) -> list[LGScoreResult]:
        """Pontua todos os ativos da carteira e ordena por LG Score desc.

        Usa o peso atual de cada ativo (do Portfolio Engine) no pilar de
        alocação. Sem peso-alvo no MVP, a alocação permanece neutra.
        """
        summary = PortfolioService(self.db).get_summary(portfolio_id)
        weight_by_ticker = {p.ticker: p.weight for p in summary.positions}

        results: list[LGScoreResult] = []
        for ticker, weight in weight_by_ticker.items():
            result = self.score_ticker(ticker, current_weight=weight)
            if result is not None:
                results.append(result)

        results.sort(key=lambda r: r.lg_score, reverse=True)
        return results
