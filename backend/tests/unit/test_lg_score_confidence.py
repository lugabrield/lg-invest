"""Testes do Confidence Score (Volume 6 §12; Volume 18 §8)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.lg_score.confidence import confidence_label
from backend.app.engines.lg_score.engine import calculate_lg_score
from backend.app.engines.lg_score.inputs import ScoreInput


def _h(n: int) -> list[Decimal]:
    # Série crescente de n pontos.
    return [Decimal(str(10 + i)) for i in range(n)]


def test_short_history_has_lower_confidence_than_long():
    short = calculate_lg_score(ScoreInput(ticker="X", asset_class="stock", price_history=_h(3)))
    long = calculate_lg_score(ScoreInput(ticker="X", asset_class="stock", price_history=_h(60)))
    assert long.confidence > short.confidence


def test_no_history_low_confidence():
    result = calculate_lg_score(ScoreInput(ticker="X", asset_class="stock", price_history=[]))
    assert result.confidence_label == "Baixa"


def test_confidence_within_zero_one():
    result = calculate_lg_score(ScoreInput(ticker="X", asset_class="stock", price_history=_h(30)))
    assert Decimal("0") <= result.confidence <= Decimal("1")


def test_confidence_label_thresholds():
    assert confidence_label(Decimal("0.85")) == "Alta"
    assert confidence_label(Decimal("0.70")) == "Média"
    assert confidence_label(Decimal("0.50")) == "Baixa"
