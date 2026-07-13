"""Grupos de campos e limiares de classificação do Data Coverage Engine
(Sprint 28).

Heurística MVP própria, no mesmo espírito de `engines/quality/thresholds.py`
e `engines/trap_detection/thresholds.py`: números simples e auditáveis,
não calibrados estatisticamente. Cada grupo de campos "espelha" — nunca
reimplementa — o que o consumidor real (`QualityEngine`, `ValuationEngineV2`,
`TrapDetectionEngine`, `IncomeRealEstateEngine`) de fato usa, para que o
relatório de cobertura nunca minta sobre o que falta.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.quality.thresholds import APPLICABLE_CLASSES as QUALITY_APPLICABLE_CLASSES
from backend.app.engines.quality.thresholds import QUALITY_BANDS
from backend.app.engines.trap_detection.thresholds import MIN_PERIODS_FOR_CONFIDENT_HISTORY
from backend.app.engines.valuation_v2.multiples import MIN_PERIODS_FOR_OWN_HISTORY

# -- Quality --------------------------------------------------------------
# Mesmos campos de `QUALITY_BANDS` (roe, net_margin, debt_to_ebitda) — a
# fonte da verdade continua sendo o Quality Engine; aqui só extraímos
# (campo, rótulo) para exibição.
QUALITY_FIELDS: tuple[tuple[str, str], ...] = tuple(
    (band.field, band.label) for band in QUALITY_BANDS
)

# -- Valuation Engine 2.0 (só ações — mesmo escopo de
# `engines/valuation_v2/engine.py::_APPLICABLE_ASSET_CLASSES`) ------------
VALUATION_APPLICABLE_CLASSES = ("stock",)

VALUATION_SNAPSHOT_FIELDS: tuple[tuple[str, str], ...] = (
    ("free_cash_flow", "FCF (fluxo de caixa livre)"),
    ("shares_outstanding", "Ações em circulação"),
    ("net_debt", "Dívida líquida"),
    ("beta", "Beta"),
    ("eps", "LPA (lucro por ação)"),
    ("total_equity", "Patrimônio líquido"),
    ("pe_ratio", "P/L"),
    ("pb_ratio", "P/VP"),
)
VALUATION_GROWTH_LABEL = "Histórico de receita/lucro/FCF (para taxa de crescimento)"

# -- Trap Detection Engine --------------------------------------------------
TRAP_DETECTION_APPLICABLE_CLASSES = ("stock", "fii", "reit")

TRAP_DETECTION_STOCK_FIELDS: tuple[tuple[str, str], ...] = (
    ("pe_ratio", "P/L"),
    ("pb_ratio", "P/VP"),
    ("roe", "ROE"),
    ("debt_to_ebitda", "Dívida/EBITDA"),
    ("interest_coverage", "Cobertura de juros"),
)
TRAP_DETECTION_INCOME_FIELDS: tuple[tuple[str, str], ...] = (("dividend_yield", "Dividend Yield"),)
TRAP_DETECTION_HISTORY_LABEL = "Histórico com pelo menos 2 períodos"

# -- Análise de Renda Imobiliária (FII/REIT) -------------------------------
INCOME_APPLICABLE_CLASSES = ("fii", "reit")
INCOME_FIELDS: tuple[tuple[str, str], ...] = (
    ("pb_ratio", "P/VP"),
    ("dividend_yield", "Dividend Yield"),
)
INCOME_HISTORY_LABEL = "Histórico de Dividend Yield (estabilidade)"

# -- Campos do relatório completo (Parte 1 da especificação) --------------
# Todos exibidos, aplicáveis ou não à classe — o relatório mostra
# disponível/ausente para cada um, sempre.
REPORT_SNAPSHOT_FIELDS: tuple[tuple[str, str], ...] = (
    ("market_cap", "Market cap"),
    ("revenue", "Receita"),
    ("net_income", "Lucro líquido"),
    ("ebitda", "EBITDA"),
    ("ebit", "EBIT"),
    ("free_cash_flow", "FCF (fluxo de caixa livre)"),
    ("net_debt", "Dívida líquida"),
    ("total_debt", "Dívida total"),
    ("total_cash", "Caixa"),
    ("total_equity", "Patrimônio líquido"),
    ("roe", "ROE"),
    ("roic", "ROIC"),
    ("net_margin", "Margem líquida"),
    ("operating_margin", "Margem operacional"),
    ("pe_ratio", "P/L"),
    ("pb_ratio", "P/VP"),
    ("ev_ebitda", "EV/EBITDA"),
    ("dividend_yield", "Dividend Yield"),
    ("payout_ratio", "Payout"),
)

FIELD_PRICE_HISTORY = "price_history"
FIELD_DIVIDEND_HISTORY = "dividend_history"
FIELD_GROWTH_HISTORY = "growth_history"
FIELD_CURRENT_PRICE = "current_price"

REPORT_SYNTHETIC_FIELDS: tuple[tuple[str, str], ...] = (
    (FIELD_CURRENT_PRICE, "Preço atual"),
    (FIELD_PRICE_HISTORY, "Histórico de preço"),
    (FIELD_DIVIDEND_HISTORY, "Histórico de dividendos (Dividend Yield por período)"),
    (FIELD_GROWTH_HISTORY, "Histórico de receita/lucro/FCF"),
)

MIN_PERIODS_FOR_PRICE_HISTORY = 2

# -- Classificação de score (0-100) ----------------------------------------
SCORE_SUFFICIENT = Decimal("70")
SCORE_PARTIAL = Decimal("30")

CLASSIFICATION_SUFFICIENT = "suficiente"
CLASSIFICATION_PARTIAL = "parcial"
CLASSIFICATION_INSUFFICIENT = "insuficiente"
CLASSIFICATION_NOT_APPLICABLE = "não aplicável"

# -- Dados desatualizados (Sprint 28, Parte 8, cenário "stale data reduces
# confidence") ---------------------------------------------------------
# 400 dias (~13 meses): folga sobre o ciclo anual normal de demonstrativos
# financeiros, para não penalizar um snapshot só porque o próximo
# fechamento anual ainda não saiu. Heurística MVP, não calibrada
# estatisticamente — mesmo espírito dos outros limiares deste módulo.
STALE_DATA_THRESHOLD_DAYS = 400
STALE_DATA_SCORE_FACTOR = Decimal("0.85")


def classify_score(score: Decimal) -> str:
    if score >= SCORE_SUFFICIENT:
        return CLASSIFICATION_SUFFICIENT
    if score >= SCORE_PARTIAL:
        return CLASSIFICATION_PARTIAL
    return CLASSIFICATION_INSUFFICIENT


__all__ = [
    "QUALITY_APPLICABLE_CLASSES",
    "QUALITY_FIELDS",
    "VALUATION_APPLICABLE_CLASSES",
    "VALUATION_SNAPSHOT_FIELDS",
    "VALUATION_GROWTH_LABEL",
    "TRAP_DETECTION_APPLICABLE_CLASSES",
    "TRAP_DETECTION_STOCK_FIELDS",
    "TRAP_DETECTION_INCOME_FIELDS",
    "TRAP_DETECTION_HISTORY_LABEL",
    "INCOME_APPLICABLE_CLASSES",
    "INCOME_FIELDS",
    "INCOME_HISTORY_LABEL",
    "REPORT_SNAPSHOT_FIELDS",
    "REPORT_SYNTHETIC_FIELDS",
    "FIELD_CURRENT_PRICE",
    "FIELD_PRICE_HISTORY",
    "FIELD_DIVIDEND_HISTORY",
    "FIELD_GROWTH_HISTORY",
    "MIN_PERIODS_FOR_PRICE_HISTORY",
    "MIN_PERIODS_FOR_CONFIDENT_HISTORY",
    "MIN_PERIODS_FOR_OWN_HISTORY",
    "SCORE_SUFFICIENT",
    "SCORE_PARTIAL",
    "CLASSIFICATION_SUFFICIENT",
    "CLASSIFICATION_PARTIAL",
    "CLASSIFICATION_INSUFFICIENT",
    "CLASSIFICATION_NOT_APPLICABLE",
    "STALE_DATA_THRESHOLD_DAYS",
    "STALE_DATA_SCORE_FACTOR",
    "classify_score",
]
