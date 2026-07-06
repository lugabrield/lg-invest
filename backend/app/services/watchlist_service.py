"""Serviço de Watchlist/Radar (Sprint 25, Parte 2.1-2.3).

A Watchlist cadastra ativos CANDIDATOS que o usuário quer acompanhar,
mas que ainda não têm posição na carteira (ou já tiveram e o usuário
quer registrar como descartado/bloqueado). Este serviço:

- NUNCA cria uma `Position`.
- NUNCA altera o patrimônio calculado pelo Portfolio Engine.
- NUNCA inventa dado: quando um valor não pode ser calculado (sem
  preço, sem fundamentos, ativo não aplicável), o campo correspondente
  fica `None`/`False` e o motivo é registrado nas `notes`.

Quem lê esta tabela: a tela Radar (Parte 2.6) e, opcionalmente, o
Decision Engine 3.0 via `allow_watchlist_candidates` (Parte 2.5) — nunca
o Portfolio Engine, nunca o cálculo de patrimônio.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.watchlist_asset import (
    WATCHLIST_STATUSES,
    WatchlistAsset,
)
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.position_repository import PositionRepository
from backend.app.infrastructure.repositories.watchlist_asset_repository import (
    WatchlistAssetRepository,
)
from backend.app.schemas.asset import AssetCreate
from backend.app.schemas.watchlist import (
    WatchlistAssetCreate,
    WatchlistAssetUpdate,
    WatchlistAssetView,
    WatchlistDataCollectionResult,
)
from backend.app.services.asset_service import AssetService
from backend.app.services.conviction_score_service import ConvictionScoreService
from backend.app.services.lg_score_service import LGScoreService

# Confiança mínima para o resultado de coleta NÃO ser marcado como
# "low_confidence" — mesmo limiar conceitual usado pelo restante do
# projeto (ver Data Quality Layer / Decision Engine 3.0): abaixo disso,
# o dado existe mas é frágil demais para ser um motivo primário de compra.
_LOW_CONFIDENCE_THRESHOLD = Decimal("0.5")


def _already_in_portfolio(db: Session, portfolio_id: int, ticker: str) -> bool:
    """True se o ticker já tem posição na carteira (não watchlist)."""
    asset = AssetRepository(db).get_by_ticker(ticker)
    if asset is None:
        return False
    position = PositionRepository(db).get_by_portfolio_and_asset(portfolio_id, asset.id)
    return position is not None


def _to_view(db: Session, portfolio_id: int, entry: WatchlistAsset) -> WatchlistAssetView:
    view = WatchlistAssetView.model_validate(entry)
    view.already_in_portfolio = _already_in_portfolio(db, portfolio_id, entry.ticker)
    return view


class WatchlistService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = WatchlistAssetRepository(db)
        self.assets = AssetRepository(db)
        self.positions = PositionRepository(db)

    # -- CRUD (Parte 2.2) -------------------------------------------------

    def list_watchlist_assets(
        self, portfolio_id: int, status: str | None = None
    ) -> list[WatchlistAssetView]:
        entries = self.repo.list_by_portfolio(portfolio_id)
        if status is not None:
            entries = [e for e in entries if e.status == status]
        return [_to_view(self.db, portfolio_id, e) for e in entries]

    def get_watchlist_asset_by_ticker(
        self, portfolio_id: int, ticker: str
    ) -> WatchlistAssetView | None:
        entry = self.repo.get_by_ticker(portfolio_id, ticker)
        if entry is None:
            return None
        return _to_view(self.db, portfolio_id, entry)

    def add_watchlist_asset(
        self, portfolio_id: int, payload: WatchlistAssetCreate
    ) -> WatchlistAssetView:
        """Cadastra um novo candidato.

        Levanta ValueError se já existir um registro ATIVO (status
        diferente de "discarded") com o mesmo ticker nesta carteira —
        nunca cria duplicata silenciosa. Um ticker "discarded" pode ser
        recadastrado (o usuário mudou de ideia).
        """
        existing = self.repo.get_by_ticker(portfolio_id, payload.ticker)
        if existing is not None and existing.status != "discarded":
            raise ValueError(
                f"Já existe um registro ativo na watchlist para {payload.ticker!r} "
                f"(status atual: {existing.status!r}). Edite o existente em vez de duplicar."
            )
        if existing is not None and existing.status == "discarded":
            existing.name = payload.name
            existing.asset_class = payload.asset_class
            existing.country = payload.country
            existing.currency = payload.currency
            existing.sector = payload.sector
            existing.status = payload.status
            existing.priority = payload.priority
            existing.thesis = payload.thesis
            existing.notes = payload.notes
            existing.source = payload.source
            entry = self.repo.update(existing)
            return _to_view(self.db, portfolio_id, entry)

        entry = WatchlistAsset(
            portfolio_id=portfolio_id,
            ticker=payload.ticker,
            name=payload.name,
            asset_class=payload.asset_class,
            country=payload.country,
            currency=payload.currency,
            sector=payload.sector,
            status=payload.status,
            priority=payload.priority,
            thesis=payload.thesis,
            notes=payload.notes,
            source=payload.source,
        )
        entry = self.repo.create(entry)
        return _to_view(self.db, portfolio_id, entry)

    def update_watchlist_asset(
        self, portfolio_id: int, watchlist_asset_id: int, update: WatchlistAssetUpdate
    ) -> WatchlistAssetView:
        entry = self.repo.get_by_id(watchlist_asset_id)
        if entry is None or entry.portfolio_id != portfolio_id:
            raise ValueError(f"Watchlist asset {watchlist_asset_id} não encontrado.")

        data = update.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(entry, field, value)

        entry = self.repo.update(entry)
        return _to_view(self.db, portfolio_id, entry)

    def remove_watchlist_asset(self, portfolio_id: int, watchlist_asset_id: int) -> bool:
        entry = self.repo.get_by_id(watchlist_asset_id)
        if entry is None or entry.portfolio_id != portfolio_id:
            return False
        self.repo.delete(entry)
        return True

    def set_status(
        self, portfolio_id: int, watchlist_asset_id: int, status: str
    ) -> WatchlistAssetView:
        if status not in WATCHLIST_STATUSES:
            raise ValueError(f"status deve ser um de: {', '.join(WATCHLIST_STATUSES)}")
        entry = self.repo.get_by_id(watchlist_asset_id)
        if entry is None or entry.portfolio_id != portfolio_id:
            raise ValueError(f"Watchlist asset {watchlist_asset_id} não encontrado.")
        entry.status = status
        entry = self.repo.update(entry)
        return _to_view(self.db, portfolio_id, entry)

    def mark_as_bought(self, portfolio_id: int, watchlist_asset_id: int) -> WatchlistAssetView:
        """Marca um candidato como comprado.

        Não cria Position nem mexe em patrimônio — só registra que o
        usuário passou a ter (ou vai ter) posição, normalmente depois de
        detectar isso via sincronização Dividendos.me ou manualmente.
        """
        return self.set_status(portfolio_id, watchlist_asset_id, "bought")

    def block_asset(self, portfolio_id: int, watchlist_asset_id: int) -> WatchlistAssetView:
        return self.set_status(portfolio_id, watchlist_asset_id, "blocked")

    def discard_asset(self, portfolio_id: int, watchlist_asset_id: int) -> WatchlistAssetView:
        return self.set_status(portfolio_id, watchlist_asset_id, "discarded")

    # -- Coleta de dados (Parte 2.3) --------------------------------------

    def collect_data_for_asset(
        self, portfolio_id: int, watchlist_asset_id: int
    ) -> WatchlistDataCollectionResult:
        """Garante cadastro em `assets`, tenta calcular LG Score/Conviction
        Score a partir de dados JÁ existentes (preço/fundamentos).

        Não dispara automaticamente coleta de preço/fundamentos externos
        (isso é responsabilidade do MarketDataService/FundamentalsService,
        chamados separadamente pela tela Ativos ou por um job de coleta) —
        aqui só garantimos o cadastro mestre e computamos os scores com o
        que já estiver disponível, marcando baixa confiança quando faltar
        dado. Isso evita chamadas de rede escondidas dentro do Radar.
        """
        entry = self.repo.get_by_id(watchlist_asset_id)
        if entry is None or entry.portfolio_id != portfolio_id:
            raise ValueError(f"Watchlist asset {watchlist_asset_id} não encontrado.")

        notes: list[str] = []
        asset = self.assets.get_by_ticker(entry.ticker)
        asset_ensured = asset is not None
        if asset is None:
            try:
                asset = AssetService(self.db).create_asset(
                    AssetCreate(
                        ticker=entry.ticker,
                        name=entry.name,
                        asset_class=entry.asset_class,
                        country=entry.country,
                        currency=entry.currency,
                        sector=entry.sector,
                        is_active=True,
                    )
                )
                asset_ensured = True
                notes.append("Ativo cadastrado em 'assets' a partir do registro da watchlist.")
            except ValueError as exc:
                notes.append(f"Falha ao cadastrar ativo mestre: {exc}")

        lg_score_value: Decimal | None = None
        conviction_value: Decimal | None = None
        confidence: Decimal | None = None

        if asset is not None:
            lg_result = LGScoreService(self.db).score_ticker(entry.ticker)
            if lg_result is not None:
                lg_score_value = lg_result.lg_score
            else:
                notes.append("LG Score indisponível (sem histórico de preço suficiente).")

            conviction_result = ConvictionScoreService(self.db).score_ticker(entry.ticker)
            if conviction_result is not None:
                conviction_value = conviction_result.conviction_score
                confidence = getattr(conviction_result, "confidence", None)
            else:
                notes.append("Conviction Score indisponível (sem dado suficiente).")
        else:
            notes.append("Ativo mestre não disponível — scores não calculados.")

        low_confidence = confidence is not None and confidence < _LOW_CONFIDENCE_THRESHOLD
        if confidence is None and (lg_score_value is None and conviction_value is None):
            low_confidence = True
            notes.append("Confiança não calculada por falta de dado — tratado como baixa.")

        return WatchlistDataCollectionResult(
            ticker=entry.ticker,
            asset_ensured=asset_ensured,
            price_collected=asset is not None and lg_score_value is not None,
            fundamentals_collected=conviction_value is not None,
            lg_score=lg_score_value,
            conviction_score=conviction_value,
            confidence=confidence,
            low_confidence=low_confidence,
            notes=notes,
        )
