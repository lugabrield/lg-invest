"""Teste smoke do Sprint 1 (Setup).

Valida que o ambiente básico carrega: configurações via .env e logging.
Não testa lógica financeira (ainda não existe).
"""

from __future__ import annotations

from backend.app.core.config import settings
from backend.app.core.logging import get_logger


def test_settings_load():
    """As configurações devem carregar com valores padrão válidos."""
    assert settings.environment in {"development", "production", "test"}
    assert settings.database_url.startswith("sqlite:///") or settings.database_url.startswith(
        "postgresql://"
    )
    assert settings.log_level.upper() in {"DEBUG", "INFO", "WARNING", "ERROR"}


def test_logger_is_created():
    """O factory de logger deve retornar um logger nomeado."""
    logger = get_logger("lg_invest.test")
    assert logger.name == "lg_invest.test"


def test_main_importable():
    """O entrypoint do backend deve ser importável sem efeitos colaterais."""
    from backend.app import main

    assert hasattr(main, "main")
