"""Testes de login do Dividendos.me (Sprint 23).

Garante a regra de segurança mais crítica da integração: nenhuma
falha de login pode vazar e-mail/senha em exceção ou log, e o usuário
sempre vê a mesma mensagem genérica.
"""

from __future__ import annotations

import logging

import pytest

from backend.app.integrations.dividendos_me.auth import (
    GENERIC_AUTH_ERROR,
    DividendosMeAuthError,
    login,
)

_PASSWORD = "secret_password_123"
_EMAIL = "user@example.com"


class _FailingPage:
    """Simula uma falha do Playwright que ecoa dados sensíveis na exceção
    original (ex.: uma URL completa) — o `login()` nunca deve deixar isso
    vazar para fora."""

    def goto(self, *_a, **_k):
        raise RuntimeError(f"timeout ao carregar url com senha={_PASSWORD}")

    def fill(self, *_a, **_k):
        pass

    def click(self, *_a, **_k):
        pass

    def wait_for_url(self, *_a, **_k):
        pass


def test_login_failure_raises_generic_error():
    page = _FailingPage()
    with pytest.raises(DividendosMeAuthError) as exc_info:
        login(page, _EMAIL, _PASSWORD)
    assert str(exc_info.value) == GENERIC_AUTH_ERROR


def test_login_failure_never_logs_password(caplog):
    page = _FailingPage()
    with caplog.at_level(logging.WARNING, logger="lg_invest.integrations.dividendos_me.auth"):
        with pytest.raises(DividendosMeAuthError):
            login(page, _EMAIL, _PASSWORD)

    assert len(caplog.records) >= 1
    for record in caplog.records:
        message = record.getMessage()
        assert _PASSWORD not in message
        assert _EMAIL not in message


def test_login_success_does_not_raise():
    class _SucceedingPage:
        def goto(self, *_a, **_k):
            pass

        def fill(self, *_a, **_k):
            pass

        def click(self, *_a, **_k):
            pass

        def wait_for_url(self, *_a, **_k):
            pass

    login(_SucceedingPage(), _EMAIL, _PASSWORD)  # não deve levantar
