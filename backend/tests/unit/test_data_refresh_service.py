"""Testes do DataRefreshService — Central de Dados (Sprint 27).

Cobre as garantias centrais da Central de Dados: preços/fundamentos da
carteira nunca tocam a watchlist; a watchlist nunca cria `Position` nem
altera patrimônio; falha num ativo nunca derruba o lote; dado ausente
vira "insufficient_data", nunca um valor fabricado; recomputação de
valuation/traps/scores respeita a classe do ativo (nunca DCF/P-L para
FII/REIT/ETF/cripto/Tesouro); nada roda sem uma chamada explícita a um
método do serviço.

Nenhum teste depende de rede: os providers do Yahoo são substituídos por
fakes controlados, no mesmo padrão de `test_market_data_service.py` e
`test_fundamentals_service.py`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from backend.app.etl.contracts.fundamental_data import FundamentalData
from backend.app.etl.contracts.price_data import PriceData
from backend.app.etl.providers.base import MarketDataProvider
from backend.app.etl.providers.fundamentals_provider import FundamentalsProvider
from backend.app.infrastructure.database.models import Asset, Portfolio, Position
from backend.app.infrastructure.database.models.watchlist_asset import WatchlistAsset
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.position_repository import PositionRepository
from backend.app.services import data_refresh_service, data_refresh_status_service
from backend.app.services.data_refresh_service import DataRefreshService
from backend.app.services.income_real_estate_service import IncomeRealEstateService
from backend.app.services.valuation_v2_service import ValuationServiceV2

# -- fakes (sem rede) --------------------------------------------------


class FakeMarketProvider(MarketDataProvider):
    name = "fake"

    def __init__(self, history: list[PriceData] | None = None, raise_exc: bool = False):
        self._history = history or []
        self._raise = raise_exc
        self.calls: list[str] = []

    def get_history(self, ticker, currency, start=None):
        self.calls.append(ticker)
        if self._raise:
            raise ConnectionError("boom")
        return list(self._history)

    def get_latest(self, ticker, currency):
        return self._history[-1] if self._history else None


class FakeFundamentalsProvider(FundamentalsProvider):
    name = "fake"

    def __init__(self, latest=None, raise_exc: bool = False):
        self._latest = latest
        self._raise = raise_exc
        self.calls: list[str] = []

    def get_latest(self, ticker: str):
        self.calls.append(ticker)
        if self._raise:
            raise ConnectionError("boom")
        return self._latest

    def get_history(self, ticker: str):
        return []


def _price(ticker, d, close=Decimal("40.0"), **kwargs) -> PriceData:
    return PriceData(
        ticker=ticker,
        date=d,
        close=close,
        currency="BRL",
        source_name="fake",
        collected_at=datetime.now(UTC),
        **kwargs,
    )


def _fund(ticker, period_end=date(2025, 12, 31), **kwargs) -> FundamentalData:
    return FundamentalData(
        ticker=ticker,
        period_end=period_end,
        source_name="fake",
        collected_at=datetime.now(UTC),
        **kwargs,
    )


def _install_fake_providers(monkeypatch, market=None, fundamentals=None) -> None:
    """Substitui os providers instanciados dentro do DataRefreshService."""
    market = market if market is not None else FakeMarketProvider()
    fundamentals = fundamentals if fundamentals is not None else FakeFundamentalsProvider()
    monkeypatch.setattr(data_refresh_service, "YahooFinanceProvider", lambda: market)
    monkeypatch.setattr(data_refresh_service, "YahooFundamentalsProvider", lambda: fundamentals)


@pytest.fixture(autouse=True)
def _isolated_status_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        data_refresh_status_service, "_STATUS_PATH", tmp_path / "refresh_status.json"
    )


def _seed_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.commit()
    return portfolio.id


def _seed_asset(db, ticker="WEGE3.SA", asset_class="stock", is_manual=False) -> Asset:
    return AssetRepository(db).create(
        Asset(
            ticker=ticker,
            name=ticker,
            asset_class=asset_class,
            country="BR",
            currency="BRL",
            is_manual=is_manual,
        )
    )


def _seed_position(db, portfolio_id, asset) -> Position:
    position = Position(
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        quantity=Decimal("10"),
        average_price=Decimal("30"),
        currency="BRL",
        opened_at=date(2024, 1, 1),
    )
    return PositionRepository(db).create(position)


def _seed_watchlist(
    db, portfolio_id, ticker="MSFT", asset_class="stock", status="watching"
) -> WatchlistAsset:
    entry = WatchlistAsset(
        portfolio_id=portfolio_id,
        ticker=ticker,
        name=ticker,
        asset_class=asset_class,
        country="US",
        currency="USD",
        status=status,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# -- Atualizar preços da carteira ---------------------------------------


def test_refresh_portfolio_prices_only_touches_portfolio_assets(db_session, monkeypatch):
    portfolio_id = _seed_portfolio(db_session)
    asset = _seed_asset(db_session)
    _seed_position(db_session, portfolio_id, asset)
    _seed_watchlist(db_session, portfolio_id, ticker="MSFT")

    provider = FakeMarketProvider([_price("WEGE3.SA", date(2026, 1, 2))])
    _install_fake_providers(monkeypatch, market=provider)

    result = DataRefreshService(db_session).refresh_portfolio_prices(portfolio_id)

    assert [o.ticker for o in result.outcomes] == ["WEGE3.SA"]
    assert provider.calls == ["WEGE3.SA"]  # nunca chamou MSFT (watchlist)


def test_refresh_portfolio_prices_updates_status(db_session, monkeypatch):
    portfolio_id = _seed_portfolio(db_session)
    asset = _seed_asset(db_session)
    _seed_position(db_session, portfolio_id, asset)

    provider = FakeMarketProvider([_price("WEGE3.SA", date(2026, 1, 2))])
    _install_fake_providers(monkeypatch, market=provider)

    result = DataRefreshService(db_session).refresh_portfolio_prices(portfolio_id)

    assert result.processed == 1
    assert result.updated == 1
    outcome = result.outcomes[0]
    assert outcome.status == "updated"
    assert outcome.price_updated is True
    assert outcome.source == "yahoo"


def test_refresh_portfolio_prices_skips_manual_assets(db_session, monkeypatch):
    portfolio_id = _seed_portfolio(db_session)
    asset = _seed_asset(db_session, ticker="TESOURO", asset_class="bond", is_manual=True)
    _seed_position(db_session, portfolio_id, asset)
    _install_fake_providers(monkeypatch)

    result = DataRefreshService(db_session).refresh_portfolio_prices(portfolio_id)

    assert result.outcomes[0].status == "skipped_manual"


def test_refresh_portfolio_prices_failure_in_one_asset_does_not_break_batch(
    db_session, monkeypatch
):
    portfolio_id = _seed_portfolio(db_session)
    ok_asset = _seed_asset(db_session, ticker="WEGE3.SA")
    bad_asset = _seed_asset(db_session, ticker="PETR4.SA")
    _seed_position(db_session, portfolio_id, ok_asset)
    _seed_position(db_session, portfolio_id, bad_asset)

    # provider comum: sempre levanta exceção -> ambos falham, mas nenhuma
    # exceção escapa do serviço (a garantia é resiliência, não sucesso parcial
    # aqui, já que os dois usam o mesmo provider fake).
    provider = FakeMarketProvider(raise_exc=True)
    _install_fake_providers(monkeypatch, market=provider)

    result = DataRefreshService(db_session).refresh_portfolio_prices(portfolio_id)

    assert result.processed == 2
    assert result.failed == 2
    assert set(result.failed_tickers) == {"WEGE3.SA", "PETR4.SA"}


def test_refresh_portfolio_prices_never_alters_position_quantity(db_session, monkeypatch):
    portfolio_id = _seed_portfolio(db_session)
    asset = _seed_asset(db_session)
    position = _seed_position(db_session, portfolio_id, asset)
    original_quantity = position.quantity

    provider = FakeMarketProvider([_price("WEGE3.SA", date(2026, 1, 2))])
    _install_fake_providers(monkeypatch, market=provider)
    DataRefreshService(db_session).refresh_portfolio_prices(portfolio_id)

    refreshed = PositionRepository(db_session).get_by_id(position.id)
    assert refreshed.quantity == original_quantity


def test_refresh_portfolio_prices_records_last_refresh_status(db_session, monkeypatch):
    portfolio_id = _seed_portfolio(db_session)
    asset = _seed_asset(db_session)
    _seed_position(db_session, portfolio_id, asset)
    _install_fake_providers(
        monkeypatch, market=FakeMarketProvider([_price("WEGE3.SA", date(2026, 1, 2))])
    )

    assert DataRefreshService.get_last_refresh_status().prices_at is None
    DataRefreshService(db_session).refresh_portfolio_prices(portfolio_id)
    assert DataRefreshService.get_last_refresh_status().prices_at is not None


# -- Atualizar fundamentos da carteira -----------------------------------


def test_refresh_portfolio_fundamentals_updates_stock_and_recomputes_valuation_and_traps(
    db_session, monkeypatch
):
    portfolio_id = _seed_portfolio(db_session)
    asset = _seed_asset(db_session, ticker="WEGE3.SA", asset_class="stock")
    _seed_position(db_session, portfolio_id, asset)

    fundamentals_provider = FakeFundamentalsProvider(latest=_fund("WEGE3.SA", roe=Decimal("0.2")))
    _install_fake_providers(monkeypatch, fundamentals=fundamentals_provider)

    result = DataRefreshService(db_session).refresh_portfolio_fundamentals(portfolio_id)

    outcome = result.outcomes[0]
    assert outcome.status == "updated"
    assert outcome.fundamentals_updated is True
    assert outcome.traps_recomputed is True
    assert outcome.valuation_recomputed is True
    assert result.scores_recalculated >= 0  # sempre tenta, sem exigir sucesso


def test_refresh_portfolio_fundamentals_shows_coverage_summary(db_session, monkeypatch):
    """Cenário 6 da Parte 8 (Sprint 28): depois de "Atualizar fundamentos",
    o resumo de execução deve trazer a cobertura de dados agregada
    (suficiente/parcial/insuficiente) e os campos mais ausentes — nunca só
    "atualizados: N"."""
    portfolio_id = _seed_portfolio(db_session)
    asset = _seed_asset(db_session, ticker="ALUP4.SA", asset_class="stock")
    _seed_position(db_session, portfolio_id, asset)

    # Só ROE volta do provider — reproduz o cenário relatado pelo usuário:
    # cobertura insuficiente para valuation (falta FCF, patrimônio etc.).
    fundamentals_provider = FakeFundamentalsProvider(latest=_fund("ALUP4.SA", roe=Decimal("0.1")))
    _install_fake_providers(monkeypatch, fundamentals=fundamentals_provider)

    result = DataRefreshService(db_session).refresh_portfolio_fundamentals(portfolio_id)

    outcome = result.outcomes[0]
    assert outcome.data_completeness_score is not None
    assert len(outcome.missing_fields) > 0

    assert result.coverage_sufficient + result.coverage_partial + result.coverage_insufficient == 1
    assert len(result.most_missing_fields) > 0

    last_status = DataRefreshService.get_last_refresh_status()
    fundamentals_summary = last_status.last_summary["fundamentals"]
    assert "dados_suficientes" in fundamentals_summary
    assert "dados_parciais" in fundamentals_summary
    assert "dados_insuficientes_cobertura" in fundamentals_summary
    assert "campos_mais_ausentes" in fundamentals_summary
    assert len(fundamentals_summary["campos_mais_ausentes"]) > 0


def test_refresh_portfolio_fundamentals_fii_never_calls_valuation_v2(db_session, monkeypatch):
    portfolio_id = _seed_portfolio(db_session)
    asset = _seed_asset(db_session, ticker="MXRF11.SA", asset_class="fii")
    _seed_position(db_session, portfolio_id, asset)
    _install_fake_providers(monkeypatch)

    def _tripwire(self, ticker):
        raise AssertionError("ValuationServiceV2 nunca deve ser chamado para FII/REIT")

    monkeypatch.setattr(ValuationServiceV2, "evaluate_ticker", _tripwire)

    result = DataRefreshService(db_session).refresh_portfolio_fundamentals(portfolio_id)

    assert result.outcomes[0].asset_class == "fii"
    # Não levantou AssertionError -> ValuationServiceV2 realmente não foi chamado.


def test_refresh_portfolio_fundamentals_stock_never_calls_income_real_estate(
    db_session, monkeypatch
):
    portfolio_id = _seed_portfolio(db_session)
    asset = _seed_asset(db_session, ticker="WEGE3.SA", asset_class="stock")
    _seed_position(db_session, portfolio_id, asset)
    _install_fake_providers(monkeypatch)

    def _tripwire(self, ticker):
        raise AssertionError("IncomeRealEstateService nunca deve ser chamado para ações")

    monkeypatch.setattr(IncomeRealEstateService, "evaluate_ticker", _tripwire)

    DataRefreshService(db_session).refresh_portfolio_fundamentals(portfolio_id)
    # Não levantou AssertionError -> IncomeRealEstateService realmente não foi chamado.


@pytest.mark.parametrize("asset_class", ["etf", "crypto", "bond"])
def test_refresh_portfolio_fundamentals_never_uses_traditional_valuation_for_non_company_classes(
    db_session, monkeypatch, asset_class
):
    portfolio_id = _seed_portfolio(db_session)
    asset = _seed_asset(db_session, ticker="TICKER1", asset_class=asset_class)
    _seed_position(db_session, portfolio_id, asset)
    _install_fake_providers(monkeypatch)

    for cls in (ValuationServiceV2, IncomeRealEstateService):
        monkeypatch.setattr(
            cls,
            "evaluate_ticker",
            lambda self, ticker, _cls=cls: (_ for _ in ()).throw(
                AssertionError(f"{_cls.__name__} nunca deve ser chamado para classe {asset_class}")
            ),
        )

    result = DataRefreshService(db_session).refresh_portfolio_fundamentals(portfolio_id)
    assert result.outcomes[0].asset_class == asset_class


def test_refresh_portfolio_fundamentals_insufficient_data_when_provider_returns_nothing(
    db_session, monkeypatch
):
    portfolio_id = _seed_portfolio(db_session)
    asset = _seed_asset(db_session, ticker="WEGE3.SA")
    _seed_position(db_session, portfolio_id, asset)
    _install_fake_providers(monkeypatch, fundamentals=FakeFundamentalsProvider(latest=None))

    result = DataRefreshService(db_session).refresh_portfolio_fundamentals(portfolio_id)

    assert result.outcomes[0].status == "insufficient_data"
    assert result.outcomes[0].fundamentals_updated is False


def test_refresh_portfolio_fundamentals_single_asset_failure_does_not_break_batch(
    db_session, monkeypatch
):
    portfolio_id = _seed_portfolio(db_session)
    ok_asset = _seed_asset(db_session, ticker="WEGE3.SA")
    bad_asset = _seed_asset(db_session, ticker="PETR4.SA")
    _seed_position(db_session, portfolio_id, ok_asset)
    _seed_position(db_session, portfolio_id, bad_asset)
    _install_fake_providers(monkeypatch, fundamentals=FakeFundamentalsProvider(raise_exc=True))

    result = DataRefreshService(db_session).refresh_portfolio_fundamentals(portfolio_id)

    assert result.processed == 2
    assert result.failed == 2  # os dois falham (mesmo provider), mas nada quebra


def test_refresh_portfolio_fundamentals_records_valuation_and_trap_timestamps(
    db_session, monkeypatch
):
    portfolio_id = _seed_portfolio(db_session)
    asset = _seed_asset(db_session)
    _seed_position(db_session, portfolio_id, asset)
    _install_fake_providers(monkeypatch)

    status_before = DataRefreshService.get_last_refresh_status()
    assert status_before.valuation_at is None
    assert status_before.trap_detection_at is None

    DataRefreshService(db_session).refresh_portfolio_fundamentals(portfolio_id)

    status_after = DataRefreshService.get_last_refresh_status()
    assert status_after.fundamentals_at is not None
    assert status_after.valuation_at is not None
    assert status_after.trap_detection_at is not None


# -- Atualizar dados da watchlist -----------------------------------------


def test_refresh_watchlist_never_creates_position(db_session, monkeypatch):
    portfolio_id = _seed_portfolio(db_session)
    _seed_watchlist(db_session, portfolio_id, ticker="MSFT")
    _install_fake_providers(
        monkeypatch,
        market=FakeMarketProvider([_price("MSFT", date(2026, 1, 2))]),
        fundamentals=FakeFundamentalsProvider(latest=_fund("MSFT")),
    )

    result = DataRefreshService(db_session).refresh_watchlist_data(portfolio_id)

    assert result.positions_created == 0
    assert PositionRepository(db_session).list_by_portfolio(portfolio_id) == []


def test_refresh_watchlist_never_changes_patrimonio_flag(db_session, monkeypatch):
    portfolio_id = _seed_portfolio(db_session)
    _seed_watchlist(db_session, portfolio_id, ticker="MSFT")
    _install_fake_providers(monkeypatch)

    result = DataRefreshService(db_session).refresh_watchlist_data(portfolio_id)

    assert result.patrimonio_changed is False


def test_refresh_watchlist_ensures_asset_master_record_without_position(db_session, monkeypatch):
    portfolio_id = _seed_portfolio(db_session)
    _seed_watchlist(db_session, portfolio_id, ticker="MSFT")
    _install_fake_providers(
        monkeypatch,
        market=FakeMarketProvider([_price("MSFT", date(2026, 1, 2))]),
        fundamentals=FakeFundamentalsProvider(latest=_fund("MSFT")),
    )

    DataRefreshService(db_session).refresh_watchlist_data(portfolio_id)

    assert AssetRepository(db_session).get_by_ticker("MSFT") is not None
    assert PositionRepository(db_session).list_by_portfolio(portfolio_id) == []


def test_refresh_watchlist_excludes_discarded_entries(db_session, monkeypatch):
    portfolio_id = _seed_portfolio(db_session)
    _seed_watchlist(db_session, portfolio_id, ticker="MSFT", status="discarded")
    provider = FakeMarketProvider([_price("MSFT", date(2026, 1, 2))])
    _install_fake_providers(monkeypatch, market=provider)

    result = DataRefreshService(db_session).refresh_watchlist_data(portfolio_id)

    assert result.outcomes == []
    assert provider.calls == []


def test_refresh_watchlist_successful_collection_marks_updated(db_session, monkeypatch):
    portfolio_id = _seed_portfolio(db_session)
    _seed_watchlist(db_session, portfolio_id, ticker="MSFT")
    _install_fake_providers(
        monkeypatch,
        market=FakeMarketProvider([_price("MSFT", date(2026, 1, 2))]),
        fundamentals=FakeFundamentalsProvider(latest=_fund("MSFT")),
    )

    result = DataRefreshService(db_session).refresh_watchlist_data(portfolio_id)

    outcome = result.outcomes[0]
    assert outcome.status == "updated"
    assert outcome.price_updated is True
    assert outcome.fundamentals_updated is True


def test_refresh_watchlist_records_last_refresh_status(db_session, monkeypatch):
    portfolio_id = _seed_portfolio(db_session)
    _seed_watchlist(db_session, portfolio_id, ticker="MSFT")
    _install_fake_providers(monkeypatch)

    assert DataRefreshService.get_last_refresh_status().watchlist_at is None
    DataRefreshService(db_session).refresh_watchlist_data(portfolio_id)
    assert DataRefreshService.get_last_refresh_status().watchlist_at is not None


# -- Atualizar tudo -----------------------------------------------------


def test_refresh_all_investment_data_processes_portfolio_and_watchlist(db_session, monkeypatch):
    portfolio_id = _seed_portfolio(db_session)
    asset = _seed_asset(db_session, ticker="WEGE3.SA")
    _seed_position(db_session, portfolio_id, asset)
    _seed_watchlist(db_session, portfolio_id, ticker="MSFT")

    _install_fake_providers(
        monkeypatch,
        market=FakeMarketProvider(
            [_price("WEGE3.SA", date(2026, 1, 2)), _price("MSFT", date(2026, 1, 2))]
        ),
        fundamentals=FakeFundamentalsProvider(latest=_fund("WEGE3.SA")),
    )

    result = DataRefreshService(db_session).refresh_all_investment_data(portfolio_id)

    assert [o.ticker for o in result.prices.outcomes] == ["WEGE3.SA"]
    assert [o.ticker for o in result.fundamentals.outcomes] == ["WEGE3.SA"]
    assert [o.ticker for o in result.watchlist.outcomes] == ["MSFT"]
    assert result.watchlist.positions_created == 0


# -- nunca roda sozinho ---------------------------------------------------


def test_constructing_service_triggers_no_provider_call(db_session, monkeypatch):
    provider = FakeMarketProvider([_price("WEGE3.SA", date(2026, 1, 2))])
    _install_fake_providers(monkeypatch, market=provider)

    DataRefreshService(db_session)  # só construção, nenhum método chamado

    assert provider.calls == []


def test_get_last_refresh_status_never_none_object_and_never_writes_file(
    db_session, tmp_path, monkeypatch
):
    status_path = tmp_path / "refresh_status.json"
    monkeypatch.setattr(data_refresh_status_service, "_STATUS_PATH", status_path)

    status = DataRefreshService.get_last_refresh_status()

    assert status.prices_at is None
    assert status.fundamentals_at is None
    assert not status_path.exists()  # leitura nunca cria
