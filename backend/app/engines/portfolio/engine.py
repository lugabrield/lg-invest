"""Portfolio Engine v1 (Volume 8 / Volume 17 §8 / Volume 20 prompt 8).

Engine PURA: recebe `PositionInput` já tratados e devolve um
`PortfolioSummary`. Não acessa banco, não busca preços, não tem efeitos
colaterais — por isso é testável com valores conhecidos.

Calcula: valor por posição, valor total, peso por ativo, peso por classe,
rentabilidade por ativo, rentabilidade total aproximada, maior posição,
concentração (HHI) e exposição por moeda.

Decisões do v1 (aprovadas):
- Sem conversão cambial: soma por moeda e sinaliza is_multi_currency.
- Rentabilidade = preço atual vs. preço médio (aproximada, não TWR/MWR).
- Posições sem preço atual entram em unpriced_tickers e ficam fora dos totais.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.portfolio.concentration import (
    effective_number_of_assets,
    herfindahl_index,
)
from backend.app.engines.portfolio.inputs import PositionInput
from backend.app.schemas.portfolio_summary import (
    AllocationSlice,
    PortfolioSummary,
    PositionResult,
)

_ZERO = Decimal("0")


def _safe_return(current: Decimal, average: Decimal) -> Decimal | None:
    """Rentabilidade vs. preço médio. None quando average == 0 (evita /0)."""
    if average == 0:
        return None
    return (current - average) / average


def build_summary(positions: list[PositionInput]) -> PortfolioSummary:
    """Constrói o resumo consolidado a partir das posições tratadas."""
    priced = [p for p in positions if p.current_price is not None]
    unpriced_tickers = [p.ticker for p in positions if p.current_price is None]

    # Valor e custo por posição (apenas posições com preço entram nos totais).
    position_values: dict[str, Decimal] = {}
    total_value = _ZERO
    total_cost = _ZERO
    for p in priced:
        value = p.quantity * p.current_price  # type: ignore[operator]
        position_values[p.ticker] = value
        total_value += value
        total_cost += p.quantity * p.average_price

    # Resultados por posição (peso depende do total).
    position_results: list[PositionResult] = []
    for p in priced:
        value = position_values[p.ticker]
        weight = (value / total_value) if total_value > 0 else _ZERO
        position_results.append(
            PositionResult(
                ticker=p.ticker,
                asset_class=p.asset_class,
                currency=p.currency,
                quantity=p.quantity,
                average_price=p.average_price,
                current_price=p.current_price,  # type: ignore[arg-type]
                position_value=value,
                weight=weight,
                return_pct=_safe_return(p.current_price, p.average_price),  # type: ignore[arg-type]
            )
        )

    allocation_by_class = _group_allocation(
        priced, position_values, total_value, key=lambda p: p.asset_class
    )
    allocation_by_currency = _group_allocation(
        priced, position_values, total_value, key=lambda p: p.currency
    )

    # Maior posição.
    largest_ticker = max(position_values, key=position_values.get) if position_values else None

    # Concentração sobre os pesos dos ativos.
    weights = [r.weight for r in position_results]
    hhi = herfindahl_index(weights)
    eff_n = effective_number_of_assets(hhi)

    # Rentabilidade total aproximada.
    total_return = _safe_return(total_value, total_cost) if total_cost > 0 else None

    currencies = {p.currency for p in priced}

    return PortfolioSummary(
        total_value=total_value,
        total_cost=total_cost,
        total_return_pct=total_return,
        is_multi_currency=len(currencies) > 1,
        positions=position_results,
        allocation_by_class=allocation_by_class,
        allocation_by_currency=allocation_by_currency,
        largest_position_ticker=largest_ticker,
        concentration_hhi=hhi,
        effective_number_of_assets=eff_n,
        unpriced_tickers=unpriced_tickers,
    )


def _group_allocation(
    priced: list[PositionInput],
    position_values: dict[str, Decimal],
    total_value: Decimal,
    key,
) -> list[AllocationSlice]:
    """Agrupa valores por uma chave (classe ou moeda) e calcula pesos."""
    grouped: dict[str, Decimal] = {}
    for p in priced:
        grouped[key(p)] = grouped.get(key(p), _ZERO) + position_values[p.ticker]

    slices = [
        AllocationSlice(
            label=label,
            value=value,
            weight=(value / total_value) if total_value > 0 else _ZERO,
        )
        for label, value in grouped.items()
    ]
    # Ordena por valor desc para leitura previsível.
    slices.sort(key=lambda s: s.value, reverse=True)
    return slices
