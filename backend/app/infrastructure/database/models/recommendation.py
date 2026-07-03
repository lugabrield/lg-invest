"""Entidade Recommendation — saída do Decision Engine (Volume 7 / Volume 17).

Toda recomendação deve guardar um snapshot das premissas e a versão do
algoritmo usada, para que a decisão seja auditável e reproduzível
(princípio central do Decision Engine, Volume 7).

Neste sprint a entidade é apenas persistência: o Decision Engine em si
será implementado em sprint futuro.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.infrastructure.database.base import Base, TimestampMixin


class Recommendation(Base, TimestampMixin):
    """Recomendação de aporte gerada para um ativo em uma data específica."""

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    contribution_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    algo_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")

    asset: Mapped[Asset] = relationship("Asset", back_populates="recommendations")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Recommendation asset_id={self.asset_id} amount={self.amount}>"
