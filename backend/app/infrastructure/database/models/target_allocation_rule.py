"""Entidade TargetAllocationRule — metas de alocação granulares (Sprint 24, Fase 3).

Substitui o antigo `target_allocation_settings_service.py` baseado em
JSON (só por classe, só `target_pct`) por uma tabela real que suporta
quatro dimensões independentes — classe, moeda, país e ativo individual
— cada uma com peso mínimo/alvo/máximo e prioridade de aporte.

Nenhuma regra é pré-cadastrada com valores inventados: enquanto o
usuário não configurar uma regra para uma dimensão, o Target Allocation
Engine trata essa dimensão como "sem meta definida" (mesmo princípio da
Sprint 17), nunca assume um número "recomendado" por conta própria.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.database.base import Base, TimestampMixin

TARGET_ALLOCATION_DIMENSIONS = ("class", "currency", "country", "asset")


class TargetAllocationRule(Base, TimestampMixin):
    """Uma meta de alocação para uma dimensão específica (ex.: dimension_type
    "class", dimension_key "fii") — nunca mistura dimensões na mesma linha."""

    __tablename__ = "target_allocation_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id"), index=True, nullable=False
    )

    # Ver TARGET_ALLOCATION_DIMENSIONS. `dimension_key` é o valor dentro da
    # dimensão: ex. "stock"/"fii"/"etf"/"reit"/"crypto"/"bond" para "class";
    # "BRL"/"USD" para "currency"; "BR"/"US" para "country"; um ticker
    # (ex. "VOO") para "asset".
    dimension_type: Mapped[str] = mapped_column(String(20), nullable=False)
    dimension_key: Mapped[str] = mapped_column(String(60), nullable=False)

    min_weight: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    target_weight: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    max_weight: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)

    # Prioridade manual de aporte (maior = mais prioritário quando underweight,
    # útil para desempatar entre duas classes/ativos igualmente underweight).
    # Nunca calculada automaticamente — é uma preferência explícita do usuário.
    priority: Mapped[int] = mapped_column(nullable=False, default=0)

    __table_args__ = (
        Index(
            "ix_target_allocation_rules_portfolio_dimension",
            "portfolio_id",
            "dimension_type",
            "dimension_key",
            unique=True,
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<TargetAllocationRule portfolio_id={self.portfolio_id} "
            f"{self.dimension_type}={self.dimension_key!r} target={self.target_weight}>"
        )
