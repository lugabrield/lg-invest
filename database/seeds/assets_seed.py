"""Seed de ativos de demonstração da LG INVEST (Volume 16, seção 11).

Apenas ativos de mercado público, sem nenhum dado pessoal de carteira.
Usado para popular o ambiente de desenvolvimento/demonstração.
"""

from __future__ import annotations

from backend.app.core.logging import configure_logging, get_logger
from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.database.session import get_session

logger = get_logger("lg_invest.seeds.assets")

INITIAL_ASSETS = [
    {
        "ticker": "WEGE3.SA",
        "name": "WEG",
        "asset_class": "stock",
        "country": "BR",
        "currency": "BRL",
        "sector": "Industrial",
    },
    {
        "ticker": "ITUB4.SA",
        "name": "Itaú Unibanco",
        "asset_class": "stock",
        "country": "BR",
        "currency": "BRL",
        "sector": "Financials",
    },
    {
        "ticker": "VOO",
        "name": "Vanguard S&P 500 ETF",
        "asset_class": "etf",
        "country": "US",
        "currency": "USD",
        "sector": "ETF",
    },
]


def run_seed() -> None:
    """Insere os ativos iniciais, ignorando os que já existem (idempotente)."""
    with get_session() as session:
        created = 0
        for item in INITIAL_ASSETS:
            exists = session.query(Asset).filter(Asset.ticker == item["ticker"]).first()
            if exists:
                continue
            session.add(Asset(**item))
            created += 1
        session.commit()
        logger.info("Seed concluído: %s ativo(s) novo(s) inserido(s).", created)


if __name__ == "__main__":
    configure_logging()
    run_seed()
