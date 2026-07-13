"""Testes do FundamentalsService usando um provider falso (sem rede).

Nenhum teste depende de conexão real (Volume 20, prompt 7).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from backend.app.etl.contracts.fundamental_data import FundamentalData
from backend.app.etl.providers.fundamentals_provider import FundamentalsProvider
from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.database.models.fundamental_snapshot import FundamentalSnapshot
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.services.fundamentals_service import FundamentalsService


class FakeFundamentalsProvider(FundamentalsProvider):
    """Provider controlado para testes."""

    name = "fake"

    def __init__(self, latest=None, history=None, raise_exc: bool = False):
        self._latest = latest
        self._history = history or []
        self._raise = raise_exc
        self.latest_calls: list[str] = []
        self.history_calls: list[str] = []

    def get_latest(self, ticker: str):
        self.latest_calls.append(ticker)
        if self._raise:
            raise ConnectionError("boom")
        return self._latest

    def get_history(self, ticker: str):
        self.history_calls.append(ticker)
        return list(self._history)


def _fund(ticker, period_end, **kwargs) -> FundamentalData:
    return FundamentalData(
        ticker=ticker,
        period_end=period_end,
        source_name="fake",
        collected_at=datetime.now(UTC),
        **kwargs,
    )


def _make_asset(
    db_session, ticker="WEGE3.SA", asset_class="stock", is_manual: bool = False
) -> Asset:
    return AssetRepository(db_session).create(
        Asset(
            ticker=ticker,
            name="X",
            asset_class=asset_class,
            country="BR",
            currency="BRL",
            is_manual=is_manual,
        )
    )


def test_collect_for_asset_persists_latest_and_history(db_session):
    _make_asset(db_session)
    latest = _fund("WEGE3.SA", date(2026, 6, 30), roe=Decimal("0.25"))
    history = [_fund("WEGE3.SA", date(2025, 12, 31), revenue=Decimal("1000"))]
    provider = FakeFundamentalsProvider(latest=latest, history=history)
    service = FundamentalsService(db_session, provider)

    result = service.collect_for_asset("WEGE3.SA")

    assert result.collected is True
    assert result.period_end == date(2026, 6, 30)

    asset = AssetRepository(db_session).get_by_ticker("WEGE3.SA")
    snapshots = FundamentalsRepository(db_session).list_by_asset(asset.id)
    assert len(snapshots) == 2


def test_manual_asset_is_skipped(db_session):
    _make_asset(db_session, "TESOURO-IPCA-2050", asset_class="bond", is_manual=True)
    provider = FakeFundamentalsProvider(latest=_fund("X", date(2026, 1, 1)))
    service = FundamentalsService(db_session, provider)

    result = service.collect_for_asset("TESOURO-IPCA-2050")

    assert result.collected is False
    assert result.reason == "ativo manual"
    assert provider.latest_calls == []


def test_not_applicable_class_is_skipped(db_session):
    _make_asset(db_session, "BTC-USD", asset_class="crypto")
    provider = FakeFundamentalsProvider(latest=_fund("X", date(2026, 1, 1)))
    service = FundamentalsService(db_session, provider)

    result = service.collect_for_asset("BTC-USD")

    assert result.collected is False
    assert "crypto" in result.reason
    assert provider.latest_calls == []


def test_provider_failure_is_handled(db_session):
    _make_asset(db_session)
    provider = FakeFundamentalsProvider(raise_exc=True)
    service = FundamentalsService(db_session, provider)

    result = service.collect_for_asset("WEGE3.SA")

    assert result.collected is False
    assert result.error is not None


def test_provider_failure_keeps_existing_snapshot_and_logs_warning(db_session, caplog):
    """Cenário 10 da Parte 8 (Sprint 28): quando a fonte externa falha, o
    snapshot já existente no banco deve permanecer intocado (nunca é
    zerado nem substituído por um erro) e a falha deve ser registrada em
    log — nunca silenciosa."""
    import logging

    asset = _make_asset(db_session)
    FundamentalsRepository(db_session).create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2026, 6, 30),
            source="yahoo",
            roe=Decimal("0.22"),
        )
    )

    provider = FakeFundamentalsProvider(raise_exc=True)
    service = FundamentalsService(db_session, provider)

    with caplog.at_level(logging.ERROR, logger="lg_invest.fundamentals"):
        result = service.collect_for_asset("WEGE3.SA")

    assert result.collected is False
    assert result.error is not None
    assert any("WEGE3.SA" in record.getMessage() for record in caplog.records)

    snapshot = FundamentalsRepository(db_session).get_by_asset_and_period(
        asset.id, date(2026, 6, 30)
    )
    assert snapshot is not None
    assert snapshot.roe == Decimal("0.22")  # dado antigo preservado, nunca apagado


def test_no_data_from_provider(db_session):
    _make_asset(db_session)
    provider = FakeFundamentalsProvider(latest=None)
    service = FundamentalsService(db_session, provider)

    result = service.collect_for_asset("WEGE3.SA")

    assert result.collected is False
    assert result.reason == "sem dado do provider"


def test_history_failure_does_not_block_latest(db_session):
    _make_asset(db_session)
    latest = _fund("WEGE3.SA", date(2026, 6, 30), roe=Decimal("0.25"))

    class _HistoryFailsProvider(FakeFundamentalsProvider):
        def get_history(self, ticker: str):
            raise ConnectionError("boom")

    provider = _HistoryFailsProvider(latest=latest)
    service = FundamentalsService(db_session, provider)

    result = service.collect_for_asset("WEGE3.SA")

    assert result.collected is True
    asset = AssetRepository(db_session).get_by_ticker("WEGE3.SA")
    snapshots = FundamentalsRepository(db_session).list_by_asset(asset.id)
    assert len(snapshots) == 1


def test_upsert_does_not_overwrite_with_none(db_session):
    _make_asset(db_session)
    provider = FakeFundamentalsProvider(
        latest=_fund("WEGE3.SA", date(2026, 6, 30), roe=Decimal("0.25"))
    )
    service = FundamentalsService(db_session, provider)
    service.collect_for_asset("WEGE3.SA")

    # Segunda coleta sem ROE (None) não deve apagar o valor já salvo.
    provider2 = FakeFundamentalsProvider(
        latest=_fund("WEGE3.SA", date(2026, 6, 30), roe=None, pe_ratio=Decimal("12"))
    )
    service2 = FundamentalsService(db_session, provider2)
    service2.collect_for_asset("WEGE3.SA")

    asset = AssetRepository(db_session).get_by_ticker("WEGE3.SA")
    snapshot = FundamentalsRepository(db_session).get_latest(asset.id)
    assert snapshot.roe == Decimal("0.25")
    assert snapshot.pe_ratio == Decimal("12")


def test_unknown_ticker_returns_error_reason(db_session):
    provider = FakeFundamentalsProvider()
    service = FundamentalsService(db_session, provider)
    result = service.collect_for_asset("NOPE9.SA")
    assert result.collected is False
    assert result.reason == "ativo não cadastrado"


def test_collect_all_batches_active_assets(db_session):
    _make_asset(db_session, "WEGE3.SA")
    _make_asset(db_session, "BTC-USD", asset_class="crypto")
    provider = FakeFundamentalsProvider(latest=_fund("X", date(2026, 1, 1)))
    service = FundamentalsService(db_session, provider)

    batch = service.collect_all()

    assert len(batch.results) == 2
    assert batch.total_collected == 1
    assert batch.total_skipped == 1
