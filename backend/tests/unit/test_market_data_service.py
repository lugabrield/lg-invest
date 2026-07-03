"""Testes do MarketDataService usando um provider falso (sem rede).

Nenhum teste depende de conexão real (Volume 20, prompt 7).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from backend.app.etl.contracts.price_data import PriceData
from backend.app.etl.providers.base import MarketDataProvider
from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.services.market_data_service import MarketDataService


class FakeProvider(MarketDataProvider):
    """Provider controlado para testes."""

    name = "fake"

    def __init__(self, history: list[PriceData] | None = None, raise_exc: bool = False):
        self._history = history or []
        self._raise = raise_exc
        self.calls: list[tuple[str, date | None]] = []

    def get_history(self, ticker, currency, start=None):
        self.calls.append((ticker, start))
        if self._raise:
            raise ConnectionError("boom")
        return list(self._history)

    def get_latest(self, ticker, currency):
        return self._history[-1] if self._history else None


def _price(ticker, d, close, **kwargs) -> PriceData:
    return PriceData(
        ticker=ticker,
        date=d,
        close=Decimal(str(close)),
        currency="BRL",
        source_name="fake",
        collected_at=datetime.now(UTC),
        **kwargs,
    )


def _make_asset(db_session, ticker="WEGE3.SA", is_manual: bool = False) -> Asset:
    return AssetRepository(db_session).create(
        Asset(
            ticker=ticker,
            name="WEG",
            asset_class="stock",
            country="BR",
            currency="BRL",
            is_manual=is_manual,
        )
    )


def test_insert_new_prices(db_session):
    _make_asset(db_session)
    provider = FakeProvider(
        [
            _price("WEGE3.SA", date(2026, 1, 2), 40.0),
            _price("WEGE3.SA", date(2026, 1, 3), 41.5),
        ]
    )
    service = MarketDataService(db_session, provider)
    result = service.update_asset_prices("WEGE3.SA")
    assert result.inserted == 2
    assert result.updated == 0
    assert result.error is None


def test_idempotent_update(db_session):
    _make_asset(db_session)
    history = [_price("WEGE3.SA", date(2026, 1, 2), 40.0)]
    provider = FakeProvider(history)
    service = MarketDataService(db_session, provider)

    first = service.update_asset_prices("WEGE3.SA")
    assert first.inserted == 1

    # Segunda chamada: começa após a última data; provider devolve o mesmo
    # registro -> deve atualizar, não duplicar.
    second = service.update_asset_prices("WEGE3.SA")
    # Como start avança para 2026-01-03, o provider ainda devolve 2026-01-02
    # (fake não filtra); o serviço faz upsert -> updated.
    assert second.inserted == 0
    assert second.updated == 1


def test_incremental_start_date(db_session):
    _make_asset(db_session)
    provider = FakeProvider([_price("WEGE3.SA", date(2026, 1, 2), 40.0)])
    service = MarketDataService(db_session, provider)
    service.update_asset_prices("WEGE3.SA")
    # A próxima coleta deve pedir start = última data + 1 dia.
    service.update_asset_prices("WEGE3.SA")
    assert provider.calls[-1] == ("WEGE3.SA", date(2026, 1, 3))


def test_rejects_invalid_price(db_session):
    _make_asset(db_session)
    provider = FakeProvider(
        [
            _price("WEGE3.SA", date(2026, 1, 2), 40.0),
            _price("WEGE3.SA", date(2026, 1, 3), -5.0),  # close negativo
        ]
    )
    service = MarketDataService(db_session, provider)
    result = service.update_asset_prices("WEGE3.SA")
    assert result.inserted == 1
    assert result.rejected == 1


def test_provider_failure_is_handled(db_session):
    _make_asset(db_session)
    provider = FakeProvider(raise_exc=True)
    service = MarketDataService(db_session, provider)
    result = service.update_asset_prices("WEGE3.SA")
    assert result.error is not None
    assert result.inserted == 0


def test_unknown_ticker_returns_error(db_session):
    provider = FakeProvider([])
    service = MarketDataService(db_session, provider)
    result = service.update_asset_prices("NOPE9.SA")
    assert result.error == "ativo não cadastrado"


def test_update_all_active(db_session):
    _make_asset(db_session, "WEGE3.SA")
    _make_asset(db_session, "ITUB4.SA")
    provider = FakeProvider([_price("X", date(2026, 1, 2), 10.0)])
    service = MarketDataService(db_session, provider)
    batch = service.update_all_active()
    assert len(batch.results) == 2
    assert batch.total_inserted == 2


def test_manual_asset_is_skipped_and_provider_not_called(db_session):
    _make_asset(db_session, "TESOURO-IPCA-2050", is_manual=True)
    provider = FakeProvider([_price("X", date(2026, 1, 2), 10.0)])
    service = MarketDataService(db_session, provider)

    result = service.update_asset_prices("TESOURO-IPCA-2050")

    assert result.skipped_manual is True
    assert result.error is None
    assert result.inserted == 0
    assert provider.calls == []


def test_update_all_active_skips_manual_assets(db_session):
    _make_asset(db_session, "WEGE3.SA", is_manual=False)
    _make_asset(db_session, "TESOURO-IPCA-2050", is_manual=True)
    provider = FakeProvider([_price("X", date(2026, 1, 2), 10.0)])
    service = MarketDataService(db_session, provider)

    batch = service.update_all_active()

    assert len(batch.results) == 2
    assert batch.total_skipped_manual == 1
    assert batch.total_inserted == 1
    manual_result = next(r for r in batch.results if r.ticker == "TESOURO-IPCA-2050")
    assert manual_result.skipped_manual is True


def test_one_ticker_failure_does_not_block_others_in_batch(db_session):
    _make_asset(db_session, "WEGE3.SA")
    _make_asset(db_session, "ITUB4.SA")

    class _PartialFailureProvider(MarketDataProvider):
        name = "partial"

        def get_history(self, ticker, currency, start=None):
            if ticker == "WEGE3.SA":
                raise ConnectionError("boom")
            return [_price(ticker, date(2026, 1, 2), 10.0)]

        def get_latest(self, ticker, currency):
            return None

    service = MarketDataService(db_session, _PartialFailureProvider())
    batch = service.update_all_active()

    assert len(batch.results) == 2
    assert batch.failed == ["WEGE3.SA"]
    assert batch.total_inserted == 1
