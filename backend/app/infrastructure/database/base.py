"""Base declarativa e mixin de timestamps da LG INVEST.

Todas as entidades ORM herdam de `Base` (e, quando fizer sentido,
de `TimestampMixin`) para manter um padrão único de criação e
auditoria temporal, conforme Volume 16.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarativa única do projeto."""


class TimestampMixin:
    """Adiciona created_at/updated_at automáticos a uma entidade."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
