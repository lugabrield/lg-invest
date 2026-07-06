"""Login no Dividendos.me via Playwright (Sprint 23).

Única responsabilidade deste módulo: preencher o formulário de login e
confirmar que a sessão entrou. Nunca loga e-mail/senha, nunca captura
screenshot da tela de login, e qualquer falha vira uma mensagem
genérica e segura — o detalhe técnico da exceção original nunca chega
ao usuário nem ao log (Volume 20, regras de segurança do usuário).
"""

from __future__ import annotations

from backend.app.core.logging import get_logger

logger = get_logger("lg_invest.integrations.dividendos_me.auth")

LOGIN_URL = "https://app.dividendos.me/signin"
DASHBOARD_URL = "https://app.dividendos.me/"

GENERIC_AUTH_ERROR = (
    "Falha ao autenticar no Dividendos.me. Verifique credenciais ou tente novamente."
)


class DividendosMeAuthError(Exception):
    """Erro de autenticação — a mensagem já é sempre segura para exibir ao usuário."""


def is_playwright_available() -> bool:
    """Usado pela UI para desabilitar o botão de sincronização quando
    Playwright não está instalado no ambiente (ex.: Streamlit Cloud)."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return True


def login(page, email: str, password: str, *, timeout_ms: int = 30_000) -> None:
    """Preenche o formulário de login e aguarda o dashboard carregar.

    Recebe uma `page` do Playwright já criada pelo chamador (`client.py`),
    para que login e navegação subsequente compartilhem o mesmo browser
    context — nenhuma sessão/cookie é persistida em disco entre execuções.
    """
    try:
        page.goto(LOGIN_URL, timeout=timeout_ms)
        page.fill('input[type="email"], input[name="email"]', email)
        page.fill('input[type="password"], input[name="password"]', password)
        page.click('button:has-text("Entrar")')
        page.wait_for_url(DASHBOARD_URL, timeout=timeout_ms)
    except Exception:  # noqa: BLE001 - nunca propagar detalhe da exceção original
        # Log só confirma QUE falhou, nunca o detalhe (poderia ecoar a URL
        # com querystring ou algum fragmento de resposta do site).
        logger.warning("Falha de login no Dividendos.me (detalhe suprimido por segurança).")
        raise DividendosMeAuthError(GENERIC_AUTH_ERROR) from None
