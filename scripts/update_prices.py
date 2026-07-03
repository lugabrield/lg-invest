"""CLI de atualização de preços de mercado.

Uso:
    python -m scripts.update_prices --ticker WEGE3.SA
    python -m scripts.update_prices --all

Usa o YahooFinanceProvider por padrão. Requer conexão de rede; os
testes automatizados usam mocks e não dependem deste script.
"""

from __future__ import annotations

import argparse
import json

from backend.app.core.logging import configure_logging
from backend.app.etl.providers.yahoo_provider import YahooFinanceProvider
from backend.app.infrastructure.database.session import get_session
from backend.app.services.market_data_service import MarketDataService


def main() -> None:
    parser = argparse.ArgumentParser(description="Atualiza preços de mercado.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticker", type=str, help="Atualiza um único ativo.")
    group.add_argument("--all", action="store_true", help="Atualiza todos os ativos ativos.")
    args = parser.parse_args()

    configure_logging()
    provider = YahooFinanceProvider()

    with get_session() as session:
        service = MarketDataService(session, provider)
        if args.all:
            result = service.update_all_active().as_dict()
        else:
            result = service.update_asset_prices(args.ticker).as_dict()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
