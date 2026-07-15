"""Rotas de sincronização com o Dividendos.me (v1.1, Fase 11 — ver
docs/API_CONTRACT.md, docs/DIVIDENDOS_ME_FRONT_SYNC.md e
docs/SECURITY_NOTES.md).

Composição fina sobre `DividendosMeSyncService` (carteira) e
`IncomeSyncService` (proventos), já validados desde a Sprint 23.
Nenhuma regra de negócio nova vive aqui — a única diferença real em
relação ao Streamlit é a ORIGEM das credenciais: em vez de
`secrets.get_dividendos_me_credentials()` (`.env`/`st.secrets`), agora
vêm no body de cada requisição (`DividendosMeCredentialsRequest`) e
nunca são persistidas, logadas ou ecoadas na resposta — cada etapa
(test-login, dry-run, sync-update, sync-replace, proventos) é uma
chamada HTTP independente, sem "token de sessão" do Dividendos.me.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_portfolio_id
from backend.app.infrastructure.repositories.external_sync_run_repository import (
    ExternalSyncRunRepository,
)
from backend.app.integrations.dividendos_me.auth import (
    DividendosMeAuthError,
    is_playwright_available,
)
from backend.app.integrations.dividendos_me.client import (
    DividendosMeClient,
    DividendosMeScrapingError,
)
from backend.app.integrations.dividendos_me.income_service import IncomeSyncService
from backend.app.integrations.dividendos_me.schemas import (
    IncomeMonthlySyncPreview,
    IncomeMonthlySyncRunResult,
    IncomeSyncPreview,
    IncomeSyncRunResult,
    SyncRunResult,
)
from backend.app.integrations.dividendos_me.secrets import sanitize_message
from backend.app.integrations.dividendos_me.service import (
    DividendosMeSyncService,
    ExtractionInvalidError,
    PortfolioNotFoundError,
    SyncConfirmationRequiredError,
    extraction_blocking_reasons,
    strong_alert_sections,
)
from backend.app.schemas.dividendos_me_bundle import (
    DividendosMeCredentialsRequest,
    DividendosMeStatusView,
    DividendosMeSyncRequest,
    DryRunResponse,
    SyncReplaceRequest,
    SyncUpdateRequest,
    TestLoginResponse,
)

router = APIRouter(prefix="/dividendos-me", tags=["dividendos-me"])

PROVIDER = "dividendos_me"
_CONFIRM_PHRASE_REPLACE = "SUBSTITUIR"

_GENERIC_500_SYNC = "Falha inesperada ao aplicar a sincronização. Nenhuma alteração foi salva."


def _make_client(credentials: DividendosMeCredentialsRequest) -> DividendosMeClient:
    return DividendosMeClient(credentials.email, credentials.password, headless=True)


def _safe_detail(exc: Exception, credentials: DividendosMeCredentialsRequest) -> str:
    """Defesa em profundidade (Regra 6 de docs/SECURITY_NOTES.md): mesmo
    as mensagens já genéricas de `DividendosMeAuthError`/
    `DividendosMeScrapingError` passam por `sanitize_message()` antes de
    virar resposta HTTP, caso alguma lib de terceiro ecoe a senha por
    engano (ex.: Playwright numa URL com querystring de erro)."""
    return sanitize_message(str(exc), secrets=[credentials.email, credentials.password])


@router.get("/status", response_model=DividendosMeStatusView)
def get_status(
    portfolio_id: int = Depends(get_portfolio_id), db: Session = Depends(get_db)
) -> DividendosMeStatusView:
    latest = ExternalSyncRunRepository(db).get_latest(portfolio_id, PROVIDER)
    return DividendosMeStatusView(
        playwright_available=is_playwright_available(),
        last_sync_at=(
            latest.finished_at.isoformat() if latest is not None and latest.finished_at else None
        ),
        last_sync_status=latest.status if latest is not None else None,
    )


@router.post("/test-login", response_model=TestLoginResponse)
def test_login(payload: DividendosMeCredentialsRequest) -> TestLoginResponse:
    """Só confirma que e-mail/senha funcionam — não busca a carteira, não
    salva nada. Mesmo fluxo do botão "Testar login" do Streamlit."""
    client = _make_client(payload)
    try:
        client.test_login()
        return TestLoginResponse(success=True)
    except DividendosMeAuthError as exc:
        raise HTTPException(status_code=401, detail=_safe_detail(exc, payload)) from None
    except DividendosMeScrapingError as exc:
        raise HTTPException(status_code=503, detail=_safe_detail(exc, payload)) from None
    except Exception:  # noqa: BLE001 - nunca vazar detalhe de exceção não prevista
        raise HTTPException(
            status_code=500,
            detail="Falha inesperada ao testar login. Tente novamente em alguns instantes.",
        ) from None


@router.post("/dry-run", response_model=DryRunResponse)
def dry_run(payload: DividendosMeSyncRequest, db: Session = Depends(get_db)) -> DryRunResponse:
    """Busca a carteira e monta o preview — nunca grava nada. A resposta
    já inclui os motivos de bloqueio de `replace`/`update` (mesma lógica
    de `service.py::extraction_blocking_reasons`), para o frontend nunca
    duplicar essa regra de segurança."""
    client = _make_client(payload)
    try:
        preview = DividendosMeSyncService(db).build_preview(payload.portfolio_id, client)
    except PortfolioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_safe_detail(exc, payload)) from None
    except DividendosMeAuthError as exc:
        raise HTTPException(status_code=401, detail=_safe_detail(exc, payload)) from None
    except DividendosMeScrapingError as exc:
        raise HTTPException(status_code=503, detail=_safe_detail(exc, payload)) from None
    except Exception:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail="Falha inesperada ao buscar a carteira. Tente novamente em alguns instantes.",
        ) from None

    return DryRunResponse(
        preview=preview,
        blocking_reasons_replace=extraction_blocking_reasons(preview, mode="replace"),
        blocking_reasons_update=extraction_blocking_reasons(preview, mode="update"),
        strong_alert_sections=strong_alert_sections(preview),
    )


@router.post("/sync-update", response_model=SyncRunResult)
def sync_update(payload: SyncUpdateRequest, db: Session = Depends(get_db)) -> SyncRunResult:
    """Cria/atualiza posições sem remover as que não vierem do
    Dividendos.me — exige `confirm=true` explícito no body (a API nunca
    assume confirmação implícita)."""
    if not payload.confirm:
        raise HTTPException(
            status_code=422,
            detail="Modo 'update' exige confirmação explícita (confirm=true).",
        )
    client = _make_client(payload)
    try:
        return DividendosMeSyncService(db).update(payload.portfolio_id, client, confirm=True)
    except SyncConfirmationRequiredError as exc:
        raise HTTPException(status_code=422, detail=_safe_detail(exc, payload)) from None
    except ExtractionInvalidError as exc:
        raise HTTPException(status_code=422, detail=_safe_detail(exc, payload)) from None
    except PortfolioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_safe_detail(exc, payload)) from None
    except DividendosMeAuthError as exc:
        raise HTTPException(status_code=401, detail=_safe_detail(exc, payload)) from None
    except DividendosMeScrapingError as exc:
        raise HTTPException(status_code=503, detail=_safe_detail(exc, payload)) from None
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=_GENERIC_500_SYNC) from None


@router.post("/sync-replace", response_model=SyncRunResult)
def sync_replace(payload: SyncReplaceRequest, db: Session = Depends(get_db)) -> SyncRunResult:
    """Substitui 100% das posições da carteira pelas do Dividendos.me —
    exige `confirmation_phrase="SUBSTITUIR"` exata (mesma trava do
    Streamlit, agora validada no backend em vez de só desabilitar um
    botão na UI: a API nunca relaxa esse bloqueio, só o `service.py`
    decide se a extração é segura o bastante)."""
    if payload.confirmation_phrase.strip() != _CONFIRM_PHRASE_REPLACE:
        raise HTTPException(
            status_code=422,
            detail=(
                "Para confirmar a substituição, envie "
                f'confirmation_phrase="{_CONFIRM_PHRASE_REPLACE}".'
            ),
        )
    client = _make_client(payload)
    try:
        return DividendosMeSyncService(db).replace(payload.portfolio_id, client, confirm=True)
    except SyncConfirmationRequiredError as exc:
        raise HTTPException(status_code=422, detail=_safe_detail(exc, payload)) from None
    except ExtractionInvalidError as exc:
        raise HTTPException(status_code=422, detail=_safe_detail(exc, payload)) from None
    except PortfolioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_safe_detail(exc, payload)) from None
    except DividendosMeAuthError as exc:
        raise HTTPException(status_code=401, detail=_safe_detail(exc, payload)) from None
    except DividendosMeScrapingError as exc:
        raise HTTPException(status_code=503, detail=_safe_detail(exc, payload)) from None
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=_GENERIC_500_SYNC) from None


# --- Proventos: histórico mensal agregado (income_monthly_summaries) ----


@router.post("/income/monthly/preview", response_model=IncomeMonthlySyncPreview)
def income_monthly_preview(
    payload: DividendosMeSyncRequest, db: Session = Depends(get_db)
) -> IncomeMonthlySyncPreview:
    client = _make_client(payload)
    try:
        return IncomeSyncService(db).build_monthly_preview(payload.portfolio_id, client)
    except PortfolioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_safe_detail(exc, payload)) from None
    except DividendosMeAuthError as exc:
        raise HTTPException(status_code=401, detail=_safe_detail(exc, payload)) from None
    except DividendosMeScrapingError as exc:
        raise HTTPException(status_code=503, detail=_safe_detail(exc, payload)) from None
    except Exception:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail="Falha inesperada ao buscar o histórico mensal de proventos.",
        ) from None


@router.post("/income/monthly/import", response_model=IncomeMonthlySyncRunResult)
def income_monthly_import(
    payload: DividendosMeSyncRequest, db: Session = Depends(get_db)
) -> IncomeMonthlySyncRunResult:
    """Só ADICIONA meses novos por carteira/moeda (nunca duplica, nunca
    remove histórico já salvo) — não exige palavra de confirmação, mesma
    regra do Streamlit."""
    client = _make_client(payload)
    try:
        return IncomeSyncService(db).import_monthly_summaries(payload.portfolio_id, client)
    except PortfolioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_safe_detail(exc, payload)) from None
    except DividendosMeAuthError as exc:
        raise HTTPException(status_code=401, detail=_safe_detail(exc, payload)) from None
    except DividendosMeScrapingError as exc:
        raise HTTPException(status_code=503, detail=_safe_detail(exc, payload)) from None
    except Exception:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail="Falha inesperada ao importar o histórico mensal de proventos.",
        ) from None


# --- Proventos: calendário futuro (income_events) ------------------------


@router.post("/income/calendar/preview", response_model=IncomeSyncPreview)
def income_calendar_preview(
    payload: DividendosMeSyncRequest, db: Session = Depends(get_db)
) -> IncomeSyncPreview:
    client = _make_client(payload)
    try:
        return IncomeSyncService(db).build_preview(payload.portfolio_id, client)
    except PortfolioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_safe_detail(exc, payload)) from None
    except DividendosMeAuthError as exc:
        raise HTTPException(status_code=401, detail=_safe_detail(exc, payload)) from None
    except DividendosMeScrapingError as exc:
        raise HTTPException(status_code=503, detail=_safe_detail(exc, payload)) from None
    except Exception:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail="Falha inesperada ao buscar o calendário futuro de proventos.",
        ) from None


@router.post("/income/calendar/import", response_model=IncomeSyncRunResult)
def income_calendar_import(
    payload: DividendosMeSyncRequest, db: Session = Depends(get_db)
) -> IncomeSyncRunResult:
    """Só ADICIONA eventos futuros novos (nunca duplica, nunca remove
    histórico já salvo) — não exige palavra de confirmação, mesma regra
    do Streamlit."""
    client = _make_client(payload)
    try:
        return IncomeSyncService(db).import_events(payload.portfolio_id, client)
    except PortfolioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_safe_detail(exc, payload)) from None
    except DividendosMeAuthError as exc:
        raise HTTPException(status_code=401, detail=_safe_detail(exc, payload)) from None
    except DividendosMeScrapingError as exc:
        raise HTTPException(status_code=503, detail=_safe_detail(exc, payload)) from None
    except Exception:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail="Falha inesperada ao importar o calendário futuro de proventos.",
        ) from None
