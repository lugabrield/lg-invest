"""Testes de `_ranking()` da tela Inteligência (Sprint 22).

Cobre a correção do bug relatado: BTC-USD aparecendo em "mais baratos
por valuation" com score 100 (proxy v1 de preço, não uma leitura real
de valuation para cripto). `_ranking` é uma função pura (sem `st.*`
dentro dela), então é testável isoladamente mesmo sendo parte de um
módulo de página Streamlit — mesma convenção de import já usada em
`test_streamlit_smoke.py`.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.schemas.intelligence_dashboard import AssetIntelligence
from frontend.streamlit_app.pages_impl.inteligencia import _ranking


def _asset(
    ticker,
    asset_class,
    *,
    valuation=None,
    quality=None,
    growth=None,
    risk=None,
    classification="hold",
    has_score=True,
) -> AssetIntelligence:
    return AssetIntelligence(
        ticker=ticker,
        asset_class=asset_class,
        current_weight=Decimal("0.1"),
        has_conviction_score=has_score,
        conviction_score=Decimal("50") if has_score else None,
        classification=classification if has_score else None,
        valuation=valuation,
        quality=quality,
        growth=growth,
        risk=risk,
    )


def test_crypto_excluded_from_valuation_ranking():
    assets = [
        _asset("BTC-USD", "crypto", valuation=Decimal("100")),
        _asset("WEGE3.SA", "stock", valuation=Decimal("70")),
    ]
    ranked = _ranking(assets, "valuation", reverse=True)
    tickers = [a.ticker for a in ranked]
    assert "BTC-USD" not in tickers
    assert "WEGE3.SA" in tickers


def test_etf_excluded_from_growth_ranking():
    assets = [
        _asset("VOO", "etf", growth=Decimal("90")),
        _asset("WEGE3.SA", "stock", growth=Decimal("60")),
    ]
    ranked = _ranking(assets, "growth", reverse=True)
    tickers = [a.ticker for a in ranked]
    assert "VOO" not in tickers
    assert "WEGE3.SA" in tickers


def test_bond_excluded_from_valuation_ranking():
    assets = [
        _asset("TESOURO-IPCA-2050", "bond", valuation=Decimal("95")),
        _asset("BTLG11.SA", "fii", valuation=Decimal("80")),
    ]
    ranked = _ranking(assets, "valuation", reverse=True)
    tickers = [a.ticker for a in ranked]
    assert "TESOURO-IPCA-2050" not in tickers
    assert "BTLG11.SA" in tickers


def test_insufficient_data_asset_excluded_from_any_ranking():
    assets = [
        _asset("NOPE9.SA", "stock", valuation=Decimal("99"), has_score=False),
        _asset("WEGE3.SA", "stock", valuation=Decimal("70")),
    ]
    ranked = _ranking(assets, "valuation", reverse=True)
    tickers = [a.ticker for a in ranked]
    assert "NOPE9.SA" not in tickers
    assert "WEGE3.SA" in tickers


def test_risk_ranking_has_no_class_filter_crypto_included():
    # Risco não tem entrada em _RANKING_APPLICABLE_CLASSES: cripto
    # legitimamente participa (classificação "alto" é política real,
    # não fallback de proxy) — ver docstring de `_ranking`.
    assets = [
        _asset("BTC-USD", "crypto", risk=Decimal("95")),
        _asset("WEGE3.SA", "stock", risk=Decimal("40")),
    ]
    ranked = _ranking(assets, "risk", reverse=True)
    tickers = [a.ticker for a in ranked]
    assert "BTC-USD" in tickers


def test_none_field_value_excluded():
    assets = [
        _asset("SEM-VALUATION", "stock", valuation=None),
        _asset("WEGE3.SA", "stock", valuation=Decimal("70")),
    ]
    ranked = _ranking(assets, "valuation", reverse=True)
    tickers = [a.ticker for a in ranked]
    assert "SEM-VALUATION" not in tickers
    assert "WEGE3.SA" in tickers


def test_top_n_respected():
    assets = [_asset(f"T{i}.SA", "stock", valuation=Decimal(str(i))) for i in range(10)]
    ranked = _ranking(assets, "valuation", reverse=True, top_n=3)
    assert len(ranked) == 3
    assert [a.ticker for a in ranked] == ["T9.SA", "T8.SA", "T7.SA"]
