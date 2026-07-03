"""CLI do LG Score Engine v1.

Uso:
    python -m scripts.lg_score --ticker WEGE3.SA
    python -m scripts.lg_score --portfolio-id 1

Lê dados do banco, calcula o score via engine e imprime em JSON.
"""

from __future__ import annotations

import argparse
import json

from backend.app.core.logging import configure_logging
from backend.app.infrastructure.database.session import get_session
from backend.app.services.lg_score_service import LGScoreService


def main() -> None:
    parser = argparse.ArgumentParser(description="Calcula o LG Score.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticker", type=str, help="Score de um único ativo.")
    group.add_argument("--portfolio-id", type=int, help="Ranking de uma carteira.")
    args = parser.parse_args()

    configure_logging()
    with get_session() as session:
        service = LGScoreService(session)
        if args.ticker:
            result = service.score_ticker(args.ticker)
            payload = (
                result.model_dump(mode="json") if result else {"error": "ativo não encontrado"}
            )
        else:
            results = service.rank_portfolio(args.portfolio_id)
            payload = [r.model_dump(mode="json") for r in results]

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
