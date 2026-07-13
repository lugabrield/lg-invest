"""Múltiplos normalizados pelo próprio histórico do ativo (Sprint 26, Fase 2).

Em vez de comparar contra uma banda fixa arbitrária (P/L < 12 = "barato" —
abordagem do Valuation Engine v1 em `engines/valuation/thresholds.py`, e
explicitamente rejeitada pela especificação desta fase: "P/L baixo =
barato" é uma regra ingênua), este método usa a MÉDIA HISTÓRICA DO PRÓPRIO
ATIVO como referência — o preço que o mercado pagaria hoje SE o múltiplo
voltasse à sua própria média histórica, aplicada ao indicador (EPS/VPA)
mais recente. É uma reversão-à-média-própria, não uma comparação com pares
do setor (este projeto não coleta múltiplos de pares); a limitação fica
explícita em `reason` quando o histórico é curto demais para ser
significativo.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.schemas.fundamentals import FundamentalSnapshotResult

MIN_PERIODS_FOR_OWN_HISTORY = 2


def _average(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def normalized_multiples_fair_value(
    history: list[FundamentalSnapshotResult],
    current_eps: Decimal | None,
    current_book_value_per_share: Decimal | None,
) -> tuple[Decimal | None, str | None]:
    """Estima valor justo pela média histórica de P/L e/ou P/VP do PRÓPRIO
    ativo aplicada ao EPS/VPA mais recentes. Devolve `(valor, None)` ou
    `(None, motivo)` — nunca estima com menos de `MIN_PERIODS_FOR_OWN_HISTORY`
    períodos com dado positivo disponível."""
    pe_series = [s.pe_ratio for s in history if s.pe_ratio is not None and s.pe_ratio > 0]
    pb_series = [s.pb_ratio for s in history if s.pb_ratio is not None and s.pb_ratio > 0]

    estimates: list[Decimal] = []
    if (
        len(pe_series) >= MIN_PERIODS_FOR_OWN_HISTORY
        and current_eps is not None
        and current_eps > 0
    ):
        estimates.append(_average(pe_series) * current_eps)
    if (
        len(pb_series) >= MIN_PERIODS_FOR_OWN_HISTORY
        and current_book_value_per_share is not None
        and current_book_value_per_share > 0
    ):
        estimates.append(_average(pb_series) * current_book_value_per_share)

    if not estimates:
        return None, (
            "histórico insuficiente de P/L ou P/VP do próprio ativo "
            f"(mínimo {MIN_PERIODS_FOR_OWN_HISTORY} períodos com dado positivo) "
            "ou EPS/valor patrimonial por ação atual indisponível"
        )

    return _average(estimates), None
