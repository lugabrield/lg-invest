"""Serviço de crescimento (Sprint 16 / Fase 2).

Ponte entre o FundamentalsAnalysisService (Sprint 14, que já calcula
CAGR e tendência de margem) e o Growth Engine (puro): não acessa o
repositório diretamente, compõe com o serviço de análise de
fundamentos para evitar duplicar a lógica de cálculo de CAGR.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.engines.growth.engine import GrowthEngine
from backend.app.schemas.growth import GrowthResult
from backend.app.services.fundamentals_analysis_service import FundamentalsAnalysisService


class GrowthService:
    def __init__(self, db: Session):
        self.db = db
        self.fundamentals_analysis = FundamentalsAnalysisService(db)
        self.engine = GrowthEngine()

    def evaluate_ticker(self, ticker: str) -> GrowthResult | None:
        """Devolve a classificação de crescimento de um ativo, ou `None`
        se o ativo não estiver cadastrado."""
        analysis = self.fundamentals_analysis.analyze_ticker(ticker)
        if analysis is None:
            return None
        return self.engine.evaluate(ticker, analysis)
