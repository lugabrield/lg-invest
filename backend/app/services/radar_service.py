"""Serviço do Radar Engine (Sprint 25, Parte 2.4).

Fronteira banco↔engine: resolve posições atuais (Portfolio Engine),
candidatos da Watchlist (excluindo "discarded" — histórico, não é mais
um candidato ativo), scores (LG Score/Conviction Score) e o status de
bloqueio por dimensão (Target Allocation Rule Engine v2), então chama
`evaluate_radar` (engine pura).

Limitação documentada (ver `docs/WATCHLIST_RADAR.md`): o bloqueio por
dimensão aqui reflete SÓ a regra detalhada de alocação-alvo (Target
Allocation Rule Engine v2). Um limite que exista apenas na Investment
Policy (sem regra detalhada equivalente) não é refletido na
classificação "blocked" do Radar — só no bloqueio real do Decision
Engine 3.0 no momento do aporte. Isso é uma escolha deliberada para não
duplicar a lógica de precedência da Parte 1 dentro do Radar; o Radar é
uma visão de apoio à decisão, não a fonte de verdade do bloqueio.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.engines.radar.engine import evaluate_radar
from backend.app.engines.radar.inputs import DEFAULT_RADAR_CONFIG, RadarCandidateInput, RadarConfig
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.watchlist_asset_repository import (
    WatchlistAssetRepository,
)
from backend.app.schemas.radar import RadarEvaluation
from backend.app.services.conviction_score_service import ConvictionScoreService
from backend.app.services.lg_score_service import LGScoreService
from backend.app.services.portfolio_service import PortfolioService
from backend.app.services.target_allocation_service import TargetAllocationService


def _dimension_blocked_map(db: Session, portfolio_id: int) -> dict[tuple[str, str], str]:
    """Mapa (dimension_type, dimension_key) -> mensagem, só para as
    entradas com `gap_status == "blocked"` na Target Allocation Rule
    Engine v2 (Sprint 24, Fase 3). Vazio quando não há nenhuma regra
    detalhada bloqueada — nunca inventa um bloqueio."""
    evaluation = TargetAllocationService(db).evaluate_portfolio_rules(portfolio_id)
    blocked: dict[tuple[str, str], str] = {}
    for item in evaluation.evaluations:
        if item.gap_status == "blocked":
            max_str = f"{item.max_weight * 100:.1f}%" if item.max_weight is not None else "?"
            blocked[(item.dimension_type, item.dimension_key)] = (
                f"Dimensão '{item.dimension_type}={item.dimension_key}' já acima do limite "
                f"máximo da regra detalhada de alocação-alvo "
                f"({item.current_weight * 100:.1f}% > {max_str})."
            )
    return blocked


class RadarService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.watchlist = WatchlistAssetRepository(db)
        self.lg_score_service = LGScoreService(db)
        self.conviction_service = ConvictionScoreService(db)

    def _scores(self, ticker: str) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        """Retorna (lg_score, conviction_score, confidence) sem nunca
        inventar valor — `None` quando o serviço correspondente não
        conseguiu calcular (ativo não cadastrado, sem histórico etc.)."""
        lg_result = self.lg_score_service.score_ticker(ticker)
        conviction_result = self.conviction_service.score_ticker(ticker)
        lg_score = lg_result.lg_score if lg_result is not None else None
        conviction_score = conviction_result.conviction_score if conviction_result else None
        confidence = conviction_result.confidence if conviction_result is not None else None
        return lg_score, conviction_score, confidence

    def evaluate(
        self, portfolio_id: int, config: RadarConfig = DEFAULT_RADAR_CONFIG
    ) -> RadarEvaluation:
        blocked_map = _dimension_blocked_map(self.db, portfolio_id)
        summary = PortfolioService(self.db).get_summary(portfolio_id)
        holding_tickers = {p.ticker for p in summary.positions}
        weight_by_ticker = {p.ticker: p.weight for p in summary.positions}

        watchlist_entries = {
            e.ticker: e
            for e in self.watchlist.list_by_portfolio(portfolio_id)
            if e.status != "discarded"
        }

        candidates: list[RadarCandidateInput] = []

        # 1. Posições já existentes na carteira (com ou sem registro na watchlist).
        for position in summary.positions:
            entry = watchlist_entries.pop(position.ticker, None)
            lg_score, conviction_score, confidence = self._scores(position.ticker)
            asset = self.assets.get_by_ticker(position.ticker)
            dim_reason = None
            dim_blocked = False
            for dim_type, dim_key in (
                ("class", position.asset_class),
                ("currency", position.currency),
                ("country", asset.country if asset is not None else None),
                ("asset", position.ticker),
            ):
                if dim_key is None:
                    continue
                if (dim_type, dim_key) in blocked_map:
                    dim_blocked = True
                    dim_reason = blocked_map[(dim_type, dim_key)]
                    break

            candidates.append(
                RadarCandidateInput(
                    ticker=position.ticker,
                    name=asset.name if asset is not None else position.ticker,
                    asset_class=position.asset_class,
                    watchlist_status=entry.status if entry is not None else None,
                    is_current_holding=True,
                    current_weight=weight_by_ticker.get(position.ticker),
                    lg_score=lg_score,
                    conviction_score=conviction_score,
                    confidence=confidence,
                    dimension_blocked=dim_blocked,
                    dimension_blocked_reason=dim_reason,
                    priority=entry.priority if entry is not None else 0,
                    thesis=entry.thesis if entry is not None else None,
                )
            )

        # 2. Candidatos só na Watchlist (não são posições atuais).
        for ticker, entry in watchlist_entries.items():
            if ticker in holding_tickers:
                continue
            lg_score, conviction_score, confidence = self._scores(ticker)
            dim_blocked = False
            dim_reason = None
            for dim_type, dim_key in (
                ("class", entry.asset_class),
                ("currency", entry.currency),
                ("country", entry.country),
            ):
                if (dim_type, dim_key) in blocked_map:
                    dim_blocked = True
                    dim_reason = blocked_map[(dim_type, dim_key)]
                    break

            candidates.append(
                RadarCandidateInput(
                    ticker=entry.ticker,
                    name=entry.name,
                    asset_class=entry.asset_class,
                    watchlist_status=entry.status,
                    is_current_holding=False,
                    current_weight=None,
                    lg_score=lg_score,
                    conviction_score=conviction_score,
                    confidence=confidence,
                    dimension_blocked=dim_blocked,
                    dimension_blocked_reason=dim_reason,
                    priority=entry.priority,
                    thesis=entry.thesis,
                )
            )

        return evaluate_radar(candidates, config)
