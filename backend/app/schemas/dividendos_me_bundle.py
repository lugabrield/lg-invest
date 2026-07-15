"""Schemas de apresentação da sincronização Dividendos.me (v1.1, Fase 11).

Fluxo desenhado em `docs/DIVIDENDOS_ME_FRONT_SYNC.md` e contratado em
`docs/API_CONTRACT.md`: credenciais chegam no body de CADA requisição
(nunca um "token de sessão"), nunca são persistidas, nunca aparecem na
resposta. `SyncPreview`/`SyncRunResult`/`IncomeSyncPreview`/
`IncomeSyncRunResult`/`IncomeMonthlySyncPreview`/
`IncomeMonthlySyncRunResult` (todos em
`backend/app/integrations/dividendos_me/schemas.py`) já eram Pydantic
1:1 e são reusados direto como `response_model` das rotas — este módulo
só acrescenta os schemas de REQUISIÇÃO (com email/senha) e o pequeno
bundle de resposta do dry-run (preview + motivos de bloqueio já
calculados, para o frontend nunca duplicar `extraction_blocking_reasons`/
`strong_alert_sections` de `service.py`).
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from backend.app.integrations.dividendos_me.schemas import SyncPreview


class DividendosMeCredentialsRequest(BaseModel):
    """Credenciais do Dividendos.me — nunca logadas, nunca persistidas,
    nunca ecoadas na resposta (ver docs/SECURITY_NOTES.md). Vivem só em
    memória pelo tempo da requisição."""

    email: str
    password: str

    @field_validator("email", "password")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Preencha e-mail e senha do Dividendos.me.")
        return value


class TestLoginResponse(BaseModel):
    success: bool = True


class DividendosMeSyncRequest(DividendosMeCredentialsRequest):
    portfolio_id: int = 1


class SyncUpdateRequest(DividendosMeSyncRequest):
    confirm: bool = False


class SyncReplaceRequest(DividendosMeSyncRequest):
    confirmation_phrase: str = ""
    """Exige exatamente "SUBSTITUIR" — mesma trava do Streamlit
    (`_CONFIRM_WORD["replace"]`), agora validada no backend em vez de só
    desabilitar um botão na UI."""


class DryRunResponse(BaseModel):
    """Preview da carteira + os mesmos motivos de bloqueio que
    `replace`/`update` calculariam com este preview — calculado uma
    única vez aqui para o frontend nunca reimplementar
    `extraction_blocking_reasons`/`strong_alert_sections`."""

    preview: SyncPreview
    blocking_reasons_replace: list[str] = []
    blocking_reasons_update: list[str] = []
    strong_alert_sections: list[str] = []


class DividendosMeStatusView(BaseModel):
    """Status somente-leitura da integração — nunca depende de
    credenciais (mesmos cards de `_render_status` do Streamlit, exceto
    "credenciais configuradas", que deixou de fazer sentido: agora o
    usuário digita a senha a cada chamada em vez de configurar
    `.env`/`st.secrets`)."""

    playwright_available: bool
    last_sync_at: str | None = None
    last_sync_status: str | None = None
