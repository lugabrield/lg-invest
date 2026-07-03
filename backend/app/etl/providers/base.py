"""Interface de provedor de dados de mercado (Volume 4, seção 5).

Nenhuma engine ou serviço deve depender diretamente de uma API externa.
Toda fonte (Yahoo, futuramente outras) implementa esta interface, de
modo que o provider seja substituível sem alterar o resto do sistema.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from backend.app.etl.contracts.price_data import PriceData


class MarketDataProvider(ABC):
    """Contrato comum para provedores de preços."""

    name: str = "abstract"

    @abstractmethod
    def get_history(self, ticker: str, currency: str, start: date | None = None) -> list[PriceData]:
        """Retorna o histórico diário de preços do ticker.

        `start` permite coleta incremental: buscar apenas a partir da
        última data já registrada. Pode levantar exceção em caso de
        ticker inválido ou falha de rede — o serviço trata o erro.
        """
        raise NotImplementedError

    @abstractmethod
    def get_latest(self, ticker: str, currency: str) -> PriceData | None:
        """Retorna o preço mais recente disponível, ou None se indisponível."""
        raise NotImplementedError
