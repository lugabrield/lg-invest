"""Schemas da Central de Dados / Data Refresh Service (Sprint 27).

Modela o resultado de cada botão da Central de Dados (tela Dashboard).
Nenhuma contagem aqui é decorativa: cada campo é somado a partir dos
resultados REAIS devolvidos por `MarketDataService`,
`FundamentalsService`, `TrapDetectionService`, `ValuationServiceV2`,
`IncomeRealEstateService`, `PortfolioAdequacyService`, `LGScoreService`,
`ConvictionScoreService` e `WatchlistService` — nunca calculado "de
fora" ou fabricado para preencher a tela (Volume 18 §8: nunca inventar
dado).

Vocabulário de status por ativo (`AssetRefreshOutcome.status`):

- "updated": o provider devolveu dado novo e ele foi persistido.
- "insufficient_data": a coleta rodou, mas o provider não devolveu nada
  aproveitável (ex.: ticker sem cobertura no Yahoo Finance).
- "not_applicable": a classe do ativo não usa esse tipo de coleta (ex.:
  fundamentos de empresa para cripto/Tesouro) — não é uma falha.
- "skipped_manual": ativo marcado como `is_manual=True` (ex.: Tesouro
  Direto) — preço é sempre cadastrado manualmente, nunca via provider.
- "failed": houve uma exceção real na coleta (rede, parsing etc.).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

# Mesmos limiares de `engines/data_coverage/thresholds.py`
# (SCORE_SUFFICIENT/SCORE_PARTIAL) — duplicados aqui deliberadamente para
# este schema não depender de um pacote de engine (camada de schemas
# permanece só dados, sem lógica de negócio importada).
_COVERAGE_SUFFICIENT_THRESHOLD = Decimal("70")
_COVERAGE_PARTIAL_THRESHOLD = Decimal("30")

REFRESH_ASSET_STATUSES = (
    "updated",
    "insufficient_data",
    "not_applicable",
    "skipped_manual",
    "failed",
)


class AssetRefreshOutcome(BaseModel):
    """Resultado da atualização/recomputação de UM ativo."""

    ticker: str
    asset_class: str | None = None
    status: str  # ver REFRESH_ASSET_STATUSES

    price_updated: bool = False
    fundamentals_updated: bool = False
    valuation_recomputed: bool = False
    traps_recomputed: bool = False
    scores_recomputed: bool = False

    # Sprint 28 (Data Coverage Report) — completude de dados fundamentais
    # deste ativo, 0-100, na mesma escala de
    # `schemas/data_coverage.py::CoveragePurposeScore`. `None` quando o
    # Data Coverage Report não pôde ser calculado (ex.: ativo sem nenhuma
    # finalidade fundamentalista aplicável à sua classe).
    data_completeness_score: Decimal | None = None
    missing_fields: list[str] = Field(default_factory=list)

    source: str | None = None
    reason: str | None = None
    error: str | None = None

    def as_dict(self) -> dict:
        return self.model_dump()


class _OutcomesSummaryMixin(BaseModel):
    """Contagens agregadas comuns a todos os resultados de refresh.

    Implementadas como `@property` (não persistidas) para nunca poderem
    divergir da lista real de `outcomes` — a UI sempre lê essas
    propriedades, nunca um contador mantido à parte.
    """

    outcomes: list[AssetRefreshOutcome] = Field(default_factory=list)

    @property
    def processed(self) -> int:
        return len(self.outcomes)

    @property
    def updated(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "updated")

    @property
    def insufficient_data(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "insufficient_data")

    @property
    def not_applicable(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "not_applicable")

    @property
    def skipped_manual(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "skipped_manual")

    @property
    def failed(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "failed")

    @property
    def failed_tickers(self) -> list[str]:
        return [o.ticker for o in self.outcomes if o.status == "failed"]

    @property
    def valuation_recalculated(self) -> int:
        return sum(1 for o in self.outcomes if o.valuation_recomputed)

    @property
    def traps_recalculated(self) -> int:
        return sum(1 for o in self.outcomes if o.traps_recomputed)

    @property
    def scores_recalculated(self) -> int:
        return sum(1 for o in self.outcomes if o.scores_recomputed)

    @property
    def sources_used(self) -> list[str]:
        return sorted({o.source for o in self.outcomes if o.source})

    # -- Sprint 28: Data Coverage Report agregado -----------------------

    @property
    def coverage_sufficient(self) -> int:
        return sum(
            1
            for o in self.outcomes
            if o.data_completeness_score is not None
            and o.data_completeness_score >= _COVERAGE_SUFFICIENT_THRESHOLD
        )

    @property
    def coverage_partial(self) -> int:
        return sum(
            1
            for o in self.outcomes
            if o.data_completeness_score is not None
            and _COVERAGE_PARTIAL_THRESHOLD
            <= o.data_completeness_score
            < _COVERAGE_SUFFICIENT_THRESHOLD
        )

    @property
    def coverage_insufficient(self) -> int:
        return sum(
            1
            for o in self.outcomes
            if o.data_completeness_score is not None
            and o.data_completeness_score < _COVERAGE_PARTIAL_THRESHOLD
        )

    @property
    def most_missing_fields(self) -> list[str]:
        """Os 5 campos mais ausentes entre os ativos processados — contagem
        real sobre `AssetRefreshOutcome.missing_fields`, nunca inventada."""
        counts: dict[str, int] = {}
        for outcome in self.outcomes:
            for label in outcome.missing_fields:
                counts[label] = counts.get(label, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return [label for label, _ in ranked[:5]]


class PortfolioPriceRefreshResult(_OutcomesSummaryMixin):
    """Resultado de "Atualizar preços da carteira" — só ativos com posição."""

    portfolio_id: int
    started_at: datetime
    finished_at: datetime


class PortfolioFundamentalsRefreshResult(_OutcomesSummaryMixin):
    """Resultado de "Atualizar fundamentos da carteira".

    Além de fundamentos, sempre tenta recomputar (quando aplicável à
    classe do ativo) Valuation Engine 2.0 / Análise de Renda Imobiliária
    / Adequação de Carteira, Trap Detection Engine, LG Score e Conviction
    Score — ver `DataRefreshService._recompute_analysis`.
    """

    portfolio_id: int
    started_at: datetime
    finished_at: datetime


class WatchlistRefreshResult(_OutcomesSummaryMixin):
    """Resultado de "Atualizar dados da watchlist".

    `positions_created` e `patrimonio_changed` são a garantia central da
    Watchlist (Sprint 25): calculados a partir da contagem REAL de
    `Position` antes/depois da rotina, não hardcoded — se algum dia uma
    mudança introduzir uma regressão que crie uma posição a partir da
    watchlist, esses campos deixam de ser 0/False e os testes acusam.
    """

    portfolio_id: int
    started_at: datetime
    finished_at: datetime
    positions_created: int = 0
    patrimonio_changed: bool = False


class FullRefreshResult(BaseModel):
    """Resultado de "Atualizar tudo" — preços + fundamentos + watchlist."""

    portfolio_id: int
    started_at: datetime
    finished_at: datetime
    prices: PortfolioPriceRefreshResult
    fundamentals: PortfolioFundamentalsRefreshResult
    watchlist: WatchlistRefreshResult


class LastRefreshStatus(BaseModel):
    """Timestamps da última execução de cada rotina, para a UI do Dashboard.

    Todos `None` até a primeira execução — nunca inventado, a UI mostra
    "nunca" nesse caso.
    """

    prices_at: datetime | None = None
    fundamentals_at: datetime | None = None
    watchlist_at: datetime | None = None
    valuation_at: datetime | None = None
    trap_detection_at: datetime | None = None
    cache_cleared_at: datetime | None = None
    last_summary: dict | None = None
