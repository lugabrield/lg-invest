"""Configuração básica de logging para a LG INVEST.

Centraliza a criação de loggers para que todos os módulos usem o
mesmo formato. Logs não devem expor informações sensíveis (Volume 18).
"""

from __future__ import annotations

import logging

from backend.app.core.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging() -> None:
    """Configura o logging raiz uma única vez, conforme LOG_LEVEL do .env."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format=_LOG_FORMAT,
    )


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger nomeado para o módulo chamador."""
    return logging.getLogger(name)
