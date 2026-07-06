"""Testes de leitura/mascaramento de credenciais do Dividendos.me (Sprint 23).

Nenhum teste aqui verifica um valor real de senha exposto em lugar
nenhum — o objetivo é justamente garantir que isso nunca acontece.
"""

from __future__ import annotations

from backend.app.integrations.dividendos_me import secrets as secrets_module


def test_read_from_env_calls_load_dotenv(monkeypatch):
    # Regressão: `pydantic-settings` (usado em `core/config.py`) só popula a
    # própria classe `Settings`, nunca `os.environ` — sem chamar
    # `load_dotenv()` explicitamente aqui, um `.env` com
    # DIVIDENDOS_ME_EMAIL/PASSWORD nunca seria enxergado por `os.getenv()`.
    calls = []
    monkeypatch.setattr(secrets_module, "load_dotenv", lambda *a, **k: calls.append(1))

    secrets_module._read_from_env()

    assert calls == [1]


def test_missing_credentials_returns_none(monkeypatch):
    # `load_dotenv()` só define uma variável se ela ainda não existir em
    # `os.environ` — numa máquina com um `.env` real já preenchido (ex.:
    # a do usuário), ele reintroduziria as credenciais reais logo depois
    # do `delenv` abaixo. Neutralizado aqui para o teste continuar
    # determinístico independente do `.env` local existir ou não.
    monkeypatch.setattr(secrets_module, "load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("DIVIDENDOS_ME_EMAIL", raising=False)
    monkeypatch.delenv("DIVIDENDOS_ME_PASSWORD", raising=False)
    monkeypatch.setattr(secrets_module, "_read_from_streamlit_secrets", lambda: (None, None))

    assert secrets_module.get_dividendos_me_credentials() is None
    assert secrets_module.has_dividendos_me_credentials() is False


def test_missing_one_field_still_returns_none(monkeypatch):
    monkeypatch.setattr(secrets_module, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("DIVIDENDOS_ME_EMAIL", "user@example.com")
    monkeypatch.delenv("DIVIDENDOS_ME_PASSWORD", raising=False)
    monkeypatch.setattr(secrets_module, "_read_from_streamlit_secrets", lambda: (None, None))

    assert secrets_module.get_dividendos_me_credentials() is None


def test_credentials_from_env(monkeypatch):
    monkeypatch.setenv("DIVIDENDOS_ME_EMAIL", "user@example.com")
    monkeypatch.setenv("DIVIDENDOS_ME_PASSWORD", "supersecret")

    creds = secrets_module.get_dividendos_me_credentials()

    assert creds is not None
    assert creds.email == "user@example.com"
    assert creds.password == "supersecret"
    assert secrets_module.has_dividendos_me_credentials() is True


def test_credentials_fallback_to_streamlit_secrets(monkeypatch):
    monkeypatch.setattr(secrets_module, "load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("DIVIDENDOS_ME_EMAIL", raising=False)
    monkeypatch.delenv("DIVIDENDOS_ME_PASSWORD", raising=False)
    monkeypatch.setattr(
        secrets_module,
        "_read_from_streamlit_secrets",
        lambda: ("cloud@example.com", "cloud-secret"),
    )

    creds = secrets_module.get_dividendos_me_credentials()

    assert creds is not None
    assert creds.email == "cloud@example.com"
    assert creds.password == "cloud-secret"


def test_credentials_repr_never_leaks_values(monkeypatch):
    monkeypatch.setenv("DIVIDENDOS_ME_EMAIL", "user@example.com")
    monkeypatch.setenv("DIVIDENDOS_ME_PASSWORD", "supersecret")
    creds = secrets_module.get_dividendos_me_credentials()

    rendered = repr(creds)

    assert "supersecret" not in rendered
    assert "user@example.com" not in rendered


def test_mask_secret():
    assert secrets_module.mask_secret("supersecret") == "••••••••"
    assert secrets_module.mask_secret(None) == "(não configurado)"
    assert secrets_module.mask_secret("") == "(não configurado)"


def test_sanitize_message_removes_known_secrets():
    message = "Erro ao acessar https://x?token=supersecret&user=user@example.com"

    sanitized = secrets_module.sanitize_message(
        message, secrets=["supersecret", "user@example.com"]
    )

    assert "supersecret" not in sanitized
    assert "user@example.com" not in sanitized


def test_sanitize_message_ignores_none_secrets():
    message = "Falha genérica"
    assert secrets_module.sanitize_message(message, secrets=[None, ""]) == message
