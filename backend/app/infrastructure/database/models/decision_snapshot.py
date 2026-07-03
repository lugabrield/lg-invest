"""Entidade DecisionSnapshot (Volume 12, seção 6).

Fotografia do contexto no momento de uma decisão/recomendação, para
que decisões antigas não sejam julgadas com dados que não existiam na
época. Campos macro (Selic, IPCA, câmbio) ficam opcionais no MVP,
pois esses dados ainda não são coletados.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.database.base import Base, TimestampMixin


class DecisionSnapshot(Base, TimestampMixin):
    """Foto dos dados disponíveis no momento de uma decisão."""

    __tablename__ = "decision_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)

    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    current_weight: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    lg_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    recommended_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DecisionSnapshot asset_id={self.asset_id} date={self.snapshot_date}>"
