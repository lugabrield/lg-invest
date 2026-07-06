"""Testes do Decision Engine v1 ponta a ponta (Volume 20 prompt 10).

Engine pura: sem banco, sem rede.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.engines.decision.engine import recommend
from backend.app.engines.decision.inputs import DecisionInput


def _candidate(ticker, lg, weight, conf="0.8") -> DecisionInput:
    return DecisionInput(
        ticker=ticker,
        asset_class="stock",
        lg_score=Decimal(str(lg)),
        confidence=Decimal(conf),
        current_weight=Decimal(str(weight)),
    )


def _portfolio() -> list[DecisionInput]:
    return [
        _candidate("WEGE3.SA", 88, "0.20"),
        _candidate("ITUB4.SA", 79, "0.25"),
        _candidate("VOO", 84, "0.15"),
    ]


def test_recommend_1000_distributes_and_explains():
    result = recommend(_portfolio(), Decimal("1000"))
    assert result.allocated_amount <= Decimal("1000")
    assert len(result.items) >= 1
    assert result.explanation  # tem texto
    for item in result.items:
        assert item.reasons  # justificativa por ativo


def test_allocation_sum_does_not_exceed_amount():
    result = recommend(_portfolio(), Decimal("1000"))
    total = sum((i.amount for i in result.items), start=Decimal("0"))
    assert total <= Decimal("1000")
    assert total == result.allocated_amount


def test_blocked_asset_not_recommended():
    result = recommend(_portfolio(), Decimal("1000"), blocked={"VOO"})
    tickers = {i.ticker for i in result.items}
    assert "VOO" not in tickers
    assert any(ig.ticker == "VOO" for ig in result.ignored)


def test_overconcentrated_asset_not_recommended():
    candidates = [
        _candidate("WEGE3.SA", 88, "0.45"),  # acima de 0.30 -> ignorado
        _candidate("ITUB4.SA", 80, "0.10"),
    ]
    result = recommend(candidates, Decimal("1000"))
    tickers = {i.ticker for i in result.items}
    assert "WEGE3.SA" not in tickers
    assert any("sobreconcentrado" in ig.reason for ig in result.ignored)


def test_zero_amount_raises():
    with pytest.raises(ValueError):
        recommend(_portfolio(), Decimal("0"))


def test_no_eligible_assets_returns_empty_with_alert():
    result = recommend(_portfolio(), Decimal("1000"), blocked={"WEGE3.SA", "ITUB4.SA", "VOO"})
    assert result.items == []
    assert any("Nenhum ativo elegível" in a for a in result.alerts)


def test_low_confidence_triggers_alert():
    low_conf = [
        _candidate("WEGE3.SA", 88, "0.10", conf="0.2"),
        _candidate("ITUB4.SA", 80, "0.10", conf="0.2"),
    ]
    result = recommend(low_conf, Decimal("1000"))
    assert result.confidence_label == "Baixa"
    # Sprint 21: alerta passou a nomear os tickers afetados em vez de um
    # aviso genérico — ver decision/engine.py::_build_alerts.
    assert any(
        "baixa confiança" in a and "WEGE3.SA" in a and "ITUB4.SA" in a for a in result.alerts
    )


def test_audit_log_is_complete():
    result = recommend(_portfolio(), Decimal("1000"), blocked={"VOO"})
    audit = result.audit
    assert audit.contribution_amount == Decimal("1000")
    assert "VOO" in audit.blocked_tickers
    assert audit.model_version == "decision_v1"
    assert audit.weights["lg_score"] == 0.50


def test_higher_score_gets_more_capital():
    # Mesma concentração; LG Score maior deve receber pelo menos tanto quanto o menor.
    candidates = [
        _candidate("HIGH", 95, "0.10"),
        _candidate("LOW", 50, "0.10"),
    ]
    result = recommend(candidates, Decimal("1000"))
    amounts = {i.ticker: i.amount for i in result.items}
    assert amounts["HIGH"] >= amounts["LOW"]
