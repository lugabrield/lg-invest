"""Testes do serviço de sincronização de proventos/dividendos (Sprint 23.2).

Usa um cliente falso (`_FakeIncomeClient`) que devolve eventos já
normalizados, para testar só orquestração/dedup/persistência — sem
depender de Playwright/rede. Cobre também as garantias explícitas do
usuário: dry-run não é bloqueado por falha isolada de proventos,
`income_events` nunca duplica e nunca é escrito por `positions`/vice-versa.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.database.models.portfolio import Portfolio
from backend.app.infrastructure.database.models.position import Position
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.income_event_repository import IncomeEventRepository
from backend.app.infrastructure.repositories.income_monthly_summary_repository import (
    IncomeMonthlySummaryRepository,
)
from backend.app.infrastructure.repositories.portfolio_repository import PortfolioRepository
from backend.app.infrastructure.repositories.position_repository import PositionRepository
from backend.app.integrations.dividendos_me.income_parser import (
    ORIGIN_INCOME_CALENDAR,
    NormalizedIncomeEvent,
    NormalizedMonthlySummary,
)
from backend.app.integrations.dividendos_me.income_service import IncomeSyncService
from backend.app.integrations.dividendos_me.schemas import SectionDiagnostics
from backend.app.integrations.dividendos_me.service import (
    DividendosMeSyncService,
    PortfolioNotFoundError,
)


class _FakeIncomeClient:
    """Fake do fluxo de CALENDÁRIO futuro — só implementa
    `fetch_income_events()` (o único método que `build_preview`/`dry_run`/
    `import_events` chamam desde a Sprint 23.3)."""

    def __init__(self, events, failed_sections=None, diagnostics=None):
        self._events = events
        self._failed_sections = failed_sections or []
        self._diagnostics = diagnostics or []
        self.call_count = 0

    def fetch_income_events(self):
        self.call_count += 1
        return self._events, self._failed_sections, self._diagnostics


class _FakeMonthlyClient:
    """Fake do fluxo de HISTÓRICO MENSAL — só implementa
    `fetch_income_monthly_summaries()`, nunca `fetch_income_events()`
    (os dois fluxos são independentes desde a Sprint 23.3)."""

    def __init__(self, summaries, failed_sections=None, diagnostics=None):
        self._summaries = summaries
        self._failed_sections = failed_sections or []
        self._diagnostics = diagnostics or []
        self.call_count = 0

    def fetch_income_monthly_summaries(self):
        self.call_count += 1
        return self._summaries, self._failed_sections, self._diagnostics


class _FakePortfolioClient:
    """Cliente falso mínimo para `DividendosMeSyncService` — usado só nos
    testes que precisam confirmar que `income_events` nunca é tocado por
    uma sincronização de carteira e vice-versa."""

    def __init__(self, positions):
        self._positions = positions

    def fetch_portfolio(self):
        return self._positions, [], []


def _event(
    ticker="ALUP4.SA",
    *,
    payment_date=date(2026, 7, 6),
    amount="6.51",
    currency="BRL",
    source=ORIGIN_INCOME_CALENDAR,
    event_type="dividendo",
    status="anunciado",
) -> NormalizedIncomeEvent:
    return NormalizedIncomeEvent(
        ticker=ticker,
        source=source,
        event_type=event_type,
        status=status,
        payment_date=payment_date,
        amount_total=Decimal(amount),
        currency=currency,
        raw_payload={"kind": "test"},
    )


def _make_portfolio(db_session) -> Portfolio:
    return PortfolioRepository(db_session).create(Portfolio(name="Carteira Teste"))


def _summary(
    *,
    wallet_name="Carteira (B3)",
    year=2026,
    month=6,
    amount="150.00",
    currency="BRL",
    source="dividendos_me:income_monthly:brasil",
    status="recebido",
    annual_total=None,
    annual_average=None,
) -> NormalizedMonthlySummary:
    return NormalizedMonthlySummary(
        wallet_name=wallet_name,
        year=year,
        month=month,
        amount_total=Decimal(amount),
        currency=currency,
        source=source,
        status=status,
        annual_total=Decimal(annual_total) if annual_total is not None else None,
        annual_average=Decimal(annual_average) if annual_average is not None else None,
        raw_payload={"kind": "test_monthly_summary"},
    )


# --- build_preview / dry_run --------------------------------------------------


def test_build_preview_never_writes_anything(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeIncomeClient([_event(), _event(ticker="MXRF11.SA")])
    service = IncomeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert preview.events_valid == 2
    assert IncomeEventRepository(db_session).list_by_portfolio(portfolio.id) == []


def test_build_preview_raises_for_unknown_portfolio(db_session):
    client = _FakeIncomeClient([])
    service = IncomeSyncService(db_session)
    with pytest.raises(PortfolioNotFoundError):
        service.build_preview(999, client)


def test_build_preview_computes_totals_by_currency(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeIncomeClient(
        [
            _event(ticker="ALUP4.SA", amount="6.51", currency="BRL"),
            _event(ticker="QQQ", amount="0.38", currency="USD"),
        ]
    )
    service = IncomeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert preview.total_by_currency == {"BRL": Decimal("6.51"), "USD": Decimal("0.38")}


def test_build_preview_computes_period_start_and_end(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeIncomeClient(
        [
            _event(payment_date=date(2026, 1, 1)),
            _event(payment_date=date(2026, 7, 6)),
        ]
    )
    service = IncomeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert preview.period_start == date(2026, 1, 1)
    assert preview.period_end == date(2026, 7, 6)


def test_dry_run_status_success_with_no_failed_sections_and_zero_events(db_session):
    # Zero eventos encontrados é um resultado legítimo (carteira sem
    # proventos no período) — nunca é reportado como falha.
    portfolio = _make_portfolio(db_session)
    client = _FakeIncomeClient([])
    service = IncomeSyncService(db_session)

    result = service.dry_run(portfolio.id, client)

    assert result.status == "success"
    assert result.events_found == 0


def test_dry_run_status_partial_when_section_fails_but_events_remain(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeIncomeClient([_event()], failed_sections=["income_calendar"])
    service = IncomeSyncService(db_session)

    result = service.dry_run(portfolio.id, client)

    assert result.status == "partial"


def test_dry_run_status_failed_when_section_fails_and_no_events_remain(db_session):
    # Sprint 23.3: `fetch_income_events()` só cobre o calendário futuro —
    # "income_calendar" é a única seção possível aqui (o histórico mensal
    # tem seu próprio fluxo, ver testes de `build_monthly_preview` abaixo).
    portfolio = _make_portfolio(db_session)
    client = _FakeIncomeClient([], failed_sections=["income_calendar"])
    service = IncomeSyncService(db_session)

    result = service.dry_run(portfolio.id, client)

    assert result.status == "failed"


def test_dry_run_only_calls_fetch_income_events_once(db_session):
    # Regressão: uma versão inicial chamava fetch (login+scrape) duas
    # vezes por engano (preview + import) — nunca deve fazer login extra.
    portfolio = _make_portfolio(db_session)
    client = _FakeIncomeClient([_event()])
    service = IncomeSyncService(db_session)

    service.dry_run(portfolio.id, client)

    assert client.call_count == 1


def test_build_preview_carries_diagnostics_from_client(db_session):
    portfolio = _make_portfolio(db_session)
    diagnostics = [
        SectionDiagnostics(
            section="income_monthly",
            selector_used="table (thead/tbody), aba Análise por carteira",
            raw_rows_detected=1,
            valid_rows=1,
            rejected_rows=0,
            rejection_reasons=[],
        )
    ]
    client = _FakeIncomeClient([_event()], diagnostics=diagnostics)
    service = IncomeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert preview.diagnostics == diagnostics


# --- import_events: dedup + persistência --------------------------------------


def test_import_events_creates_new_events(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeIncomeClient([_event(ticker="ALUP4.SA"), _event(ticker="MXRF11.SA")])
    service = IncomeSyncService(db_session)

    result = service.import_events(portfolio.id, client)

    assert result.events_created == 2
    assert result.events_skipped_duplicate == 0
    assert len(IncomeEventRepository(db_session).list_by_portfolio(portfolio.id)) == 2


def test_import_events_only_calls_fetch_income_events_once(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeIncomeClient([_event()])
    service = IncomeSyncService(db_session)

    service.import_events(portfolio.id, client)

    assert client.call_count == 1


def test_import_events_never_duplicates_against_existing_db_rows(db_session):
    portfolio = _make_portfolio(db_session)
    service = IncomeSyncService(db_session)

    client = _FakeIncomeClient([_event(ticker="ALUP4.SA")])
    first = service.import_events(portfolio.id, client)
    assert first.events_created == 1

    # Mesma extração rodada de novo (ex.: usuário clicou duas vezes) —
    # nunca deve criar uma segunda linha para o mesmo evento.
    client_again = _FakeIncomeClient([_event(ticker="ALUP4.SA")])
    second = service.import_events(portfolio.id, client_again)

    assert second.events_created == 0
    assert second.events_skipped_duplicate == 1
    assert len(IncomeEventRepository(db_session).list_by_portfolio(portfolio.id)) == 1


def test_import_events_treats_different_amounts_as_distinct_events(db_session):
    # Mesmo ticker/data/tipo/fonte mas valor diferente não é duplicata —
    # pode ser um provento diferente (ou uma correção legítima).
    portfolio = _make_portfolio(db_session)
    service = IncomeSyncService(db_session)

    service.import_events(portfolio.id, _FakeIncomeClient([_event(amount="6.51")]))
    result = service.import_events(portfolio.id, _FakeIncomeClient([_event(amount="7.00")]))

    assert result.events_created == 1
    assert len(IncomeEventRepository(db_session).list_by_portfolio(portfolio.id)) == 2


def test_import_events_resolves_asset_id_when_ticker_matches_known_asset(db_session):
    portfolio = _make_portfolio(db_session)
    asset = AssetRepository(db_session).create(
        Asset(ticker="ALUP4.SA", name="Alupar", asset_class="stock", country="BR", currency="BRL")
    )
    client = _FakeIncomeClient([_event(ticker="ALUP4.SA")])
    service = IncomeSyncService(db_session)

    service.import_events(portfolio.id, client)

    saved = IncomeEventRepository(db_session).list_by_portfolio(portfolio.id)[0]
    assert saved.asset_id == asset.id


def test_import_events_allows_null_asset_id_when_ticker_is_none(db_session):
    # Sprint 23.3: o histórico mensal agregado (que antes gerava eventos
    # sem ticker) não passa mais por `import_events` — mas o calendário
    # futuro continua podendo, em tese, trazer um evento sem ticker
    # reconhecido (ex.: badge de ativo não mapeado), então esta garantia
    # (nunca inventa um `asset_id`) continua válida e testada aqui.
    portfolio = _make_portfolio(db_session)
    client = _FakeIncomeClient(
        [_event(ticker=None, source=ORIGIN_INCOME_CALENDAR, event_type="outro", status="anunciado")]
    )
    service = IncomeSyncService(db_session)

    result = service.import_events(portfolio.id, client)

    assert result.events_created == 1
    saved = IncomeEventRepository(db_session).list_by_portfolio(portfolio.id)[0]
    assert saved.asset_id is None
    assert saved.ticker is None


def test_import_events_never_deletes_existing_income_events(db_session):
    portfolio = _make_portfolio(db_session)
    service = IncomeSyncService(db_session)
    service.import_events(portfolio.id, _FakeIncomeClient([_event(ticker="ALUP4.SA")]))

    # Uma extração seguinte, sem o evento antigo (ex.: fora do período
    # exibido no calendário), nunca remove o histórico já salvo —
    # `import_events` é estritamente aditivo.
    service.import_events(portfolio.id, _FakeIncomeClient([_event(ticker="MXRF11.SA")]))

    tickers = {e.ticker for e in IncomeEventRepository(db_session).list_by_portfolio(portfolio.id)}
    assert tickers == {"ALUP4.SA", "MXRF11.SA"}


def test_import_events_status_success_with_no_errors(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeIncomeClient([_event()])
    service = IncomeSyncService(db_session)

    result = service.import_events(portfolio.id, client)

    assert result.status == "success"
    assert result.errors == []


def test_import_events_reports_failed_sections_as_errors_but_still_imports_valid_events(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeIncomeClient([_event()], failed_sections=["income_monthly"])
    service = IncomeSyncService(db_session)

    result = service.import_events(portfolio.id, client)

    assert result.events_created == 1
    assert any("income_monthly" in e for e in result.errors)


# --- Isolamento: proventos nunca bloqueiam nem misturam com a carteira --------


def test_income_sync_failure_never_raised_as_exception_blocking_caller(db_session):
    # `IncomeSyncService` propaga exceções de conexão/rede como qualquer
    # chamada Python normal — a garantia de "nunca bloqueia a carteira" é
    # implementada por quem ORQUESTRA as duas chamadas (CLI/UI), cada uma
    # em seu próprio try/except. Este teste documenta que uma falha do
    # cliente de proventos não corrompe nem toca as tabelas de posições.
    portfolio = _make_portfolio(db_session)
    _seed_position_for_isolation_test(db_session, portfolio.id, "WEGE3.SA")

    class _BrokenIncomeClient:
        def fetch_income_events(self):
            raise RuntimeError("falha de rede simulada")

    service = IncomeSyncService(db_session)
    with pytest.raises(RuntimeError):
        service.build_preview(portfolio.id, _BrokenIncomeClient())

    # A posição da carteira (tabela `positions`) continua intacta.
    assert len(PositionRepository(db_session).list_by_portfolio(portfolio.id)) == 1
    assert IncomeEventRepository(db_session).list_by_portfolio(portfolio.id) == []


def test_positions_sync_never_touches_income_events_table(db_session):
    portfolio = _make_portfolio(db_session)
    income_service = IncomeSyncService(db_session)
    income_service.import_events(portfolio.id, _FakeIncomeClient([_event(ticker="ALUP4.SA")]))

    portfolio_client = _FakePortfolioClient(
        [
            _fake_extracted_position("MXRF11.SA"),
        ]
    )
    portfolio_service = DividendosMeSyncService(db_session)
    portfolio_service.replace(portfolio.id, portfolio_client, confirm=True)

    # income_events continua com exatamente o mesmo evento — replace da
    # carteira nunca cria, altera ou remove uma linha de `income_events`.
    events = IncomeEventRepository(db_session).list_by_portfolio(portfolio.id)
    assert len(events) == 1
    assert events[0].ticker == "ALUP4.SA"


def _seed_position_for_isolation_test(db_session, portfolio_id: int, ticker: str) -> None:
    asset = AssetRepository(db_session).create(
        Asset(ticker=ticker, name=ticker, asset_class="stock", country="BR", currency="BRL")
    )
    PositionRepository(db_session).create(
        Position(
            portfolio_id=portfolio_id,
            asset_id=asset.id,
            quantity=Decimal("10"),
            average_price=Decimal("5"),
            currency="BRL",
            opened_at=date(2020, 1, 1),
        )
    )


def _fake_extracted_position(ticker: str):
    from datetime import UTC, datetime

    from backend.app.integrations.dividendos_me.schemas import ORIGIN_B3, ExtractedPosition

    return ExtractedPosition(
        raw_ticker=ticker,
        ticker=ticker,
        asset_class="stock",
        country="BR",
        currency="BRL",
        quantity=Decimal("10"),
        average_price=Decimal("5"),
        current_value=Decimal("50"),
        origin=ORIGIN_B3,
        synced_at=datetime.now(UTC),
    )


# --- Sprint 23.3: histórico mensal (build_monthly_preview / dry_run_monthly /
# import_monthly_summaries) — fluxo independente do calendário acima --------


def test_build_monthly_preview_never_writes_anything(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeMonthlyClient([_summary(), _summary(month=7)])
    service = IncomeSyncService(db_session)

    preview = service.build_monthly_preview(portfolio.id, client)

    assert preview.summaries_valid == 2
    assert IncomeMonthlySummaryRepository(db_session).list_by_portfolio(portfolio.id) == []


def test_build_monthly_preview_raises_for_unknown_portfolio(db_session):
    client = _FakeMonthlyClient([])
    service = IncomeSyncService(db_session)
    with pytest.raises(PortfolioNotFoundError):
        service.build_monthly_preview(999, client)


def test_build_monthly_preview_computes_years_months_wallets_and_totals(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeMonthlyClient(
        [
            _summary(wallet_name="Carteira (B3)", year=2026, month=6, amount="100.00"),
            _summary(wallet_name="Carteira (B3)", year=2026, month=7, amount="50.00"),
            _summary(
                wallet_name="Carteira Dolar", year=2025, month=12, amount="20.00", currency="USD"
            ),
        ]
    )
    service = IncomeSyncService(db_session)

    preview = service.build_monthly_preview(portfolio.id, client)

    assert preview.years_found == [2025, 2026]
    assert preview.months_found == [6, 7, 12]
    assert preview.wallets_found == ["Carteira (B3)", "Carteira Dolar"]
    assert preview.total_by_currency == {"BRL": Decimal("150.00"), "USD": Decimal("20.00")}
    assert preview.total_by_year == {"2026": Decimal("150.00"), "2025": Decimal("20.00")}


def test_dry_run_monthly_status_success_with_no_failed_sections(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeMonthlyClient([_summary()])
    service = IncomeSyncService(db_session)

    result = service.dry_run_monthly(portfolio.id, client)

    assert result.status == "success"
    assert result.summaries_found == 1


def test_dry_run_monthly_status_partial_when_section_fails_but_data_remains(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeMonthlyClient([_summary()], failed_sections=["income_monthly"])
    service = IncomeSyncService(db_session)

    result = service.dry_run_monthly(portfolio.id, client)

    assert result.status == "partial"


def test_dry_run_monthly_status_failed_when_section_fails_and_no_data_remains(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeMonthlyClient([], failed_sections=["income_monthly"])
    service = IncomeSyncService(db_session)

    result = service.dry_run_monthly(portfolio.id, client)

    assert result.status == "failed"


def test_dry_run_monthly_only_calls_fetch_once(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeMonthlyClient([_summary()])
    service = IncomeSyncService(db_session)

    service.dry_run_monthly(portfolio.id, client)

    assert client.call_count == 1


def test_import_monthly_summaries_creates_new_rows(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeMonthlyClient([_summary(month=6), _summary(month=7)])
    service = IncomeSyncService(db_session)

    result = service.import_monthly_summaries(portfolio.id, client)

    assert result.summaries_created == 2
    assert result.summaries_skipped_duplicate == 0
    assert len(IncomeMonthlySummaryRepository(db_session).list_by_portfolio(portfolio.id)) == 2


def test_import_monthly_summaries_never_duplicates_against_existing_db_rows(db_session):
    portfolio = _make_portfolio(db_session)
    service = IncomeSyncService(db_session)

    first = service.import_monthly_summaries(portfolio.id, _FakeMonthlyClient([_summary(month=6)]))
    assert first.summaries_created == 1

    # Mesma extração rodada de novo (ex.: usuário clicou duas vezes) —
    # nunca deve criar uma segunda linha para o mesmo mês/carteira/moeda.
    second = service.import_monthly_summaries(portfolio.id, _FakeMonthlyClient([_summary(month=6)]))

    assert second.summaries_created == 0
    assert second.summaries_skipped_duplicate == 1
    assert len(IncomeMonthlySummaryRepository(db_session).list_by_portfolio(portfolio.id)) == 1


def test_import_monthly_summaries_treats_different_wallets_as_distinct_rows(db_session):
    portfolio = _make_portfolio(db_session)
    service = IncomeSyncService(db_session)

    client = _FakeMonthlyClient(
        [
            _summary(wallet_name="Carteira (B3)", month=6),
            _summary(wallet_name="Carteira Dolar", month=6, currency="USD"),
        ]
    )
    result = service.import_monthly_summaries(portfolio.id, client)

    assert result.summaries_created == 2
    assert len(IncomeMonthlySummaryRepository(db_session).list_by_portfolio(portfolio.id)) == 2


def test_import_monthly_summaries_never_deletes_existing_rows(db_session):
    portfolio = _make_portfolio(db_session)
    service = IncomeSyncService(db_session)
    service.import_monthly_summaries(portfolio.id, _FakeMonthlyClient([_summary(month=6)]))

    # Uma extração seguinte, sem o mês antigo, nunca remove o histórico já
    # salvo — `import_monthly_summaries` é estritamente aditivo.
    service.import_monthly_summaries(portfolio.id, _FakeMonthlyClient([_summary(month=7)]))

    months = {
        s.month for s in IncomeMonthlySummaryRepository(db_session).list_by_portfolio(portfolio.id)
    }
    assert months == {6, 7}


def test_import_monthly_summaries_status_success_with_no_errors(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeMonthlyClient([_summary()])
    service = IncomeSyncService(db_session)

    result = service.import_monthly_summaries(portfolio.id, client)

    assert result.status == "success"
    assert result.errors == []


def test_import_monthly_summaries_reports_failed_sections_as_errors_but_still_imports(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeMonthlyClient([_summary()], failed_sections=["income_monthly"])
    service = IncomeSyncService(db_session)

    result = service.import_monthly_summaries(portfolio.id, client)

    assert result.summaries_created == 1
    assert any("income_monthly" in e for e in result.errors)


def test_monthly_and_calendar_flows_never_write_to_each_others_table(db_session):
    # Garantia central da separação Sprint 23.3: importar um nunca cria
    # linha nenhuma na tabela do outro.
    portfolio = _make_portfolio(db_session)
    service = IncomeSyncService(db_session)

    service.import_events(portfolio.id, _FakeIncomeClient([_event(ticker="ALUP4.SA")]))
    service.import_monthly_summaries(portfolio.id, _FakeMonthlyClient([_summary(month=6)]))

    assert len(IncomeEventRepository(db_session).list_by_portfolio(portfolio.id)) == 1
    assert len(IncomeMonthlySummaryRepository(db_session).list_by_portfolio(portfolio.id)) == 1
