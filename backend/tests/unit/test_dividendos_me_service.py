"""Testes do serviço de sincronização com o Dividendos.me (Sprint 23 / 23.1).

Usa um cliente falso (`_FakeClient`) que devolve posições já
normalizadas, para testar só a orquestração/gravação no banco — sem
depender de Playwright/rede.

Sprint 23.1 acrescentou as checagens de segurança obrigatórias (nunca
substituir com extração quebrada/incompleta) e o cálculo de status
success/partial/failed do preview — a maior parte dos novos testes
neste arquivo cobre exatamente essas regras.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.database.models.portfolio import Portfolio
from backend.app.infrastructure.database.models.position import Position
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.portfolio_repository import PortfolioRepository
from backend.app.infrastructure.repositories.position_repository import PositionRepository
from backend.app.integrations.dividendos_me.schemas import (
    ORIGIN_B3,
    ORIGIN_CRYPTO,
    ORIGIN_INTERNATIONAL,
    ExtractedPosition,
    SectionDiagnostics,
)
from backend.app.integrations.dividendos_me.service import (
    EXTRACTION_INCOMPLETE_SECTIONS_MESSAGE,
    DividendosMeSyncService,
    ExtractionInvalidError,
    PortfolioNotFoundError,
    SyncConfirmationRequiredError,
    _apply_btc_fallback,
    _consolidate_positions,
    _CurrentPosition,
    _expected_sections_from_current,
    extraction_blocking_reasons,
    has_section_gap,
    strong_alert_sections,
)


class _FakeClient:
    def __init__(self, positions, failed_sections=None, diagnostics=None):
        self._positions = positions
        self._failed_sections = failed_sections or []
        self._diagnostics = diagnostics or []

    def fetch_portfolio(self):
        return self._positions, self._failed_sections, self._diagnostics


def _extracted(
    ticker,
    *,
    quantity="10",
    average_price="100.00",
    current_value="1000.00",
    origin=ORIGIN_B3,
    asset_class="stock",
    currency="BRL",
    country="BR",
    review_required=False,
    review_reason=None,
    is_manual=False,
    section="brasil",
) -> ExtractedPosition:
    return ExtractedPosition(
        raw_ticker=ticker,
        ticker=ticker,
        asset_class=asset_class,
        country=country,
        currency=currency,
        is_manual=is_manual,
        review_required=review_required,
        review_reason=review_reason,
        section=section,
        quantity=Decimal(quantity),
        average_price=Decimal(average_price) if average_price is not None else None,
        current_value=Decimal(current_value) if current_value is not None else None,
        origin=origin,
        synced_at=datetime.now(UTC),
    )


def _make_portfolio(db_session) -> Portfolio:
    return PortfolioRepository(db_session).create(Portfolio(name="Carteira Teste"))


def _seed_position(db_session, portfolio_id: int, ticker: str) -> None:
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


def _seed_old_position(db_session, portfolio_id: int, ticker: str = "OLDX3.SA") -> None:
    _seed_position(db_session, portfolio_id, ticker)


def _seed_asset_position(
    db_session,
    portfolio_id: int,
    ticker: str,
    *,
    asset_class: str = "stock",
    country: str = "BR",
    currency: str = "BRL",
) -> None:
    """Igual a `_seed_position`, mas permite escolher `asset_class`/`country`
    — necessário para os testes Sprint 23.3 de "seções esperadas" (EUA,
    Criptomoedas, Renda Fixa), que dependem da classe/país do ativo já
    presente na carteira atual."""
    asset = AssetRepository(db_session).create(
        Asset(
            ticker=ticker, name=ticker, asset_class=asset_class, country=country, currency=currency
        )
    )
    PositionRepository(db_session).create(
        Position(
            portfolio_id=portfolio_id,
            asset_id=asset.id,
            quantity=Decimal("10"),
            average_price=Decimal("5"),
            currency=currency,
            opened_at=date(2020, 1, 1),
        )
    )


def test_dry_run_never_writes_anything(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeClient([_extracted("WEGE3.SA"), _extracted("MXRF11.SA", asset_class="fii")])
    service = DividendosMeSyncService(db_session)

    result = service.dry_run(portfolio.id, client)

    assert result.status == "success"
    assert result.mode == "dry-run"
    assert result.preview.total_assets == 2
    assert PositionRepository(db_session).list_by_portfolio(portfolio.id) == []
    assert AssetRepository(db_session).get_by_ticker("WEGE3.SA") is None


def test_dry_run_raises_for_unknown_portfolio(db_session):
    client = _FakeClient([])
    service = DividendosMeSyncService(db_session)
    with pytest.raises(PortfolioNotFoundError):
        service.dry_run(999, client)


def test_replace_requires_explicit_confirmation(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeClient([_extracted("WEGE3.SA"), _extracted("MXRF11.SA")])
    service = DividendosMeSyncService(db_session)

    with pytest.raises(SyncConfirmationRequiredError):
        service.replace(portfolio.id, client, confirm=False)

    # Nada foi gravado.
    assert PositionRepository(db_session).list_by_portfolio(portfolio.id) == []


def test_update_requires_explicit_confirmation(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeClient([_extracted("WEGE3.SA"), _extracted("MXRF11.SA")])
    service = DividendosMeSyncService(db_session)

    with pytest.raises(SyncConfirmationRequiredError):
        service.update(portfolio.id, client, confirm=False)


def test_replace_creates_new_asset_and_position(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeClient(
        [
            _extracted("WEGE3.SA", quantity="50", average_price="30.00", origin=ORIGIN_B3),
            _extracted("MXRF11.SA", asset_class="fii"),
        ]
    )
    service = DividendosMeSyncService(db_session)

    result = service.replace(portfolio.id, client, confirm=True)

    assert result.status == "success"
    assert result.positions_created == 2
    asset = AssetRepository(db_session).get_by_ticker("WEGE3.SA")
    assert asset is not None
    positions = PositionRepository(db_session).list_by_portfolio(portfolio.id)
    assert len(positions) == 2
    wege = next(p for p in positions if p.asset_id == asset.id)
    assert wege.quantity == Decimal("50")
    assert wege.source == ORIGIN_B3


def test_replace_removes_positions_missing_from_source(db_session):
    portfolio = _make_portfolio(db_session)
    # Carteira atual com 2 posições; a extração só traz 1 de volta (50% —
    # não dispara o bloqueio de >50%, que exige estritamente mais da metade).
    _seed_old_position(db_session, portfolio.id, ticker="OLDX3.SA")
    _seed_old_position(db_session, portfolio.id, ticker="WEGE3.SA")
    client = _FakeClient([_extracted("WEGE3.SA"), _extracted("MXRF11.SA")])
    service = DividendosMeSyncService(db_session)

    result = service.replace(portfolio.id, client, confirm=True)

    assert result.positions_removed == 1
    tickers = {
        p.asset.ticker for p in PositionRepository(db_session).list_by_portfolio(portfolio.id)
    }
    assert "OLDX3.SA" not in tickers
    assert "WEGE3.SA" in tickers


def test_update_mode_keeps_positions_missing_from_source(db_session):
    portfolio = _make_portfolio(db_session)
    _seed_old_position(db_session, portfolio.id, ticker="OLDX3.SA")
    _seed_old_position(db_session, portfolio.id, ticker="WEGE3.SA")
    client = _FakeClient([_extracted("WEGE3.SA"), _extracted("MXRF11.SA")])
    service = DividendosMeSyncService(db_session)

    result = service.update(portfolio.id, client, confirm=True)

    assert result.positions_removed == 0
    tickers = {
        p.asset.ticker for p in PositionRepository(db_session).list_by_portfolio(portfolio.id)
    }
    assert "OLDX3.SA" in tickers
    assert "WEGE3.SA" in tickers


def test_review_required_positions_are_never_written(db_session):
    # Ticker não-vazio ("???", ex.: subgrupo não reconhecido) marcado para
    # revisão manual: não dispara o bloqueio de segurança (que é
    # especificamente para ticker VAZIO), mas ainda assim nunca é
    # escrito no banco.
    portfolio = _make_portfolio(db_session)
    client = _FakeClient(
        [
            _extracted("???", review_required=True, review_reason="ticker vazio"),
            _extracted("MXRF11.SA"),
        ]
    )
    service = DividendosMeSyncService(db_session)

    result = service.replace(portfolio.id, client, confirm=True)

    assert result.positions_created == 1
    assert any("ticker vazio" in e for e in result.errors)


def test_review_required_empty_ticker_blocks_replace_even_with_valid_assets(db_session):
    # Diferente do teste acima: aqui o TICKER em si vem vazio (não só o
    # motivo mencionando "vazio") — isso é sempre bloqueado, mesmo com
    # outros ativos válidos na mesma extração (Prioridade 1 do usuário).
    portfolio = _make_portfolio(db_session)
    client = _FakeClient(
        [
            _extracted("", review_required=True, review_reason="ticker vazio"),
            _extracted("MXRF11.SA"),
        ]
    )
    service = DividendosMeSyncService(db_session)

    with pytest.raises(ExtractionInvalidError, match="Substituição bloqueada"):
        service.replace(portfolio.id, client, confirm=True)


def test_sections_failed_are_reported_as_errors(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeClient(
        [_extracted("WEGE3.SA"), _extracted("MXRF11.SA")], failed_sections=["criptomoedas"]
    )
    service = DividendosMeSyncService(db_session)

    result = service.replace(portfolio.id, client, confirm=True)

    assert any("criptomoedas" in e for e in result.errors)


def test_tesouro_position_created_as_manual_asset(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeClient(
        [
            _extracted(
                "TESOURO-IPCA-2045",
                asset_class="bond",
                currency="BRL",
                origin=ORIGIN_B3,
                is_manual=True,
            ),
            _extracted("MXRF11.SA"),
        ]
    )
    service = DividendosMeSyncService(db_session)

    service.replace(portfolio.id, client, confirm=True)

    asset = AssetRepository(db_session).get_by_ticker("TESOURO-IPCA-2045")
    assert asset is not None
    assert asset.is_manual is True


def test_run_is_recorded_in_external_sync_runs(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeClient([_extracted("WEGE3.SA"), _extracted("MXRF11.SA")])
    service = DividendosMeSyncService(db_session)

    result = service.replace(portfolio.id, client, confirm=True)

    run = service.sync_runs.get_by_id(result.run_id)
    assert run is not None
    assert run.provider == "dividendos_me"
    assert run.mode == "replace"
    assert run.status == "success"
    assert run.positions_created == 2
    # Nunca guarda senha/cookie/token — só metadados operacionais.
    assert "senha" not in (run.summary_json or "").lower()
    assert "password" not in (run.summary_json or "").lower()


def test_consolidate_merges_same_ticker_across_sections():
    positions = [
        _extracted(
            "VOO", quantity="5", average_price="400", current_value="2000", origin=ORIGIN_B3
        ),
        _extracted(
            "VOO",
            quantity="5",
            average_price="420",
            current_value="2100",
            origin=ORIGIN_INTERNATIONAL,
        ),
    ]

    merged = _consolidate_positions(positions)

    assert len(merged) == 1
    assert merged[0].quantity == Decimal("10")
    assert merged[0].average_price == Decimal("410")
    assert merged[0].current_value == Decimal("4100")


def test_consolidate_keeps_distinct_tickers_separate():
    positions = [_extracted("WEGE3.SA"), _extracted("MXRF11.SA", asset_class="fii")]
    merged = _consolidate_positions(positions)
    assert len(merged) == 2


# --- Sprint 23.1: status success/partial/failed no preview -----------------


def test_preview_status_is_success_with_enough_valid_assets(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeClient([_extracted("WEGE3.SA"), _extracted("MXRF11.SA")])
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert preview.status == "success"
    assert preview.total_assets == 2


def test_preview_status_is_failed_when_only_empty_ticker_found(db_session):
    # Reproduz o bug real: um único "ativo" agregado com ticker vazio e
    # patrimônio total > 0 nunca pode ser reportado como sucesso.
    portfolio = _make_portfolio(db_session)
    client = _FakeClient(
        [
            _extracted(
                "",
                review_required=True,
                review_reason="ticker vazio",
                current_value="999999.00",
            )
        ]
    )
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert preview.status in ("partial", "failed")
    assert preview.status != "success"
    assert preview.total_assets == 0
    assert preview.total_patrimonio > 0


def test_preview_status_is_partial_with_one_valid_asset_below_minimum(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeClient([_extracted("WEGE3.SA")])
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert preview.status == "partial"
    assert preview.total_assets == 1


def test_preview_status_is_partial_when_a_section_fails_even_with_enough_assets(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeClient(
        [_extracted("WEGE3.SA"), _extracted("MXRF11.SA")], failed_sections=["renda_fixa"]
    )
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert preview.status == "partial"


def test_dry_run_never_reports_success_with_aggregate_patrimony_and_no_valid_assets(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeClient(
        [
            _extracted(
                "",
                review_required=True,
                review_reason="ticker vazio",
                current_value="500000.00",
            )
        ]
    )
    service = DividendosMeSyncService(db_session)

    result = service.dry_run(portfolio.id, client)

    assert result.status != "success"
    assert result.preview.total_patrimonio == Decimal("500000.00")
    assert result.preview.total_assets == 0


# --- Sprint 23.1: bloqueio obrigatório de replace/update --------------------


def test_replace_blocks_when_single_position_has_empty_ticker(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeClient(
        [_extracted("", review_required=True, review_reason="ticker vazio", quantity="9999")]
    )
    service = DividendosMeSyncService(db_session)

    with pytest.raises(ExtractionInvalidError, match="Substituição bloqueada"):
        service.replace(portfolio.id, client, confirm=True)

    # Nada foi gravado nem removido.
    assert PositionRepository(db_session).list_by_portfolio(portfolio.id) == []


def test_replace_blocks_when_review_required_ticker_is_empty_even_with_other_assets(db_session):
    portfolio = _make_portfolio(db_session)
    _seed_position(db_session, portfolio.id, "OLDX3.SA")
    client = _FakeClient(
        [
            _extracted("WEGE3.SA"),
            _extracted("MXRF11.SA"),
            _extracted("", review_required=True, review_reason="ticker vazio"),
        ]
    )
    service = DividendosMeSyncService(db_session)

    with pytest.raises(ExtractionInvalidError, match="Substituição bloqueada"):
        service.replace(portfolio.id, client, confirm=True)

    # A carteira antiga continua intacta — nada foi removido.
    tickers = {
        p.asset.ticker for p in PositionRepository(db_session).list_by_portfolio(portfolio.id)
    }
    assert tickers == {"OLDX3.SA"}


def test_replace_blocks_when_more_than_half_of_portfolio_would_be_removed(db_session):
    portfolio = _make_portfolio(db_session)
    # 3 posições atuais, só 1 volta na extração -> 2/3 (>50%) seriam removidas.
    _seed_position(db_session, portfolio.id, "A3.SA")
    _seed_position(db_session, portfolio.id, "B3.SA")
    _seed_position(db_session, portfolio.id, "C3.SA")
    client = _FakeClient([_extracted("A3.SA"), _extracted("D3.SA")])
    service = DividendosMeSyncService(db_session)

    with pytest.raises(ExtractionInvalidError, match="Substituição bloqueada"):
        service.replace(portfolio.id, client, confirm=True)

    tickers = {
        p.asset.ticker for p in PositionRepository(db_session).list_by_portfolio(portfolio.id)
    }
    assert tickers == {"A3.SA", "B3.SA", "C3.SA"}


def test_replace_never_removes_portfolio_when_extraction_invalid(db_session):
    """Prioridade 5 do usuário: replace nunca deve deletar a carteira atual
    quando a extração é inválida — nem parcialmente, nem antes de checar."""
    portfolio = _make_portfolio(db_session)
    _seed_position(db_session, portfolio.id, "A3.SA")
    _seed_position(db_session, portfolio.id, "B3.SA")
    client = _FakeClient(
        [_extracted("", review_required=True, review_reason="ticker vazio", quantity="9999")]
    )
    service = DividendosMeSyncService(db_session)

    with pytest.raises(ExtractionInvalidError):
        service.replace(portfolio.id, client, confirm=True)

    positions = PositionRepository(db_session).list_by_portfolio(portfolio.id)
    assert len(positions) == 2


def test_update_also_blocks_on_broken_extraction_but_not_on_removal_risk(db_session):
    # `update` nunca remove nada, então a regra de >50% não se aplica a
    # ele — mas a extração "quebrada" (ticker vazio) ainda bloqueia,
    # porque nada deveria ser escrito com um dado tão pouco confiável.
    portfolio = _make_portfolio(db_session)
    client = _FakeClient(
        [_extracted("", review_required=True, review_reason="ticker vazio", quantity="9999")]
    )
    service = DividendosMeSyncService(db_session)

    with pytest.raises(ExtractionInvalidError):
        service.update(portfolio.id, client, confirm=True)


def test_replace_allowed_when_missing_ratio_is_exactly_half(db_session):
    # Exatamente 50% não deve bloquear — a regra é "mais de 50%".
    portfolio = _make_portfolio(db_session)
    _seed_position(db_session, portfolio.id, "A3.SA")
    _seed_position(db_session, portfolio.id, "B3.SA")
    client = _FakeClient([_extracted("A3.SA")])
    service = DividendosMeSyncService(db_session)

    result = service.replace(portfolio.id, client, confirm=True)

    assert result.status == "success"
    assert result.positions_removed == 1


def test_extraction_blocking_reasons_empty_for_healthy_preview(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeClient([_extracted("WEGE3.SA"), _extracted("MXRF11.SA")])
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert extraction_blocking_reasons(preview, mode="replace") == []


def test_strong_alert_sections_flags_crypto_and_renda_fixa(db_session):
    portfolio = _make_portfolio(db_session)
    client = _FakeClient(
        [_extracted("WEGE3.SA"), _extracted("MXRF11.SA")],
        failed_sections=["criptomoedas", "eua"],
    )
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert strong_alert_sections(preview) == ["criptomoedas"]


def test_preview_carries_diagnostics_from_client(db_session):
    portfolio = _make_portfolio(db_session)
    diagnostics = [
        SectionDiagnostics(
            section="brasil",
            selector_used="table (thead/tbody)",
            raw_rows_detected=10,
            valid_rows=9,
            rejected_rows=1,
            rejection_reasons=["subgrupo não reconhecido"],
        )
    ]
    client = _FakeClient([_extracted("WEGE3.SA"), _extracted("MXRF11.SA")], diagnostics=diagnostics)
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert preview.diagnostics == diagnostics


# --- Sprint 23.2: rede de segurança do BTC (_apply_btc_fallback) -----------


def _current_btc() -> dict[str, _CurrentPosition]:
    position = Position(
        id=1,
        portfolio_id=1,
        asset_id=1,
        quantity=Decimal("1"),
        average_price=Decimal("50000"),
        currency="USD",
        opened_at=date(2020, 1, 1),
    )
    return {"BTC-USD": _CurrentPosition(position=position, ticker="BTC-USD")}


def test_btc_fallback_maps_single_unmatched_crypto_when_btc_already_in_portfolio():
    extracted = [
        _extracted(
            "",
            section="criptomoedas",
            review_required=True,
            review_reason="ticker vazio",
            asset_class="crypto",
            currency="USD",
            country="US",
        ),
        _extracted("WEGE3.SA"),
    ]

    result = _apply_btc_fallback(extracted, _current_btc())

    crypto = next(p for p in result if p.section == "criptomoedas")
    assert crypto.ticker == "BTC-USD"
    assert crypto.asset_class == "crypto"
    assert crypto.review_required is False
    assert crypto.review_reason is None


def test_btc_fallback_never_triggers_with_multiple_unmatched_cryptos():
    extracted = [
        _extracted(
            "",
            section="criptomoedas",
            review_required=True,
            review_reason="ticker vazio",
            asset_class="crypto",
            currency="USD",
            country="US",
        ),
        _extracted(
            "",
            section="criptomoedas",
            review_required=True,
            review_reason="ticker vazio",
            asset_class="crypto",
            currency="USD",
            country="US",
        ),
    ]

    result = _apply_btc_fallback(extracted, _current_btc())

    # Nada foi remapeado — ambíguo demais para adivinhar qual é o BTC.
    assert all(p.ticker == "" and p.review_required for p in result)


def test_btc_fallback_never_triggers_when_btc_not_already_in_portfolio():
    extracted = [
        _extracted(
            "",
            section="criptomoedas",
            review_required=True,
            review_reason="ticker vazio",
            asset_class="crypto",
            currency="USD",
            country="US",
        ),
    ]

    result = _apply_btc_fallback(extracted, current={})

    assert result[0].ticker == ""
    assert result[0].review_required is True


def test_btc_fallback_never_triggers_outside_crypto_section():
    # Ticker vazio em outra seção (ex.: "brasil") nunca é remapeado para
    # BTC — a rede de segurança é estritamente escopada a "criptomoedas".
    extracted = [
        _extracted(
            "",
            section="brasil",
            review_required=True,
            review_reason="ticker vazio",
        ),
    ]

    result = _apply_btc_fallback(extracted, _current_btc())

    assert result[0].ticker == ""
    assert result[0].review_required is True


def test_btc_usd_correctly_extracted_appears_in_positions_and_not_missing(db_session):
    # Sprint 23.2 (requisito do usuário): quando o card de "Criptomoedas →
    # Extrato" é reconhecido corretamente (ticker "btc" -> BTC-USD, sem
    # precisar da rede de segurança `_apply_btc_fallback`), BTC-USD deve
    # aparecer em `positions` e NUNCA em `missing_in_source`.
    portfolio = _make_portfolio(db_session)
    asset = AssetRepository(db_session).create(
        Asset(ticker="BTC-USD", name="BTC-USD", asset_class="crypto", country="US", currency="USD")
    )
    PositionRepository(db_session).create(
        Position(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("0.005"),
            average_price=Decimal("70000"),
            currency="USD",
            opened_at=date(2020, 1, 1),
        )
    )
    client = _FakeClient(
        [
            _extracted(
                "BTC-USD",
                section="criptomoedas",
                asset_class="crypto",
                currency="USD",
                country="US",
                quantity="0.00584925",
                average_price="76308.58",
                current_value="365.02",
                origin=ORIGIN_CRYPTO,
            ),
            _extracted("WEGE3.SA"),
        ]
    )
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert "BTC-USD" in {p.ticker for p in preview.positions}
    assert "BTC-USD" not in preview.diff.missing_in_source


def test_replace_blocks_when_btc_usd_missing_even_under_50_percent_ratio(db_session):
    # Regressão-alvo da Sprint 23.2: a regra geral de >50% NÃO dispararia
    # aqui (só 1 de 4 ativos "sumiria" = 25%), mas BTC-USD é um ticker
    # sempre protegido (`_ALWAYS_PROTECTED_TICKERS`) — perder ele sozinho
    # já basta para bloquear o replace, independentemente do percentual.
    portfolio = _make_portfolio(db_session)
    asset = AssetRepository(db_session).create(
        Asset(ticker="BTC-USD", name="BTC-USD", asset_class="crypto", country="US", currency="USD")
    )
    PositionRepository(db_session).create(
        Position(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("0.005"),
            average_price=Decimal("70000"),
            currency="USD",
            opened_at=date(2020, 1, 1),
        )
    )
    _seed_position(db_session, portfolio.id, "A3.SA")
    _seed_position(db_session, portfolio.id, "B3.SA")
    _seed_position(db_session, portfolio.id, "C3.SA")
    # Extração traz de volta A3/B3/C3, mas NÃO traz BTC-USD (1 de 4 = 25%,
    # bem abaixo do limite de >50% da regra geral).
    client = _FakeClient([_extracted("A3.SA"), _extracted("B3.SA"), _extracted("C3.SA")])
    service = DividendosMeSyncService(db_session)

    with pytest.raises(ExtractionInvalidError, match="Substituição bloqueada"):
        service.replace(portfolio.id, client, confirm=True)

    # Nada foi removido — a carteira antiga (incluindo BTC-USD) continua intacta.
    tickers = {
        p.asset.ticker for p in PositionRepository(db_session).list_by_portfolio(portfolio.id)
    }
    assert tickers == {"BTC-USD", "A3.SA", "B3.SA", "C3.SA"}


def test_build_preview_applies_btc_fallback_before_consolidation(db_session):
    portfolio = _make_portfolio(db_session)
    asset = AssetRepository(db_session).create(
        Asset(ticker="BTC-USD", name="BTC-USD", asset_class="crypto", country="US", currency="USD")
    )
    PositionRepository(db_session).create(
        Position(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("1"),
            average_price=Decimal("50000"),
            currency="USD",
            opened_at=date(2020, 1, 1),
        )
    )
    client = _FakeClient(
        [
            _extracted(
                "",
                section="criptomoedas",
                review_required=True,
                review_reason="ticker vazio",
                asset_class="crypto",
                currency="USD",
                country="US",
                current_value="4093.00",
            ),
            _extracted("WEGE3.SA"),
        ]
    )
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert "BTC-USD" in {p.ticker for p in preview.positions}
    assert "" not in preview.review_required_tickers
    assert "BTC-USD" not in preview.diff.missing_in_source


# --- Sprint 23.3: seções esperadas derivadas da carteira atual --------------


def test_expected_sections_from_current_covers_all_known_classes():
    current = {
        "WEGE3.SA": _CurrentPosition(
            position=None, ticker="WEGE3.SA", asset_class="stock", country="BR"
        ),
        "VOO": _CurrentPosition(position=None, ticker="VOO", asset_class="etf", country="US"),
        "BTC-USD": _CurrentPosition(
            position=None, ticker="BTC-USD", asset_class="crypto", country="US"
        ),
        "TESOURO-IPCA-2050": _CurrentPosition(
            position=None, ticker="TESOURO-IPCA-2050", asset_class="bond", country="BR"
        ),
    }

    assert _expected_sections_from_current(current) == [
        "brasil",
        "criptomoedas",
        "eua",
        "renda_fixa",
    ]


def test_expected_sections_from_current_empty_when_no_positions():
    assert _expected_sections_from_current({}) == []


def test_build_preview_populates_sections_expected_from_current_portfolio(db_session):
    portfolio = _make_portfolio(db_session)
    _seed_asset_position(db_session, portfolio.id, "WEGE3.SA")
    _seed_asset_position(db_session, portfolio.id, "VOO", asset_class="etf", country="US")
    client = _FakeClient(
        [
            _extracted("WEGE3.SA", section="brasil"),
            _extracted("VOO", asset_class="etf", country="US", currency="USD", section="eua"),
        ]
    )
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert preview.sections_expected == ["brasil", "eua"]


def test_replace_blocks_when_eua_expected_but_returns_empty(db_session):
    # Reproduz o bug real reportado: a carteira atual tem ativo dos EUA,
    # mas a extração desta vez não trouxe NADA da seção "eua" (nem erro,
    # nem posição) — isso deve bloquear o replace com a mensagem
    # específica de seção incompleta, mesmo sem nenhum ticker
    # "sempre protegido" envolvido.
    portfolio = _make_portfolio(db_session)
    _seed_asset_position(db_session, portfolio.id, "WEGE3.SA")
    _seed_asset_position(db_session, portfolio.id, "VOO", asset_class="etf", country="US")
    client = _FakeClient([_extracted("WEGE3.SA", section="brasil")])
    service = DividendosMeSyncService(db_session)

    with pytest.raises(ExtractionInvalidError) as exc_info:
        service.replace(portfolio.id, client, confirm=True)

    assert str(exc_info.value) == EXTRACTION_INCOMPLETE_SECTIONS_MESSAGE
    # Nada foi removido — a carteira antiga (incluindo VOO) continua intacta.
    tickers = {
        p.asset.ticker for p in PositionRepository(db_session).list_by_portfolio(portfolio.id)
    }
    assert tickers == {"WEGE3.SA", "VOO"}


def test_replace_blocks_when_criptomoedas_expected_but_returns_empty(db_session):
    portfolio = _make_portfolio(db_session)
    _seed_asset_position(db_session, portfolio.id, "WEGE3.SA")
    _seed_asset_position(db_session, portfolio.id, "BTC-USD", asset_class="crypto", country="US")
    client = _FakeClient([_extracted("WEGE3.SA", section="brasil")])
    service = DividendosMeSyncService(db_session)

    with pytest.raises(ExtractionInvalidError) as exc_info:
        service.replace(portfolio.id, client, confirm=True)

    assert str(exc_info.value) == EXTRACTION_INCOMPLETE_SECTIONS_MESSAGE


def test_replace_blocks_when_renda_fixa_expected_but_returns_empty(db_session):
    portfolio = _make_portfolio(db_session)
    _seed_asset_position(db_session, portfolio.id, "WEGE3.SA")
    _seed_asset_position(db_session, portfolio.id, "TESOURO-IPCA-2050", asset_class="bond")
    client = _FakeClient([_extracted("WEGE3.SA", section="brasil")])
    service = DividendosMeSyncService(db_session)

    with pytest.raises(ExtractionInvalidError) as exc_info:
        service.replace(portfolio.id, client, confirm=True)

    assert str(exc_info.value) == EXTRACTION_INCOMPLETE_SECTIONS_MESSAGE


def test_update_never_blocks_on_section_gap_since_it_never_removes(db_session):
    # `update` nunca remove posições, então a checagem de seção esperada
    # vazia (que só existe para proteger contra remoção silenciosa) não
    # se aplica — mesmo com EUA esperado e ausente, `update` deve rodar.
    portfolio = _make_portfolio(db_session)
    _seed_asset_position(db_session, portfolio.id, "WEGE3.SA")
    _seed_asset_position(db_session, portfolio.id, "VOO", asset_class="etf", country="US")
    client = _FakeClient([_extracted("WEGE3.SA", section="brasil")])
    service = DividendosMeSyncService(db_session)

    result = service.update(portfolio.id, client, confirm=True)

    assert result.status == "success"


def test_strong_alert_sections_includes_eua_when_expected_and_failed(db_session):
    portfolio = _make_portfolio(db_session)
    _seed_asset_position(db_session, portfolio.id, "VOO", asset_class="etf", country="US")
    client = _FakeClient([_extracted("WEGE3.SA", section="brasil")], failed_sections=["eua"])
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert "eua" in strong_alert_sections(preview)


def test_total_patrimonio_status_partial_when_expected_section_missing(db_session):
    portfolio = _make_portfolio(db_session)
    _seed_asset_position(db_session, portfolio.id, "VOO", asset_class="etf", country="US")
    client = _FakeClient([_extracted("WEGE3.SA", section="brasil")])
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert preview.total_patrimonio_status == "partial"


def test_total_patrimonio_status_consolidated_when_all_sections_present(db_session):
    portfolio = _make_portfolio(db_session)
    _seed_asset_position(db_session, portfolio.id, "WEGE3.SA")
    client = _FakeClient([_extracted("WEGE3.SA", section="brasil")])
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert preview.total_patrimonio_status == "consolidated"


def test_has_section_gap_true_when_expected_section_missing(db_session):
    portfolio = _make_portfolio(db_session)
    _seed_asset_position(db_session, portfolio.id, "VOO", asset_class="etf", country="US")
    client = _FakeClient([_extracted("WEGE3.SA", section="brasil")])
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert has_section_gap(preview) is True


def test_has_section_gap_false_for_healthy_preview(db_session):
    portfolio = _make_portfolio(db_session)
    _seed_asset_position(db_session, portfolio.id, "WEGE3.SA")
    client = _FakeClient([_extracted("WEGE3.SA", section="brasil")])
    service = DividendosMeSyncService(db_session)

    preview = service.build_preview(portfolio.id, client)

    assert has_section_gap(preview) is False
