"""Testes do filtro de elegibilidade do Decision Engine (Volume 7 §7 e §9)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.decision.eligibility import filter_eligible
from backend.app.engines.decision.inputs import DEFAULT_CONFIG, DecisionInput


def _input(ticker, weight="0.10") -> DecisionInput:
    return DecisionInput(
        ticker=ticker,
        asset_class="stock",
        lg_score=Decimal("80"),
        confidence=Decimal("0.8"),
        current_weight=Decimal(weight),
    )


def test_blocked_asset_is_ignored():
    candidates = [_input("WEGE3.SA"), _input("VOO")]
    eligible, ignored = filter_eligible(candidates, {"VOO"}, DEFAULT_CONFIG)
    tickers = {e.ticker for e in eligible}
    assert "VOO" not in tickers
    assert any(i.ticker == "VOO" and "bloqueado" in i.reason for i in ignored)
    assert next(i for i in ignored if i.ticker == "VOO").block_source == "bloqueio_manual"


def test_overconcentrated_asset_is_ignored():
    # peso 0.40 > limite 0.30 -> ignorado
    candidates = [_input("WEGE3.SA", weight="0.40"), _input("ITUB4.SA", weight="0.10")]
    eligible, ignored = filter_eligible(candidates, set(), DEFAULT_CONFIG)
    tickers = {e.ticker for e in eligible}
    assert "WEGE3.SA" not in tickers
    assert "ITUB4.SA" in tickers
    assert any("sobreconcentrado" in i.reason for i in ignored)
    assert ignored[0].block_source == "sobreconcentracao"


def test_all_eligible_when_no_restrictions():
    candidates = [_input("WEGE3.SA"), _input("ITUB4.SA")]
    eligible, ignored = filter_eligible(candidates, set(), DEFAULT_CONFIG)
    assert len(eligible) == 2
    assert ignored == []
