"""Entidade InvestmentPolicy — política de investimento do usuário (Sprint 24, Fase 3).

Guarda os limites/parâmetros que orientam Decision Engine, Target
Allocation e (no futuro) o Simulation Engine: NUNCA são calculados por
uma engine — são configuração explícita do usuário, com defaults
sensatos sugeridos na primeira vez que a tela de Configurações é aberta,
mas sempre editáveis e nunca hardcoded dentro de uma engine.

Uma linha por `portfolio_id` (política única por carteira — o MVP tem
uma carteira consolidada por usuário).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.database.base import Base, TimestampMixin

RISK_TOLERANCES = ("baixo", "moderado", "moderado-alto", "alto")


class InvestmentPolicy(Base, TimestampMixin):
    """Política de investimento pessoal — perfil, limites e parâmetros
    de simulação. Nenhuma engine deve hardcodar estes valores; todas
    devem ler desta entidade (via `investment_policy_service.py`)."""

    __tablename__ = "investment_policy"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id"), unique=True, index=True, nullable=False
    )

    # --- Perfil do investidor -------------------------------------------------
    investor_profile: Mapped[str] = mapped_column(String(120), nullable=False)
    horizon_years: Mapped[int] = mapped_column(nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    risk_tolerance: Mapped[str] = mapped_column(String(20), nullable=False)

    # --- Limites (guardrails usados pelo Decision Engine) ---------------------
    max_asset_weight: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    max_crypto_weight: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    target_international_min: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    target_international_max: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    target_fii_max: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)

    # --- Metas de referência por classe/mercado (informativas — usadas na
    # explicação do Decision Engine, não substituem `target_allocation_rules`
    # quando o usuário configurar metas mais granulares lá) ---------------
    target_brazil_equity: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    target_us_equity: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    target_etf: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    target_reit: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    target_fixed_income: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)

    # --- Aportes e rebalanceamento ---------------------------------------
    rebalance_threshold: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    monthly_contribution_default: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<InvestmentPolicy portfolio_id={self.portfolio_id} "
            f"profile={self.investor_profile!r} horizon={self.horizon_years}>"
        )
