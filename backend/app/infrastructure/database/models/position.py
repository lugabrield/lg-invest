"""Entidade Position — posição consolidada de um ativo numa carteira
(Volume 16, seção 5.4).

Decisão técnica: uma posição é única por (portfolio_id, asset_id) — ou
seja, o MVP trabalha com posição consolidada (quantidade e preço médio),
não com lotes individuais. Essa é a forma mais simples de alimentar o
Portfolio Engine v1 e está alinhada ao modelo do Volume 16.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.infrastructure.database.base import Base, TimestampMixin


class Position(Base, TimestampMixin):
    """Posição consolidada de um ativo dentro de uma carteira."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id"), index=True, nullable=False
    )
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    average_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    opened_at: Mapped[date] = mapped_column(Date, nullable=False)
    # Origem da posição (Sprint 23): None para posições criadas manualmente
    # ou importadas por CSV; "dividendos_me:b3"/"dividendos_me:international"
    # quando vieram da sincronização com o Dividendos.me. Só rastreabilidade —
    # nenhum engine depende deste campo para calcular nada.
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)

    portfolio: Mapped[Portfolio] = relationship(  # noqa: F821
        "Portfolio", back_populates="positions"
    )
    asset: Mapped[Asset] = relationship("Asset", back_populates="positions")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("portfolio_id", "asset_id", name="uq_position_portfolio_asset"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Position portfolio_id={self.portfolio_id} asset_id={self.asset_id}>"
