"""Testes do Radar Engine puro (Sprint 25, Parte 2.4).

Cobre as 6 classificações e a regra de ouro: um ativo já na carteira
NUNCA recebe "avoid" (reservado a candidatos novos), mesmo com score
fraco — vira "monitor".
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.radar.engine import evaluate_radar
from backend.app.engines.radar.inputs import RadarCandidateInput


def _candidate(**overrides) -> RadarCandidateInput:
    base = dict(
        ticker="TEST3.SA",
        name="Teste SA",
        asset_class="stock",
        watchlist_status="candidate",
        is_current_holding=False,
        lg_score=Decimal("70"),
        conviction_score=Decimal("70"),
        confidence=Decimal("0.9"),
    )
    base.update(overrides)
    return RadarCandidateInput(**base)


def test_blocked_status_wins_over_everything(db_session=None):
    result = evaluate_radar([_candidate(watchlist_status="blocked", lg_score=Decimal("90"))])
    assert result.candidates[0].classification == "blocked"


def test_dimension_blocked_classifies_as_blocked():
    result = evaluate_radar(
        [_candidate(dimension_blocked=True, dimension_blocked_reason="classe fii no limite")]
    )
    assert result.candidates[0].classification == "blocked"
    assert "classe fii no limite" in result.candidates[0].reasons[0]


def test_no_score_is_insufficient_data():
    result = evaluate_radar([_candidate(lg_score=None, conviction_score=None)])
    assert result.candidates[0].classification == "insufficient_data"


def test_low_confidence_is_insufficient_data():
    result = evaluate_radar([_candidate(confidence=Decimal("0.2"))])
    assert result.candidates[0].classification == "insufficient_data"


def test_new_candidate_with_good_score_and_candidate_status():
    result = evaluate_radar(
        [_candidate(watchlist_status="candidate", lg_score=Decimal("75"), conviction_score=None)]
    )
    assert result.candidates[0].classification == "new_candidate"
    assert result.candidates[0].score_source == "conviction_score" or (
        result.candidates[0].effective_score == Decimal("75")
    )


def test_new_asset_poor_score_is_avoid():
    result = evaluate_radar(
        [
            _candidate(
                watchlist_status="candidate",
                lg_score=Decimal("30"),
                conviction_score=Decimal("30"),
            )
        ]
    )
    assert result.candidates[0].classification == "avoid"


def test_new_asset_middling_score_is_monitor():
    result = evaluate_radar(
        [
            _candidate(
                watchlist_status="watching",
                lg_score=Decimal("50"),
                conviction_score=Decimal("50"),
            )
        ]
    )
    assert result.candidates[0].classification == "monitor"


def test_watching_status_with_good_score_never_becomes_new_candidate():
    """Ajuste Watchlist/Radar: só o status 'candidate' pode virar
    'new_candidate' - 'watching' com o mesmo score bom continua
    'monitor' (o usuario ainda nao promoveu o ativo)."""
    result = evaluate_radar(
        [
            _candidate(
                watchlist_status="watching",
                lg_score=Decimal("90"),
                conviction_score=Decimal("90"),
                confidence=Decimal("0.95"),
            )
        ]
    )
    assert result.candidates[0].classification == "monitor"
    assert result.candidates[0].classification != "new_candidate"


def test_bought_status_with_good_score_never_becomes_new_candidate():
    """'bought' tambem nao e 'candidate' - nao deve virar candidato
    principal de aporte, mesmo com score bom (o registro na watchlist e
    so historico depois que o usuario sinalizou a compra)."""
    result = evaluate_radar(
        [
            _candidate(
                watchlist_status="bought",
                lg_score=Decimal("90"),
                conviction_score=Decimal("90"),
                confidence=Decimal("0.95"),
            )
        ]
    )
    assert result.candidates[0].classification != "new_candidate"


def test_current_holding_good_score_is_current_holding_candidate():
    result = evaluate_radar(
        [
            _candidate(
                is_current_holding=True,
                current_weight=Decimal("0.05"),
                watchlist_status=None,
                lg_score=Decimal("75"),
                conviction_score=Decimal("75"),
            )
        ]
    )
    assert result.candidates[0].classification == "current_holding_candidate"


def test_current_holding_poor_score_is_monitor_never_avoid():
    """Regra de ouro: um ativo já na carteira nunca vira 'avoid' — mesmo
    com score fraco, é sempre 'monitor' (nunca sugestão de venda)."""
    result = evaluate_radar(
        [
            _candidate(
                is_current_holding=True,
                current_weight=Decimal("0.05"),
                watchlist_status=None,
                lg_score=Decimal("20"),
                conviction_score=Decimal("20"),
            )
        ]
    )
    assert result.candidates[0].classification == "monitor"
    assert result.candidates[0].classification != "avoid"


def test_conviction_score_preferred_over_lg_score():
    result = evaluate_radar([_candidate(lg_score=Decimal("10"), conviction_score=Decimal("80"))])
    assert result.candidates[0].score_source == "conviction_score"
    assert result.candidates[0].effective_score == Decimal("80")


def test_lg_score_fallback_when_no_conviction_score():
    result = evaluate_radar([_candidate(lg_score=Decimal("65"), conviction_score=None)])
    assert result.candidates[0].score_source == "lg_score"
    assert result.candidates[0].effective_score == Decimal("65")


def test_no_classification_ever_mentions_selling():
    """Regra de ouro geral do projeto: nenhuma classificação do Radar
    sugere venda, em nenhum cenário."""
    scenarios = [
        _candidate(watchlist_status="blocked"),
        _candidate(dimension_blocked=True),
        _candidate(lg_score=None, conviction_score=None),
        _candidate(confidence=Decimal("0.1")),
        _candidate(is_current_holding=True, lg_score=Decimal("10"), conviction_score=Decimal("10")),
        _candidate(
            watchlist_status="candidate", lg_score=Decimal("20"), conviction_score=Decimal("20")
        ),
        _candidate(
            watchlist_status="candidate", lg_score=Decimal("50"), conviction_score=Decimal("50")
        ),
        _candidate(
            watchlist_status="candidate", lg_score=Decimal("90"), conviction_score=Decimal("90")
        ),
    ]
    result = evaluate_radar(scenarios)
    for candidate_result in result.candidates:
        for reason in candidate_result.reasons:
            assert "vender" not in reason.lower()


def test_evaluation_helpers_count_and_filter_by_classification():
    result = evaluate_radar(
        [
            _candidate(ticker="A", watchlist_status="blocked"),
            _candidate(
                ticker="B",
                watchlist_status="candidate",
                lg_score=Decimal("90"),
                conviction_score=Decimal("90"),
            ),
        ]
    )
    assert result.count_by_classification("blocked") == 1
    assert result.count_by_classification("new_candidate") == 1
    assert len(result.by_classification("blocked")) == 1
    assert result.by_classification("blocked")[0].ticker == "A"
