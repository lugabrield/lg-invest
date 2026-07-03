"""Provedor de preços via Yahoo Finance (yfinance).

Este é o ÚNICO módulo que importa yfinance. Se a fonte mudar ou
quebrar, basta criar outro MarketDataProvider sem tocar no serviço
nem nas engines (Volume 4: conectores substituíveis).

O import de yfinance é tardio (dentro dos métodos) para que os testes
possam mockar o provider sem precisar da biblioteca instalada.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from backend.app.core.logging import get_logger
from backend.app.etl.contracts.price_data import PriceData
from backend.app.etl.providers.base import MarketDataProvider

logger = get_logger("lg_invest.provider.yahoo")


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        if value != value:  # NaN
            return None
    except TypeError:
        pass
    return Decimal(str(value))


class YahooFinanceProvider(MarketDataProvider):
    name = "yahoo_finance"

    def get_history(self, ticker: str, currency: str, start: date | None = None) -> list[PriceData]:
        import yfinance as yf

        kwargs = {"auto_adjust": False}
        if start is not None:
            kwargs["start"] = start.isoformat()
        else:
            kwargs["period"] = "1y"

        data = yf.Ticker(ticker).history(**kwargs)
        if data is None or data.empty:
            logger.warning("Sem dados retornados para %s.", ticker)
            return []

        collected = datetime.now(UTC)
        prices: list[PriceData] = []
        for idx, row in data.iterrows():
            row_date = idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])
            close = _to_decimal(row.get("Close"))
            if close is None:
                continue
            prices.append(
                PriceData(
                    ticker=ticker,
                    date=row_date,
                    open=_to_decimal(row.get("Open")),
                    high=_to_decimal(row.get("High")),
                    low=_to_decimal(row.get("Low")),
                    close=close,
                    adjusted_close=_to_decimal(row.get("Adj Close")),
                    volume=_to_decimal(row.get("Volume")),
                    currency=currency,
                    source_name=self.name,
                    collected_at=collected,
                )
            )
        return prices

    def get_latest(self, ticker: str, currency: str) -> PriceData | None:
        history = self.get_history(ticker, currency)
        return history[-1] if history else None
