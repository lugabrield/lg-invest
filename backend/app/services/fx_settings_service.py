"""Serviço de configurações de câmbio (Dashboard multi-moeda).

Guarda o câmbio USD/BRL usado apenas para exibição no Dashboard
(conversão de apresentação). Não é usado por nenhuma engine e não afeta
Decision Engine, LG Score nem o Portfolio Engine — esses continuam
recebendo valores nominais por moeda, sem conversão.

Persistência simples em arquivo JSON (`data/app_settings.json`), para
manter o MVP sem migration nova: é uma configuração de uso pessoal, não
uma entidade de domínio.

Sprint 12 acrescenta origem (`bcb` | `yahoo` | `manual`) e o momento da
coleta, para que a UI mostre de onde veio o câmbio em uso — sem quebrar
arquivos já existentes de instalações anteriores (Sprint 10.1/11), que
só tinham `usd_brl_rate`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from backend.app.schemas.market_data import FxQuote

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS_PATH = _PROJECT_ROOT / "data" / "app_settings.json"

_DEFAULT_USD_BRL_RATE = Decimal("5.00")
_KEY_USD_BRL_RATE = "usd_brl_rate"
_KEY_USD_BRL_SOURCE = "usd_brl_source"
_KEY_USD_BRL_QUOTE_DATE = "usd_brl_quote_date"
_KEY_USD_BRL_FETCHED_AT = "usd_brl_fetched_at"


def _read_all() -> dict:
    if not _SETTINGS_PATH.exists():
        return {}
    try:
        with _SETTINGS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_all(data: dict) -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _SETTINGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_usd_brl_rate() -> Decimal:
    """Retorna o câmbio USD/BRL configurado, ou o valor padrão se ausente/inválido."""
    data = _read_all()
    raw = data.get(_KEY_USD_BRL_RATE)
    if raw is None:
        return _DEFAULT_USD_BRL_RATE
    try:
        rate = Decimal(str(raw))
    except InvalidOperation:
        return _DEFAULT_USD_BRL_RATE
    if rate <= 0:
        return _DEFAULT_USD_BRL_RATE
    return rate


def get_fx_quote() -> FxQuote | None:
    """Retorna a cotação completa (origem, datas), ou None se nunca foi salva.

    Arquivos antigos (só com `usd_brl_rate`, sem os campos novos) são
    tratados como origem "manual" com data de coleta desconhecida —
    retrocompatibilidade sem exigir migração de arquivo.
    """
    data = _read_all()
    raw_rate = data.get(_KEY_USD_BRL_RATE)
    if raw_rate is None:
        return None
    try:
        rate = Decimal(str(raw_rate))
    except InvalidOperation:
        return None
    if rate <= 0:
        return None

    source = data.get(_KEY_USD_BRL_SOURCE, "manual")
    fetched_at_raw = data.get(_KEY_USD_BRL_FETCHED_AT)
    quote_date_raw = data.get(_KEY_USD_BRL_QUOTE_DATE)
    fetched_at = _parse_datetime(fetched_at_raw) or datetime.now(UTC)
    quote_date = _parse_datetime(quote_date_raw) or fetched_at

    return FxQuote(
        pair="USDBRL",
        rate=rate,
        source=source,
        quote_date=quote_date,
        fetched_at=fetched_at,
        is_override=(source == "manual"),
    )


def set_usd_brl_rate(rate: Decimal) -> None:
    """Salva um câmbio USD/BRL informado manualmente pelo usuário (override)."""
    if rate <= 0:
        raise ValueError("Câmbio USD/BRL deve ser maior que zero.")
    now = datetime.now(UTC)
    data = _read_all()
    data[_KEY_USD_BRL_RATE] = str(rate)
    data[_KEY_USD_BRL_SOURCE] = "manual"
    data[_KEY_USD_BRL_QUOTE_DATE] = now.isoformat()
    data[_KEY_USD_BRL_FETCHED_AT] = now.isoformat()
    _write_all(data)


def set_fx_quote(quote: FxQuote) -> None:
    """Salva uma cotação obtida automaticamente (BCB/Yahoo), com origem e datas."""
    if quote.rate <= 0:
        raise ValueError("Câmbio USD/BRL deve ser maior que zero.")
    data = _read_all()
    data[_KEY_USD_BRL_RATE] = str(quote.rate)
    data[_KEY_USD_BRL_SOURCE] = quote.source
    data[_KEY_USD_BRL_QUOTE_DATE] = quote.quote_date.isoformat()
    data[_KEY_USD_BRL_FETCHED_AT] = quote.fetched_at.isoformat()
    _write_all(data)


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None
