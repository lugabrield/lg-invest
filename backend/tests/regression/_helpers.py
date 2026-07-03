"""Utilitário para testes de regressão (Volume 18, seção 9).

Carrega uma fixture de carteira (JSON) num banco SQLite em memória,
com ativos, posições e um preço atual por ativo, e devolve a sessão
e o portfolio_id. Assim os serviços podem ser exercitados de ponta a
ponta de forma determinística, sem rede.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import (
    Asset,
    Portfolio,
    Position,
    Price,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def load_fixture(name: str) -> dict:
    with (FIXTURES_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


def build_session_from_fixture(name: str):
    """Cria um banco em memória populado com a fixture. Retorna (session, portfolio_id)."""
    data = load_fixture(name)

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()

    portfolio = Portfolio(
        name=data["portfolio"]["name"],
        base_currency=data["portfolio"]["base_currency"],
    )
    session.add(portfolio)
    session.flush()

    asset_by_ticker: dict[str, Asset] = {}
    for a in data["assets"]:
        asset = Asset(
            ticker=a["ticker"],
            name=a["name"],
            asset_class=a["asset_class"],
            country=a["country"],
            currency=a["currency"],
            sector=a.get("sector"),
        )
        session.add(asset)
        session.flush()
        asset_by_ticker[a["ticker"]] = asset

    for p in data["positions"]:
        asset = asset_by_ticker[p["ticker"]]
        session.add(
            Position(
                portfolio_id=portfolio.id,
                asset_id=asset.id,
                quantity=Decimal(p["quantity"]),
                average_price=Decimal(p["average_price"]),
                currency=p["currency"],
                opened_at=date.fromisoformat(p["opened_at"]),
            )
        )

    for ticker, price in data["current_prices"].items():
        asset = asset_by_ticker[ticker]
        session.add(
            Price(
                asset_id=asset.id,
                date=date(2026, 6, 27),
                close=Decimal(price),
            )
        )

    session.commit()
    return session, portfolio.id
