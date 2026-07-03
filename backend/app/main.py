"""Entrypoint do backend da LG INVEST.

Neste sprint (Setup) o main apenas valida que o ambiente carrega as
configurações e o logging corretamente. A API HTTP, o banco e as
engines financeiras serão adicionados nos sprints seguintes.
"""

from __future__ import annotations

from backend.app.core.config import settings
from backend.app.core.logging import configure_logging, get_logger


def main() -> None:
    configure_logging()
    logger = get_logger("lg_invest.main")
    logger.info("LG INVEST backend iniciado.")
    logger.info("Ambiente: %s", settings.environment)
    logger.info("Banco de dados: %s", settings.database_url)
    logger.info("Setup OK. Engines financeiras serão adicionadas nos próximos sprints.")


if __name__ == "__main__":
    main()
