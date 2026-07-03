"""Funções de normalização e estatística para o LG Score (Volume 20, prompt 9).

Helpers puros, sem estado. Todas as notas finais passam por `clamp_score`
para garantir o intervalo 0..100 exigido pela especificação.
"""

from __future__ import annotations

from decimal import Decimal

NEUTRAL = Decimal("50")
MIN_SCORE = Decimal("0")
MAX_SCORE = Decimal("100")


def clamp_score(value: Decimal) -> Decimal:
    """Garante que a nota fique entre 0 e 100."""
    if value < MIN_SCORE:
        return MIN_SCORE
    if value > MAX_SCORE:
        return MAX_SCORE
    return value


def mean(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, start=Decimal("0")) / Decimal(len(values))


def cagr(history: list[Decimal]) -> Decimal | None:
    """CAGR aproximado sobre a série de preços (primeiro -> último).

    Usa o número de pontos como proxy de períodos. Retorna None se não
    houver dados suficientes ou se o preço inicial for não-positivo.
    """
    if len(history) < 2:
        return None
    first = history[0]
    last = history[-1]
    if first <= 0:
        return None
    periods = len(history) - 1
    ratio = last / first
    # CAGR = ratio**(1/periods) - 1, via float só para o expoente fracionário.
    growth = Decimal(str(float(ratio) ** (1.0 / periods))) - Decimal("1")
    return growth


def volatility(history: list[Decimal]) -> Decimal | None:
    """Desvio-padrão dos retornos simples período a período.

    Retorna None se não houver retornos suficientes.
    """
    if len(history) < 2:
        return None
    returns: list[Decimal] = []
    for prev, curr in zip(history[:-1], history[1:], strict=False):
        if prev <= 0:
            continue
        returns.append((curr - prev) / prev)
    if len(returns) < 2:
        return None
    avg = sum(returns, start=Decimal("0")) / Decimal(len(returns))
    variance = sum(((r - avg) ** 2 for r in returns), start=Decimal("0")) / Decimal(len(returns))
    return Decimal(str(float(variance) ** 0.5))


def max_drawdown(history: list[Decimal]) -> Decimal | None:
    """Maior queda do pico ao vale (fração positiva). None se insuficiente."""
    if len(history) < 2:
        return None
    peak = history[0]
    worst = Decimal("0")
    for price in history:
        if price > peak:
            peak = price
        if peak > 0:
            drawdown = (peak - price) / peak
            if drawdown > worst:
                worst = drawdown
    return worst
