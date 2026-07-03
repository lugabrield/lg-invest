"""Serviço do Diagnóstico da Carteira.

Fronteira fina entre banco e o engine de diagnóstico: monta o
`DashboardView` (via `dashboard_view_service`, que já lida com câmbio e
preços) e chama o engine puro. Nenhuma regra vive aqui — só wiring.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.engines.portfolio_diagnostics.engine import build_diagnostics
from backend.app.schemas.portfolio_diagnostics import PortfolioDiagnostics
from backend.app.services.dashboard_view_service import build_dashboard_view


def get_portfolio_diagnostics(
    db: Session, portfolio_id: int, exchange_rate: Decimal
) -> PortfolioDiagnostics:
    """Monta o view-model do Dashboard e devolve o diagnóstico calculado sobre ele."""
    view = build_dashboard_view(db, portfolio_id, exchange_rate)
    return build_diagnostics(view)
