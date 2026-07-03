"""Provedor de câmbio via BCB PTAX (API pública de dados abertos, sem chave).

Fonte primária da cadeia de fallback de câmbio (Sprint 12):
https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata

Usa apenas a biblioteca padrão (`urllib`/`json`) para não adicionar uma
dependência nova só por esta chamada. Não há cotação em finais de
semana e feriados — `get_quote_on_or_before` consulta uma janela de
dias anteriores e usa a cotação mais recente disponível dentro dela.

A cotação PTAX final do dia traz `cotacaoCompra` e `cotacaoVenda`; a
taxa usada aqui é a média simples entre as duas, uma aproximação comum
e neutra (nem sempre o usuário compra nem sempre vende dólar).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from backend.app.core.logging import get_logger
from backend.app.etl.providers.fx_provider import FxRateProvider
from backend.app.schemas.market_data import FxQuote

logger = get_logger("lg_invest.provider.bcb_fx")

_BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"
_TIMEOUT_SECONDS = 10
# Cobre fins de semana longos e feriados prolongados sem exagerar no range.
_MAX_LOOKBACK_DAYS = 7


class BcbFxProvider(FxRateProvider):
    """Cotação PTAX de fechamento (compra/venda) do Banco Central do Brasil."""

    name = "bcb"

    def get_latest(self, pair: str = "USDBRL") -> FxQuote | None:
        return self.get_quote_on_or_before(date.today(), pair=pair)

    def get_quote_on_or_before(self, target: date, pair: str = "USDBRL") -> FxQuote | None:
        if pair != "USDBRL":
            raise ValueError(f"BcbFxProvider só suporta USDBRL no momento (recebido: {pair}).")

        start = target - timedelta(days=_MAX_LOOKBACK_DAYS)
        url = (
            f"{_BASE_URL}/CotacaoDolarPeriodo(dataInicial='{start:%m-%d-%Y}',"
            f"dataFinalCotacao='{target:%m-%d-%Y}')"
            "?$format=json&$select=cotacaoCompra,cotacaoVenda,dataHoraCotacao"
        )

        try:
            payload = self._fetch(url)
        except Exception as exc:  # noqa: BLE001 - falha de fonte externa tratada pelo serviço
            logger.warning("Falha ao consultar BCB PTAX: %s", exc)
            return None

        values = payload.get("value") or []
        if not values:
            logger.warning("BCB PTAX sem cotação entre %s e %s.", start, target)
            return None

        # A API retorna em ordem cronológica crescente; o último item é o
        # pregão mais recente dentro da janela consultada.
        return self._to_quote(values[-1])

    def _fetch(self, url: str) -> dict:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310
            body = response.read().decode("utf-8")
        return json.loads(body)

    def _to_quote(self, raw: dict) -> FxQuote | None:
        try:
            compra = Decimal(str(raw["cotacaoCompra"]))
            venda = Decimal(str(raw["cotacaoVenda"]))
        except (KeyError, InvalidOperation, TypeError) as exc:
            logger.warning("Resposta do BCB PTAX em formato inesperado: %s", exc)
            return None

        rate = (compra + venda) / Decimal("2")
        quote_date_raw = raw.get("dataHoraCotacao")
        quote_date = self._parse_datetime(quote_date_raw) if quote_date_raw else datetime.now(UTC)

        return FxQuote(
            pair="USDBRL",
            rate=rate,
            source=self.name,
            quote_date=quote_date,
            fetched_at=datetime.now(UTC),
            is_override=False,
        )

    @staticmethod
    def _parse_datetime(raw: str) -> datetime:
        # Formato usual do BCB: "2026-07-01 13:05:00.123".
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        return datetime.now(UTC)
