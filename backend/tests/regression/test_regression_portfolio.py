"""Testes de regressão (Volume 18, seção 9).

Compara a saída atual dos serviços sobre carteiras de exemplo com um
baseline salvo em expected_regression.json. Se uma engine mudar, estes
testes falham — a mudança precisa ser intencional e o baseline
atualizado conscientemente.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.services.lg_score_service import LGScoreService
from backend.app.services.portfolio_service import PortfolioService
from backend.tests.regression._helpers import build_session_from_fixture

_EXPECTED = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "expected_regression.json").read_text(
        encoding="utf-8"
    )
)

_CASES = [
    ("sample_portfolio_brazil.json", "brazil"),
    ("sample_portfolio_global.json", "global"),
]


@pytest.mark.parametrize("fixture,key", _CASES)
def test_portfolio_summary_matches_baseline(fixture, key):
    session, pid = build_session_from_fixture(fixture)
    try:
        summary = PortfolioService(session).get_summary(pid)
        expected = _EXPECTED[key]["portfolio"]

        assert summary.total_value == Decimal(expected["total_value"])
        assert summary.total_cost == Decimal(expected["total_cost"])
        assert summary.largest_position_ticker == expected["largest_position_ticker"]
        for ticker, value in expected["positions"].items():
            actual = next(p.position_value for p in summary.positions if p.ticker == ticker)
            assert actual == Decimal(value)
    finally:
        session.close()


@pytest.mark.parametrize("fixture,key", _CASES)
def test_lg_score_ranking_matches_baseline(fixture, key):
    session, pid = build_session_from_fixture(fixture)
    try:
        scores = LGScoreService(session).rank_portfolio(pid)
        expected = _EXPECTED[key]["lg_scores"]
        actual = {r.ticker: round(float(r.lg_score), 1) for r in scores}
        assert actual == expected
    finally:
        session.close()


@pytest.mark.parametrize("fixture,key", _CASES)
def test_weights_sum_to_one(fixture, key):
    session, pid = build_session_from_fixture(fixture)
    try:
        summary = PortfolioService(session).get_summary(pid)
        total = sum((p.weight for p in summary.positions), start=Decimal("0"))
        assert total == pytest.approx(Decimal("1"))
    finally:
        session.close()
