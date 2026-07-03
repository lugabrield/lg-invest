"""CLI do Decision Engine v1.

Uso:
    python -m scripts.recommend --portfolio-id 1 --amount 1000
    python -m scripts.recommend --portfolio-id 1 --amount 1000 --blocked VOO,ITUB4.SA
    python -m scripts.recommend --portfolio-id 1 --amount 1000 --no-persist

Lê posições e LG Scores do banco, gera a recomendação via engine e
imprime em JSON. Por padrão persiste a recomendação para auditoria.
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal

from backend.app.core.logging import configure_logging
from backend.app.infrastructure.database.session import get_session
from backend.app.services.decision_service import DecisionService


def main() -> None:
    parser = argparse.ArgumentParser(description="Recomenda a distribuição de um aporte.")
    parser.add_argument("--portfolio-id", type=int, required=True)
    parser.add_argument("--amount", type=str, required=True, help="Valor do aporte, ex.: 1000")
    parser.add_argument(
        "--blocked", type=str, default="", help="Tickers bloqueados separados por vírgula."
    )
    parser.add_argument(
        "--no-persist", action="store_true", help="Não salvar a recomendação no banco."
    )
    args = parser.parse_args()

    configure_logging()
    blocked = {t.strip().upper() for t in args.blocked.split(",") if t.strip()}

    with get_session() as session:
        service = DecisionService(session)
        result = service.recommend(
            args.portfolio_id,
            Decimal(args.amount),
            blocked=blocked,
            persist=not args.no_persist,
        )

    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
