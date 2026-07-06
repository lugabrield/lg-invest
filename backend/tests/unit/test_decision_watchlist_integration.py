"""Testes da integração opcional Watchlist/Radar no Decision Engine 3.0
(Sprint 25, Parte 2.5).

Cobre: `allow_watchlist_candidates=False` (default) preserva o
comportamento v3 anterior à Sprint 25 e nunca chama o Radar; com
`allow_watchlist_candidates=True`, só candidatos classificados como
"new_candidate" pelo Radar entram como `DecisionInput` novos (nunca
"monitor"/"avoid"/"blocked"/"insufficient_data", nunca um ticker que já
é posição); e o teto de alocação inicial (`max_new_asset_weight`, 25%
por padrão) nunca é ultrapassado, mesmo quando o candidato novo domina
o score. Usa `monkeypatch` no `RadarService.evaluate` para isolar esta
integração da lógica de classificação do Radar em si (já testada em
`test_radar_engine.py`/`test_radar_service.py`).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.schemas.radar import RadarClassificationResult, RadarEvaluation
from backend.app.services.decision_service import DecisionService


def _seed_portfolio_with_holding(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    stock = Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
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


def _seed_empty_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira vazia", base_currency="BRL")
    db.add(portfolio)
    db.commit()
    return portfolio.id


def _seed_new_asset(db, ticker: str, asset_class: str = "stock") -> None:
    asset = Asset(ticker=ticker, name=ticker, asset_class=asset_class, country="BR", currency="BRL")
    db.add(asset)
    db.commit()
    db.add(Price(asset_id=asset.id, date=date(2026, 6, 27), close=Decimal("10.00")))
    db.commit()


def _fake_radar_evaluation(
    ticker: str = "ITSA4.SA", asset_class: str = "stock", classification: str = "new_candidate"
) -> RadarEvaluation:
    return RadarEvaluation(
        candidates=[
            RadarClassificationResult(
                ticker=ticker,
                name=ticker,
                asset_class=asset_class,
                watchlist_status="candidate",
                is_current_holding=False,
                classification=classification,
                effective_score=Decimal("90"),
                score_source="lg_score",
                confidence=Decimal("0.9"),
                reasons=["score alto e status candidate"],
            )
        ]
    )


def _patch_radar(monkeypatch, evaluation: RadarEvaluation) -> None:
    monkeypatch.setattr(
        "backend.app.services.radar_service.RadarService.evaluate",
        lambda self, portfolio_id, config=None: evaluation,
    )


def test_build_inputs_v3_default_never_calls_radar_or_includes_new_asset(db_session):
    portfolio_id = _seed_portfolio_with_holding(db_session)
    _seed_new_asset(db_session, "ITSA4.SA")

    inputs = DecisionService(db_session).build_inputs_v3(portfolio_id)

    tickers = [i.ticker for i in inputs]
    assert "ITSA4.SA" not in tickers
    assert all(not i.is_new_from_watchlist for i in inputs)


def test_build_inputs_v3_with_allow_watchlist_includes_new_candidate(db_session, monkeypatch):
    portfolio_id = _seed_portfolio_with_holding(db_session)
    _seed_new_asset(db_session, "ITSA4.SA")
    _patch_radar(monkeypatch, _fake_radar_evaluation())

    inputs = DecisionService(db_session).build_inputs_v3(
        portfolio_id, allow_watchlist_candidates=True
    )

    new_item = next(i for i in inputs if i.ticker == "ITSA4.SA")
    assert new_item.is_new_from_watchlist is True
    assert new_item.current_weight == Decimal("0")


def test_build_inputs_v3_excludes_non_new_candidate_classifications(db_session, monkeypatch):
    portfolio_id = _seed_portfolio_with_holding(db_session)
    _seed_new_asset(db_session, "ITSA4.SA")
    _patch_radar(monkeypatch, _fake_radar_evaluation(classification="monitor"))

    inputs = DecisionService(db_session).build_inputs_v3(
        portfolio_id, allow_watchlist_candidates=True
    )

    assert "ITSA4.SA" not in [i.ticker for i in inputs]


def test_build_inputs_v3_never_duplicates_existing_holding(db_session, monkeypatch):
    portfolio_id = _seed_portfolio_with_holding(db_session)
    _patch_radar(monkeypatch, _fake_radar_evaluation(ticker="WEGE3.SA"))

    inputs = DecisionService(db_session).build_inputs_v3(
        portfolio_id, allow_watchlist_candidates=True
    )

    wege_entries = [i for i in inputs if i.ticker == "WEGE3.SA"]
    assert len(wege_entries) == 1
    assert wege_entries[0].is_new_from_watchlist is False


def test_recommend_v3_caps_new_asset_allocation(db_session, monkeypatch):
    """Regra central da Parte 2.5: mesmo com o único candidato elegível
    sendo um ativo novo com score dominante, a alocação nunca ultrapassa
    o teto de ativo novo (25% por padrão) — o resto fica não alocado."""
    portfolio_id = _seed_empty_portfolio(db_session)
    _seed_new_asset(db_session, "ITSA4.SA")
    _patch_radar(monkeypatch, _fake_radar_evaluation())

    result = DecisionService(db_session).recommend_v3(
        portfolio_id, Decimal("1000"), persist=False, allow_watchlist_candidates=True
    )

    assert len(result.items) == 1
    item = result.items[0]
    assert item.ticker == "ITSA4.SA"
    assert item.is_new_from_watchlist is True
    assert item.weight <= Decimal("0.25")
    assert result.allocated_amount <= Decimal("250.00")


def test_recommend_v3_without_flag_ignores_new_candidate_even_if_radar_finds_one(
    db_session, monkeypatch
):
    portfolio_id = _seed_portfolio_with_holding(db_session)
    _seed_new_asset(db_session, "ITSA4.SA")
    _patch_radar(monkeypatch, _fake_radar_evaluation())

    result = DecisionService(db_session).recommend_v3(portfolio_id, Decimal("1000"), persist=False)

    assert "ITSA4.SA" not in [i.ticker for i in result.items]


def test_recommend_v3_new_candidate_alert_never_mentions_selling(db_session, monkeypatch):
    portfolio_id = _seed_empty_portfolio(db_session)
    _seed_new_asset(db_session, "ITSA4.SA")
    _patch_radar(monkeypatch, _fake_radar_evaluation())

    result = DecisionService(db_session).recommend_v3(
        portfolio_id, Decimal("1000"), persist=False, allow_watchlist_candidates=True
    )

    all_text = result.explanation + " ".join(result.alerts)
    assert "vender" not in all_text.lower()
    assert any("candidato" in alert.lower() for alert in result.alerts)
