"""Normalização pura de proventos/dividendos extraídos do Dividendos.me
(Sprint 23.2 / 23.3).

Nenhuma função aqui acessa rede, banco ou DOM — só transforma texto
bruto (já extraído pelo `client.py` via `page.evaluate`) em DTOs
tipados. Mesmo princípio do `parser.py` (Sprint 23): puro e testável
sem Playwright.

Teto de dado real (ver diagnóstico entregue ao usuário e
`docs/DIVIDENDOS_ME_INTEGRATION.md`): a conta investigada — mesmo com
Premium — não expõe um evento por ativo com data+tipo+valor-por-cota já
PAGO. As únicas fontes confiáveis encontradas foram:

1. Aba "Análise" (tabela ano x mês, uma por carteira BR/Dólar): total já
   RECEBIDO/ANUNCIADO por mês, agregado por carteira — sem ticker.
   `parse_monthly_summary`. Correção Sprint 23.3: isso NUNCA é um evento
   (não tem data exata nem ticker) — é um RESUMO mensal, e vive em
   `income_monthly_summaries`, nunca em `income_events`.
2. Aba "Próximos Dividendos" (lista agrupada por dia): por ticker, mas é
   um CALENDÁRIO FUTURO/ANUNCIADO — nunca "recebido". `parse_upcoming_dividends`.
   Continua gravado em `income_events` (é o único uso real dessa tabela
   a partir da Sprint 23.3).
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from backend.app.integrations.dividendos_me.parser import parse_number

# Rótulos de mês em português, na ordem em que aparecem na tabela "Análise"
# do Dividendos.me — usados só para saber quais colunas de uma linha são
# meses (as demais, "ANO"/"TOTAL"/"MÉDIA", são ignoradas).
MONTH_LABELS_PT: tuple[str, ...] = (
    "JAN",
    "FEV",
    "MAR",
    "ABR",
    "MAI",
    "JUN",
    "JUL",
    "AGO",
    "SET",
    "OUT",
    "NOV",
    "DEZ",
)

# Rótulos de tipo de provento vistos ao vivo na aba "Próximos Dividendos"
# ("Div.", "JCP", "Rend.") -> vocabulário fechado de `IncomeEvent.event_type`.
_EVENT_TYPE_BY_BADGE = {
    "div": "dividendo",
    "div.": "dividendo",
    "dividendo": "dividendo",
    "jcp": "jcp",
    "rend": "rendimento_fii",
    "rend.": "rendimento_fii",
    "rendimento": "rendimento_fii",
    "amortização": "amortizacao",
    "amortizacao": "amortizacao",
}

# Origens (Position.source/IncomeEvent.source/IncomeMonthlySummary.source
# seguem a mesma convenção do Sprint 23): uma por sub-fonte de provento,
# para nunca misturar o agregado mensal (sem ticker, tabela própria desde
# a Sprint 23.3) com o calendário futuro (com ticker, `income_events`) no
# mesmo "balde" de deduplicação.
ORIGIN_INCOME_MONTHLY_BR = "dividendos_me:income_monthly:brasil"
ORIGIN_INCOME_MONTHLY_INTERNATIONAL = "dividendos_me:income_monthly:internacional"
ORIGIN_INCOME_CALENDAR = "dividendos_me:income_calendar"

# Status de uma linha mensal: "recebido" para mês já fechado (passado ou
# mês atual, já que o Dividendos.me só preenche o valor quando o provento
# já caiu), "anunciado" para mês futuro dentro do ano corrente exibido na
# tabela — nunca inventamos um valor para mês futuro, só classificamos
# como o status esperado quando o mês já vem preenchido com um valor > 0
# (ex.: provento já comunicado/anunciado antes do pagamento).
INCOME_MONTHLY_STATUSES = ("recebido", "anunciado")

_DDMM_PATTERN = re.compile(r"^(\d{1,2})/(\d{1,2})$")


class NormalizedIncomeEvent:
    """DTO leve (não é `BaseModel` Pydantic de propósito — puramente
    interno ao parser, convertido para `IncomeEvent`/schemas pelo
    `income_service.py`) representando um evento de CALENDÁRIO já
    normalizado (ver módulo docstring — nunca mais usado para o agregado
    mensal desde a Sprint 23.3, que tem `NormalizedMonthlySummary` própria)."""

    def __init__(
        self,
        *,
        ticker: str | None,
        source: str,
        event_type: str,
        status: str,
        payment_date: date | None,
        amount_total: Decimal,
        currency: str,
        raw_payload: dict,
    ) -> None:
        self.ticker = ticker
        self.source = source
        self.event_type = event_type
        self.status = status
        self.payment_date = payment_date
        self.amount_total = amount_total
        self.currency = currency
        self.raw_payload = raw_payload

    def dedup_key(self, portfolio_id: int) -> tuple:
        return (
            portfolio_id,
            self.ticker,
            self.payment_date,
            self.event_type,
            self.amount_total,
            self.source,
        )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"NormalizedIncomeEvent(ticker={self.ticker!r}, event_type={self.event_type!r}, "
            f"payment_date={self.payment_date!r}, amount_total={self.amount_total}, "
            f"currency={self.currency!r})"
        )


class NormalizedMonthlySummary:
    """DTO leve (Sprint 23.3) representando UMA linha mensal já normalizada
    da aba "Análise" — nunca um evento (não tem ticker nem data exata),
    por isso vive em `income_monthly_summaries`, separada de `income_events`.
    `annual_total`/`annual_average` vêm direto das colunas TOTAL/MÉDIA da
    própria tabela (nunca recalculados aqui — evita divergir do que o
    Dividendos.me mostra)."""

    def __init__(
        self,
        *,
        wallet_name: str,
        year: int,
        month: int,
        amount_total: Decimal,
        currency: str,
        source: str,
        status: str,
        annual_total: Decimal | None,
        annual_average: Decimal | None,
        raw_payload: dict,
    ) -> None:
        self.wallet_name = wallet_name
        self.year = year
        self.month = month
        self.amount_total = amount_total
        self.currency = currency
        self.source = source
        self.status = status
        self.annual_total = annual_total
        self.annual_average = annual_average
        self.raw_payload = raw_payload

    def dedup_key(self, portfolio_id: int) -> tuple:
        return (portfolio_id, self.wallet_name, self.year, self.month, self.currency, self.source)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"NormalizedMonthlySummary(wallet_name={self.wallet_name!r}, year={self.year}, "
            f"month={self.month}, amount_total={self.amount_total}, status={self.status!r})"
        )


def _wallet_origin(wallet: str) -> str:
    key = (wallet or "").strip().lower()
    if "dolar" in key or "dólar" in key or "internacional" in key or "usd" in key:
        return ORIGIN_INCOME_MONTHLY_INTERNATIONAL
    return ORIGIN_INCOME_MONTHLY_BR


def _wallet_currency(wallet: str) -> str:
    return "USD" if _wallet_origin(wallet) == ORIGIN_INCOME_MONTHLY_INTERNATIONAL else "BRL"


def parse_monthly_summary(
    year_rows: list[dict], *, wallet: str, today: date | None = None
) -> list[NormalizedMonthlySummary]:
    """Converte as linhas da tabela "Análise" (uma por ano) num resumo
    mensal por carteira — NUNCA um evento por ticker (Sprint 23.3: essa
    tabela é agregada por carteira, não quebrada por ativo, e não tem
    data exata de pagamento — só ano/mês).

    `year_rows`: lista de dicts como `{"ANO": "2026", "JAN": "156,44",
    ..., "OUT": "3,29", "TOTAL": "1.131,14", "MÉDIA": "94,26"}`, extraídos
    por `client.py` de um `<table>` real (thead/tbody). Meses com R$ 0,00
    (ou ausentes) são pulados — não representam um provento real.

    `today`: injetável para teste; usa a data real por padrão. Meses
    estritamente no futuro (ano/mês maior que hoje) nunca deveriam
    aparecer preenchidos na tabela real, mas se aparecerem viram status
    "anunciado" em vez de "recebido" — nunca inventamos um recebimento
    para o futuro.
    """
    reference = today or date.today()
    source = _wallet_origin(wallet)
    currency = _wallet_currency(wallet)
    summaries: list[NormalizedMonthlySummary] = []

    for row in year_rows:
        year_raw = row.get("ANO")
        year = int(str(year_raw).strip()) if year_raw and str(year_raw).strip().isdigit() else None
        if year is None:
            continue

        annual_total = parse_number(row.get("TOTAL"))
        annual_average = parse_number(row.get("MÉDIA"))

        for month_index, label in enumerate(MONTH_LABELS_PT, start=1):
            amount = parse_number(row.get(label))
            if amount is None or amount == 0:
                continue

            is_future = (year, month_index) > (reference.year, reference.month)
            status = "anunciado" if is_future else "recebido"

            summaries.append(
                NormalizedMonthlySummary(
                    wallet_name=wallet,
                    year=year,
                    month=month_index,
                    amount_total=amount,
                    currency=currency,
                    source=source,
                    status=status,
                    annual_total=annual_total,
                    annual_average=annual_average,
                    raw_payload={
                        "kind": "monthly_summary_by_wallet",
                        "wallet": wallet,
                        "year": year,
                        "month": month_index,
                    },
                )
            )
    return summaries


def _event_type_from_badge(badge: str | None) -> str:
    key = (badge or "").strip().lower()
    return _EVENT_TYPE_BY_BADGE.get(key, "outro")


def _detect_currency_and_amount(
    display_value: str | None, native_value: str | None
) -> tuple[str, Decimal | None]:
    """O card de "Próximos Dividendos" mostra dois valores: um convertido
    para BRL (`display_value`, sempre em negrito) e um na moeda nativa do
    ativo (`native_value`, cinza/menor). Para tickers BR os dois batem
    (mesma moeda); para tickers dos EUA o segundo vem com "$" e um valor
    menor (ex.: QQQ: "R$ 1,98" / "$ 0,38"). Detectamos a moeda pelo
    símbolo do valor nativo e usamos ESSE valor como `amount_total` —
    nunca o convertido, para não fixar uma taxa de câmbio num evento
    histórico."""
    text = (native_value or display_value or "").strip()
    currency = "USD" if text.startswith("$") and not text.startswith("R$") else "BRL"
    amount = parse_number(native_value if native_value is not None else display_value)
    return currency, amount


def _normalize_income_ticker(raw_ticker: str, *, currency: str) -> str | None:
    """Normaliza o ticker de um evento de provento — mesma convenção do
    resto da LG INVEST (Sprint 22/23): tickers BR levam sufixo `.SA`,
    tickers dos EUA ficam como estão. Nunca gera evento para
    cripto/Tesouro (ver módulo docstring) — ambos ficam fora do vocabulário
    de tickers de renda variável que esta aba mostra, mas a checagem abaixo
    é uma rede de segurança defensiva mesmo assim."""
    ticker = (raw_ticker or "").strip().upper()
    if not ticker:
        return None
    if "TESOURO" in ticker:
        return None
    if currency == "BRL" and not ticker.endswith(".SA"):
        ticker = f"{ticker}.SA"
    return ticker


def infer_dates_with_rollover(ddmm_list: list[str], *, start_year: int) -> list[date | None]:
    """Infere o ano de uma sequência de datas "DD/MM" (formato do
    Dividendos.me, sem ano) assumindo que a lista já vem em ordem
    cronológica crescente (como exibida na tela, agrupada por dia de
    pagamento). O ano é incrementado sempre que o mês de uma entrada for
    MENOR que o mês da entrada anterior (virada de ano, ex.: Dez -> Jan).
    Entradas em formato inválido viram `None` (nunca inventam uma data)."""
    result: list[date | None] = []
    year = start_year
    last_month: int | None = None

    for raw in ddmm_list:
        match = _DDMM_PATTERN.match((raw or "").strip())
        if not match:
            result.append(None)
            continue
        day, month = int(match.group(1)), int(match.group(2))
        if last_month is not None and month < last_month:
            year += 1
        last_month = month
        try:
            result.append(date(year, month, day))
        except ValueError:
            result.append(None)
    return result


def parse_upcoming_dividends(
    day_groups: list[dict], *, start_year: int
) -> list[NormalizedIncomeEvent]:
    """Converte os grupos-por-dia da aba "Próximos Dividendos" em eventos
    "anunciado" (calendário futuro, nunca "recebido" — ver módulo
    docstring). `day_groups`: lista de
    `{"payment_date_ddmm": "06/07", "rows": [{"ticker": "ALUP4", "type":
    "Div.", "display_value": "R$ 6,51", "native_value": "R$ 6,51"}, ...]}`.

    Este é o ÚNICO fluxo que ainda grava em `income_events` desde a
    Sprint 23.3 — é um calendário futuro por ticker, nunca histórico
    mensal agregado (ver `parse_monthly_summary`, que vai para
    `income_monthly_summaries`)."""
    ddmm_list = [g.get("payment_date_ddmm") for g in day_groups]
    dates = infer_dates_with_rollover(ddmm_list, start_year=start_year)

    events: list[NormalizedIncomeEvent] = []
    for group, payment_date in zip(day_groups, dates, strict=False):
        for row in group.get("rows", []):
            currency, amount = _detect_currency_and_amount(
                row.get("display_value"), row.get("native_value")
            )
            if amount is None or amount <= 0:
                continue
            ticker = _normalize_income_ticker(row.get("ticker", ""), currency=currency)
            if ticker is None:
                continue
            events.append(
                NormalizedIncomeEvent(
                    ticker=ticker,
                    source=ORIGIN_INCOME_CALENDAR,
                    event_type=_event_type_from_badge(row.get("type")),
                    status="anunciado",
                    payment_date=payment_date,
                    amount_total=amount,
                    currency=currency,
                    raw_payload={
                        "kind": "upcoming_dividend",
                        "raw_ticker": row.get("ticker"),
                        "asset_class_badge": row.get("asset_class"),
                        "payment_date_ddmm": group.get("payment_date_ddmm"),
                    },
                )
            )
    return events


def deduplicate_in_batch(
    events: list[NormalizedIncomeEvent], *, portfolio_id: int
) -> list[NormalizedIncomeEvent]:
    """Remove duplicatas dentro da MESMA extração (ex.: um artefato de
    re-render que faz uma linha aparecer duplicada no DOM) usando a
    mesma chave de deduplicação usada contra o banco. Nunca substitui a
    checagem contra o banco (`IncomeEventRepository.exists_duplicate`),
    só evita inserir a mesma linha duas vezes na mesma rodada."""
    seen: set[tuple] = set()
    result: list[NormalizedIncomeEvent] = []
    for event in events:
        key = event.dedup_key(portfolio_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(event)
    return result


def deduplicate_monthly_summaries_in_batch(
    summaries: list[NormalizedMonthlySummary], *, portfolio_id: int
) -> list[NormalizedMonthlySummary]:
    """Mesmo princípio de `deduplicate_in_batch`, mas para resumos mensais
    (chave própria: carteira + ano + mês + moeda + fonte, sem ticker/data
    exata — ver `NormalizedMonthlySummary.dedup_key`)."""
    seen: set[tuple] = set()
    result: list[NormalizedMonthlySummary] = []
    for summary in summaries:
        key = summary.dedup_key(portfolio_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(summary)
    return result
