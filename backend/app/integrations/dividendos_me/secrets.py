"""Leitura e proteção de credenciais do Dividendos.me (Sprint 23).

Regra de ouro deste módulo (e de qualquer código que o use): o valor
real de e-mail/senha nunca é logado, nunca é salvo em banco/arquivo e
nunca aparece em uma mensagem de erro exibida ao usuário. A única coisa
que a UI/CLI podem mostrar é "configurado: sim/não".

Ordem de leitura (Volume 20, prompt de segurança do usuário):
1. Variáveis de ambiente `DIVIDENDOS_ME_EMAIL` / `DIVIDENDOS_ME_PASSWORD`,
   carregadas do `.env` local via `python-dotenv` diretamente aqui
   (`load_dotenv()`). Importante: `backend/app/core/config.py` usa
   `pydantic-settings` com `env_file=".env"`, mas isso só popula os
   atributos da classe `Settings` — nunca escreve em `os.environ`. Por
   isso este módulo chama `load_dotenv()` por conta própria antes de
   ler `os.getenv`, em vez de depender do carregamento de `config.py`.
2. `st.secrets["dividendos_me"]["email"/"password"]`, só quando rodando
   dentro do Streamlit (import tardio, nunca falha se não houver
   `secrets.toml` ou se o Streamlit não estiver disponível).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

_MASK = "••••••••"
_MISSING_LABEL = "(não configurado)"


@dataclass(frozen=True)
class DividendosMeCredentials:
    """Par de credenciais em memória — nunca serializado, nunca logado."""

    email: str
    password: str

    def __repr__(self) -> str:  # pragma: no cover - defesa extra contra log acidental
        return "DividendosMeCredentials(email=***, password=***)"


def _read_from_env() -> tuple[str | None, str | None]:
    # `load_dotenv()` só define variáveis que ainda não existem em
    # `os.environ` (nunca sobrescreve uma variável de ambiente real já
    # exportada pelo usuário) e é seguro chamar várias vezes — por isso
    # não há necessidade de um "já foi carregado" guardado em cache.
    load_dotenv()
    return os.getenv("DIVIDENDOS_ME_EMAIL"), os.getenv("DIVIDENDOS_ME_PASSWORD")


def _read_from_streamlit_secrets() -> tuple[str | None, str | None]:
    """Só tenta st.secrets quando disponível — nunca levanta exceção para
    quem chama (CLI local não tem Streamlit rodando, e tudo bem)."""
    try:
        import streamlit as st

        section = st.secrets.get("dividendos_me", {})
        return section.get("email"), section.get("password")
    except Exception:  # noqa: BLE001 - ausência de secrets.toml/Streamlit é esperada
        return None, None


def get_dividendos_me_credentials() -> DividendosMeCredentials | None:
    """Devolve as credenciais configuradas, ou `None` se alguma estiver ausente."""
    email, password = _read_from_env()
    if not email or not password:
        st_email, st_password = _read_from_streamlit_secrets()
        email = email or st_email
        password = password or st_password
    if not email or not password:
        return None
    return DividendosMeCredentials(email=email, password=password)


def has_dividendos_me_credentials() -> bool:
    """Usado pela UI/CLI para exibir 'credenciais configuradas: sim/não' — nunca o valor."""
    return get_dividendos_me_credentials() is not None


def mask_secret(value: str | None) -> str:
    """Nunca devolve o valor real: só um indicador fixo de presença/ausência."""
    return _MASK if value else _MISSING_LABEL


def sanitize_message(message: str, *, secrets: list[str | None]) -> str:
    """Remove qualquer substring sensível conhecida de uma mensagem antes de exibi-la.

    Defesa em profundidade: mesmo mensagens de erro que deveriam já vir
    genéricas passam por aqui antes de qualquer log/exibição, caso algum
    valor sensível vaze por engano de uma biblioteca de terceiros
    (ex.: Playwright ecoando a URL completa com querystring).
    """
    sanitized = message
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, _MASK)
    return sanitized
