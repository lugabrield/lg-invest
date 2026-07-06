"""Bandas do Capital Reinvestment Engine (Sprint 21).

Heurística MVP própria — taxa de retenção de lucro (1 − payout ratio)
como proxy de disciplina/capacidade de reinvestimento, alinhada à
filosofia de longo prazo do investidor (priorizar reinvestimento sobre
distribuição imediata, documentada em `engines/ids_methodology/profile.py`).
Não é uma regra "universalmente correta" — uma empresa com payout alto
pode simplesmente não ter mais oportunidades atrativas de reinvestir
(maturidade), o que também é uma decisão de capital válida; o MVP não
diferencia os dois casos.

Aplicável só a `stock`/`etf` (equity puro): FIIs/REITs são obrigados por
regulação a distribuir a maior parte do resultado, então payout baixo
não indicaria disciplina — indicaria não conformidade. Cripto/bond/cash
não têm payout ratio (não são participação societária).
"""

from __future__ import annotations

from decimal import Decimal

APPLICABLE_CLASSES = ("stock", "etf")

STRONG_THRESHOLD = Decimal("70")
WEAK_THRESHOLD = Decimal("40")
