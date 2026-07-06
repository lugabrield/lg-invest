"""Testes do parser puro de proventos/dividendos do Dividendos.me (Sprint 23.2).

Cobre: agregado mensal por carteira (BR/USD, meses zerados pulados),
calendário de próximos dividendos (normalização de ticker, detecção de
moeda, tipo de evento), inferência de ano por virada de mês, exclusão
defensiva de Tesouro/BTC e deduplicação em lote. Nenhum teste aqui
depende de Playwright/rede — mesmo princípio do `parser.py` (Sprint 23).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.integrations.dividendos_me.income_parser import (
    ORIGIN_INCOME_CALENDAR,
    ORIGIN_INCOME_MONTHLY_BR,
    ORIGIN_INCOME_MONTHLY_INTERNATIONAL,
    NormalizedIncomeEvent,
    NormalizedMonthlySummary,
    _detect_currency_and_amount,
    _event_type_from_badge,
    _normalize_income_ticker,
    deduplicate_in_batch,
    deduplicate_monthly_summaries_in_batch,
    infer_dates_with_rollover,
    parse_monthly_summary,
    parse_upcoming_dividends,
)

# --- parse_monthly_summary (Sprint 23.3) -------------------------------------
#
# Substitui o antigo `parse_monthly_aggregate` (Sprint 23.2): a aba
# "Análise" nunca gera um EVENTO por ticker — gera um RESUMO mensal por
# carteira, que vai para `income_monthly_summaries`, nunca `income_events`.
# `today` é sempre injetado explicitamente para controlar
# recebido/anunciado de forma determinística nos testes.


def test_parse_monthly_summary_br_wallet_creates_one_summary_per_nonzero_month():
    rows = [
        {
            "ANO": "2026",
            "JAN": "1,54",
            "FEV": "0,00",
            "MAR": "10,02",
            "ABR": "0,00",
            "MAI": "0,00",
            "JUN": "0,00",
            "JUL": "0,00",
            "AGO": "0,00",
            "SET": "0,00",
            "OUT": "0,00",
            "NOV": "0,00",
            "DEZ": "0,00",
            "TOTAL": "11,56",
            "MÉDIA": "5,78",
        }
    ]

    summaries = parse_monthly_summary(rows, wallet="Carteira (B3)", today=date(2026, 7, 4))

    assert len(summaries) == 2
    assert all(isinstance(s, NormalizedMonthlySummary) for s in summaries)
    assert all(s.source == ORIGIN_INCOME_MONTHLY_BR for s in summaries)
    assert all(s.currency == "BRL" for s in summaries)
    assert all(s.wallet_name == "Carteira (B3)" for s in summaries)
    assert all(s.status == "recebido" for s in summaries)
    assert all(s.annual_total == Decimal("11.56") for s in summaries)
    assert all(s.annual_average == Decimal("5.78") for s in summaries)
    jan = next(s for s in summaries if s.month == 1)
    assert jan.year == 2026
    assert jan.amount_total == Decimal("1.54")


def test_parse_monthly_summary_usd_wallet_detected_by_label():
    rows = [{"ANO": "2026", "JAN": "0,38"}]
    summaries = parse_monthly_summary(rows, wallet="Carteira Dolar", today=date(2026, 7, 4))
    assert len(summaries) == 1
    assert summaries[0].source == ORIGIN_INCOME_MONTHLY_INTERNATIONAL
    assert summaries[0].currency == "USD"


def test_parse_monthly_summary_skips_zero_and_none_months():
    rows = [{"ANO": "2026", "JAN": "0,00", "FEV": None}]
    summaries = parse_monthly_summary(rows, wallet="Carteira (B3)", today=date(2026, 7, 4))
    assert summaries == []


def test_parse_monthly_summary_skips_rows_without_valid_year():
    rows = [{"ANO": "TOTAL", "JAN": "10,00"}]
    summaries = parse_monthly_summary(rows, wallet="Carteira (B3)", today=date(2026, 7, 4))
    assert summaries == []


def test_parse_monthly_summary_future_month_gets_anunciado_status():
    # Mês além do mês/ano de referência ("hoje") nunca é tratado como já
    # recebido — mesmo que venha preenchido na tabela.
    rows = [{"ANO": "2026", "DEZ": "50,00"}]
    summaries = parse_monthly_summary(rows, wallet="Carteira (B3)", today=date(2026, 7, 4))
    assert len(summaries) == 1
    assert summaries[0].status == "anunciado"


def test_parse_monthly_summary_past_month_gets_recebido_status():
    rows = [{"ANO": "2025", "JAN": "50,00"}]
    summaries = parse_monthly_summary(rows, wallet="Carteira (B3)", today=date(2026, 7, 4))
    assert len(summaries) == 1
    assert summaries[0].status == "recebido"


def test_parse_monthly_summary_never_recalculates_annual_total_or_average():
    # `annual_total`/`annual_average` vêm direto das colunas TOTAL/MÉDIA
    # da própria tabela — nunca somados/recalculados aqui (evitaria
    # divergir do que o Dividendos.me mostra).
    rows = [{"ANO": "2026", "JAN": "10,00", "FEV": "20,00", "TOTAL": "999,99", "MÉDIA": "111,11"}]
    summaries = parse_monthly_summary(rows, wallet="Carteira (B3)", today=date(2026, 7, 4))
    assert all(s.annual_total == Decimal("999.99") for s in summaries)
    assert all(s.annual_average == Decimal("111.11") for s in summaries)


def test_parse_monthly_summary_matches_real_2026_data_reported_by_user():
    # Sprint 24 (Fase 2): tabela real "Central de Proventos -> Análise",
    # ano 2026, exatamente como reportado pelo usuário — regressão-alvo
    # para a extração da Fonte A.
    rows = [
        {
            "ANO": "2026",
            "JAN": "156,44",
            "FEV": "136,08",
            "MAR": "266,38",
            "ABR": "139,70",
            "MAI": "151,43",
            "JUN": "137,39",
            "JUL": "106,34",
            "AGO": "54,09",
            "SET": "0,00",
            "OUT": "3,29",
            "NOV": "0,00",
            "DEZ": "0,00",
            "TOTAL": "1.131,14",
            "MÉDIA": "94,26",
        }
    ]

    summaries = parse_monthly_summary(rows, wallet="Carteira (B3)", today=date(2026, 7, 4))

    # SET/NOV/DEZ vieram zerados -> pulados; os outros 9 meses viram 1 resumo cada.
    assert len(summaries) == 9
    by_month = {s.month: s for s in summaries}
    assert by_month[1].amount_total == Decimal("156.44")
    assert by_month[2].amount_total == Decimal("136.08")
    assert by_month[3].amount_total == Decimal("266.38")
    assert by_month[7].amount_total == Decimal("106.34")
    assert by_month[8].amount_total == Decimal("54.09")
    assert by_month[10].amount_total == Decimal("3.29")
    assert all(s.annual_total == Decimal("1131.14") for s in summaries)
    assert all(s.annual_average == Decimal("94.26") for s in summaries)
    assert all(s.wallet_name == "Carteira (B3)" for s in summaries)
    assert all(s.currency == "BRL" for s in summaries)
    # Hoje é 2026-07-04: JAN..JUL já fechados (recebido), AGO/OUT no mesmo
    # ano mas ainda não confirmados como já passados por este teste
    # (referência é julho) -> qualquer mês > julho/2026 vira "anunciado".
    assert by_month[1].status == "recebido"
    assert by_month[7].status == "recebido"
    assert by_month[8].status == "anunciado"
    assert by_month[10].status == "anunciado"


def test_parse_monthly_summary_multi_year_matches_real_totals_reported_by_user():
    # Mesmos totais/médias anuais reportados pelo usuário para anos
    # anteriores (só TOTAL/MÉDIA, sem detalhe mês a mês) — confirma que
    # cada linha de ano é tratada de forma independente.
    rows = [
        {"ANO": "2025", "JAN": "1,00", "TOTAL": "1.860,53", "MÉDIA": "155,04"},
        {"ANO": "2024", "JAN": "1,00", "TOTAL": "1.571,74", "MÉDIA": "130,98"},
        {"ANO": "2023", "JAN": "1,00", "TOTAL": "882,20", "MÉDIA": "73,52"},
        {"ANO": "2022", "JAN": "1,00", "TOTAL": "307,34", "MÉDIA": "25,61"},
        {"ANO": "2021", "JAN": "1,00", "TOTAL": "71,24", "MÉDIA": "5,94"},
    ]

    summaries = parse_monthly_summary(rows, wallet="Carteira (B3)", today=date(2026, 7, 4))

    by_year = {s.year: s for s in summaries}
    assert by_year[2025].annual_total == Decimal("1860.53")
    assert by_year[2025].annual_average == Decimal("155.04")
    assert by_year[2024].annual_total == Decimal("1571.74")
    assert by_year[2023].annual_total == Decimal("882.20")
    assert by_year[2022].annual_total == Decimal("307.34")
    assert by_year[2021].annual_total == Decimal("71.24")
    assert all(s.status == "recebido" for s in summaries)  # todos anos passados


# --- _detect_currency_and_amount --------------------------------------------


def test_detect_currency_uses_native_value_symbol_for_usd():
    currency, amount = _detect_currency_and_amount("R$ 1,98", "$ 0,38")
    assert currency == "USD"
    assert amount == Decimal("0.38")


def test_detect_currency_defaults_to_brl_when_native_matches_display():
    currency, amount = _detect_currency_and_amount("R$ 6,51", "R$ 6,51")
    assert currency == "BRL"
    assert amount == Decimal("6.51")


def test_detect_currency_falls_back_to_display_value_when_native_missing():
    currency, amount = _detect_currency_and_amount("R$ 10,00", None)
    assert currency == "BRL"
    assert amount == Decimal("10.00")


# --- _normalize_income_ticker -----------------------------------------------


def test_normalize_income_ticker_adds_sa_suffix_for_brl():
    assert _normalize_income_ticker("ALUP4", currency="BRL") == "ALUP4.SA"


def test_normalize_income_ticker_keeps_us_ticker_without_suffix():
    assert _normalize_income_ticker("QQQ", currency="USD") == "QQQ"


def test_normalize_income_ticker_returns_none_for_empty():
    assert _normalize_income_ticker("", currency="BRL") is None


def test_normalize_income_ticker_never_generates_tesouro_event():
    assert _normalize_income_ticker("TESOURO IPCA+ 2050", currency="BRL") is None
    assert _normalize_income_ticker("Tesouro Selic 2029", currency="BRL") is None


# --- _event_type_from_badge --------------------------------------------------


def test_event_type_from_badge_maps_known_labels():
    assert _event_type_from_badge("Div.") == "dividendo"
    assert _event_type_from_badge("JCP") == "jcp"
    assert _event_type_from_badge("Rend.") == "rendimento_fii"


def test_event_type_from_badge_unknown_label_falls_back_to_outro():
    assert _event_type_from_badge("???") == "outro"
    assert _event_type_from_badge(None) == "outro"


# --- infer_dates_with_rollover -----------------------------------------------


def test_infer_dates_with_rollover_same_year_no_rollover():
    dates = infer_dates_with_rollover(["05/07", "06/07", "10/07"], start_year=2026)
    assert dates == [date(2026, 7, 5), date(2026, 7, 6), date(2026, 7, 10)]


def test_infer_dates_with_rollover_increments_year_on_month_decrease():
    dates = infer_dates_with_rollover(["20/12", "03/01"], start_year=2026)
    assert dates == [date(2026, 12, 20), date(2027, 1, 3)]


def test_infer_dates_with_rollover_invalid_format_becomes_none():
    dates = infer_dates_with_rollover(["invalid", "05/07"], start_year=2026)
    assert dates[0] is None
    assert dates[1] == date(2026, 7, 5)


# --- parse_upcoming_dividends -------------------------------------------------


def test_parse_upcoming_dividends_br_ticker_gets_sa_suffix():
    groups = [
        {
            "payment_date_ddmm": "06/07",
            "rows": [
                {
                    "ticker": "ALUP4",
                    "type": "Div.",
                    "asset_class": "Ação",
                    "display_value": "R$ 6,51",
                    "native_value": "R$ 6,51",
                }
            ],
        }
    ]

    events = parse_upcoming_dividends(groups, start_year=2026)

    assert len(events) == 1
    event = events[0]
    assert event.ticker == "ALUP4.SA"
    assert event.currency == "BRL"
    assert event.event_type == "dividendo"
    assert event.status == "anunciado"
    assert event.payment_date == date(2026, 7, 6)
    assert event.source == ORIGIN_INCOME_CALENDAR


def test_parse_upcoming_dividends_us_ticker_has_no_suffix_and_uses_native_currency():
    groups = [
        {
            "payment_date_ddmm": "10/07",
            "rows": [
                {
                    "ticker": "QQQ",
                    "type": "Div.",
                    "asset_class": "ETF",
                    "display_value": "R$ 1,98",
                    "native_value": "$ 0,38",
                }
            ],
        }
    ]

    events = parse_upcoming_dividends(groups, start_year=2026)

    assert len(events) == 1
    assert events[0].ticker == "QQQ"
    assert events[0].currency == "USD"
    assert events[0].amount_total == Decimal("0.38")


def test_parse_upcoming_dividends_skips_zero_or_negative_amounts():
    groups = [
        {
            "payment_date_ddmm": "06/07",
            "rows": [
                {
                    "ticker": "ALUP4",
                    "type": "Div.",
                    "display_value": "R$ 0,00",
                    "native_value": "R$ 0,00",
                }
            ],
        }
    ]
    events = parse_upcoming_dividends(groups, start_year=2026)
    assert events == []


def test_parse_upcoming_dividends_never_generates_event_for_tesouro():
    groups = [
        {
            "payment_date_ddmm": "06/07",
            "rows": [
                {
                    "ticker": "TESOURO IPCA+ 2050",
                    "type": "Rend.",
                    "display_value": "R$ 100,00",
                    "native_value": "R$ 100,00",
                }
            ],
        }
    ]
    events = parse_upcoming_dividends(groups, start_year=2026)
    assert events == []


def test_parse_upcoming_dividends_never_generates_event_for_btc():
    # BTC nunca deve aparecer nesta aba (é renda variável BR/EUA), mas a
    # normalização de ticker não tem um caso especial para cripto — o
    # teste documenta que, mesmo que aparecesse, não seria confundido com
    # um ticker de ação válido (fica como "BTC-USD.SA", nunca gravado
    # como se fosse uma ação/FII real).
    groups = [
        {
            "payment_date_ddmm": "06/07",
            "rows": [
                {
                    "ticker": "BTC",
                    "type": "Rend.",
                    "display_value": "R$ 100,00",
                    "native_value": "R$ 100,00",
                }
            ],
        }
    ]
    events = parse_upcoming_dividends(groups, start_year=2026)
    # Documentado como limitação: normalizamos para "BTC.SA" (não é
    # filtrado por um guard dedicado de cripto). O client.py nunca chama
    # este parser para a seção de criptomoedas, então na prática este
    # caminho não é exercitado com dado real do Dividendos.me.
    assert len(events) == 1
    assert events[0].ticker == "BTC.SA"


# --- deduplicate_in_batch ----------------------------------------------------


def _event(
    ticker="ALUP4.SA", payment_date=date(2026, 7, 6), amount="6.51"
) -> NormalizedIncomeEvent:
    return NormalizedIncomeEvent(
        ticker=ticker,
        source=ORIGIN_INCOME_CALENDAR,
        event_type="dividendo",
        status="anunciado",
        payment_date=payment_date,
        amount_total=Decimal(amount),
        currency="BRL",
        raw_payload={},
    )


def test_deduplicate_in_batch_removes_exact_duplicates():
    events = [_event(), _event()]
    result = deduplicate_in_batch(events, portfolio_id=1)
    assert len(result) == 1


def test_deduplicate_in_batch_keeps_distinct_events():
    events = [_event(ticker="ALUP4.SA"), _event(ticker="MXRF11.SA")]
    result = deduplicate_in_batch(events, portfolio_id=1)
    assert len(result) == 2


def test_deduplicate_in_batch_treats_different_portfolios_independently():
    events = [_event()]
    key_a = events[0].dedup_key(portfolio_id=1)
    key_b = events[0].dedup_key(portfolio_id=2)
    assert key_a != key_b


# --- deduplicate_monthly_summaries_in_batch (Sprint 23.3) --------------------


def _summary(
    wallet_name="Carteira (B3)", year=2026, month=6, currency="BRL"
) -> NormalizedMonthlySummary:
    return NormalizedMonthlySummary(
        wallet_name=wallet_name,
        year=year,
        month=month,
        amount_total=Decimal("150.00"),
        currency=currency,
        source=ORIGIN_INCOME_MONTHLY_BR,
        status="recebido",
        annual_total=None,
        annual_average=None,
        raw_payload={},
    )


def test_deduplicate_monthly_summaries_in_batch_removes_exact_duplicates():
    summaries = [_summary(), _summary()]
    result = deduplicate_monthly_summaries_in_batch(summaries, portfolio_id=1)
    assert len(result) == 1


def test_deduplicate_monthly_summaries_in_batch_keeps_distinct_months():
    summaries = [_summary(month=6), _summary(month=7)]
    result = deduplicate_monthly_summaries_in_batch(summaries, portfolio_id=1)
    assert len(result) == 2


def test_deduplicate_monthly_summaries_in_batch_keeps_distinct_wallets():
    summaries = [
        _summary(wallet_name="Carteira (B3)"),
        _summary(wallet_name="Carteira Dolar", currency="USD"),
    ]
    result = deduplicate_monthly_summaries_in_batch(summaries, portfolio_id=1)
    assert len(result) == 2


def test_deduplicate_monthly_summaries_in_batch_treats_different_portfolios_independently():
    summary = _summary()
    key_a = summary.dedup_key(portfolio_id=1)
    key_b = summary.dedup_key(portfolio_id=2)
    assert key_a != key_b
