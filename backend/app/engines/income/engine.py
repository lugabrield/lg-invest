"""Income Engine (Sprint 24, Fase 7).

Analisa a renda de proventos já recebida (dividendos, JCP, rendimento de
FII, amortização) a partir de duas fontes independentes já persistidas
pela integração Dividendos.me (Sprint 23) — nunca inventa proventos nem
projeta um valor sem dado histórico.

Duas análises **deliberadamente separadas, nunca somadas entre si**:

1. `PortfolioIncomeTrend` — tendência mensal agregada da carteira inteira
   (fonte: `income_monthly_summaries`, aba "Análise" do Dividendos.me):
   total dos últimos 12 meses (TTM), comparação com os 12 meses
   anteriores (crescimento de renda) e uma projeção simples (naive) dos
   próximos 12 meses.
2. `TickerIncomeBreakdown` — renda por ativo (fonte: `income_events`,
   calendário individual de proventos): renda dos últimos 12 meses por
   ticker, *yield on cost* (renda / custo de aquisição, não sobre o
   valor de mercado atual — métrica central para quem segue Buy and
   Hold: mostra se o "aluguel" do capital investido está crescendo) e
   concentração de renda entre os ativos.

Somar as duas fontes seria arriscado (uma agregada, outra granular por
ativo — risco de dupla contagem do mesmo provento). Ver
`docs/INCOME_ENGINE.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.app.engines.income.inputs import DEFAULT_CONFIG, IncomeConfig, IncomeEngineInput

MODEL_VERSION = "income_v1"
_ZERO = Decimal("0")


@dataclass
class MonthlyPoint:
    year: int
    month: int
    amount_total: Decimal


@dataclass
class PortfolioIncomeTrend:
    ttm_total: Decimal
    prior_ttm_total: Decimal
    growth_pct: Decimal | None
    monthly_series: list[MonthlyPoint]
    projected_next_12_months: Decimal
    months_with_data_ttm: int
    months_with_data_prior_ttm: int
    reason: str


@dataclass
class TickerIncomeRow:
    ticker: str
    ttm_income: Decimal
    cost_basis: Decimal | None
    yield_on_cost: Decimal | None


@dataclass
class TickerIncomeBreakdown:
    rows: list[TickerIncomeRow]
    concentration_hhi: Decimal | None
    portfolio_yield_on_cost: Decimal | None
    excluded_tickers_without_position: list[str]
    reason: str


@dataclass
class IncomeAnalysisResult:
    model_version: str
    trend: PortfolioIncomeTrend
    breakdown: TickerIncomeBreakdown
    reasons: list[str]
    warnings: list[str]


def _month_index(year: int, month: int) -> int:
    """Índice inteiro contínuo (mês 0-indexado internamente) para permitir
    aritmética simples de "N meses atrás" sem lidar com virada de ano."""
    return year * 12 + (month - 1)


def _index_to_year_month(idx: int) -> tuple[int, int]:
    return idx // 12, (idx % 12) + 1


def _compute_trend(
    data: IncomeEngineInput, config: IncomeConfig, warnings: list[str]
) -> PortfolioIncomeTrend:
    ref_idx = _month_index(data.reference_date.year, data.reference_date.month)
    ttm_start, ttm_end = ref_idx - 11, ref_idx
    prior_start, prior_end = ttm_start - 12, ttm_start - 1
    series_start = ref_idx - (config.months_lookback - 1)

    by_month: dict[int, Decimal] = {}
    for entry in data.monthly_totals:
        idx = _month_index(entry.year, entry.month)
        by_month[idx] = by_month.get(idx, _ZERO) + entry.amount_total

    ttm_months = {idx: v for idx, v in by_month.items() if ttm_start <= idx <= ttm_end}
    prior_months = {idx: v for idx, v in by_month.items() if prior_start <= idx <= prior_end}

    ttm_total = sum(ttm_months.values(), _ZERO)
    prior_ttm_total = sum(prior_months.values(), _ZERO)

    if prior_ttm_total > 0:
        growth_pct = (ttm_total - prior_ttm_total) / prior_ttm_total
        reason = (
            f"renda dos últimos 12 meses: {ttm_total}; período anterior: "
            f"{prior_ttm_total}; crescimento de {growth_pct * 100:.1f}%."
        )
    else:
        growth_pct = None
        warnings.append(
            "sem dado de renda suficiente nos 12 meses anteriores ao período atual — "
            "crescimento de renda não pôde ser calculado (nunca inventado)."
        )
        reason = f"renda dos últimos 12 meses: {ttm_total}; sem base de comparação anterior."

    if ttm_total > 0:
        projected = ttm_total * (1 + growth_pct) if growth_pct is not None else ttm_total
        reason += (
            " Projeção dos próximos 12 meses é uma extrapolação simples (naive) — assume "
            + (
                "a mesma taxa de crescimento observada"
                if growth_pct is not None
                else "repetição do valor dos últimos 12 meses"
            )
            + ", não é garantia de recebimento futuro."
        )
    else:
        projected = _ZERO
        warnings.append("sem histórico de renda nos últimos 12 meses — projeção zerada.")

    monthly_series = [
        MonthlyPoint(
            year=_index_to_year_month(idx)[0], month=_index_to_year_month(idx)[1], amount_total=v
        )
        for idx, v in sorted(by_month.items())
        if idx >= series_start
    ]

    return PortfolioIncomeTrend(
        ttm_total=ttm_total,
        prior_ttm_total=prior_ttm_total,
        growth_pct=growth_pct,
        monthly_series=monthly_series,
        projected_next_12_months=Decimal(str(round(float(projected), 2))),
        months_with_data_ttm=len(ttm_months),
        months_with_data_prior_ttm=len(prior_months),
        reason=reason,
    )


def _compute_breakdown(data: IncomeEngineInput, warnings: list[str]) -> TickerIncomeBreakdown:
    ref_idx = _month_index(data.reference_date.year, data.reference_date.month)
    ttm_start = ref_idx - 11

    ttm_by_ticker: dict[str, Decimal] = {}
    for event in data.ticker_events:
        idx = _month_index(event.payment_date.year, event.payment_date.month)
        if ttm_start <= idx <= ref_idx:
            ttm_by_ticker[event.ticker] = (
                ttm_by_ticker.get(event.ticker, _ZERO) + event.amount_total
            )

    total_ttm_income = sum(ttm_by_ticker.values(), _ZERO)
    concentration_hhi = (
        sum((amount / total_ttm_income) ** 2 for amount in ttm_by_ticker.values())
        if total_ttm_income > 0
        else None
    )

    rows: list[TickerIncomeRow] = []
    excluded: list[str] = []
    known_cost_total = _ZERO
    known_income_total = _ZERO
    for ticker, cost_basis in data.position_cost_basis.items():
        income = ttm_by_ticker.get(ticker, _ZERO)
        if cost_basis <= 0:
            rows.append(
                TickerIncomeRow(
                    ticker=ticker, ttm_income=income, cost_basis=None, yield_on_cost=None
                )
            )
            continue
        yield_on_cost = income / cost_basis
        rows.append(
            TickerIncomeRow(
                ticker=ticker,
                ttm_income=income,
                cost_basis=cost_basis,
                yield_on_cost=Decimal(str(round(float(yield_on_cost), 4))),
            )
        )
        known_cost_total += cost_basis
        known_income_total += income

    for ticker in ttm_by_ticker:
        if ticker not in data.position_cost_basis:
            excluded.append(ticker)

    if excluded:
        warnings.append(
            f"eventos de renda para {sorted(excluded)} não têm posição correspondente na "
            "carteira atual (ativo já vendido, ou dado de posição indisponível) — "
            "excluídos do yield on cost, mas contam na concentração de renda."
        )

    portfolio_yield_on_cost = (
        known_income_total / known_cost_total if known_cost_total > 0 else None
    )
    if portfolio_yield_on_cost is None:
        warnings.append(
            "sem custo de aquisição conhecido para nenhum ativo com renda — yield on cost "
            "da carteira não pôde ser calculado."
        )

    reason = (
        f"renda por ativo (últimos 12 meses) calculada para {len(ttm_by_ticker)} ativo(s); "
        f"yield on cost calculado para {sum(1 for r in rows if r.yield_on_cost is not None)} "
        "posição(ões) com custo de aquisição conhecido."
    )

    return TickerIncomeBreakdown(
        rows=sorted(rows, key=lambda r: r.ttm_income, reverse=True),
        concentration_hhi=(
            Decimal(str(round(float(concentration_hhi), 4)))
            if concentration_hhi is not None
            else None
        ),
        portfolio_yield_on_cost=(
            Decimal(str(round(float(portfolio_yield_on_cost), 4)))
            if portfolio_yield_on_cost is not None
            else None
        ),
        excluded_tickers_without_position=sorted(excluded),
        reason=reason,
    )


def analyze_income(
    data: IncomeEngineInput,
    config: IncomeConfig = DEFAULT_CONFIG,
) -> IncomeAnalysisResult:
    """Roda as duas análises de renda (pura, sem banco/rede)."""
    warnings: list[str] = []
    trend = _compute_trend(data, config, warnings)
    breakdown = _compute_breakdown(data, warnings)

    reasons = [
        trend.reason,
        breakdown.reason,
        "tendência agregada (fonte: Análise/resumo mensal) e renda por ativo (fonte: "
        "calendário de proventos) vêm de fontes diferentes e nunca são somadas entre si, "
        "para evitar contagem duplicada do mesmo provento.",
    ]

    return IncomeAnalysisResult(
        model_version=MODEL_VERSION,
        trend=trend,
        breakdown=breakdown,
        reasons=reasons,
        warnings=warnings,
    )
