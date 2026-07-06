"""Limiares do Portfolio Health Score (Sprint 24, Fase 8).

Bandas próprias desta engine, deliberadamente independentes das usadas
por `portfolio_diagnostics/thresholds.py` e `portfolio_risk/thresholds.py`
(mesma convenção: cada engine tem seus próprios limiares documentados,
sem acoplar uma à outra).
"""

from __future__ import annotations

from decimal import Decimal

# Diversificação (número efetivo de ativos, 1/HHI). 1 ativo = saúde 0%;
# a partir de HIGH_N ativos efetivos, saúde máxima (100%).
DIVERSIFICATION_HIGH_N = Decimal("15")

# Alinhamento de risco: quantas faixas de RISK_TOLERANCES acima da
# declarada o risco medido está. 0 faixas = 100; cada faixa acima
# desconta PENALTY_PER_BAND.
RISK_TOLERANCE_ORDER = ("baixo", "moderado", "moderado-alto", "alto")
RISK_ALIGNMENT_PENALTY_PER_BAND = Decimal("30")

# Tendência de renda (Income Engine, growth_pct TTM vs período anterior).
INCOME_GROWTH_STRONG = Decimal("0.05")  # >= 5%: saúde máxima
INCOME_GROWTH_DECLINE_SEVERE = Decimal("-0.10")  # <= -10%: saúde mínima

HEALTH_CRITICA_MAX = Decimal("40")
HEALTH_ATENCAO_MAX = Decimal("65")
HEALTH_BOA_MAX = Decimal("85")
HEALTH_LABELS = ("crítica", "atenção", "boa", "excelente")


def classify_health_score(score: Decimal) -> str:
    """Classifica o score composto (0..100, maior = mais saudável)."""
    if score <= HEALTH_CRITICA_MAX:
        return "crítica"
    if score <= HEALTH_ATENCAO_MAX:
        return "atenção"
    if score <= HEALTH_BOA_MAX:
        return "boa"
    return "excelente"
