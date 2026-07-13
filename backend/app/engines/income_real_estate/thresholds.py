"""Limiares da Análise de Renda Imobiliária (Sprint 26, Fase 4).

Mesma natureza das bandas do Valuation Engine v1 — heurística MVP
própria, não calibrada por setor. P/VP reaproveita as mesmas bandas já
usadas por `engines/valuation/thresholds.py` para FII/REIT (0.9/1.1);
DY usa uma faixa de referência para o mercado brasileiro de FIIs
(tipicamente 6-9% ao ano histórico).
"""

from __future__ import annotations

from decimal import Decimal

PVP_CHEAP_THRESHOLD = Decimal("0.9")
PVP_EXPENSIVE_THRESHOLD = Decimal("1.1")

DY_ATTRACTIVE_THRESHOLD = Decimal("0.08")
DY_LOW_THRESHOLD = Decimal("0.05")

# Coeficiente de variação (desvio padrão / média) do DY histórico acima
# do qual o yield é considerado "instável" — um yield que oscila muito
# de período a período não é confiável como renda recorrente.
DY_STABILITY_CV_THRESHOLD = Decimal("0.35")
MIN_PERIODS_FOR_STABILITY = 2
