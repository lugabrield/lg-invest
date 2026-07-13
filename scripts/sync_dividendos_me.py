"""CLI de sincronização com o Dividendos.me (Sprint 23 / 23.2 / 23.3).

Uso:
    python -m scripts.sync_dividendos_me --portfolio-id 1 --mode dry-run
    python -m scripts.sync_dividendos_me --portfolio-id 1 --mode replace --confirm
    python -m scripts.sync_dividendos_me --portfolio-id 1 --mode update --confirm
    python -m scripts.sync_dividendos_me --portfolio-id 1 --mode dry-run --skip-income

Credenciais SEMPRE vêm de variáveis de ambiente / `.env` local
(DIVIDENDOS_ME_EMAIL, DIVIDENDOS_ME_PASSWORD) — nunca de argumento de
linha de comando (apareceria no histórico do shell e em `ps aux`) e
nunca hardcoded. Este script nunca imprime a senha, nem em log, nem em
mensagem de erro.

Modo `replace`/`update` sem `--confirm` só mostra o preview e para —
a confirmação é uma decisão explícita do usuário, nunca automática.

Sprint 23.2/23.3: além da carteira, o script também tenta extrair
proventos/dividendos (`--include-income`, padrão) — em DOIS blocos
separados no JSON de saída: `income_monthly` (histórico mensal agregado,
aba "Análise") e `income_calendar` (calendário futuro, aba "Próximos
Dividendos"). Proventos NUNCA bloqueiam a sincronização da carteira —
uma falha em qualquer um dos dois blocos só aparece nele mesmo, nunca
interrompe `replace`/`update` nem o outro bloco de proventos. Use
`--skip-income` se a extração de proventos deixar o dry-run lento.
"""

from __future__ import annotations

import argparse
import json

from backend.app.core.logging import configure_logging, get_logger
from backend.app.infrastructure.database.session import get_session
from backend.app.integrations.dividendos_me.auth import DividendosMeAuthError
from backend.app.integrations.dividendos_me.client import (
    DividendosMeClient,
    DividendosMeScrapingError,
)
from backend.app.integrations.dividendos_me.income_service import IncomeSyncService
from backend.app.integrations.dividendos_me.secrets import get_dividendos_me_credentials
from backend.app.integrations.dividendos_me.service import (
    DividendosMeSyncService,
    ExtractionInvalidError,
    PortfolioNotFoundError,
    SyncConfirmationRequiredError,
    strong_alert_sections,
)

logger = get_logger("lg_invest.cli.sync_dividendos_me")


def _preview_to_dict(preview) -> dict:
    return {
        "portfolio_id": preview.portfolio_id,
        "status": preview.status,
        "total_patrimonio": str(preview.total_patrimonio),
        "total_patrimonio_status": preview.total_patrimonio_status,
        "total_assets": preview.total_assets,
        "sections_expected": preview.sections_expected,
        "sections_failed": preview.sections_failed,
        "strong_alert_sections": strong_alert_sections(preview),
        "review_required_tickers": preview.review_required_tickers,
        "diagnostics": [
            {
                "section": d.section,
                "selector_used": d.selector_used,
                "raw_rows_detected": d.raw_rows_detected,
                "valid_rows": d.valid_rows,
                "rejected_rows": d.rejected_rows,
                "rejection_reasons": d.rejection_reasons,
                "navigation_detail": d.navigation_detail,
            }
            for d in preview.diagnostics
        ],
        "diff": {
            "kept": preview.diff.kept,
            "updated": preview.diff.updated,
            "created": preview.diff.created,
            "missing_in_source_will_be_removed": preview.diff.missing_in_source,
        },
        "positions": [
            {
                "ticker": p.ticker,
                "asset_class": p.asset_class,
                "quantity": str(p.quantity),
                "average_price": str(p.average_price) if p.average_price is not None else None,
                "current_price": str(p.current_price) if p.current_price is not None else None,
                "current_value": str(p.current_value) if p.current_value is not None else None,
                "currency": p.currency,
                "origin": p.origin,
                "review_required": p.review_required,
            }
            for p in preview.positions
        ],
    }


def _result_to_dict(result) -> dict:
    return {
        "run_id": result.run_id,
        "mode": result.mode,
        "status": result.status,
        "portfolio_id": result.portfolio_id,
        "assets_found": result.assets_found,
        "positions_created": result.positions_created,
        "positions_updated": result.positions_updated,
        "positions_removed": result.positions_removed,
        "errors": result.errors,
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat() if result.finished_at else None,
        "preview": _preview_to_dict(result.preview) if result.preview else None,
    }


