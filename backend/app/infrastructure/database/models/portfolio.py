"""Entidade Portfolio — representa uma carteira (Volume 16, seção 5.3).

Multiusuário está fora do MVP (Volume 17), por isso esta entidade ainda
não possui `user_id`. O campo poderá ser adicionado depois via migration
Alembic sem necessidade de reescrever o modelo.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.infrastructure.database.base import Base, TimestampMixin


class Portfolio(Base, TimestampMixin):
    """Uma carteira de investimentos."""

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    strategy: Mapped[str | None] = mapped_column(String(60), nullable=True)

    positions: Mapped[list[Position]] = relationship(  # noqa: F821
        "Position", back_populates="portfolio", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Portfolio id={self.id} name={self.name!r}>"
