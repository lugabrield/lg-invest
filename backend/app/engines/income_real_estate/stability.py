"""Estabilidade do Dividend Yield histórico (Sprint 26, Fase 4) — puro.

Um DY alto só é um sinal de renda confiável se for consistente ao longo
do tempo. Mede isso via coeficiente de variação (desvio padrão / média)
da série histórica de `dividend_yield` do próprio ativo — nunca compara
com pares do setor (este projeto não coleta esse dado).
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.income_real_estate.thresholds import (
    DY_STABILITY_CV_THRESHOLD,
    MIN_PERIODS_FOR_STABILITY,
)
from backend.app.schemas.income_real_estate import (
    DY_STABILITY_INDETERMINATE,
    DY_STABILITY_STABLE,
    DY_STABILITY_UNSTABLE,
)


def _average(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def dy_stability(dy_series: list[Decimal]) -> tuple[str, Decimal | None, str | None]:
    """Devolve `(classificação, média_histórica, motivo_se_indeterminado)`.

    `dy_series` deve conter só valores positivos já disponíveis (sem
    `None`) — filtragem é responsabilidade de quem chama."""
    positive_series = [v for v in dy_series if v is not None and v > 0]
    if len(positive_series) < MIN_PERIODS_FOR_STABILITY:
        return (
            DY_STABILITY_INDETERMINATE,
            None,
            f"histórico insuficiente de DY (mínimo {MIN_PERIODS_FOR_STABILITY} períodos "
            "com dado positivo)",
        )

    mean = _average(positive_series)
    if mean <= 0:
        return DY_STABILITY_INDETERMINATE, None, "média histórica de DY não positiva"

    variance = _average([(v - mean) ** 2 for v in positive_series])
    # Decimal não tem sqrt de alta precisão sem `decimal.Context.sqrt`; raiz
    # via float é suficiente para uma fração — mesmo padrão de graham.py.
    stdev = Decimal(str(float(variance) ** 0.5))
    coefficient_of_variation = stdev / mean

    classification = (
        DY_STABILITY_UNSTABLE
        if coefficient_of_variation >= DY_STABILITY_CV_THRESHOLD
        else DY_STABILITY_STABLE
    )
    return classification, mean, None
