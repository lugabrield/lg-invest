"""Entidade JournalEntry — registro de teses e decisões do investidor
(Volume 12 — Investment Memory & Journal Engine; Volume 17, seção 7).

No MVP, JournalEntry é a versão simplificada da tese de investimento:
registra o que foi decidido, por quê, e o resultado esperado.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.infrastructure.database.base import Base, TimestampMixin

# Ações registráveis no MVP. Conjunto reduzido em relação à lista completa
# do Volume 12 (compra, venda, aporte, revisão de tese, etc.).
JOURNAL_ACTIONS = ("buy", "sell", "hold", "thesis_review")


class JournalEntry(Base, TimestampMixin):
    """Entrada do Investment Journal: tese, decisão e expectativa."""

    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    thesis: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset: Mapped[Asset] = relationship("Asset", back_populates="journal_entries")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<JournalEntry asset_id={self.asset_id} action={self.action!r}>"
