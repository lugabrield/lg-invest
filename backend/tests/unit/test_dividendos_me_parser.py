"""Testes de normalização pura do Dividendos.me (Sprint 23).

Cobre o parser de número/percentual em formato BR e US, e a
normalização de ticker por seção (Brasil, EUA, Cripto, Renda Fixa).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.integrations.dividendos_me.parser import (
    normalize_position,
    origin_for_section,
    parse_card_lines,
    parse_number,
    parse_percentage,
)
from backend.app.integrations.dividendos_me.schemas import (
    ORIGIN_B3,
    ORIGIN_CRYPTO,
    ORIGIN_INTERNATIONAL,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("R$ 1.234,56", Decimal("1234.56")),
        ("1.234,56", Decimal("1234.56")),
        ("1234.56", Decimal("1234.56")),
        ("US$ 1,234.56", Decimal("1234.56")),
        ("$1,234.56", Decimal("1234.56")),
        ("6,52", Decimal("6.52")),
        ("-2,40", Decimal("-2.40")),
        ("(2,40)", Decimal("-2.40")),
        ("+5,44", Decimal("5.44")),
        ("0", Decimal("0")),
        (None, None),
        ("", None),
        ("   ", None),
        ("abc", None),
    ],
)
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("6,52%", Decimal("0.0652")),
        ("-2,40%", Decimal("-0.0240")),
        (None, None),
    ],
)
def test_parse_percentage(raw, expected):
    assert parse_percentage(raw) == expected


def test_normalize_br_stock_gets_sa_suffix():
    result = normalize_position("WEGE3", section="brasil", subheader="Ações")
    assert result.ticker == "WEGE3.SA"
    assert result.asset_class == "stock"
    assert result.country == "BR"
    assert result.currency == "BRL"
    assert not result.review_required


def test_normalize_br_stock_already_with_suffix_not_duplicated():
    result = normalize_position("WEGE3.SA", section="brasil", subheader="Ações")
    assert result.ticker == "WEGE3.SA"


def test_normalize_br_fii():
    result = normalize_position("MXRF11", section="brasil", subheader="Fundos Imobiliários")
    assert result.ticker == "MXRF11.SA"
    assert result.asset_class == "fii"


def test_normalize_br_unknown_subheader_flags_review():
    result = normalize_position("XPTO11", section="brasil", subheader="Outra Coisa")
    assert result.review_required


def test_normalize_us_stock_has_no_sa_suffix():
    result = normalize_position("AAPL", section="eua", subheader="Ações")
    assert result.ticker == "AAPL"
    assert result.asset_class == "stock"
    assert result.country == "US"
    assert result.currency == "USD"
    assert not result.review_required


def test_normalize_us_stock_strips_sa_suffix_if_present():
    result = normalize_position("AAPL.SA", section="eua", subheader="Ações")
    assert result.ticker == "AAPL"


def test_normalize_us_etf():
    result = normalize_position("VOO", section="eua", subheader="ETFs")
    assert result.asset_class == "etf"


def test_normalize_us_reit():
    result = normalize_position("O", section="eua", subheader="REITs")
    assert result.asset_class == "reit"


def test_normalize_btc_becomes_btc_usd():
    result = normalize_position("BTC", section="criptomoedas")
    assert result.ticker == "BTC-USD"
    assert result.asset_class == "crypto"
    assert not result.review_required
    # Sprint 24: qualquer par "-USD" é USD — a moeda nunca é inferida pelo
    # símbolo visual "R$" da tela, e sim pelo próprio ticker/natureza do
    # ativo (correção sobre a Sprint 23.2, que estava errada).
    assert result.currency == "USD"


def test_normalize_unknown_crypto_flags_review():
    result = normalize_position("DOGE", section="criptomoedas")
    assert result.ticker == "DOGE-USD"
    assert result.review_required
    assert result.currency == "USD"


def test_normalize_tesouro_ipca_plus():
    result = normalize_position("TD IPCA+ 2045", section="renda_fixa", name="Tesouro IPCA+ 2045")
    assert result.ticker == "TESOURO-IPCA-2045"
    assert result.is_manual
    assert not result.review_required


def test_normalize_tesouro_selic():
    result = normalize_position("TD SELIC 2029", section="renda_fixa", name="Tesouro Selic 2029")
    assert result.ticker == "TESOURO-SELIC-2029"
    assert result.is_manual


def test_normalize_renda_fixa_not_tesouro_flags_review():
    result = normalize_position("CDB-XYZ", section="renda_fixa", name="CDB Banco XYZ")
    assert result.review_required
    assert result.is_manual


def test_normalize_empty_ticker_flags_review():
    result = normalize_position("", section="brasil", subheader="Ações")
    assert result.review_required


def test_normalize_unknown_section_flags_review():
    result = normalize_position("XYZ", section="uma_secao_nova")
    assert result.review_required


def test_origin_for_section():
    assert origin_for_section("brasil") == ORIGIN_B3
    assert origin_for_section("br") == ORIGIN_B3
    assert origin_for_section("eua") == ORIGIN_INTERNATIONAL
    # Sprint 23.2: cripto ganhou origem própria, nunca mais reaproveita
    # ORIGIN_INTERNATIONAL (evita confundir posições de cripto com
    # ações/ETFs/REITs internacionais).
    assert origin_for_section("criptomoedas") == ORIGIN_CRYPTO
    assert origin_for_section("cripto") == ORIGIN_CRYPTO
    assert origin_for_section("crypto") == ORIGIN_CRYPTO
    assert origin_for_section("renda_fixa") == ORIGIN_INTERNATIONAL


# --- Sprint 23.2: parse_card_lines / card de cripto de "Extrato" -----------


def test_parse_card_lines_discards_carteira_prefix_pair():
    # Card real confirmado ao vivo em "Criptomoedas → Extrato": o par
    # "Carteira:"/"Carteira Criptomoeda (Manual)" precede o nome do ativo
    # e nunca pode virar parte do nome (bug real corrigido nesta sprint).
    lines = [
        "Carteira:",
        "Carteira Criptomoeda (Manual)",
        "btc",
        "Quantidade:",
        "0,00584925",
        "Preço Médio:",
        "R$ 76.308,58",
        "Preço Atual:",
        "R$ 62.404,96",
        "Total:",
        "R$ 365,02",
        "Rentabilidade:",
        "-18,22",
        "Ver Operações",
    ]

    fields = parse_card_lines(lines)

    assert fields["__name"] == "btc"
    assert fields["quantity"] == "0,00584925"
    assert fields["average_price"] == "R$ 76.308,58"
    assert fields["current_price"] == "R$ 62.404,96"
    assert fields["current_value"] == "R$ 365,02"
    assert fields["return_pct"] == "-18,22"


def test_parse_card_lines_without_carteira_prefix_still_works():
    # Formato mais simples (sem o prefixo de carteira) continua funcionando
    # — o descarte do prefixo é aditivo, não uma exigência.
    lines = ["btc", "Quantidade:", "0,001", "Total:", "R$ 100,00", "Ver Operações"]

    fields = parse_card_lines(lines)
    assert fields["__name"] == "btc"
    assert fields["quantity"] == "0,001"
    assert fields["current_value"] == "R$ 100,00"
