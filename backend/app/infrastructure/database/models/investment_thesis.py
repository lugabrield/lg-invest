"""Entidade InvestmentThesis (Volume 12, seções 3 e 5).

A tese é um documento vivo: nasce numa decisão e recebe um status ao
longo do tempo (em observação, confirmada, parcialmente confirmada,
invalidada). O histórico nunca é sobrescrito — mudanças de status vêm
de revisões (ThesisReview).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.infrastructure.database.base import Base, TimestampMixin

# Ciclo de vida da tese (Volume 12, seção 7).
THESIS_STATUSES = ("open", "confirmed", "partially_confirmed", "invalidated")


class InvestmentThesis(Base, TimestampMixin):
    """Tese de investimento associada a um ativo."""

    __tablename__ = "investment_theses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True, nullable=False)
    thesis_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)

    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    return_drivers: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_risks: Mapped[str | None] = mapped_column(Text, nullable=True)
    horizon: Mapped[str | None] = mapped_column(String(60), nullable=True)
    review_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)

    reviews: Mapped[list[ThesisReview]] = relationship(  # noqa: F821
        "ThesisReview", back_populates="thesis", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<InvestmentThesis asset_id={self.asset_id} status={self.status!r}>"
