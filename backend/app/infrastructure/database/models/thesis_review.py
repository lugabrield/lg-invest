"""Entidade ThesisReview (Volume 12, seções 4 e 7).

Cada revisão é um registro histórico imutável: guarda a classificação
atribuída na data e a nota da revisão. Revisar uma tese cria uma nova
review e atualiza o status da tese, sem apagar revisões anteriores.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.infrastructure.database.base import Base, TimestampMixin

# Classificação de uma revisão (Volume 12, seção 7).
REVIEW_CLASSIFICATIONS = (
    "confirmed",
    "partially_confirmed",
    "in_observation",
    "invalidated",
)


class ThesisReview(Base, TimestampMixin):
    """Uma revisão periódica de uma tese de investimento."""

    __tablename__ = "thesis_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    thesis_id: Mapped[int] = mapped_column(
        ForeignKey("investment_theses.id"), index=True, nullable=False
    )
    review_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    classification: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    thesis: Mapped[InvestmentThesis] = relationship(  # noqa: F821
        "InvestmentThesis", back_populates="reviews"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ThesisReview thesis_id={self.thesis_id} class={self.classification!r}>"
