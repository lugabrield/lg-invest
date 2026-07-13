"""Testes da integração Decision Engine 3.0 <-> Trap Detection Engine +
Valuation Engine 2.0 (Sprint 26, Fase 6).

Cobre `DecisionService._fundamental_signals_for_ticker` e o wiring em
`_decision_input_for_ticker`: a penalidade de confiança do Trap Detection
Engine deve reduzir `DecisionInput.confidence` (nunca bloquear nem virar
peso novo no score), e os avisos (flags de armadilha + status
"sobrevalorizado" do Valuation Engine 2.0, só para ações) devem aparecer
em `DecisionInput.fundamental_warnings` como texto explicativo.

Usa monkeypatch nos serviços dependentes (`TrapDetectionService`,
`ValuationServiceV2`) em vez de tentar reproduzir fundamentos reais que
disparem cada flag — isola o teste ao contrato de integração, não à
lógica interna desses engines (já coberta em seus próprios testes)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.schemas.data_coverage import CoveragePurposeScore, DataCoverageResult
from backend.app.schemas.trap_detection import TrapDetectionResult, TrapFlag
from backend.app.schemas.valuation_v2 import (
    VALUATION_STATUS_INDETERMINATE,
    VALUATION_STATUS_OVERVALUED,
    ValuationV2Result,
)
from backend.app.services import data_coverage_service as data_coverage_service_module
from backend.app.services import trap_detection_service as trap_detection_service_module
from backend.app.services import valuation_v2_service as valuation_v2_service_module
from backend.app.services.decision_service import DecisionService


def _sufficient_coverage(ticker: str, asset_class: str = "stock") -> DataCoverageResult:
    """Cobertura de dados "suficiente" (Sprint 28) — usada para neutralizar
    o sinal de Data Coverage Report nos testes que focam só em Trap
    Detection/Valuation Engine 2.0 (Sprint 26), preservando o isolamento
    original do arquivo."""
    return DataCoverageResult(
        ticker=ticker,
        asset_class=asset_class,
        decision_engine=CoveragePurposeScore(score=Decimal("90"), classification="suficiente"),
    )


def _patch_sufficient_coverage(monkeypatch, ticker: str, asset_class: str = "stock") -> None:
    monkeypatch.setattr(
        data_coverage_service_module.DataCoverageService,
        "evaluate_ticker",
        lambda self, t: _sufficient_coverage(t, asset_class),
    )


def _seed_single_stock(db, ticker: str = "WEGE3.SA") -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    stock = Asset(ticker=ticker, name="WEG", asset_class="stock", country="BR", currency="BRL")
    db.add(stock)
    db.flush()

    db.add(
        Position(
            portfolio_id=portfolio.id,
            asset_id=stock.id,
            quantity=Decimal("100"),
            average_price=Decimal("38"),
            currency="BRL",
            opened_at=date(2025, 1, 1),
        )
    )
    db.add(Price(asset_id=stock.id, date=date(2026, 6, 27), close=Decimal("40")))
    db.commit()
    return portfolio.id


def _trap_flag(severity: str, penalty: Decimal) -> TrapFlag:
    return TrapFlag(
        trap_type="low_pe_trap",
        label="Armadilha do P/L baixo",
        severity=severity,
        affected_metric="pe_ratio",
        explanation="P/L artificialmente baixo por evento não recorrente.",
        impact_on_score="Reduz confiança na leitura de barato.",
        recommended_interpretation="Investigar a causa do lucro atípico.",
        confidence_penalty=penalty,
    )


def test_fundamental_signals_no_trap_no_overvaluation_returns_zero_and_empty(
    db_session, monkeypatch
):
    portfolio_id = _seed_single_stock(db_session)

    monkeypatch.setattr(
        trap_detection_service_module.TrapDetectionService,
        "evaluate_ticker",
        lambda self, ticker: TrapDetectionResult(
            ticker=ticker, asset_class="stock", flags=[], confidence_penalty=Decimal("0")
        ),
    )
    monkeypatch.setattr(
        valuation_v2_service_module.ValuationServiceV2,
        "evaluate_ticker",
        lambda self, ticker: ValuationV2Result(
            ticker=ticker,
            asset_class="stock",
            valuation_status=VALUATION_STATUS_INDETERMINATE,
        ),
    )
    _patch_sufficient_coverage(monkeypatch, "WEGE3.SA")

    penalty, warnings = DecisionService(db_session)._fundamental_signals_for_ticker(
        "WEGE3.SA", "stock"
    )
    assert penalty == Decimal("0")
    assert warnings == ()
    del portfolio_id


def test_fundamental_signals_trap_flag_reduces_confidence_and_adds_warning(db_session, monkeypatch):
    _seed_single_stock(db_session)

    flag = _trap_flag("alta", Decimal("0.20"))
    monkeypatch.setattr(
        trap_detection_service_module.TrapDetectionService,
        "evaluate_ticker",
        lambda self, ticker: TrapDetectionResult(
            ticker=ticker,
            asset_class="stock",
            flags=[flag],
            confidence_penalty=Decimal("0.20"),
        ),
    )
    monkeypatch.setattr(
        valuation_v2_service_module.ValuationServiceV2,
        "evaluate_ticker",
        lambda self, ticker: ValuationV2Result(
            ticker=ticker,
            asset_class="stock",
            valuation_status=VALUATION_STATUS_INDETERMINATE,
        ),
    )
    _patch_sufficient_coverage(monkeypatch, "WEGE3.SA")

    penalty, warnings = DecisionService(db_session)._fundamental_signals_for_ticker(
        "WEGE3.SA", "stock"
    )
    assert penalty == Decimal("0.20")
    assert len(warnings) == 1
    assert "Armadilha do P/L baixo" in warnings[0]
    assert "alta" in warnings[0]


def test_fundamental_signals_overvalued_stock_adds_warning_without_confidence_penalty(
    db_session, monkeypatch
):
    _seed_single_stock(db_session)

    monkeypatch.setattr(
        trap_detection_service_module.TrapDetectionService,
        "evaluate_ticker",
        lambda self, ticker: TrapDetectionResult(
            ticker=ticker, asset_class="stock", flags=[], confidence_penalty=Decimal("0")
        ),
    )
    monkeypatch.setattr(
        valuation_v2_service_module.ValuationServiceV2,
        "evaluate_ticker",
        lambda self, ticker: ValuationV2Result(
            ticker=ticker,
            asset_class="stock",
            valuation_status=VALUATION_STATUS_OVERVALUED,
        ),
    )
    _patch_sufficient_coverage(monkeypatch, "WEGE3.SA")

    penalty, warnings = DecisionService(db_session)._fundamental_signals_for_ticker(
        "WEGE3.SA", "stock"
    )
    assert penalty == Decimal("0")
    assert len(warnings) == 1
    assert "sobrevalorizado" in warnings[0]


def test_fundamental_signals_valuation_v2_never_consulted_for_non_stock(db_session, monkeypatch):
    """FII/ETF/cripto/Tesouro nunca usam DCF/P-L (Valuation Engine 2.0 é
    exclusivo de ações) — a função nem deve chamar o serviço para essas
    classes."""
    _seed_single_stock(db_session, ticker="MXRF11.SA")

    monkeypatch.setattr(
        trap_detection_service_module.TrapDetectionService,
        "evaluate_ticker",
        lambda self, ticker: None,
    )

    def _fail_if_called(self, ticker):
        raise AssertionError("ValuationServiceV2 não deve ser chamado para classes != stock")

    monkeypatch.setattr(
        valuation_v2_service_module.ValuationServiceV2, "evaluate_ticker", _fail_if_called
    )
    _patch_sufficient_coverage(monkeypatch, "MXRF11.SA", asset_class="fii")

    penalty, warnings = DecisionService(db_session)._fundamental_signals_for_ticker(
        "MXRF11.SA", "fii"
    )
    assert penalty == Decimal("0")
    assert warnings == ()


def test_fundamental_signals_ticker_not_found_returns_zero_and_empty(db_session, monkeypatch):
    monkeypatch.setattr(
        trap_detection_service_module.TrapDetectionService,
        "evaluate_ticker",
        lambda self, ticker: None,
    )
    monkeypatch.setattr(
        valuation_v2_service_module.ValuationServiceV2,
        "evaluate_ticker",
        lambda self, ticker: None,
    )

    penalty, warnings = DecisionService(db_session)._fundamental_signals_for_ticker(
        "NAOEXISTE.SA", "stock"
    )
    assert penalty == Decimal("0")
    assert warnings == ()


def test_decision_input_for_ticker_applies_confidence_penalty_and_warnings(db_session, monkeypatch):
    portfolio_id = _seed_single_stock(db_session)

    flag = _trap_flag("média", Decimal("0.10"))
    monkeypatch.setattr(
        trap_detection_service_module.TrapDetectionService,
        "evaluate_ticker",
        lambda self, ticker: TrapDetectionResult(
            ticker=ticker,
            asset_class="stock",
            flags=[flag],
            confidence_penalty=Decimal("0.10"),
        ),
    )
    monkeypatch.setattr(
        valuation_v2_service_module.ValuationServiceV2,
        "evaluate_ticker",
        lambda self, ticker: ValuationV2Result(
            ticker=ticker,
            asset_class="stock",
            valuation_status=VALUATION_STATUS_OVERVALUED,
        ),
    )
    _patch_sufficient_coverage(monkeypatch, "WEGE3.SA")

    service = DecisionService(db_session)
    inputs = service.build_inputs_v3(portfolio_id)
    assert len(inputs) == 1
    candidate = inputs[0]

    assert len(candidate.fundamental_warnings) == 2
    assert any("P/L baixo" in w for w in candidate.fundamental_warnings)
    assert any("sobrevalorizado" in w for w in candidate.fundamental_warnings)
    # A confiança efetiva deve ser estritamente menor que a confiança "crua"
    # do LG Score, já que a penalidade de 0.10 foi subtraída na origem.
    from backend.app.services.lg_score_service import LGScoreService

    raw = LGScoreService(db_session).score_ticker(
        candidate.ticker, current_weight=candidate.current_weight
    )
    assert raw is not None
    assert candidate.confidence == max(Decimal("0"), raw.confidence - Decimal("0.10"))


def test_decision_input_for_ticker_confidence_penalty_never_goes_below_zero(
    db_session, monkeypatch
):
    portfolio_id = _seed_single_stock(db_session)

    flag = _trap_flag("alta", Decimal("1.00"))
    monkeypatch.setattr(
        trap_detection_service_module.TrapDetectionService,
        "evaluate_ticker",
        lambda self, ticker: TrapDetectionResult(
            ticker=ticker,
            asset_class="stock",
            flags=[flag, flag, flag],
            confidence_penalty=Decimal("1.00"),
        ),
    )
    monkeypatch.setattr(
        valuation_v2_service_module.ValuationServiceV2,
        "evaluate_ticker",
        lambda self, ticker: ValuationV2Result(
            ticker=ticker,
            asset_class="stock",
            valuation_status=VALUATION_STATUS_INDETERMINATE,
        ),
    )
    _patch_sufficient_coverage(monkeypatch, "WEGE3.SA")

    service = DecisionService(db_session)
    inputs = service.build_inputs_v3(portfolio_id)
    assert len(inputs) == 1
    assert inputs[0].confidence == Decimal("0")


def test_recommend_v3_never_mentions_selling_even_with_trap_warnings(db_session, monkeypatch):
    portfolio_id = _seed_single_stock(db_session)

    flag = _trap_flag("alta", Decimal("0.20"))
    monkeypatch.setattr(
        trap_detection_service_module.TrapDetectionService,
        "evaluate_ticker",
        lambda self, ticker: TrapDetectionResult(
            ticker=ticker,
            asset_class="stock",
            flags=[flag],
            confidence_penalty=Decimal("0.20"),
        ),
    )
    monkeypatch.setattr(
        valuation_v2_service_module.ValuationServiceV2,
        "evaluate_ticker",
        lambda self, ticker: ValuationV2Result(
            ticker=ticker,
            asset_class="stock",
            valuation_status=VALUATION_STATUS_OVERVALUED,
        ),
    )
    _patch_sufficient_coverage(monkeypatch, "WEGE3.SA")

    result = DecisionService(db_session).recommend_v3(portfolio_id, Decimal("1000"), persist=False)
    text_parts = [result.explanation, *result.alerts]
    for rec_item in result.items:
        text_parts.extend(rec_item.reasons)
    for ignored_item in result.ignored:
        if ignored_item.reason:
            text_parts.append(ignored_item.reason)
    all_text = " ".join(text_parts).lower()
    assert "vend" not in all_text


@pytest.mark.parametrize("asset_class", ["etf", "crypto", "bond"])
def test_fundamental_signals_non_applicable_classes_never_call_valuation(
    db_session, monkeypatch, asset_class
):
    monkeypatch.setattr(
        trap_detection_service_module.TrapDetectionService,
        "evaluate_ticker",
        lambda self, ticker: None,
    )

    def _fail_if_called(self, ticker):
        raise AssertionError("ValuationServiceV2 não deve ser chamado fora de 'stock'")

    monkeypatch.setattr(
        valuation_v2_service_module.ValuationServiceV2, "evaluate_ticker", _fail_if_called
    )

    penalty, warnings = DecisionService(db_session)._fundamental_signals_for_ticker(
        "QUALQUER.SA", asset_class
    )
    assert penalty == Decimal("0")
    assert warnings == ()


# -- Sprint 28, Fase 6: Decision Engine explica dados ausentes -------------


def test_fundamental_signals_insufficient_coverage_adds_warning_and_penalty(
    db_session, monkeypatch
):
    """Reproduz o cenário relatado pelo usuário (ALUP4.SA): ativo com
    cobertura de dados insuficiente para valuation deve gerar um aviso
    explícito com os campos que faltam, e uma penalidade de confiança
    REAL — não só um rótulo "confiança baixa" genérico."""
    _seed_single_stock(db_session, ticker="ALUP4.SA")

    monkeypatch.setattr(
        trap_detection_service_module.TrapDetectionService,
        "evaluate_ticker",
        lambda self, ticker: TrapDetectionResult(
            ticker=ticker, asset_class="stock", flags=[], confidence_penalty=Decimal("0")
        ),
    )
    monkeypatch.setattr(
        valuation_v2_service_module.ValuationServiceV2,
        "evaluate_ticker",
        lambda self, ticker: ValuationV2Result(
            ticker=ticker,
            asset_class="stock",
            valuation_status=VALUATION_STATUS_INDETERMINATE,
        ),
    )
    monkeypatch.setattr(
        data_coverage_service_module.DataCoverageService,
        "evaluate_ticker",
        lambda self, ticker: DataCoverageResult(
            ticker=ticker,
            asset_class="stock",
            decision_engine=CoveragePurposeScore(
                score=Decimal("20"), classification="insuficiente"
            ),
            valuation=CoveragePurposeScore(
                score=Decimal("10"),
                classification="insuficiente",
                missing_labels=["FCF", "Ações em circulação", "Patrimônio líquido"],
            ),
        ),
    )

    penalty, warnings = DecisionService(db_session)._fundamental_signals_for_ticker(
        "ALUP4.SA", "stock"
    )
    assert penalty == Decimal("0.10")
    assert len(warnings) == 1
    assert "cobertura de dados fundamentais insuficiente" in warnings[0]
    assert "FCF" in warnings[0]
    assert "Score reduzido por baixa cobertura de dados." in warnings[0]


def test_fundamental_signals_partial_coverage_applies_smaller_penalty(db_session, monkeypatch):
    _seed_single_stock(db_session, ticker="ALUP4.SA")

    monkeypatch.setattr(
        trap_detection_service_module.TrapDetectionService,
        "evaluate_ticker",
        lambda self, ticker: TrapDetectionResult(
            ticker=ticker, asset_class="stock", flags=[], confidence_penalty=Decimal("0")
        ),
    )
    monkeypatch.setattr(
        valuation_v2_service_module.ValuationServiceV2,
        "evaluate_ticker",
        lambda self, ticker: ValuationV2Result(
            ticker=ticker,
            asset_class="stock",
            valuation_status=VALUATION_STATUS_INDETERMINATE,
        ),
    )
    monkeypatch.setattr(
        data_coverage_service_module.DataCoverageService,
        "evaluate_ticker",
        lambda self, ticker: DataCoverageResult(
            ticker=ticker,
            asset_class="stock",
            decision_engine=CoveragePurposeScore(score=Decimal("50"), classification="parcial"),
            valuation=CoveragePurposeScore(
                score=Decimal("50"), classification="parcial", missing_labels=["ROIC"]
            ),
        ),
    )

    penalty, warnings = DecisionService(db_session)._fundamental_signals_for_ticker(
        "ALUP4.SA", "stock"
    )
    assert penalty == Decimal("0.05")
    assert len(warnings) == 1
    assert "cobertura de dados fundamentais parcial" in warnings[0]


def test_fundamental_signals_sufficient_coverage_adds_no_warning(db_session, monkeypatch):
    _seed_single_stock(db_session, ticker="ALUP4.SA")

    monkeypatch.setattr(
        trap_detection_service_module.TrapDetectionService,
        "evaluate_ticker",
        lambda self, ticker: TrapDetectionResult(
            ticker=ticker, asset_class="stock", flags=[], confidence_penalty=Decimal("0")
        ),
    )
    monkeypatch.setattr(
        valuation_v2_service_module.ValuationServiceV2,
        "evaluate_ticker",
        lambda self, ticker: ValuationV2Result(
            ticker=ticker,
            asset_class="stock",
            valuation_status=VALUATION_STATUS_INDETERMINATE,
        ),
    )
    _patch_sufficient_coverage(monkeypatch, "ALUP4.SA")

    penalty, warnings = DecisionService(db_session)._fundamental_signals_for_ticker(
        "ALUP4.SA", "stock"
    )
    assert penalty == Decimal("0")
    assert warnings == ()


def test_fundamental_signals_no_coverage_report_never_breaks(db_session, monkeypatch):
    """Ticker sem cadastro (Data Coverage Report indisponível) nunca deve
    levantar exceção — mesma regra de "nunca derruba o lote" já aplicada
    ao Trap Detection Engine e ao Valuation Engine 2.0."""
    monkeypatch.setattr(
        trap_detection_service_module.TrapDetectionService,
        "evaluate_ticker",
        lambda self, ticker: None,
    )
    monkeypatch.setattr(
        valuation_v2_service_module.ValuationServiceV2,
        "evaluate_ticker",
        lambda self, ticker: None,
    )

    penalty, warnings = DecisionService(db_session)._fundamental_signals_for_ticker(
        "NAOEXISTE.SA", "stock"
    )
    assert penalty == Decimal("0")
    assert warnings == ()