def _income_calendar_preview_to_dict(preview) -> dict:
    return {
        "portfolio_id": preview.portfolio_id,
        "events_found": preview.events_found,
        "events_valid": preview.events_valid,
        "events_rejected": preview.events_rejected,
        "calendar_period_start": preview.period_start.isoformat() if preview.period_start else None,
        "calendar_period_end": preview.period_end.isoformat() if preview.period_end else None,
        "total_by_currency": {k: str(v) for k, v in preview.total_by_currency.items()},
        "sections_failed": preview.sections_failed,
        "diagnostics": [
            {
                "section": d.section,
                "selector_used": d.selector_used,
                "raw_rows_detected": d.raw_rows_detected,
                "valid_rows": d.valid_rows,
                "rejected_rows": d.rejected_rows,
                "rejection_reasons": d.rejection_reasons,
                "navigation_detail": d.navigation_detail,
            }
            for d in preview.diagnostics
        ],
        "sample": [
            {
                "ticker": s.ticker,
                "event_type": s.event_type,
                "status": s.status,
                "payment_date": s.payment_date.isoformat() if s.payment_date else None,
                "amount_total": str(s.amount_total),
                "currency": s.currency,
                "source": s.source,
            }
            for s in preview.sample
        ],
    }


def _income_calendar_result_to_dict(result) -> dict:
    return {
        "status": result.status,
        "portfolio_id": result.portfolio_id,
        "calendar_events_found": result.events_found,
        "events_created": result.events_created,
        "events_skipped_duplicate": result.events_skipped_duplicate,
        "errors": result.errors,
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat() if result.finished_at else None,
        "preview": _income_calendar_preview_to_dict(result.preview) if result.preview else None,
    }


def _income_monthly_preview_to_dict(preview) -> dict:
    return {
        "portfolio_id": preview.portfolio_id,
        "monthly_income_found": preview.summaries_valid,
        "summaries_found": preview.summaries_found,
        "summaries_valid": preview.summaries_valid,
        "summaries_rejected": preview.summaries_rejected,
        "years_found": preview.years_found,
        "months_found": preview.months_found,
        "wallets_found": preview.wallets_found,
        "total_by_year": {k: str(v) for k, v in preview.total_by_year.items()},
        "total_by_currency": {k: str(v) for k, v in preview.total_by_currency.items()},
        "sections_failed": preview.sections_failed,
        "diagnostics": [
            {
                "section": d.section,
                "selector_used": d.selector_used,
                "raw_rows_detected": d.raw_rows_detected,
                "valid_rows": d.valid_rows,
                "rejected_rows": d.rejected_rows,
                "rejection_reasons": d.rejection_reasons,
                "navigation_detail": d.navigation_detail,
                "final_url": d.final_url,
                "tabs_found": d.tabs_found,
                "wallet_selectors_found": d.wallet_selectors_found,
                "table_elements_found": d.table_elements_found,
                "canvas_or_svg_detected": d.canvas_or_svg_detected,
                "debug_snapshot_path": d.debug_snapshot_path,
                "debug_screenshot_path": d.debug_screenshot_path,
            }
            for d in preview.diagnostics
        ],
        "sample": [
            {
                "wallet_name": s.wallet_name,
                "year": s.year,
                "month": s.month,
                "amount_total": str(s.amount_total),
                "currency": s.currency,
                "status": s.status,
                "annual_total": str(s.annual_total) if s.annual_total is not None else None,
                "annual_average": str(s.annual_average) if s.annual_average is not None else None,
            }
            for s in preview.sample
        ],
    }


