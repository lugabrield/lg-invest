"""Interface de provedor de fundamentos (Sprint 13 / Fase 2).

Espelha `MarketDataProvider`/`FxRateProvider`: nenhuma engine ou
serviço deve depender diretamente de uma API externa de fundamentos.
Toda fonte implementa esta interface, de modo que seja substituível
sem alterar o resto do sistema (Volume 4, seção 5).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.app.etl.contracts.fundamental_data import FundamentalData


class FundamentalsProvider(ABC):
    """Contrato comum para provedores de fundamentos."""

    name: str = "abstract"

    @abstractmethod
    def get_latest(self, ticker: str) -> FundamentalData | None:
        """Retorna o snapshot mais recente (TTM/atual) de fundamentos.

        Pode levantar exceção em caso de ticker inválido ou falha de
        rede — o serviço trata o erro. Retorna None quando o provider
        não tem nenhum dado (não necessariamente um erro).
        """
        raise NotImplementedError

    @abstractmethod
    def get_history(self, ticker: str) -> list[FundamentalData]:
        """Retorna snapshots anuais históricos (receita, lucro, EBITDA, FCF, dívida).

        Usado pelo Fundamentals Engine (Sprint 14) para calcular CAGR e
        tendências. Lista vazia quando não há demonstrativos disponíveis.
        """
        raise NotImplementedError
