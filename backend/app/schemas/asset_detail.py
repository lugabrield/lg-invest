"""Schema de detalhe de um ativo (v1.1, Fase 6 — ver docs/API_CONTRACT.md).

Embrulha o que a seção "Análise Fundamentalista" + "LG Score" +
"LG Conviction Score v2" de `pages_impl/ativos.py` compõe para UM
ticker: LG Score, Conviction Score, qualidade de dado, fundamentos
brutos, análise de crescimento (CAGR), valuation legado (v1, múltiplos),
Valuation Engine 2.0 (só ações), Análise de Renda Imobiliária (só
FII/REIT), Adequação à Política de Alocação (ETF/cripto/Tesouro), Trap
Detection e cobertura de dado. Cada bloco é `None` quando não aplicável
à classe do ativo ou quando não há dado suficiente — nunca um valor
inventado, mesma regra do resto da plataforma.
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.app.schemas.data_coverage import DataCoverageResult
from backend.app.schemas.data_quality import AssetDataQuality
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.fundamentals_analysis import FundamentalsAnalysisResult
from backend.app.schemas.ids_methodology import ConvictionScoreResult
from backend.app.schemas.income_real_estate import IncomeRealEstateAnalysisResult
from backend.app.schemas.lg_score import LGScoreResult
from backend.app.schemas.portfolio_adequacy import PortfolioAdequacyResult
from backend.app.schemas.trap_detection import TrapDetectionResult
from backend.app.schemas.valuation import ValuationResult
from backend.app.schemas.valuation_v2 import ValuationV2Result


class AssetDetailBundle(BaseModel):
    ticker: str
    name: str
    asset_class: str
    currency: str
    is_manual: bool

    lg_score: LGScoreResult | None = None
    conviction: ConvictionScoreResult | None = None
    data_quality: AssetDataQuality | None = None

    fundamentals: FundamentalSnapshotResult | None = None
    fundamentals_analysis: FundamentalsAnalysisResult | None = None
    legacy_valuation: ValuationResult | None = None

    # Só um dos três abaixo é preenchido, conforme a classe do ativo
    # (mesma regra de `_STOCK_CLASSES`/`_INCOME_REAL_ESTATE_CLASSES`/
    # `_NO_TRADITIONAL_VALUATION_CLASSES` em `pages_impl/ativos.py`).
    valuation_v2: ValuationV2Result | None = None
    income_real_estate: IncomeRealEstateAnalysisResult | None = None
    adequacy: PortfolioAdequacyResult | None = None

    trap_detection: TrapDetectionResult | None = None
    coverage: DataCoverageResult | None = None
