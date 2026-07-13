"""Testes do Data Coverage Engine (Sprint 28, Fase 2/7).

Cobre os cenários 1-4 e 11 da Parte 8 da especificação:
- Data Coverage Report completo (todos os campos presentes)
- Data Coverage Report incompleto (reproduz o cenário relatado pelo
  usuário: ALUP4.SA com poucos campos)
- valuation bloqueado por FCF/patrimônio/lucro ausentes
- quality score parcial com só alguns dados disponíveis
- trap detection roda com dados parciais mas reduz confiança (via score
  de cobertura, não da engine de trap em si — essa já tem seus próprios
  testes em `test_trap_detection_engine.py`)
- dado desatualizado reduz o score/confiança do Decision Engine

Usa `FundamentalSnapshotResult` diretamente (schema puro), sem banco —
mesmo padrão dos outros testes de engine pura do projeto."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from backend.app.engines.data_coverage.engine import DataCoverageEngine
from backend.app.engines.data_coverage.thresholds import (
    CLASSIFICATION_INSUFFICIENT,
    CLASSIFICATION_NOT_APPLICABLE,
    CLASSIFICATION_PARTIAL,
    CLASSIFICATION_SUFFICIENT,
    STALE_DATA_THRESHOLD_DAYS,
)
from backend.app.schemas.fundamentals import FundamentalSnapshotResult

_TODAY = date(2026, 7, 10)


def _full_snapshot(
    ticker: str = "WEGE3.SA", collected_at: datetime | None = None
) -> FundamentalSnapshotResult:
    """Snapshot com TODOS os campos usados pelo relatório preenchidos —
    cenário "completo"."""
    return FundamentalSnapshotResult(
        ticker=ticker,
        period_end=date(2025, 12, 31),
        source="yahoo",
        collected_at=collected_at or datetime(2026, 7, 1, 12, 0, 0),
        roe=Decimal("0.20"),
        roa=Decimal("0.10"),
        net_margin=Decimal("0.15"),
        ebitda_margin=Decimal("0.25"),
        revenue=Decimal("1000000"),
        net_income=Decimal("150000"),
        ebitda=Decimal("250000"),
        ebit=Decimal("200000"),
        free_cash_flow=Decimal("120000"),
        net_debt=Decimal("50000"),
        debt_to_ebitda=Decimal("0.5"),
        pe_ratio=Decimal("15"),
        pb_ratio=Decimal("3"),
        ev_ebitda=Decimal("10"),
        dividend_yield=Decimal("0.03"),
        payout_ratio=Decimal("0.30"),
        eps=Decimal("2.5"),
        revenue_per_share=Decimal("20"),
        beta=Decimal("1.1"),
        market_cap=Decimal("5000000"),
        enterprise_value=Decimal("5050000"),
        forward_pe=Decimal("14"),
        operating_margin=Decimal("0.20"),
        total_debt=Decimal("100000"),
        total_cash=Decimal("50000"),
        operating_cash_flow=Decimal("130000"),
        gross_profit=Decimal("400000"),
        shares_outstanding=Decimal("60000"),
        total_equity=Decimal("800000"),
        roic=Decimal("0.18"),
        interest_coverage=Decimal("8"),
    )


def _sparse_snapshot(ticker: str = "ALUP4.SA") -> FundamentalSnapshotResult:
    """Reproduz o cenário relatado pelo usuário: só P/L, P/VP e Dividend
    Yield vêm do Yahoo Finance — tudo o resto ausente."""
    return FundamentalSnapshotResult(
        ticker=ticker,
        period_end=date(2025, 12, 31),
        source="yahoo",
        collected_at=datetime(2026, 7, 1, 12, 0, 0),
        pe_ratio=Decimal("8.4"),
        pb_ratio=Decimal("1.2"),
        dividend_yield=Decimal("0.06"),
    )


def test_full_data_produces_sufficient_coverage_for_all_purposes():
    """Cenário 1a (Data Coverage Report completo): snapshot com todos os
    campos + histórico de 2+ períodos + análise de crescimento disponível
    deve classificar Quality/Valuation/Trap Detection como "suficiente"."""
    from backend.app.schemas.fundamentals_analysis import FundamentalsAnalysisResult

    snapshot = _full_snapshot()
    history = [snapshot, _full_snapshot()]
    analysis = FundamentalsAnalysisResult(
        ticker="WEGE3.SA",
        periods_used=2,
        revenue_cagr=Decimal("0.12"),
        net_income_cagr=Decimal("0.10"),
        fcf_cagr=Decimal("0.08"),
        margin_trend="estável",
        confidence="alta",
    )

    result = DataCoverageEngine().evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        latest_snapshot=snapshot,
        history=history,
        fundamentals_analysis=analysis,
        has_current_price=True,
        price_history_periods=10,
        today=_TODAY,
    )

    assert result.quality.classification == CLASSIFICATION_SUFFICIENT
    assert result.valuation.classification == CLASSIFICATION_SUFFICIENT
    assert result.trap_detection.classification == CLASSIFICATION_SUFFICIENT
    assert result.decision_engine.classification == CLASSIFICATION_SUFFICIENT
    assert result.missing_field_labels == []


def test_sparse_data_reproduces_alup4_symptom():
    """Cenário 1b (Data Coverage Report incompleto): reproduz o sintoma
    relatado pelo usuário para ALUP4.SA — valuation e trap detection ficam
    com cobertura insuficiente e os rótulos ausentes citam FCF, ações em
    circulação e patrimônio líquido, nunca um "confiança baixa" genérico."""
    snapshot = _sparse_snapshot()

    result = DataCoverageEngine().evaluate(
        ticker="ALUP4.SA",
        asset_class="stock",
        latest_snapshot=snapshot,
        history=[snapshot],
        fundamentals_analysis=None,
        has_current_price=True,
        price_history_periods=1,
        today=_TODAY,
    )

    assert result.valuation.classification == CLASSIFICATION_INSUFFICIENT
    assert "FCF (fluxo de caixa livre)" in result.valuation.missing_labels
    assert "Ações em circulação" in result.valuation.missing_labels
    assert "Patrimônio líquido" in result.valuation.missing_labels
    assert result.decision_engine.classification != CLASSIFICATION_SUFFICIENT


def test_valuation_blocked_by_missing_fcf_and_equity():
    """Cenário 2 (valuation bloqueado por FCF/lucro ausentes): mesmo com
    P/L e P/VP presentes, sem FCF/patrimônio/ações em circulação o score
    de valuation não pode ser "suficiente"."""
    snapshot = FundamentalSnapshotResult(
        ticker="XYZ3.SA",
        period_end=date(2025, 12, 31),
        source="yahoo",
        collected_at=datetime(2026, 7, 1),
        pe_ratio=Decimal("10"),
        pb_ratio=Decimal("1.5"),
    )

    result = DataCoverageEngine().evaluate(
        ticker="XYZ3.SA",
        asset_class="stock",
        latest_snapshot=snapshot,
        history=[snapshot],
        fundamentals_analysis=None,
        has_current_price=True,
        price_history_periods=1,
        today=_TODAY,
    )

    assert result.valuation.score < Decimal("50")
    assert "FCF (fluxo de caixa livre)" in result.valuation.missing_labels


def test_quality_score_partial_with_only_some_fields():
    """Cenário 3 (quality score parcial): só ROE disponível (de 3 campos
    do Quality Engine) deve dar um score intermediário, não 0 nem 100."""
    snapshot = FundamentalSnapshotResult(
        ticker="XYZ3.SA",
        period_end=date(2025, 12, 31),
        source="yahoo",
        collected_at=datetime(2026, 7, 1),
        roe=Decimal("0.18"),
    )

    result = DataCoverageEngine().evaluate(
        ticker="XYZ3.SA",
        asset_class="stock",
        latest_snapshot=snapshot,
        history=[snapshot],
        fundamentals_analysis=None,
        has_current_price=True,
        price_history_periods=1,
        today=_TODAY,
    )

    assert Decimal("0") < result.quality.score < Decimal("100")
    assert result.quality.classification == CLASSIFICATION_PARTIAL


def test_trap_detection_partial_data_reduces_score_but_still_runs():
    """Cenário 4 (trap detection com dados parciais): faltando histórico
    de 2+ períodos, o score de cobertura para Trap Detection cai mas
    continua calculável (não vira `None`/não aplicável)."""
    snapshot = FundamentalSnapshotResult(
        ticker="XYZ3.SA",
        period_end=date(2025, 12, 31),
        source="yahoo",
        collected_at=datetime(2026, 7, 1),
        pe_ratio=Decimal("10"),
        pb_ratio=Decimal("1.5"),
        roe=Decimal("0.15"),
        debt_to_ebitda=Decimal("2"),
        interest_coverage=Decimal("5"),
    )

    result = DataCoverageEngine().evaluate(
        ticker="XYZ3.SA",
        asset_class="stock",
        latest_snapshot=snapshot,
        history=[snapshot],  # só 1 período — abaixo do mínimo de histórico confiável
        fundamentals_analysis=None,
        has_current_price=True,
        price_history_periods=1,
        today=_TODAY,
    )

    assert result.trap_detection.score is not None
    assert result.trap_detection.score < Decimal("100")
    assert "Histórico com pelo menos 2 períodos" in result.trap_detection.missing_labels


def test_fii_trap_detection_uses_only_dividend_yield_not_pb_ratio():
    """Roteamento por classe de ativo: para FII/REIT, o Trap Detection
    Engine só olha Dividend Yield (não P/VP) — o relatório de cobertura
    tem que espelhar exatamente isso."""
    snapshot = FundamentalSnapshotResult(
        ticker="MXRF11.SA",
        period_end=date(2025, 12, 31),
        source="yahoo",
        collected_at=datetime(2026, 7, 1),
        pb_ratio=Decimal("1.0"),  # presente, mas NÃO deveria contar para trap_detection de FII
    )

    result = DataCoverageEngine().evaluate(
        ticker="MXRF11.SA",
        asset_class="fii",
        latest_snapshot=snapshot,
        history=[snapshot],
        fundamentals_analysis=None,
        has_current_price=True,
        price_history_periods=1,
        today=_TODAY,
    )

    # dividend_yield ausente é o único campo de snapshot considerado —
    # com ele faltando, o score de campo deve ser 0% (mesmo com pb_ratio presente).
    assert "Dividend Yield" in result.trap_detection.missing_labels
    assert "P/VP" not in result.trap_detection.missing_labels


def test_valuation_not_applicable_for_non_stock_classes():
    """Valuation Engine 2.0 só cobre ações — para outras classes, o
    Data Coverage Report deve marcar "não aplicável", nunca um score
    fabricado de 0."""
    result = DataCoverageEngine().evaluate(
        ticker="MXRF11.SA",
        asset_class="fii",
        latest_snapshot=None,
        history=[],
        fundamentals_analysis=None,
        has_current_price=True,
        price_history_periods=1,
        today=_TODAY,
    )

    assert result.valuation.score is None
    assert result.valuation.classification == CLASSIFICATION_NOT_APPLICABLE


def test_no_snapshot_at_all_never_breaks():
    """Ativo sem nenhum snapshot ainda: relatório deve rodar normalmente,
    tudo ausente, nunca uma exceção."""
    result = DataCoverageEngine().evaluate(
        ticker="NOVO.SA",
        asset_class="stock",
        latest_snapshot=None,
        history=[],
        fundamentals_analysis=None,
        has_current_price=False,
        price_history_periods=0,
        today=_TODAY,
    )

    assert result.decision_engine.score is not None
    assert result.decision_engine.classification == CLASSIFICATION_INSUFFICIENT
    assert len(result.missing_field_labels) == len(result.fields)


def test_stale_data_reduces_decision_engine_score():
    """Cenário 11 (stale data reduces confidence): um snapshot completo,
    mas coletado há mais de `STALE_DATA_THRESHOLD_DAYS`, deve ter o score
    do Decision Engine reduzido em relação ao mesmo snapshot recente —
    com o motivo explicando a razão (nunca um rótulo genérico)."""
    old_collected_at = datetime.combine(_TODAY, datetime.min.time()) - timedelta(
        days=STALE_DATA_THRESHOLD_DAYS + 30
    )
    stale_snapshot = _full_snapshot(collected_at=old_collected_at)
    fresh_snapshot = _full_snapshot()

    engine = DataCoverageEngine()
    stale_result = engine.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        latest_snapshot=stale_snapshot,
        history=[stale_snapshot],
        fundamentals_analysis=None,
        has_current_price=True,
        price_history_periods=1,
        today=_TODAY,
    )
    fresh_result = engine.evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        latest_snapshot=fresh_snapshot,
        history=[fresh_snapshot],
        fundamentals_analysis=None,
        has_current_price=True,
        price_history_periods=1,
        today=_TODAY,
    )

    assert stale_result.decision_engine.score < fresh_result.decision_engine.score
    assert "desatualizados" in stale_result.decision_engine.reason
    assert "desatualizado" in stale_result.summary


def test_recent_data_never_flagged_as_stale():
    snapshot = _full_snapshot(collected_at=datetime.combine(_TODAY, datetime.min.time()))
    result = DataCoverageEngine().evaluate(
        ticker="WEGE3.SA",
        asset_class="stock",
        latest_snapshot=snapshot,
        history=[snapshot],
        fundamentals_analysis=None,
        has_current_price=True,
        price_history_periods=1,
        today=_TODAY,
    )
    assert result.decision_engine.reason is None or "desatualizado" not in (
        result.decision_engine.reason or ""
    )
