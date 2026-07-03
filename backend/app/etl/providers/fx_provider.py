"""Interface de provedor de câmbio (Sprint 12).

Espelha `MarketDataProvider`: nenhum serviço ou engine deve depender
diretamente de uma API externa de câmbio. Cada fonte (BCB, Yahoo) é um
`FxRateProvider` substituível, permitindo cadeia de fallback no serviço
sem acoplar o resto do sistema a nenhuma fonte específica.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from backend.app.schemas.market_data import FxQuote


class FxRateProvider(ABC):
    """Contrato comum para provedores de câmbio."""

    name: str = "abstract"

    @abstractmethod
    def get_latest(self, pair: str = "USDBRL") -> FxQuote | None:
        """Retorna a cotação mais recente disponível, ou None se indisponível.

        Pode levantar exceção em caso de falha de rede ou resposta
        inválida — o serviço trata o erro e segue para o próximo
        provider da cadeia de fallback.
        """
        raise NotImplementedError

    @abstractmethod
    def get_quote_on_or_before(self, target: date, pair: str = "USDBRL") -> FxQuote | None:
        """Retorna a cotação em `target` ou, se ausente, no último dia útil anterior.

        Necessário porque o PTAX do BCB não cotiza finais de semana e
        feriados: o provider caminha para trás até encontrar uma cotação.
        """
        raise NotImplementedError
