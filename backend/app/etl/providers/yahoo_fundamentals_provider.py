"""Provedor de fundamentos via Yahoo Finance (yfinance).

Única classe que acessa fundamentos via yfinance. Import tardio dentro
dos métodos, para permitir mock nos testes sem a biblioteca instalada
(mesmo padrão de `yahoo_provider.py`).

Cobertura é inconsistente por natureza da fonte gratuita (Volume 4
§17): FIIs, small caps e ativos fora de ações/ETFs costumam trazer
`info` quase vazio, e nomes de campos podem mudar sem aviso entre
versões do yfinance. Todo campo ausente ou não numérico vira `None`,
nunca uma exceção — quem decide como comunicar isso ao usuário é a
camada de schema/serviço, não este provider.

`dividendYield`/`payoutRatio` são normalmente devolvidos pelo yfinance
como fração (ex.: 0.03 = 3%), mas foi observado na prática (Sprint 22 —
BTLG11 exibindo Dividend Yield de 950%) que, para alguns tickers,
sobretudo FIIs/ativos fora de ações americanas, o yfinance retorna
esses campos já multiplicados por 100 (ex.: 9.5 em vez de 0.095). Todo
campo percentual lido de `info` passa por `_normalize_percentage()`
antes de virar `FundamentalData`, que corrige essa inconsistência de
escala sem distorcer valores que já chegam como fração — ver a função
para o critério exato.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from backend.app.core.logging import get_logger
from backend.app.etl.contracts.fundamental_data import FundamentalData
from backend.app.etl.providers.fundamentals_provider import FundamentalsProvider

logger = get_logger("lg_invest.provider.yahoo_fundamentals")

# yfinance normalmente devolve até ~4 anos de demonstrativos anuais
# numa única chamada — não é preciso esperar o calendário real para
# ter uma série útil para CAGR (Sprint 14).
_MAX_HISTORY_PERIODS = 4


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        if value != value:  # NaN
            return None
    except TypeError:
        pass
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 - valor não numérico devolvido pelo provider
        return None


def _ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


# Acima deste limiar (100%), um campo que deveria ser uma fração 0..1
# quase certamente foi devolvido pelo yfinance já em escala percentual
# (ex.: 9.5 em vez de 0.095) — dividend yield, payout ratio e margens
# acima de 100% são praticamente inexistentes na prática, então esse
# limiar é seguro para os campos onde `_normalize_percentage` é usada.
# Limitação conhecida e documentada: ROE/ROA de empresas com alavancagem
# extrema podem, em casos raros e legítimos, superar 100% — esses casos
# ficariam incorretamente divididos por 100 por esta heurística. Ver
# docs/DATA_QUALITY.md.
_PERCENTAGE_SANITY_THRESHOLD = Decimal("1")


def _normalize_percentage(value: Decimal | None) -> Decimal | None:
    """Normaliza um campo que deveria ser fração 0..1 (ex.: 0.095 = 9,5%).

    Não distorce valores que já chegam corretamente como fração (`<= 1`
    em módulo) — só divide por 100 quando o valor já parece estar em
    escala percentual (`> 1`), corrigindo a inconsistência observada em
    alguns tickers/classes (Sprint 22) sem exigir uma lista de exceções
    por ticker.
    """
    if value is None:
        return None
    if abs(value) > _PERCENTAGE_SANITY_THRESHOLD:
        return value / Decimal("100")
    return value


def _row_value(frame, row_label: str, column) -> Decimal | None:
    """Lê uma célula de um DataFrame de demonstrativo (yfinance), com
    ausência de linha/coluna tratada como dado indisponível."""
    if frame is None:
        return None
    try:
        if row_label not in frame.index:
            return None
        return _to_decimal(frame.loc[row_label, column])
    except Exception:  # noqa: BLE001 - qualquer inconsistência vira ausência de dado
        return None


# Faixa sã de alíquota efetiva de imposto — fora disso (crédito fiscal,
# prejuízo pontual, etc.) o número não representa uma taxa "normal" o
# suficiente para compor NOPAT com confiança, então é descartado (vira
# None) em vez de gerar um ROIC distorcido (Sprint 26, Fase 1).
_MIN_SANE_TAX_RATE = Decimal("0")
_MAX_SANE_TAX_RATE = Decimal("1")


def _effective_tax_rate(income, col) -> Decimal | None:
    tax_provision = _row_value(income, "Tax Provision", col)
    pretax_income = _row_value(income, "Pretax Income", col)
    if tax_provision is None or pretax_income in (None, Decimal("0")):
        return None
    rate = tax_provision / pretax_income
    if not (_MIN_SANE_TAX_RATE <= rate <= _MAX_SANE_TAX_RATE):
        return None
    return rate


def _roic_and_coverage(
    income, balance, col, ebit: Decimal | None, total_debt: Decimal | None, cash: Decimal | None
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """ROIC (NOPAT / capital investido) e cobertura de juros (EBIT /
    despesa financeira) a partir de linhas reais dos demonstrativos —
    nunca aproximados de um único indicador solto. Devolve
    `(total_equity, roic, interest_coverage)`; qualquer componente
    ausente ou fora de faixa sã faz o resultado correspondente ficar
    `None` (Volume 18 §8: nunca inventar dado ausente)."""
    total_equity = _row_value(balance, "Stockholders Equity", col) or _row_value(
        balance, "Common Stock Equity", col
    )

    roic = None
    tax_rate = _effective_tax_rate(income, col)
    has_roic_inputs = (
        ebit is not None
        and tax_rate is not None
        and total_debt is not None
        and total_equity is not None
        and cash is not None
    )
    if has_roic_inputs:
        invested_capital = total_debt + total_equity - cash
        if invested_capital not in (None, Decimal("0")):
            nopat = ebit * (Decimal("1") - tax_rate)
            roic = nopat / invested_capital

    interest_coverage = None
    interest_expense = _row_value(income, "Interest Expense", col)
    if ebit is not None and interest_expense not in (None, Decimal("0")):
        interest_coverage = ebit / abs(interest_expense)

    return total_equity, roic, interest_coverage


class YahooFundamentalsProvider(FundamentalsProvider):
    name = "yahoo_fundamentals"

    def get_latest(self, ticker: str) -> FundamentalData | None:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
        if not info:
            logger.warning("Sem 'info' retornado para %s.", ticker)
            return None

        collected = datetime.now(UTC)
        period_end_raw = info.get("mostRecentQuarter")
        period_end = (
            date.fromtimestamp(period_end_raw)
            if isinstance(period_end_raw, (int, float))
            else date.today()
        )

        total_debt = _to_decimal(info.get("totalDebt"))
        total_cash = _to_decimal(info.get("totalCash"))
        net_debt = (
            total_debt - total_cash if total_debt is not None and total_cash is not None else None
        )

        ebitda = _to_decimal(info.get("ebitda"))
        debt_to_ebitda = None
        if total_debt is not None and ebitda not in (None, Decimal("0")):
            debt_to_ebitda = total_debt / ebitda

        # Sprint 26, Fase 1: patrimônio líquido aproximado por valor
        # patrimonial por ação x nº de ações (ambos publicados pelo
        # yfinance) — mesma base usada pelo próprio `priceToBook`, não é
        # um valor inventado. `roic`/`interest_coverage` NÃO são
        # calculados aqui: exigiriam taxa efetiva de imposto e despesa
        # financeira, que `.info` não expõe de forma confiável; ficam
        # restritos aos snapshots históricos anuais (`get_history`),
        # onde vêm de linhas reais dos demonstrativos.
        book_value_per_share = _to_decimal(info.get("bookValue"))
        shares_outstanding = _to_decimal(info.get("sharesOutstanding"))
        total_equity = (
            book_value_per_share * shares_outstanding
            if book_value_per_share is not None and shares_outstanding is not None
            else None
        )

        return FundamentalData(
            ticker=ticker,
            period_end=period_end,
            source_name=self.name,
            collected_at=collected,
            roe=_normalize_percentage(_to_decimal(info.get("returnOnEquity"))),
            roa=_normalize_percentage(_to_decimal(info.get("returnOnAssets"))),
            net_margin=_normalize_percentage(_to_decimal(info.get("profitMargins"))),
            ebitda_margin=_normalize_percentage(_to_decimal(info.get("ebitdaMargins"))),
            revenue=_to_decimal(info.get("totalRevenue")),
            net_income=_to_decimal(info.get("netIncomeToCommon")),
            ebitda=ebitda,
            ebit=_to_decimal(info.get("ebit")),
            free_cash_flow=_to_decimal(info.get("freeCashflow")),
            net_debt=net_debt,
            debt_to_ebitda=debt_to_ebitda,
            pe_ratio=_to_decimal(info.get("trailingPE")),
            pb_ratio=_to_decimal(info.get("priceToBook")),
            ev_ebitda=_to_decimal(info.get("enterpriseToEbitda")),
            dividend_yield=_normalize_percentage(_to_decimal(info.get("dividendYield"))),
            payout_ratio=_normalize_percentage(_to_decimal(info.get("payoutRatio"))),
            eps=_to_decimal(info.get("trailingEps")),
            revenue_per_share=_to_decimal(info.get("revenuePerShare")),
            beta=_to_decimal(info.get("beta")),
            market_cap=_to_decimal(info.get("marketCap")),
            enterprise_value=_to_decimal(info.get("enterpriseValue")),
            forward_pe=_to_decimal(info.get("forwardPE")),
            operating_margin=_normalize_percentage(_to_decimal(info.get("operatingMargins"))),
            total_debt=total_debt,
            total_cash=total_cash,
            operating_cash_flow=_to_decimal(info.get("operatingCashflow")),
            gross_profit=_to_decimal(info.get("grossProfits")),
            shares_outstanding=shares_outstanding,
            total_equity=total_equity,
        )

    def get_history(self, ticker: str) -> list[FundamentalData]:
        import yfinance as yf

        t = yf.Ticker(ticker)
        income = getattr(t, "income_stmt", None)
        balance = getattr(t, "balance_sheet", None)
        cashflow = getattr(t, "cashflow", None)

        if income is None or income.empty:
            logger.warning("Sem demonstrativo de resultados para %s.", ticker)
            return []

        collected = datetime.now(UTC)
        results: list[FundamentalData] = []
        columns = list(income.columns)[:_MAX_HISTORY_PERIODS]

        for col in columns:
            period_end = col.date() if hasattr(col, "date") else date.fromisoformat(str(col)[:10])

            revenue = _row_value(income, "Total Revenue", col)
            net_income = _row_value(income, "Net Income", col)
            ebitda = _row_value(income, "EBITDA", col)
            ebit = _row_value(income, "EBIT", col) or _row_value(income, "Operating Income", col)

            free_cash_flow = _row_value(cashflow, "Free Cash Flow", col)
            total_debt = _row_value(balance, "Total Debt", col)
            cash = _row_value(balance, "Cash And Cash Equivalents", col)
            net_debt = total_debt - cash if total_debt is not None and cash is not None else None

            debt_to_ebitda = None
            if total_debt is not None and ebitda not in (None, Decimal("0")):
                debt_to_ebitda = total_debt / ebitda

            total_equity, roic, interest_coverage = _roic_and_coverage(
                income, balance, col, ebit, total_debt, cash
            )

            results.append(
                FundamentalData(
                    ticker=ticker,
                    period_end=period_end,
                    source_name=self.name,
                    collected_at=collected,
                    net_margin=_ratio(net_income, revenue),
                    ebitda_margin=_ratio(ebitda, revenue),
                    revenue=revenue,
                    net_income=net_income,
                    ebitda=ebitda,
                    ebit=ebit,
                    free_cash_flow=free_cash_flow,
                    net_debt=net_debt,
                    debt_to_ebitda=debt_to_ebitda,
                    total_equity=total_equity,
                    roic=roic,
                    interest_coverage=interest_coverage,
                )
            )

        return results
