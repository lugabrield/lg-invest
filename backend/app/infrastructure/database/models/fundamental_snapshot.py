"""Entidade FundamentalSnapshot — fundamentos de um ativo em um período
(Sprint 13 / Fase 2).

Um ativo pode ter vários snapshots ao longo do tempo (um por
`period_end`), o que permite ao Fundamentals Engine (Sprint 14)
calcular CAGR de receita/lucro/FCF a partir de múltiplos períodos
coletados de uma vez (yfinance devolve ~4 anos de demonstrativos numa
única chamada, sem precisar esperar o calendário real).

Todos os campos financeiros são nullable: a ausência de um indicador é
normal (cobertura do yfinance é inconsistente, principalmente para
FIIs, small caps e ativos fora de ações/ETFs) e nunca deve virar erro —
mesma regra de dado ausente usada em todo o projeto (Volume 18 §8).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.infrastructure.database.base import Base, TimestampMixin

# Origem do snapshot: "yahoo" (coleta automática), "manual" (cadastro
# manual avulso, legado), "manual_import" (importação em lote via
# CSV/Excel — Sprint 28, Fase 5, `fundamentals_import_service.py`) ou
# "unavailable" (classe sem fundamentos aplicáveis, ex.: cripto/Tesouro
# Direto — registrado para não recoletar à toa).
FUNDAMENTALS_SOURCES = ("yahoo", "manual", "manual_import", "unavailable")


class FundamentalSnapshot(Base, TimestampMixin):
    """Fundamentos de um ativo referentes a um período (ano fiscal ou TTM)."""

    __tablename__ = "fundamental_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="yahoo")

    # Rentabilidade (frações, ex.: 0.15 = 15%)
    roe: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    roa: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    net_margin: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    ebitda_margin: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    # Demonstrativos (valores absolutos, na moeda do ativo)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    net_income: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    ebitda: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    ebit: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    free_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    net_debt: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)

    # Alavancagem
    debt_to_ebitda: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    # Múltiplos e indicadores por ação (fazem sentido sobretudo no snapshot
    # mais recente/TTM, mas ficam no mesmo modelo por simplicidade do MVP)
    pe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    pb_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    ev_ebitda: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    payout_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    eps: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    revenue_per_share: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    beta: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    # Sprint 21 — campos adicionais de fundamentos (Fundamentals Foundation).
    # Todos nullable pela mesma regra dos campos acima: ausência de dado é
    # normal e nunca deve virar erro.
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    enterprise_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    forward_pe: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    operating_margin: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    total_debt: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    total_cash: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    operating_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    gross_profit: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    shares_outstanding: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)

    # Sprint 26 — Análise Fundamentalista Avançada / Valuation Engine 2.0,
    # Fase 1. Todos nullable pela mesma regra: ausência de dado é normal
    # (ver `etl/providers/yahoo_fundamentals_provider.py` para a fórmula
    # e as limitações — `roic`/`interest_coverage` só são calculados nos
    # snapshots históricos anuais, nunca no snapshot TTM/latest).
    total_equity: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    roic: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    interest_coverage: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    asset: Mapped[Asset] = relationship(  # noqa: F821
        "Asset", back_populates="fundamental_snapshots"
    )

    __table_args__ = (
        UniqueConstraint("asset_id", "period_end", name="uq_fundamental_asset_period"),
        Index("ix_fundamental_snapshots_asset_period", "asset_id", "period_end"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FundamentalSnapshot asset_id={self.asset_id} period_end={self.period_end}>"
