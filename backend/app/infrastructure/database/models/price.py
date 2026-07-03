"""Entidade Price — histórico diário de preços por ativo
(Volume 16, seção 5.6 / exemplo de implementação)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.infrastructure.database.base import Base, TimestampMixin

# Origem do preço: "yahoo" (coleta automática via yfinance) ou "manual"
# (cadastrado pelo usuário, ex.: Tesouro Direto). Default "yahoo" preserva
# o comportamento de dados já existentes (Sprint 11).
PRICE_SOURCES = ("yahoo", "manual")


class Price(Base, TimestampMixin):
    """Preço diário (OHLCV) de um ativo."""

    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True, nullable=False)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="yahoo")

    asset: Mapped[Asset] = relationship("Asset", back_populates="prices")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("asset_id", "date", name="uq_price_asset_date"),
        Index("ix_prices_asset_date", "asset_id", "date"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Price asset_id={self.asset_id} date={self.date} close={self.close}>"
