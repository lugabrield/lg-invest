"""Limiares dos detectores de armadilha (Sprint 26, Fase 3).

Assim como as bandas do Valuation Engine v1 (`engines/valuation/thresholds.py`),
estes números são uma heurística MVP própria — não específica de setor,
nem calibrada estatisticamente. Ficam isolados aqui, documentados, para
serem fáceis de revisar. Cada detector só dispara quando MAIS DE UM sinal
concorda (ex.: P/L baixo sozinho nunca é armadilha — some com lucro em
queda ou margem piorando) — essa é a defesa central contra a regra
ingênua "P/L baixo = barato" que a especificação proíbe.
"""

from __future__ import annotations

from decimal import Decimal

# --- Low P/E Trap ------------------------------------------------------
LOW_PE_THRESHOLD = Decimal("8")

# --- Low P/B Trap --------------------------------------------------------
LOW_PB_THRESHOLD = Decimal("1.0")
LOW_ROE_THRESHOLD = Decimal("0.05")  # ROE abaixo disso não sustenta um P/VP baixo como "barato"

# --- Growth Overpriced Trap ---------------------------------------------
# Diferença (em pontos percentuais, fração) entre o crescimento implícito
# no preço (reverse DCF) e o crescimento histórico real acima da qual o
# mercado está "comprando a história", não os números já entregues.
GROWTH_OVERPRICED_GAP_MEDIUM = Decimal("0.08")
GROWTH_OVERPRICED_GAP_HIGH = Decimal("0.15")

# --- Leverage Trap ---------------------------------------------------
HIGH_LEVERAGE_DEBT_TO_EBITDA = Decimal("4")
VERY_HIGH_LEVERAGE_DEBT_TO_EBITDA = Decimal("6")
LOW_INTEREST_COVERAGE = Decimal("2")
VERY_LOW_INTEREST_COVERAGE = Decimal("1")

# --- Data Quality Trap -------------------------------------------------
LOW_COVERAGE_PCT = Decimal("0.5")
VERY_LOW_COVERAGE_PCT = Decimal("0.3")
MIN_PERIODS_FOR_CONFIDENT_HISTORY = 2

# --- High DY Trap (FIIs/REITs, Sprint 26 Fase 4) ------------------------
# DY anual acima disso é incomum o suficiente para merecer verificação —
# pode refletir queda de preço recente, distribuição pontual de capital
# (não recorrente), ou simplesmente insustentabilidade.
HIGH_DY_THRESHOLD = Decimal("0.12")
VERY_HIGH_DY_THRESHOLD = Decimal("0.18")

# --- FII Yield Trap (FIIs/REITs, Sprint 26 Fase 4) -----------------------
# Razão entre o DY do período mais recente e a média histórica do PRÓPRIO
# ativo acima da qual o yield atual parece um pico não recorrente, não a
# distribuição recorrente esperada.
FII_YIELD_SPIKE_RATIO_MEDIUM = Decimal("1.4")
FII_YIELD_SPIKE_RATIO_HIGH = Decimal("1.8")
