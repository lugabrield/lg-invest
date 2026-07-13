"""Entidade WatchlistAsset — Watchlist/Radar (Sprint 25, Parte 2.1).

Cadastro de ativos candidatos que o usuário quer acompanhar mas ainda
NÃO tem posição na carteira (ou já teve e quer registrar como
descartado/bloqueado). Nunca cria uma `Position`, nunca altera o
patrimônio calculado pelo Portfolio Engine — só o Radar Engine (e,
opcionalmente, o Decision Engine 3.0, quando o usuário habilitar
`allow_watchlist_candidates`) lê esta tabela.

A LG INVEST não recomenda ativos aleatórios da internet: o universo de
"candidatos novos" é sempre controlado pelo usuário, cadastrado aqui
manualmente (ou, no futuro, importado) — nunca inventado por uma engine.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.database.base import Base, TimestampMixin

# "watching": só acompanhando, sem convicção formada ainda;
# "candidate": candidato ativo a receber aporte (via Radar/Aporte v3);
# "blocked": usuário decidiu bloquear manualmente (nunca aparece como
#   candidato, mesmo com bom score — decisão explícita do usuário, não
#   um limite de carteira);
# "discarded": usuário olhou e descartou (perdeu a tese, não se aplica
#   mais etc.) — mantido no histórico, não aparece nos resumos ativos;
# "bought": usuário comprou o ativo (passou a ter posição na carteira,
#   normalmente detectado após a sincronização Dividendos.me) — a
#   watchlist NÃO remove o registro automaticamente, só permite marcar.
WATCHLIST_STATUSES = ("watching", "candidate", "blocked", "discarded", "bought")


class WatchlistAsset(Base, TimestampMixin):
    """Um ativo candidato na Watchlist/Radar de uma carteira."""

    __tablename__ = "watchlist_assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id"), index=True, nullable=False
    )

    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(30), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(120), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="watching")
    # 0..10, maior = mais prioritário para o usuário revisar/considerar
    # primeiro — nunca calculado pela engine, é uma preferência manual.
    priority: Mapped[int] = mapped_column(nullable=False, default=0)

    thesis: Mapped[str | None] = mapped_column(Text(), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # "manual" (cadastrado na tela Radar), "imported" (upload em lote,
    # futuro), "future_api" (integração futura) — nunca inventa a origem.
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")

    # Quando `collect_data_for_asset` rodou com sucesso pela última vez.
    # `None` até a primeira coleta — nunca inventado, só a UI mostra "—".
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    __table_args__ = (
        Index(
            "ix_watchlist_assets_portfolio_ticker",
            "portfolio_id",
            "ticker",
            unique=True,
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<WatchlistAsset portfolio_id={self.portfolio_id} ticker={self.ticker!r} "
            f"status={self.status!r}>"
        )
