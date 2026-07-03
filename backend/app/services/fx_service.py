"""Serviço de câmbio (Sprint 12): cadeia de fallback BCB -> Yahoo -> manual.

Orquestra a atualização automática do câmbio USD/BRL usado para exibição
no Dashboard: tenta o BCB PTAX (fonte primária, oficial e gratuita) e
cai para o Yahoo Finance se o BCB falhar ou não responder. Se ambos
falharem, mantém a última cotação persistida (`fx_settings_service`) em
vez de derrubar a tela por falta de rede. Todo resultado automático é
salvo com origem e data/hora, para a UI mostrar de onde veio o câmbio
em uso.
"""

from __future__ import annotations

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.etl.providers.bcb_fx_provider import BcbFxProvider
from backend.app.etl.providers.fx_provider import FxRateProvider
from backend.app.etl.providers.yahoo_fx_provider import YahooFxProvider
from backend.app.schemas.market_data import FxQuote
from backend.app.services import fx_settings_service

logger = get_logger("lg_invest.service.fx")


def _default_provider_chain() -> list[FxRateProvider]:
    chain: list[FxRateProvider] = []
    if settings.bcb_fx_enabled:
        chain.append(BcbFxProvider())
    chain.append(YahooFxProvider())
    return chain


def update_usd_brl_rate(providers: list[FxRateProvider] | None = None) -> FxQuote:
    """Busca o câmbio USD/BRL automático (BCB -> Yahoo) e persiste o resultado.

    `providers` permite injeção para teste (mesmo padrão de
    `MarketDataService`); em produção usa a cadeia padrão BCB -> Yahoo,
    respeitando `settings.bcb_fx_enabled`.

    Se todas as fontes automáticas falharem, devolve a última cotação
    já persistida (sem sobrescrever o arquivo) em vez de levantar
    exceção — só levanta erro se nunca houve nenhuma cotação salva.
    """
    chain = providers if providers is not None else _default_provider_chain()

    for provider in chain:
        try:
            quote = provider.get_latest("USDBRL")
        except Exception as exc:  # noqa: BLE001 - falha de uma fonte não derruba a cadeia
            logger.warning("Provider de câmbio '%s' falhou: %s", provider.name, exc)
            continue
        if quote is not None:
            fx_settings_service.set_fx_quote(quote)
            logger.info("Câmbio USD/BRL atualizado via %s: %s", quote.source, quote.rate)
            return quote
        logger.warning("Provider de câmbio '%s' não retornou cotação.", provider.name)

    existing = fx_settings_service.get_fx_quote()
    if existing is not None:
        logger.warning("Nenhum provider de câmbio disponível; mantendo última cotação salva.")
        return existing

    raise RuntimeError(
        "Não foi possível obter câmbio USD/BRL (BCB e Yahoo falharam) e não há "
        "nenhuma cotação salva anteriormente. Cadastre um câmbio manual em Configurações."
    )
