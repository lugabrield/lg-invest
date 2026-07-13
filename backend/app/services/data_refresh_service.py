"""Central de Dados — orquestração de atualização manual de dados (Sprint 27).

Camada de orquestração pura de I/O: nenhum cálculo novo mora aqui, só
chamadas aos serviços já existentes (`MarketDataService`,
`FundamentalsService`, `TrapDetectionService`, `ValuationServiceV2`,
`IncomeRealEstateService`, `PortfolioAdequacyService`, `LGScoreService`,
`ConvictionScoreService`, `WatchlistService`) na ordem certa, com
agregação dos resultados reais em `AssetRefreshOutcome` (ver
`schemas/data_refresh.py`).

Nunca roda sozinho: só é chamado a partir de um clique explícito na
Central de Dados (tela Dashboard) ou de um teste. Nenhum import deste
módulo, nenhuma inicialização de `DataRefreshService` e nenhum código no
nível do módulo dispara coleta de rede — ver `docs/DATA_REFRESH_CENTER.md`.

Garantias mantidas em todo o arquivo (Volume 18 §8 + regras da Watchlist
do Sprint 25, reafirmadas no Sprint 27):

- "Atualizar preços"/"Atualizar fundamentos" da carteira: processam
  SOMENTE ativos com `Position` na carteira informada — nunca a
  watchlist inteira.
- "Atualizar dados da watchlist": nunca cria `Position`, nunca altera o
  patrimônio calculado pelo Portfolio Engine — `positions_created` é
  calculado a partir da contagem real de posições antes/depois, não
  hardcoded, para que uma regressão futura seja pega pelos testes.
- Falha num ativo nunca derruba o lote inteiro (mesmo padrão de
  `MarketDataService`/`FundamentalsService`).
- Nenhum dado é inventado: um ticker sem retorno do provider vira
  "insufficient_data", nunca um valor fabricado.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.etl.providers.yahoo_fundamentals_provider import YahooFundamentalsProvider
from backend.app.etl.providers.yahoo_provider import YahooFinanceProvider
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.position_repository import PositionRepository
from backend.app.infrastructure.repositories.watchlist_asset_repository import (
    WatchlistAssetRepository,
)
from backend.app.schemas.data_refresh import (
    AssetRefreshOutcome,
    FullRefreshResult,
    LastRefreshStatus,
    PortfolioFundamentalsRefreshResult,
    PortfolioPriceRefreshResult,
    WatchlistRefreshResult,
)
from backend.app.services import data_refresh_status_service as status_service
from backend.app.services.conviction_score_service import ConvictionScoreService
from backend.app.services.data_coverage_service import DataCoverageService
from backend.app.services.fundamentals_service import FundamentalsService
from backend.app.services.income_real_estate_service import IncomeRealEstateService
from backend.app.services.lg_score_service import LGScoreService
from backend.app.services.market_data_service import MarketDataService
from backend.app.services.portfolio_adequacy_service import PortfolioAdequacyService
from backend.app.services.trap_detection_service import TrapDetectionService
from backend.app.services.valuation_v2_service import ValuationServiceV2
from backend.app.services.watchlist_service import WatchlistService

logger = get_logger("lg_invest.data_refresh")

# Mesmas constantes de roteamento por classe já usadas em
# `pages_impl/ativos.py` (seção "Análise Fundamentalista") — repetidas
# aqui, não importadas da UI, porque a UI é a camada de apresentação e
# não deve ser importada por um serviço de backend.
_STOCK_CLASSES = ("stock",)
_INCOME_REAL_ESTATE_CLASSES = ("fii", "reit")
_ADEQUACY_CLASSES = ("etf", "crypto", "bond")
_TRAP_APPLICABLE_CLASSES = ("stock", "fii", "reit")

# Motivos de `FundamentalsService.collect_for_asset` que indicam que a
# classe/situação do ativo simplesmente não usa fundamentos de empresa —
# não é uma falha nem dado insuficiente.
_FUNDAMENTALS_NOT_APPLICABLE_REASONS_PREFIXES = ("classe ", "ativo manual")


class DataRefreshService:
    """Orquestra as 4 rotinas de coleta/recomputação da Central de Dados.

    A 5ª ação do botão "Limpar cache / Recarregar análises" não precisa
    deste serviço — é só `clear_all_caches()` na camada Streamlit, sem
    nenhuma chamada de rede (ver `docs/DATA_REFRESH_CENTER.md`).
    """

    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.positions = PositionRepository(db)
        self.watchlist = WatchlistAssetRepository(db)

    # -- helpers internos ---------------------------------------------

    def _portfolio_tickers(self, portfolio_id: int) -> list[str]:
        """Tickers com `Position` nesta carteira — nunca a watchlist."""
        tickers = []
        for position in self.positions.list_by_portfolio(portfolio_id):
            asset = self.assets.get_by_id(position.asset_id)
            if asset is not None:
                tickers.append(asset.ticker)
        return tickers

    def _recompute_analysis(
        self, ticker: str, asset_class: str | None, portfolio_id: int
    ) -> tuple[bool, bool, bool]:
        """Recomputa valuation/traps/scores já aplicáveis à classe do ativo.

        Retorna `(valuation_recomputed, traps_recomputed, scores_recomputed)`.
        Cada engine já sabe devolver `None`/indeterminado quando não há
        dado suficiente — este método só conta "rodou e devolveu algo",
        nunca decide por conta própria se o resultado é bom ou ruim.
        """
        if asset_class is None:
            return False, False, False

        valuation_done = False
        traps_done = False
        scores_done = False

        if asset_class in _TRAP_APPLICABLE_CLASSES:
            try:
                if TrapDetectionService(self.db).evaluate_ticker(ticker) is not None:
                    traps_done = True
            except Exception as exc:  # noqa: BLE001 - engine não pode derrubar o lote
                logger.warning("Trap Detection falhou para %s: %s", ticker, exc)

        try:
            if asset_class in _STOCK_CLASSES:
                if ValuationServiceV2(self.db).evaluate_ticker(ticker) is not None:
                    valuation_done = True
            elif asset_class in _INCOME_REAL_ESTATE_CLASSES:
                if IncomeRealEstateService(self.db).evaluate_ticker(ticker) is not None:
                    valuation_done = True
            elif asset_class in _ADEQUACY_CLASSES:
                if (
                    PortfolioAdequacyService(self.db).evaluate_ticker(ticker, portfolio_id)
                    is not None
                ):
                    valuation_done = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Análise fundamentalista falhou para %s: %s", ticker, exc)

        try:
            lg_result = LGScoreService(self.db).score_ticker(ticker)
            conviction_result = ConvictionScoreService(self.db).score_ticker(ticker)
            scores_done = lg_result is not None or conviction_result is not None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Recomputação de score falhou para %s: %s", ticker, exc)

        return valuation_done, traps_done, scores_done

    def _data_coverage(self, ticker: str) -> tuple[Decimal | None, list[str]]:
        """Score de completude (0-100) + rótulos ausentes (Sprint 28: Data
        Coverage Report), para alimentar o resumo "campos mais ausentes"
        da Central de Dados. Nunca derruba o lote: falha vira `(None, [])`,
        igual a qualquer outra recomputação desta classe."""
        try:
            coverage = DataCoverageService(self.db).evaluate_ticker(ticker)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Data Coverage Report falhou para %s: %s", ticker, exc)
            return None, []
        if coverage is None:
            return None, []
        return coverage.decision_engine.score, coverage.missing_field_labels

    @staticmethod
    def _fundamentals_status(collected: bool, reason: str | None, error: str | None) -> str:
        if error:
            return "failed"
        if collected:
            return "updated"
        if reason is not None and reason.startswith(_FUNDAMENTALS_NOT_APPLICABLE_REASONS_PREFIXES):
            return "not_applicable"
        return "insufficient_data"

    # -- botão 1: Atualizar preços da carteira -------------------------

    def refresh_portfolio_prices(self, portfolio_id: int) -> PortfolioPriceRefreshResult:
        """Atualiza preços SOMENTE dos ativos com posição nesta carteira.

        Nunca toca a watchlist, nunca recomputa fundamentos/valuation —
        só o histórico de preços (Volume 20, prompt 7).
        """
        started_at = datetime.now(UTC)
        service = MarketDataService(self.db, YahooFinanceProvider())
        outcomes: list[AssetRefreshOutcome] = []

        for ticker in self._portfolio_tickers(portfolio_id):
            asset = self.assets.get_by_ticker(ticker)
            result = service.update_asset_prices(ticker)

            if result.skipped_manual:
                status = "skipped_manual"
            elif result.error:
                status = "failed"
            elif result.inserted == 0 and result.updated == 0:
                status = "insufficient_data"
            else:
                status = "updated"

            outcomes.append(
                AssetRefreshOutcome(
                    ticker=ticker,
                    asset_class=asset.asset_class if asset else None,
                    status=status,
                    price_updated=status == "updated",
                    source="yahoo" if status == "updated" else None,
                    error=result.error,
                )
            )

        finished_at = datetime.now(UTC)
        result = PortfolioPriceRefreshResult(
            portfolio_id=portfolio_id,
            started_at=started_at,
            finished_at=finished_at,
            outcomes=outcomes,
        )
        status_service.record_prices_refresh(
            {
                "processados": result.processed,
                "atualizados": result.updated,
                "pulados_manual": result.skipped_manual,
                "dados_insuficientes": result.insufficient_data,
                "falhas": result.failed,
                "fontes": result.sources_used,
            }
        )
        return result

    # -- botão 2: Atualizar fundamentos da carteira --------------------

    def refresh_portfolio_fundamentals(
        self, portfolio_id: int
    ) -> PortfolioFundamentalsRefreshResult:
        """Coleta fundamentos e recomputa análises dos ativos da carteira.

        Para cada ticker com posição: coleta fundamentos (quando
        aplicável à classe) e, na sequência, tenta recomputar Valuation
        Engine 2.0 / Análise de Renda Imobiliária / Adequação de
        Carteira, Trap Detection, LG Score e Conviction Score — sempre
        que a classe do ativo suporta aquele tipo de análise, mesmo
        quando a coleta de fundamentos em si não trouxe dado novo (as
        engines já leem o que estiver salvo no banco).
        """
        started_at = datetime.now(UTC)
        fundamentals_service = FundamentalsService(self.db, YahooFundamentalsProvider())
        outcomes: list[AssetRefreshOutcome] = []

        for ticker in self._portfolio_tickers(portfolio_id):
            asset = self.assets.get_by_ticker(ticker)
            asset_class = asset.asset_class if asset else None
            collection = fundamentals_service.collect_for_asset(ticker)
            status = self._fundamentals_status(
                collection.collected, collection.reason, collection.error
            )

            valuation_done, traps_done, scores_done = self._recompute_analysis(
                ticker, asset_class, portfolio_id
            )
            completeness_score, missing_fields = self._data_coverage(ticker)

            outcomes.append(
                AssetRefreshOutcome(
                    ticker=ticker,
                    asset_class=asset_class,
                    status=status,
                    fundamentals_updated=status == "updated",
                    valuation_recomputed=valuation_done,
                    traps_recomputed=traps_done,
                    scores_recomputed=scores_done,
                    data_completeness_score=completeness_score,
                    missing_fields=missing_fields,
                    source="yahoo" if status == "updated" else None,
                    reason=collection.reason,
                    error=collection.error,
                )
            )

        finished_at = datetime.now(UTC)
        result = PortfolioFundamentalsRefreshResult(
            portfolio_id=portfolio_id,
            started_at=started_at,
            finished_at=finished_at,
            outcomes=outcomes,
        )
        status_service.record_fundamentals_refresh(
            {
                "processados": result.processed,
                "atualizados": result.updated,
                "dados_insuficientes": result.insufficient_data,
                "nao_aplicaveis": result.not_applicable,
                "falhas": result.failed,
                "fontes": result.sources_used,
                "valuation_recalculado": result.valuation_recalculated,
                "traps_recalculadas": result.traps_recalculated,
                "scores_recalculados": result.scores_recalculated,
                "dados_suficientes": result.coverage_sufficient,
                "dados_parciais": result.coverage_partial,
                "dados_insuficientes_cobertura": result.coverage_insufficient,
                "campos_mais_ausentes": result.most_missing_fields,
            }
        )
        return result

    # -- botão 3: Atualizar dados da watchlist -------------------------

    def refresh_watchlist_data(self, portfolio_id: int) -> WatchlistRefreshResult:
        """Coleta preço/fundamentos dos candidatos da watchlist e recomputa scores.

        NUNCA cria `Position`, NUNCA altera o patrimônio: só toca as
        tabelas `assets` (cadastro mestre, se ainda não existir),
        `prices`, `fundamental_snapshots` e `watchlist_assets` (campo
        `last_collected_at`). `positions_created` é a contagem real de
        `Position` antes/depois — deve ser sempre 0.
        """
        started_at = datetime.now(UTC)
        market_service = MarketDataService(self.db, YahooFinanceProvider())
        fundamentals_service = FundamentalsService(self.db, YahooFundamentalsProvider())
        watchlist_service = WatchlistService(self.db)
        outcomes: list[AssetRefreshOutcome] = []

        positions_before = len(self.positions.list_by_portfolio(portfolio_id))

        entries = [
            entry
            for entry in self.watchlist.list_by_portfolio(portfolio_id)
            if entry.status != "discarded"
        ]

        for entry in entries:
            # 1) garante o cadastro mestre em `assets` (sem criar Position).
            watchlist_service.collect_data_for_asset(portfolio_id, entry.id)
            asset = self.assets.get_by_ticker(entry.ticker)

            price_result = None
            fundamentals_result = None
            error: str | None = None

            if asset is not None:
                price_result = market_service.update_asset_prices(entry.ticker)
                fundamentals_result = fundamentals_service.collect_for_asset(entry.ticker)
                error = price_result.error or fundamentals_result.error

            # 2) recomputa scores JÁ com o dado recém-coletado.
            final_collection = watchlist_service.collect_data_for_asset(portfolio_id, entry.id)

            price_updated = bool(
                price_result
                and not price_result.error
                and (price_result.inserted or price_result.updated)
            )
            fundamentals_updated = bool(fundamentals_result and fundamentals_result.collected)

            if asset is None:
                status = "failed"
            elif error:
                status = "failed"
            elif price_updated or fundamentals_updated:
                status = "updated"
            else:
                status = "insufficient_data"

            valuation_done = traps_done = False
            completeness_score, missing_fields = None, []
            if asset is not None:
                valuation_done, traps_done, _ = self._recompute_analysis(
                    entry.ticker, asset.asset_class, portfolio_id
                )
                completeness_score, missing_fields = self._data_coverage(entry.ticker)

            outcomes.append(
                AssetRefreshOutcome(
                    ticker=entry.ticker,
                    asset_class=entry.asset_class,
                    status=status,
                    price_updated=price_updated,
                    fundamentals_updated=fundamentals_updated,
                    valuation_recomputed=valuation_done,
                    traps_recomputed=traps_done,
                    scores_recomputed=(
                        final_collection.lg_score is not None
                        or final_collection.conviction_score is not None
                    ),
                    data_completeness_score=completeness_score,
                    missing_fields=missing_fields,
                    source="yahoo" if (price_updated or fundamentals_updated) else None,
                    reason=(
                        None
                        if status == "updated"
                        else "; ".join(final_collection.notes) or "sem dado suficiente"
                    ),
                    error=error,
                )
            )

        positions_after = len(self.positions.list_by_portfolio(portfolio_id))
        finished_at = datetime.now(UTC)
        result = WatchlistRefreshResult(
            portfolio_id=portfolio_id,
            started_at=started_at,
            finished_at=finished_at,
            outcomes=outcomes,
            positions_created=positions_after - positions_before,
            patrimonio_changed=False,
        )
        status_service.record_watchlist_refresh(
            {
                "processados": result.processed,
                "atualizados": result.updated,
                "dados_insuficientes": result.insufficient_data,
                "falhas": result.failed,
                "fontes": result.sources_used,
                "posicoes_criadas": result.positions_created,
                "patrimonio_alterado": result.patrimonio_changed,
            }
        )
        return result

    # -- botão 4: Atualizar tudo ----------------------------------------

    def refresh_all_investment_data(self, portfolio_id: int) -> FullRefreshResult:
        """Preços + fundamentos da carteira e dados da watchlist, em sequência.

        A confirmação do usuário ("pode ser lento, tem certeza?") é
        responsabilidade da camada Streamlit — este método não decide
        isso, só orquestra; nunca é chamado por conta própria (sem
        clique nenhum em algum job/import).
        """
        started_at = datetime.now(UTC)
        prices = self.refresh_portfolio_prices(portfolio_id)
        fundamentals = self.refresh_portfolio_fundamentals(portfolio_id)
        watchlist = self.refresh_watchlist_data(portfolio_id)
        finished_at = datetime.now(UTC)

        return FullRefreshResult(
            portfolio_id=portfolio_id,
            started_at=started_at,
            finished_at=finished_at,
            prices=prices,
            fundamentals=fundamentals,
            watchlist=watchlist,
        )

    # -- status -----------------------------------------------------------

    @staticmethod
    def get_last_refresh_status() -> LastRefreshStatus:
        return status_service.get_last_refresh_status()
