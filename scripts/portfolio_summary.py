"""CLI de resumo de carteira (Portfolio Engine v1).

Uso:
    python -m scripts.portfolio_summary --portfolio-id 1

Lê posições e últimos preços do banco, calcula o resumo via engine e
imprime em JSON. Não busca dados externos.
"""

from __future__ import annotations

import argparse
import json

from backend.app.core.logging import configure_logging
from backend.app.infrastructure.database.session import get_session
from backend.app.services.portfolio_service import PortfolioService


def main() -> None:
    parser = argparse.ArgumentParser(description="Resumo consolidado de uma carteira.")
    parser.add_argument("--portfolio-id", type=int, required=True)
    args = parser.parse_args()

    configure_logging()
    with get_session() as session:
        summary = PortfolioService(session).get_summary(args.portfolio_id)

    # Pydantic serializa Decimal como string em mode="json", preservando precisão.
    print(json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
