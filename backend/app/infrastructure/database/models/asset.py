"""Entidade Asset — cadastro mestre de ativos (Volume 16, seção 5.2)."""

from __future__ import annotations

from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.infrastructure.database.base import Base, TimestampMixin

# Classes de ativo suportadas pelo MVP. Mantido como string validada em vez de
# Enum nativo do banco para facilitar evolução sem migration a cada nova classe.
ASSET_CLASSES = ("stock", "fii", "etf", "reit", "crypto", "bond", "cash")


class Asset(Base, TimestampMixin):
    """Cadastro mestre de um ativo negociável (ação, FII, ETF, etc.)."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    country: Mapped[str] = mapped_column(String(2), index=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Ativo sem cotação de mercado (ex.: Tesouro Direto): a atualização
    # automática de preços (MarketDataService) pula esses ativos, e o preço
    # é sempre cadastrado manualmente na tela Ativos (Sprint 12).
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    prices: Mapped[list[Price]] = relationship(  # noqa: F821
        "Price", back_populates="asset", cascade="all, delete-orphan"
    )
    positions: Mapped[list[Position]] = relationship(  # noqa: F821
        "Position", back_populates="asset"
    )
    recommendations: Mapped[list[Recommendation]] = relationship(  # noqa: F821
        "Recommendation", back_populates="asset"
    )
    journal_entries: Mapped[list[JournalEntry]] = relationship(  # noqa: F821
        "JournalEntry", back_populates="asset"
    )
    fundamental_snapshots: Mapped[list[FundamentalSnapshot]] = relationship(  # noqa: F821
        "FundamentalSnapshot", back_populates="asset", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_assets_ticker_class_country", "ticker", "asset_class", "country"),)

    def __repr__(self) -> str:  # pragma: no cover - apenas debug
        return f"<Asset id={self.id} ticker={self.ticker!r}>"