def _income_monthly_result_to_dict(result) -> dict:
    return {
        "status": result.status,
        "portfolio_id": result.portfolio_id,
        "monthly_income_found": result.summaries_found,
        "summaries_created": result.summaries_created,
        "summaries_skipped_duplicate": result.summaries_skipped_duplicate,
        "errors": result.errors,
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat() if result.finished_at else None,
        "preview": _income_monthly_preview_to_dict(result.preview) if result.preview else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincroniza a carteira da LG INVEST com o Dividendos.me."
    )
    parser.add_argument("--portfolio-id", type=int, required=True)
    parser.add_argument("--mode", choices=["dry-run", "replace", "update"], default="dry-run")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Obrigatório para os modos replace/update — nunca implícito.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Roda o browser visível (debug) em vez de headless.",
    )
    income_group = parser.add_mutually_exclusive_group()
    income_group.add_argument(
        "--include-income",
        action="store_true",
        default=True,
        help="Também tenta extrair proventos/dividendos, mensal e calendário (padrão).",
    )
    income_group.add_argument(
        "--skip-income",
        action="store_true",
        help="Pula a extração de proventos (mais rápido, só sincroniza a carteira).",
    )
    parser.add_argument(
        "--debug-income-monthly",
        action="store_true",
        help=(
            "Salva localmente um snapshot de HTML sanitizado + screenshot do estado final "
            "da extração do histórico mensal (aba Análise) — nunca enviado a lugar nenhum, "
            "só para investigar por que raw_rows_detected ficou em 0."
        ),
    )
    parser.add_argument(
        "--debug-dir",
        default=None,
        help="Diretório local para os snapshots de --debug-income-monthly (default: ./debug_dividendos_me).",
    )
    args = parser.parse_args()
    include_income = not args.skip_income

    configure_logging()

    credentials = get_dividendos_me_credentials()
    if credentials is None:
        raise SystemExit(
            "Credenciais do Dividendos.me não configuradas. Defina "
            "DIVIDENDOS_ME_EMAIL e DIVIDENDOS_ME_PASSWORD no .env local."
        )

    client = DividendosMeClient(credentials.email, credentials.password, headless=not args.headed)

    try:
        with get_session() as session:
            service = DividendosMeSyncService(session)

            if args.mode == "dry-run":
                result = service.dry_run(args.portfolio_id, client)
            elif args.mode == "replace":
                result = service.replace(args.portfolio_id, client, confirm=args.confirm)
            else:
                result = service.update(args.portfolio_id, client, confirm=args.confirm)

            output = _result_to_dict(result)

            if include_income:
                income_service = IncomeSyncService(session)

                # Histórico mensal (aba "Análise") — bloco próprio, nunca
                # misturado com o calendário futuro abaixo.
                try:
                    if args.mode == "dry-run":
                        monthly_result = income_service.dry_run_monthly(
                            args.portfolio_id,
                            client,
                            debug=args.debug_income_monthly,
                            debug_dir=args.debug_dir,
                        )
                    else:
                        monthly_result = income_service.import_monthly_summaries(
                            args.portfolio_id, client
                        )
                    output["income_monthly"] = _income_monthly_result_to_dict(monthly_result)
                except Exception as exc:  # noqa: BLE001 - proventos nunca derruba a carteira
                    logger.warning(
                        "Falha ao processar histórico mensal de proventos (detalhe "
                        "suprimido): %s",
                        type(exc).__name__,
                    )
                    output["income_monthly"] = {
                        "status": "failed",
                        "errors": [
                            "Carteira sincronizada, mas o histórico mensal não foi extraído."
                        ],
                    }

                # Calendário futuro (aba "Próximos Dividendos") — bloco
                # próprio, independente do histórico mensal acima.
                try:
                    if args.mode == "dry-run":
                        calendar_result = income_service.dry_run(args.portfolio_id, client)
                    else:
                        calendar_result = income_service.import_events(args.portfolio_id, client)
                    output["income_calendar"] = _income_calendar_result_to_dict(calendar_result)
                except Exception as exc:  # noqa: BLE001 - proventos nunca derruba a carteira
                    logger.warning(
                        "Falha ao processar calendário futuro de proventos (detalhe "
                        "suprimido): %s",
                        type(exc).__name__,
                    )
                    output["income_calendar"] = {
                        "status": "failed",
                        "errors": [
                            "Carteira sincronizada, mas o calendário futuro não foi extraído."
                        ],
                    }

        print(json.dumps(output, indent=2, ensure_ascii=False))

    except SyncConfirmationRequiredError as exc:
        raise SystemExit(
            f"{exc} Rode novamente com --confirm depois de revisar o preview "
            "(use --mode dry-run primeiro para ver o que vai mudar)."
        ) from None
    except ExtractionInvalidError as exc:
        # Mensagem já é a exata exigida (definida em service.py) — nunca
        # existe --force para contornar esta checagem.
        raise SystemExit(str(exc)) from None
    except PortfolioNotFoundError as exc:
        raise SystemExit(str(exc)) from None
    except DividendosMeAuthError as exc:
        # Mensagem já é segura (definida em auth.py) — nunca inclui credenciais.
        raise SystemExit(str(exc)) from None
    except DividendosMeScrapingError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
