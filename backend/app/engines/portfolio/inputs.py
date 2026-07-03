"""Contrato de entrada do Portfolio Engine (Volume 20, prompt 8).

`PositionInput` é o "dado já tratado" que a engine recebe. A engine
NUNCA vê SQLAlchemy nem busca preços: o serviço resolve quantity,
preço médio e preço atual e entrega esta estrutura pronta.

Manter este contrato puro (dataclass, Decimal) é o que permite testar
a engine com valores conhecidos, sem banco e sem rede.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PositionInput:
    """Uma posição com tudo o que a engine precisa para calcular."""

    ticker: str
    asset_class: str
    currency: str
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal | None  # None quando não há preço atual disponível
