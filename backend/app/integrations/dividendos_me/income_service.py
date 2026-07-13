"""Serviço de sincronização de proventos/dividendos do Dividendos.me
(Sprint 23.2 / 23.3).

Separado de `service.py` (carteira) de propósito: proventos e posições
têm ciclos de vida, regras de bloqueio e riscos completamente diferentes.
- Proventos NUNCA bloqueiam nem são bloqueados pela sincronização da
  carteira — uma falha aqui só gera um alerta, nunca impede `replace`.
- Proventos são sempre ADITIVOS: não existe modo "replace" aqui. Cada
  evento/resumo novo é comparado contra o histórico já salvo via chave de
  deduplicação própria — nunca duplica, nunca apaga histórico existente.

Sprint 23.3 (correção pós-produção — resumo mensal estava sendo forçado
no formato de evento por ticker): este módulo agora tem DOIS fluxos
paralelos e independentes, nunca misturados:
- Calendário futuro (`build_preview`/`dry_run`/`import_events`): aba
  "Próximos Dividendos", grava em `income_events`, dedup por
  `portfolio_id+ticker+payment_date+event_type+amount_total+source`.
- Histórico mensal (`build_monthly_preview`/`dry_run_monthly`/
  `import_monthly_summaries`): aba "Análise", grava em
  `income_monthly_summaries`, dedup por
  `portfolio_id+wallet_name+year+month+currency+source`.
Uma falha num fluxo nunca afeta o outro nem a carteira.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.infrastructure.database.models.income_event import IncomeEvent
from backend.app.infrastructure.database.models.income_monthly_summary import (
    IncomeMonthlySummary,
)
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.income_event_repository import IncomeEventRepository
from backend.app.infrastructure.repositories.income_monthly_summary_repository import (
    IncomeMonthlySummaryRepository,
)
from backend.app.infrastructure.repositories.portfolio_repository import PortfolioRepository
from backend.app.integrations.dividendos_me.client import DividendosMeClient
from backend.app.integrations.dividendos_me.income_parser import (
    NormalizedIncomeEvent,
    NormalizedMonthlySummary,
    deduplicate_in_batch,
    deduplicate_monthly_summaries_in_batch,
)
from backend.app.integrations.dividendos_me.schemas import (
    IncomeEventPreviewItem,
    IncomeMonthlySummaryPreviewItem,
    IncomeMonthlySyncPreview,
    IncomeMonthlySyncRunResult,
    IncomeSyncPreview,
    IncomeSyncRunResult,
)
from backend.app.integrations.dividendos_me.service import PortfolioNotFoundError

logger = get_logger("lg_invest.integrations.dividendos_me.income_service")

PROVIDER = "dividendos_me"

_SAMPLE_SIZE = 10


class IncomeSyncService:
    def __init__(self, db: Session):
        self.db = db
        self.portfolios = PortfolioRepository(db)
        self.assets = AssetRepository(db)
        self.income_events = IncomeEventRepository(db)
        self.income_monthly_summaries = IncomeMonthlySummaryRepository(db)

    # --- Calendário futuro (income_events) --------------------------------

    def _fetch_and_deduplicate(
        self, portfolio_id: int, client: DividendosMeClient
    ) -> tuple[list[NormalizedIncomeEvent], list[NormalizedIncomeEvent], list[str], list]:
        """Chama `client.fetch_income_events()` (calendário futuro) UMA vez
        e devolve `(eventos_brutos, eventos_sem_duplicata_no_lote,
        seções_falhas, diagnósticos)` — usado tanto por `build_preview`
        quanto por `import_events`, para nunca fazer login/scrape duas
        vezes numa mesma operação."""
        portfolio = self.portfolios.get_by_id(portfolio_id)
        if portfolio is None:
            raise PortfolioNotFoundError(f"Carteira {portfolio_id} não existe na LG INVEST.")

        events_raw, failed_sections, diagnostics = client.fetch_income_events()
        events = deduplicate_in_batch(events_raw, portfolio_id=portfolio_id)
        return events_raw, events, failed_sections, diagnostics

    def _build_preview_from_events(
        self,
        portfolio_id: int,
        events_raw: list[NormalizedIncomeEvent],
        events: list[NormalizedIncomeEvent],
        failed_sections: list[str],
        diagnostics: list,
    ) -> IncomeSyncPreview:
        total_by_currency: dict[str, Decimal] = {}
        for event in events:
            total_by_currency[event.currency] = (
                total_by_currency.get(event.currency, Decimal("0")) + event.amount_total
            )

        dated = [e.payment_date for e in events if e.payment_date is not None]
        period_start = min(dated) if dated else None
        period_end = max(dated) if dated else None

        sample = [
            IncomeEventPreviewItem(
                ticker=e.ticker,
                event_type=e.event_type,
                status=e.status,
                payment_date=e.payment_date,
                amount_total=e.amount_total,
                currency=e.currency,
                source=e.source,
            )
            for e in events[:_SAMPLE_SIZE]
        ]

        return IncomeSyncPreview(
            portfolio_id=portfolio_id,
            events_found=len(events_raw),
            events_valid=len(events),
            events_rejected=max(len(events_raw) - len(events), 0),
            period_start=period_start,
            period_end=period_end,
            total_by_currency=total_by_currency,
            sections_failed=failed_sections,
            diagnostics=diagnostics,
            sample=sample,
            generated_at=datetime.now(UTC),
        )

    def build_preview(self, portfolio_id: int, client: DividendosMeClient) -> IncomeSyncPreview:
        """Busca o CALENDÁRIO FUTURO de proventos no Dividendos.me e monta
        o preview — nunca grava nada. Uma falha de extração vira
        `sections_failed`, nunca uma exceção que interrompa o chamador."""
        events_raw, events, failed_sections, diagnostics = self._fetch_and_deduplicate(
            portfolio_id, client
        )
        return self._build_preview_from_events(
            portfolio_id, events_raw, events, failed_sections, diagnostics
        )

    @staticmethod
    def _status_from_preview(sections_failed: list[str], valid_count: int) -> str:
        # "failed": alguma seção falhou e não sobrou nenhum dado válido;
        # "partial": alguma seção falhou mas ainda há dado utilizável;
        # "success": nenhuma seção falhou (zero itens encontrados é um
        # resultado legítimo — a carteira pode simplesmente não ter
        # proventos no período, isso não é falha).
        if sections_failed:
            return "failed" if valid_count == 0 else "partial"
        return "success"

    def dry_run(self, portfolio_id: int, client: DividendosMeClient) -> IncomeSyncRunResult:
        started_at = datetime.now(UTC)
        events_raw, events, failed_sections, diagnostics = self._fetch_and_deduplicate(
            portfolio_id, client
        )
        preview = self._build_preview_from_events(
            portfolio_id, events_raw, events, failed_sections, diagnostics
        )

        return IncomeSyncRunResult(
            provider=PROVIDER,
            status=self._status_from_preview(failed_sections, preview.events_valid),
            portfolio_id=portfolio_id,
            events_found=preview.events_valid,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            preview=preview,
        )

    def import_events(self, portfolio_id: int, client: DividendosMeClient) -> IncomeSyncRunResult:
        """Busca o calendário futuro (uma única vez) e GRAVA os eventos que
        ainda não existem (dedup contra o banco) em `income_events`. Nunca
        remove eventos existentes — só adiciona."""
        started_at = datetime.now(UTC)
        events_raw, events, failed_sections, diagnostics = self._fetch_and_deduplicate(
            portfolio_id, client
        )
        preview = self._build_preview_from_events(
            portfolio_id, events_raw, events, failed_sections, diagnostics
        )

        created = 0
        skipped_duplicate = 0
        errors: list[str] = []
        for section in preview.sections_failed:
            errors.append(f"seção de proventos não extraída: {section}")

        for event in events:
            try:
                is_duplicate = self.income_events.exists_duplicate(
                    portfolio_id=portfolio_id,
                    ticker=event.ticker,
                    payment_date=event.payment_date,
                    event_type=event.event_type,
                    amount_total=event.amount_total,
                    source=event.source,
                )
                if is_duplicate:
                    skipped_duplicate += 1
                    continue

                asset_id = None
                if event.ticker:
                    asset = self.assets.get_by_ticker(event.ticker)
                    asset_id = asset.id if asset is not None else None

                self.income_events.create(self._to_event_model(portfolio_id, asset_id, event))
                created += 1
            except Exception as exc:  # noqa: BLE001 - um evento ruim não derruba os demais
                self.db.rollback()
                errors.append(
                    f"falha ao gravar evento de {event.ticker or 'desconhecido'}: "
                    f"{type(exc).__name__}"
                )
                logger.error("Falha ao gravar IncomeEvent: %s", type(exc).__name__)

        status = "success" if not errors else ("partial" if created else "failed")
        finished_at = datetime.now(UTC)

        return IncomeSyncRunResult(
            provider=PROVIDER,
            status=status,
            portfolio_id=portfolio_id,
            events_found=preview.events_valid,
            events_created=created,
            events_skipped_duplicate=skipped_duplicate,
            errors=errors,
            started_at=started_at,
            finished_at=finished_at,
            preview=preview,
        )

    @staticmethod
    def _to_event_model(
        portfolio_id: int, asset_id: int | None, event: NormalizedIncomeEvent
    ) -> IncomeEvent:
        return IncomeEvent(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            ticker=event.ticker,
            source=event.source,
            event_type=event.event_type,
            status=event.status,
            ex_date=None,
            payment_date=event.payment_date,
            declared_date=None,
            quantity=None,
            amount_per_share=None,
            amount_total=event.amount_total,
            currency=event.currency,
            raw_payload_json=json.dumps(event.raw_payload, ensure_ascii=False),
        )

    # --- Histórico mensal agregado (income_monthly_summaries) -------------

    def _fetch_and_deduplicate_monthly(
        self,
        portfolio_id: int,
        client: DividendosMeClient,
        *,
        debug: bool = False,
        debug_dir: str | None = None,
    ) -> tuple[list[NormalizedMonthlySummary], list[NormalizedMonthlySummary], list[str], list]:
        """Mesmo princípio de `_fetch_and_deduplicate`, mas para o
        histórico mensal (`client.fetch_income_monthly_summaries()`) —
        nunca chama a extração do calendário, e vice-versa.

        `debug`/`debug_dir` (ajuste pós-Sprint 25, Parte 3): repassados
        direto para `client.fetch_income_monthly_summaries()` — permitem
        salvar um snapshot local (HTML sanitizado + screenshot) quando o
        diagnóstico padrão (`raw_rows_detected=0`) não for suficiente."""
        portfolio = self.portfolios.get_by_id(portfolio_id)
        if portfolio is None:
            raise PortfolioNotFoundError(f"Carteira {portfolio_id} não existe na LG INVEST.")

        summaries_raw, failed_sections, diagnostics = client.fetch_income_monthly_summaries(
            debug=debug, debug_dir=debug_dir
        )
        summaries = deduplicate_monthly_summaries_in_batch(summaries_raw, portfolio_id=portfolio_id)
        return summaries_raw, summaries, failed_sections, diagnostics

    def _build_monthly_preview_from_summaries(
        self,
        portfolio_id: int,
        summaries_raw: list[NormalizedMonthlySummary],
        summaries: list[NormalizedMonthlySummary],
        failed_sections: list[str],
        diagnostics: list,
    ) -> IncomeMonthlySyncPreview:
        total_by_currency: dict[str, Decimal] = {}
        total_by_year: dict[str, Decimal] = {}
        years_found: set[int] = set()
        months_found: set[int] = set()
        wallets_found: set[str] = set()

        for s in summaries:
            total_by_currency[s.currency] = (
                total_by_currency.get(s.currency, Decimal("0")) + s.amount_total
            )
            year_key = str(s.year)
            total_by_year[year_key] = total_by_year.get(year_key, Decimal("0")) + s.amount_total
            years_found.add(s.year)
            months_found.add(s.month)
            wallets_found.add(s.wallet_name)

        sample = [
            IncomeMonthlySummaryPreviewItem(
                wallet_name=s.wallet_name,
                year=s.year,
                month=s.month,
                amount_total=s.amount_total,
                currency=s.currency,
                status=s.status,
                annual_total=s.annual_total,
                annual_average=s.annual_average,
            )
            for s in summaries[:_SAMPLE_SIZE]
        ]

        return IncomeMonthlySyncPreview(
            portfolio_id=portfolio_id,
            summaries_found=len(summaries_raw),
            summaries_valid=len(summaries),
            summaries_rejected=max(len(summaries_raw) - len(summaries), 0),
            years_found=sorted(years_found),
            months_found=sorted(months_found),
            wallets_found=sorted(wallets_found),
            total_by_year=total_by_year,
            total_by_currency=total_by_currency,
            sections_failed=failed_sections,
            diagnostics=diagnostics,
            sample=sample,
            generated_at=datetime.now(UTC),
        )

    def build_monthly_preview(
        self,
        portfolio_id: int,
        client: DividendosMeClient,
        *,
        debug: bool = False,
        debug_dir: str | None = None,
    ) -> IncomeMonthlySyncPreview:
        """Busca o HISTÓRICO MENSAL agregado (aba "Análise") no
        Dividendos.me e monta o preview — nunca grava nada."""
        summaries_raw, summaries, failed_sections, diagnostics = (
            self._fetch_and_deduplicate_monthly(
                portfolio_id, client, debug=debug, debug_dir=debug_dir
            )
        )
        return self._build_monthly_preview_from_summaries(
            portfolio_id, summaries_raw, summaries, failed_sections, diagnostics
        )

    def dry_run_monthly(
        self,
        portfolio_id: int,
        client: DividendosMeClient,
        *,
        debug: bool = False,
        debug_dir: str | None = None,
    ) -> IncomeMonthlySyncRunResult:
        started_at = datetime.now(UTC)
        summaries_raw, summaries, failed_sections, diagnostics = (
            self._fetch_and_deduplicate_monthly(
                portfolio_id, client, debug=debug, debug_dir=debug_dir
            )
        )
        preview = self._build_monthly_preview_from_summaries(
            portfolio_id, summaries_raw, summaries, failed_sections, diagnostics
        )

        return IncomeMonthlySyncRunResult(
            provider=PROVIDER,
            status=self._status_from_preview(failed_sections, preview.summaries_valid),
            portfolio_id=portfolio_id,
            summaries_found=preview.summaries_valid,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            preview=preview,
        )

    def import_monthly_summaries(
        self, portfolio_id: int, client: DividendosMeClient
    ) -> IncomeMonthlySyncRunResult:
        """Busca o histórico mensal (uma única vez) e GRAVA os resumos que
        ainda não existem (dedup contra o banco) em
        `income_monthly_summaries`. Nunca remove resumos existentes — só
        adiciona. Nunca grava em `income_events` (ver módulo docstring)."""
        started_at = datetime.now(UTC)
        summaries_raw, summaries, failed_sections, diagnostics = (
            self._fetch_and_deduplicate_monthly(portfolio_id, client)
        )
        preview = self._build_monthly_preview_from_summaries(
            portfolio_id, summaries_raw, summaries, failed_sections, diagnostics
        )

        created = 0
        skipped_duplicate = 0
        errors: list[str] = []
        for section in preview.sections_failed:
            errors.append(f"seção de histórico mensal não extraída: {section}")

        for summary in summaries:
            try:
                is_duplicate = self.income_monthly_summaries.exists_duplicate(
                    portfolio_id=portfolio_id,
                    wallet_name=summary.wallet_name,
                    year=summary.year,
                    month=summary.month,
                    currency=summary.currency,
                    source=summary.source,
                )
                if is_duplicate:
                    skipped_duplicate += 1
                    continue

                self.income_monthly_summaries.create(
                    self._to_monthly_summary_model(portfolio_id, summary)
                )
                created += 1
            except Exception as exc:  # noqa: BLE001 - um resumo ruim não derruba os demais
                self.db.rollback()
                errors.append(
                    f"falha ao gravar resumo mensal de {summary.wallet_name} "
                    f"{summary.year}-{summary.month:02d}: {type(exc).__name__}"
                )
                logger.error("Falha ao gravar IncomeMonthlySummary: %s", type(exc).__name__)

        status = "success" if not errors else ("partial" if created else "failed")
        finished_at = datetime.now(UTC)

        return IncomeMonthlySyncRunResult(
            provider=PROVIDER,
            status=status,
            portfolio_id=portfolio_id,
            summaries_found=preview.summaries_valid,
            summaries_created=created,
            summaries_skipped_duplicate=skipped_duplicate,
            errors=errors,
            started_at=started_at,
            finished_at=finished_at,
            preview=preview,
        )

    @staticmethod
    def _to_monthly_summary_model(
        portfolio_id: int, summary: NormalizedMonthlySummary
    ) -> IncomeMonthlySummary:
        return IncomeMonthlySummary(
            portfolio_id=portfolio_id,
            wallet_name=summary.wallet_name,
            year=summary.year,
            month=summary.month,
            amount_total=summary.amount_total,
            currency=summary.currency,
            source=summary.source,
            status=summary.status,
            annual_total=summary.annual_total,
            annual_average=summary.annual_average,
            raw_payload_json=json.dumps(summary.raw_payload, ensure_ascii=False),
        )
