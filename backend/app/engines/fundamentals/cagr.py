"""Cálculo puro de CAGR (Compound Annual Growth Rate).

Regra de dado ausente (Volume 18 §8): quando o CAGR não pode ser
calculado de forma significativa (histórico insuficiente, valor
inicial/final não positivo, período de tempo insuficiente), a função
devolve `None` acompanhado de uma razão explícita — nunca um número
inventado ou uma exceção.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

_MIN_POINTS = 2


def compute_cagr(series: list[tuple[date, Decimal]]) -> tuple[Decimal | None, str | None]:
    """Calcula o CAGR entre o primeiro e o último ponto de uma série.

    `series` deve estar ordenada por data ascendente e já filtrada para
    remover pontos sem valor (`None`). Usa apenas o primeiro e o último
    ponto — pontos intermediários não afetam CAGR por definição.
    """
    if len(series) < _MIN_POINTS:
        return None, "histórico insuficiente (mínimo 2 períodos com dado)"

    start_date, start_value = series[0]
    end_date, end_value = series[-1]

    if start_value <= 0 or end_value <= 0:
        return None, "valor inicial ou final não positivo — CAGR não é significativo"

    years = (end_date - start_date).days / 365.25
    if years <= 0:
        return None, "período de tempo insuficiente para calcular CAGR"

    ratio = float(end_value) / float(start_value)
    cagr = ratio ** (1 / years) - 1
    return Decimal(str(round(cagr, 6))), None
