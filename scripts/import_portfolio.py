"""CLI de importação de carteira.

Uso:
    python -m scripts.import_portfolio --portfolio-id 1 --file caminho/arquivo.csv

Cria a carteira se ela não existir (com nome padrão) apenas quando a
flag --create-portfolio for usada, para evitar criar carteiras por engano.
"""

from __future__ import annotations

import argparse
import json

from backend.app.core.logging import configure_logging, get_logger
from backend.app.infrastructure.database.models.portfolio import Portfolio
from backend.app.infrastructure.database.session import get_session
from backend.app.infrastructure.repositories.portfolio_repository import PortfolioRepository
from backend.app.services.portfolio_import_service import PortfolioImportService

logger = get_logger("lg_invest.cli.import_portfolio")


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa posições para uma carteira.")
    parser.add_argument("--portfolio-id", type=int, required=True)
    parser.add_argument("--file", type=str, required=True)
    parser.add_argument(
        "--create-portfolio",
        action="store_true",
        help="Cria a carteira com nome padrão caso o id não exista.",
    )
    args = parser.parse_args()

    configure_logging()

    with get_session() as session:
        repo = PortfolioRepository(session)
        portfolio = repo.get_by_id(args.portfolio_id)
        if portfolio is None:
            if not args.create_portfolio:
                raise SystemExit(
                    f"Carteira {args.portfolio_id} não existe. "
                    "Use --create-portfolio para criá-la."
                )
            portfolio = repo.create(Portfolio(name=f"Carteira {args.portfolio_id}"))
            logger.info("Carteira criada: id=%s", portfolio.id)

        service = PortfolioImportService(session)
        result = service.import_positions(portfolio.id, args.file)

    print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
