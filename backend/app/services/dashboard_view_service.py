"""Servico de apresentacao do Dashboard (multi-moeda + preco estimado/manual)."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.engines.portfolio.engine import build_summary
from backend.app.infrastructure.database.models.price import Price
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.position_repository import PositionRepository
from backend.app.infrastructure.repositories.price_repository import PriceRepository
from backend.app.schemas.dashboard_view import (
    ConvertedPosition,
    CurrencyExposure,
    DashboardView,
)
from backend.app.services.portfolio_service import PortfolioService

_ZERO = Decimal("0")

_GROUP_LABELS: dict[tuple[str, str], str] = {
    ("stock", "BRL"): "Ações BR",
    ("stock", "USD"): "Ações EUA",
    ("fii", "BRL"): "FIIs",
    ("etf", "BRL"): "ETFs",
    ("etf", "USD"): "ETFs",
    ("reit", "BRL"): "REITs",
    ("reit", "USD"): "REITs",
    ("crypto", "BRL"): "Cripto",
    ("crypto", "USD"): "Cripto",
    ("bond", "BRL"): "Renda Fixa",
    ("bond", "USD"): "Renda Fixa",
    ("cash", "BRL"): "Renda Fixa",
    ("cash", "USD"): "Renda Fixa",
}

GROUP_ORDER: list[str] = [
    "Ações BR",
    "FIIs",
    "Ações EUA",
    "ETFs",
    "REITs",
    "Cripto",
    "Renda Fixa",
]


def _group_label(asset_class: str, currency: str) -> str:
    return _GROUP_LABELS.get((asset_class, currency), f"{asset_class.title()} ({currency})")


def _load_price_rows(
    db: Session, portfolio_id: int
) -> tuple[dict[str, Price | None], dict[str, bool]]:
    positions = PositionRepository(db).list_by_portfolio(portfolio_id)
    assets = AssetRepository(db)
    prices = PriceRepository(db)

    latest_by_ticker: dict[str, Price | None] = {}
    is_manual_by_ticker: dict[str, bool] = {}
    for position in positions:
        asset = assets.get_by_id(position.asset_id)
        if asset is None:
            continue
        latest_by_ticker[asset.ticker] = prices.get_latest(asset.id)
        is_manual_by_ticker[asset.ticker] = asset.is_manual
    return latest_by_ticker, is_manual_by_ticker


def build_dashboard_view(db: Session, portfolio_id: int, exchange_rate: Decimal) -> DashboardView:
    raw_inputs = PortfolioService(db).build_inputs(portfolio_id)
    latest_price_by_ticker, is_manual_by_ticker = _load_price_rows(db, portfolio_id)

    estimated_tickers: list[str] = []
    adjusted_inputs = []
    for position_input in raw_inputs:
        # Ativo manual (ex.: Tesouro Direto) sem nenhuma linha de Price ainda
        # não deve virar "estimado" (preço médio como aproximação) — deve
        # continuar sinalizado como "manual" mais abaixo, mesmo que o valor
        # de exibição também caia no preço médio na ausência de cotação
        # própria. A lista `estimated_tickers` (usada pelo aviso amarelo do
        # Dashboard) é reservada para ativos automáticos sem cotação.
        if position_input.current_price is None:
            if not is_manual_by_ticker.get(position_input.ticker, False):
                estimated_tickers.append(position_input.ticker)
            adjusted_inputs.append(
                replace(position_input, current_price=position_input.average_price)
            )
        else:
            adjusted_inputs.append(position_input)

    summary = build_summary(adjusted_inputs)

    def to_brl(value: Decimal, currency: str) -> Decimal:
        if currency == "USD":
            return value * exchange_rate
        return value

    converted_values: dict[str, Decimal] = {}
    converted_costs: dict[str, Decimal] = {}
    total_converted = _ZERO
    total_cost_converted = _ZERO
    for p in summary.positions:
        value_brl = to_brl(p.position_value, p.currency)
        cost_brl = to_brl(p.quantity * p.average_price, p.currency)
        converted_values[p.ticker] = value_brl
        converted_costs[p.ticker] = cost_brl
        total_converted += value_brl
        total_cost_converted += cost_brl

    manual_tickers: list[str] = []
    positions: list[ConvertedPosition] = []
    for p in summary.positions:
        value_brl = converted_values[p.ticker]
        weight = (value_brl / total_converted) if total_converted > 0 else _ZERO
        is_estimated = p.ticker in estimated_tickers
        is_manual_asset = is_manual_by_ticker.get(p.ticker, False)

        latest_price = latest_price_by_ticker.get(p.ticker)
        if is_manual_asset:
            # Ativo marcado como manual (ex.: Tesouro Direto) tem prioridade
            # sobre qualquer outra inferência: nunca "estimado" nem "ausente",
            # mesmo que ainda não tenha uma linha de Price salva — mesma
            # convenção de `pages_impl/ativos.py::_price_status`.
            price_source = "manual"
            price_updated_at = latest_price.updated_at if latest_price is not None else None
            manual_tickers.append(p.ticker)
        elif is_estimated:
            price_source = "estimated"
            price_updated_at = None
        elif latest_price is not None and latest_price.source == "manual":
            price_source = "manual"
            price_updated_at = latest_price.updated_at
            manual_tickers.append(p.ticker)
        else:
            price_source = "yahoo"
            price_updated_at = latest_price.updated_at if latest_price is not None else None

        positions.append(
            ConvertedPosition(
                ticker=p.ticker,
                asset_class=p.asset_class,
                currency=p.currency,
                quantity=p.quantity,
                average_price=p.average_price,
                current_price=p.current_price,
                position_value=p.position_value,
                position_value_brl=value_brl,
                weight=weight,
                return_pct=p.return_pct,
                is_price_estimated=is_estimated,
                group_label=_group_label(p.asset_class, p.currency),
                price_source=price_source,
                price_updated_at=price_updated_at,
            )
        )
    positions.sort(key=lambda pos: pos.position_value_brl, reverse=True)

    total_brl_nominal = sum(
        (p.position_value for p in summary.positions if p.currency == "BRL"), _ZERO
    )
    total_usd_nominal = sum(
        (p.position_value for p in summary.positions if p.currency == "USD"), _ZERO
    )

    by_currency: dict[str, Decimal] = {}
    for p in summary.positions:
        by_currency[p.currency] = by_currency.get(p.currency, _ZERO) + converted_values[p.ticker]
    currency_exposure = [
        CurrencyExposure(
            currency=currency,
            value_brl=value,
            weight=(value / total_converted) if total_converted > 0 else _ZERO,
        )
        for currency, value in sorted(by_currency.items(), key=lambda kv: kv[1], reverse=True)
    ]

    largest = max(converted_values, key=converted_values.get) if converted_values else None

    total_return_pct = (
        (total_converted - total_cost_converted) / total_cost_converted
        if total_cost_converted > 0
        else None
    )

    return DashboardView(
        exchange_rate=exchange_rate,
        total_brl=total_brl_nominal,
        total_usd=total_usd_nominal,
        total_converted_brl=total_converted,
        total_cost_brl=total_cost_converted,
        total_return_pct=total_return_pct,
        is_multi_currency=summary.is_multi_currency,
        currency_exposure=currency_exposure,
        positions=positions,
        largest_position_ticker=largest,
        concentration_hhi=summary.concentration_hhi,
        effective_number_of_assets=summary.effective_number_of_assets,
        estimated_price_tickers=estimated_tickers,
        manual_price_tickers=manual_tickers,
        unpriced_tickers=summary.unpriced_tickers,
    )
