"""Provedor de câmbio via Yahoo Finance (yfinance) — fallback do BCB.

Mesma biblioteca já usada para preços de ativos (`yahoo_provider.py`).
Import tardio de yfinance dentro dos métodos, para que os testes
mockem o provider sem precisar da biblioteca instalada — mesmo padrão
do provider de preços.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from backend.app.core.logging import get_logger
from backend.app.etl.providers.fx_provider import FxRateProvider
from backend.app.schemas.market_data import FxQuote

logger = get_logger("lg_invest.provider.yahoo_fx")

_TICKER_BY_PAIR = {"USDBRL": "USDBRL=X"}


class YahooFxProvider(FxRateProvider):
    """Cotação de câmbio via ticker sintético do Yahoo Finance (ex.: USDBRL=X)."""

    name = "yahoo"

    def get_latest(self, pair: str = "USDBRL") -> FxQuote | None:
        return self.get_quote_on_or_before(date.today(), pair=pair)

    def get_quote_on_or_before(self, target: date, pair: str = "USDBRL") -> FxQuote | None:
        ticker = _TICKER_BY_PAIR.get(pair)
        if ticker is None:
            raise ValueError(f"YahooFxProvider não conhece o par '{pair}'.")

        import yfinance as yf

        start = target - timedelta(days=10)
        end = target + timedelta(days=1)
        data = yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat())
        if data is None or data.empty:
            logger.warning("Sem cotação Yahoo para %s até %s.", pair, target)
            return None

        row = data.iloc[-1]
        close = row.get("Close")
        if close is None or close != close:  # NaN
            return None

        row_index = data.index[-1]
        quote_date = (
            row_index.to_pydatetime() if hasattr(row_index, "to_pydatetime") else datetime.now(UTC)
        )

        return FxQuote(
            pair=pair,
            rate=Decimal(str(close)),
            source=self.name,
            quote_date=quote_date,
            fetched_at=datetime.now(UTC),
            is_override=False,
        )
