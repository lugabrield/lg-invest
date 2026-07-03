"""Validadores de qualidade de preço (Volume 4, seção 13; Volume 18, seção 7).

Antes de qualquer PriceData entrar na tabela `prices`, ele passa por
estas regras mínimas. Dados ruins são rejeitados com um motivo claro,
em vez de contaminarem as engines silenciosamente.
"""

from __future__ import annotations

from datetime import date

from backend.app.etl.contracts.price_data import PriceData


def validate_price(price: PriceData, today: date | None = None) -> str | None:
    """Retorna None se o preço é válido, ou uma string com o motivo da rejeição."""
    reference = today or date.today()

    if price.close <= 0:
        return "close deve ser positivo"

    if price.date > reference:
        return "data no futuro"

    # Coerência OHLC quando os campos existem.
    if price.high is not None and price.low is not None and price.high < price.low:
        return "high menor que low"

    for field_name in ("open", "high", "low", "adjusted_close"):
        value = getattr(price, field_name)
        if value is not None and value < 0:
            return f"{field_name} negativo"

    if price.volume is not None and price.volume < 0:
        return "volume negativo"

    return None
