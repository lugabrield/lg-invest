"""Testes de ponta a ponta (ajuste Watchlist/Radar): confirma que trocar o
status de um ativo da Watchlist via `WatchlistService.set_status` reflete
de verdade na classificação do `RadarService` REAL (sem mock no próprio
`RadarService.evaluate`, diferente de `test_decision_watchlist_integration.py`,
que isola a integração no Decision Engine) e, a partir daí, no
`DecisionService.build_inputs_v3`/`recommend_v3`.

Só o cálculo de score (`LGScoreService`/`ConvictionScoreService`) é
substituído por um valor determinístico — isso é fronteira de dado
externo/fundamentos, não a lógica que este teste quer validar. Toda a
cadeia real (Watchlist -> Radar -> Decision Engine) roda sem mock.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.infrastructure.database.models import Portfolio
from backend.app.schemas.ids_methodology import ConvictionPillarResult, ConvictionScoreResult
from backend.app.schemas.lg_score import LGScoreResult, PillarResult
from backend.app.schemas.watchlist import WatchlistAssetCreate
from backend.app.services.conviction_score_service import ConvictionScoreService
from backend.app.services.decision_service import DecisionService
from backend.app.services.lg_score_service import LGScoreService
from backend.app.services.radar_service import RadarService
from backend.app.services.watchlist_service import WatchlistService


def _seed_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.commit()
    return portfolio.id


def _good_lg_result(ticker: str) -> LGScoreResult:
    return LGScoreResult(
        ticker=ticker,
        lg_score=Decimal("85"),
        quality=Decimal("85"),
        valuation=Decimal("85"),
        growth=Decimal("85"),
        risk=Decimal("85"),
        allocation=Decimal("85"),
        confidence=Decimal("0.95"),
        confidence_label="alta",
        classification="strong_buy",
        model_version="test",
        explanation=[
            PillarResult(
                name="quality", score=Decimal("85"), confidence=Decimal("0.95"), reasons=[]
            )
        ],
    )


def _good_conviction_result(ticker: str) -> ConvictionScoreResult:
    return ConvictionScoreResult(
        ticker=ticker,
        conviction_score=Decimal("85"),
        quality=Decimal("85"),
        valuation=Decimal("85"),
        growth=Decimal("85"),
        risk=Decimal("85"),
        capital_reinvestment=Decimal("85"),
        confidence=Decimal("0.95"),
        confidence_label="alta",
        classification="strong_buy",
        recommendation_hint="",
        model_version="test",
        explanation=[
            ConvictionPillarResult(
                name="quality", score=Decimal("85"), confidence=Decimal("0.95"), reasons=[]
            )
        ],
    )


@pytest.fixture
def deterministic_good_scores(monkeypatch):
    """Faz LG Score/Conviction Score sempre retornarem um score alto e
    confiança alta, para qualquer ticker — a fronteira de dado externo
    que este teste de integração real não quer exercitar."""
    monkeypatch.setattr(
        LGScoreService,
        "score_ticker",
        lambda self, ticker, current_weight=None, target_weight=None: _good_lg_result(ticker),
    )
    monkeypatch.setattr(
        ConvictionScoreService,
        "score_ticker",
        lambda self, ticker, current_weight=None, target_weight=None: _good_conviction_result(
            ticker
        ),
    )


def test_candidate_status_becomes_new_candidate_in_real_radar_service(
    db_session, deterministic_good_scores
):
    portfolio_id = _seed_portfolio(db_session)
    WatchlistService(db_session).add_watchlist_asset(
        portfolio_id,
        WatchlistAssetCreate(
            ticker="NVDC34.SA",
            name="Nvidia BDR",
            asset_class="stock",
            country="US",
            currency="USD",
            status="candidate",
        ),
    )

    evaluation = RadarService(db_session).evaluate(portfolio_id)

    candidate = next(c for c in evaluation.candidates if c.ticker == "NVDC34.SA")
    assert candidate.classification == "new_candidate"


def test_candidate_status_flows_into_build_inputs_v3_when_allowed(
    db_session, deterministic_good_scores
):
    portfolio_id = _seed_portfolio(db_session)
    WatchlistService(db_session).add_watchlist_asset(
        portfolio_id,
        WatchlistAssetCreate(
            ticker="NVDC34.SA",
            name="Nvidia BDR",
            asset_class="stock",
            country="US",
            currency="USD",
            status="candidate",
        ),
    )

    inputs = DecisionService(db_session).build_inputs_v3(
        portfolio_id, allow_watchlist_candidates=True
    )

    new_item = next(i for i in inputs if i.ticker == "NVDC34.SA")
    assert new_item.is_new_from_watchlist is True
    assert new_item.current_weight == Decimal("0")


def test_candidate_status_ignored_when_flag_is_off(db_session, deterministic_good_scores):
    portfolio_id = _seed_portfolio(db_session)
    WatchlistService(db_session).add_watchlist_asset(
        portfolio_id,
        WatchlistAssetCreate(
            ticker="NVDC34.SA",
            name="Nvidia BDR",
            asset_class="stock",
            country="US",
            currency="USD",
            status="candidate",
        ),
    )

    inputs = DecisionService(db_session).build_inputs_v3(portfolio_id)

    assert "NVDC34.SA" not in [i.ticker for i in inputs]


def test_watching_status_never_flows_into_build_inputs_v3_even_with_good_score(
    db_session, deterministic_good_scores
):
    """Regra central do ajuste: 'watching' continua monitoramento — só
    'candidate' pode virar 'new_candidate' e entrar no Aporte v3."""
    portfolio_id = _seed_portfolio(db_session)
    WatchlistService(db_session).add_watchlist_asset(
        portfolio_id,
        WatchlistAssetCreate(
            ticker="NVDC34.SA",
            name="Nvidia BDR",
            asset_class="stock",
            country="US",
            currency="USD",
            status="watching",
        ),
    )

    evaluation = RadarService(db_session).evaluate(portfolio_id)
    candidate = next(c for c in evaluation.candidates if c.ticker == "NVDC34.SA")
    assert candidate.classification != "new_candidate"

    inputs = DecisionService(db_session).build_inputs_v3(
        portfolio_id, allow_watchlist_candidates=True
    )
    assert "NVDC34.SA" not in [i.ticker for i in inputs]


@pytest.mark.parametrize("status", ["blocked", "discarded", "bought"])
def test_non_candidate_statuses_never_flow_into_build_inputs_v3(
    db_session, deterministic_good_scores, status
):
    portfolio_id = _seed_portfolio(db_session)
    WatchlistService(db_session).add_watchlist_asset(
        portfolio_id,
        WatchlistAssetCreate(
            ticker="NVDC34.SA",
            name="Nvidia BDR",
            asset_class="stock",
            country="US",
            currency="USD",
            status=status,
        ),
    )

    inputs = DecisionService(db_session).build_inputs_v3(
        portfolio_id, allow_watchlist_candidates=True
    )
    assert "NVDC34.SA" not in [i.ticker for i in inputs]


def test_promoting_watching_to_candidate_via_set_status_unlocks_new_candidate(
    db_session, deterministic_good_scores
):
    """Fluxo real reportado pelo usuário: cadastrar como 'watching' e
    depois promover para 'candidate' sem remover/recadastrar deve passar
    a valer para o Radar e para o Aporte v3 — mesma sessão, mesmo registro."""
    portfolio_id = _seed_portfolio(db_session)
    service = WatchlistService(db_session)
    created = service.add_watchlist_asset(
        portfolio_id,
        WatchlistAssetCreate(
            ticker="NVDC34.SA",
            name="Nvidia BDR",
            asset_class="stock",
            country="US",
            currency="USD",
            status="watching",
        ),
    )

    # Antes da promoção: nunca entra no Aporte v3.
    inputs_before = DecisionService(db_session).build_inputs_v3(
        portfolio_id, allow_watchlist_candidates=True
    )
    assert "NVDC34.SA" not in [i.ticker for i in inputs_before]

    service.set_status(portfolio_id, created.id, "candidate")

    # Depois da promoção: mesmo registro (não duplicado), agora elegível.
    assert len(service.list_watchlist_assets(portfolio_id)) == 1
    inputs_after = DecisionService(db_session).build_inputs_v3(
        portfolio_id, allow_watchlist_candidates=True
    )
    new_item = next(i for i in inputs_after if i.ticker == "NVDC34.SA")
    assert new_item.is_new_from_watchlist is True
