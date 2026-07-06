"""Testes do Data Quality Engine (puro, sem banco/rede) — Sprint 22.

Cobre especificamente a correção do Sprint 22: um ativo manual (ex.:
Tesouro Direto) nunca deve ser classificado como "ausente"/"estimado",
mesmo que a linha de `Price` mais recente não tenha `source="manual"`
ou não exista ainda.
"""

from __future__ import annotations

from backend.app.engines.data_quality.engine import (
    build_asset_data_quality,
    classify_fundamentals_status,
    classify_price_status,
    classify_score_confidence,
    classify_valuation_status,
)

# --- classify_price_status: prioridade do is_manual ------------------------


def test_manual_asset_is_always_manual_even_with_yahoo_source():
    # Caso hipotético: linha de Price existente com source != "manual",
    # mas o ativo está marcado como manual — is_manual tem prioridade.
    assert classify_price_status("yahoo", False, is_manual=True) == "manual"


def test_manual_asset_is_manual_even_without_any_price_row():
    # Tesouro Direto recém-cadastrado, sem preço salvo ainda: nunca "ausente".
    assert classify_price_status(None, True, is_manual=True) == "manual"


def test_manual_asset_with_manual_price_row_is_manual():
    assert classify_price_status("manual", False, is_manual=True) == "manual"


def test_non_manual_asset_keeps_original_behavior():
    assert classify_price_status(None, False, is_manual=False) == "ausente"
    assert classify_price_status(None, True, is_manual=False) == "estimado"
    assert classify_price_status("manual", False, is_manual=False) == "manual"
    assert classify_price_status("yahoo", False, is_manual=False) == "automatico"


# --- build_asset_data_quality: issues coerentes com ativo manual -----------


def test_manual_asset_without_price_gets_helpful_issue_not_ausente():
    dq = build_asset_data_quality(
        ticker="TESOURO-IPCA-2050",
        asset_class="bond",
        price_source=None,
        is_price_estimated=True,
        fundamentals_fields_available=0,
        fundamentals_fields_total=28,
        fundamentals_applicable=False,
        valuation_classification=None,
        valuation_applicable=False,
        score_confidence_label=None,
        is_manual=True,
    )
    assert dq.price_status == "manual"
    # A mensagem genérica de "ausente" (usada só quando price_status ==
    # "ausente") não deve aparecer — só a variante específica de ativo
    # manual sem preço ainda.
    assert not any(issue == "sem preço cadastrado" for issue in dq.issues)
    assert any("ativo manual sem preço cadastrado ainda" in issue for issue in dq.issues)


def test_manual_asset_with_price_has_no_price_issue():
    dq = build_asset_data_quality(
        ticker="TESOURO-IPCA-2050",
        asset_class="bond",
        price_source="manual",
        is_price_estimated=False,
        fundamentals_fields_available=0,
        fundamentals_fields_total=28,
        fundamentals_applicable=False,
        valuation_classification=None,
        valuation_applicable=False,
        score_confidence_label=None,
        is_manual=True,
    )
    assert dq.price_status == "manual"
    assert not any("sem preço" in issue for issue in dq.issues)


def test_non_manual_asset_without_price_still_shows_estimado():
    # Garante que a correção não afeta ativos automáticos legítimos.
    dq = build_asset_data_quality(
        ticker="WEGE3.SA",
        asset_class="stock",
        price_source=None,
        is_price_estimated=True,
        fundamentals_fields_available=0,
        fundamentals_fields_total=28,
        fundamentals_applicable=True,
        valuation_classification=None,
        valuation_applicable=True,
        score_confidence_label=None,
        is_manual=False,
    )
    assert dq.price_status == "estimado"
    assert any("preço estimado" in issue for issue in dq.issues)


# --- Demais classificadores (sem alteração nesta sprint, cobertura básica) --


def test_classify_fundamentals_status_not_applicable():
    assert classify_fundamentals_status(0, 0, applicable=False) == "nao_aplicavel"


def test_classify_valuation_status_not_applicable():
    assert classify_valuation_status(None, applicable=False) == "nao_aplicavel"


def test_classify_score_confidence_unknown_label_is_indisponivel():
    assert classify_score_confidence("desconhecido") == "indisponivel"
