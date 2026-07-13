"""Persistência do status da Central de Dados (Sprint 27).

Mesma técnica já usada por `fx_settings_service.py`: JSON simples em
`data/refresh_status.json`, sem migration nova — isto é estado
operacional da UI (quando cada rotina de atualização rodou pela última
vez, e o resumo da última execução), não uma entidade de domínio nem um
dado financeiro em si.

Nunca lido por nenhuma engine — só pela tela Dashboard, para mostrar o
bloco "Última atualização" e o resumo da última execução da Central de
Dados.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from backend.app.schemas.data_refresh import LastRefreshStatus

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_STATUS_PATH = _PROJECT_ROOT / "data" / "refresh_status.json"


def _read_all() -> dict:
    if not _STATUS_PATH.exists():
        return {}
    try:
        with _STATUS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_all(data: dict) -> None:
    _STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _STATUS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def get_last_refresh_status() -> LastRefreshStatus:
    """Timestamps + resumo da última execução de cada rotina.

    Todos os campos ficam `None`/ausentes até a primeira execução real —
    a UI mostra "nunca" nesse caso, nunca uma data fabricada.
    """
    data = _read_all()
    return LastRefreshStatus(
        prices_at=_parse_datetime(data.get("prices_at")),
        fundamentals_at=_parse_datetime(data.get("fundamentals_at")),
        watchlist_at=_parse_datetime(data.get("watchlist_at")),
        valuation_at=_parse_datetime(data.get("valuation_at")),
        trap_detection_at=_parse_datetime(data.get("trap_detection_at")),
        cache_cleared_at=_parse_datetime(data.get("cache_cleared_at")),
        last_summary=data.get("last_summary"),
    )


def record_prices_refresh(summary: dict) -> None:
    """Chamado depois de "Atualizar preços da carteira"."""
    data = _read_all()
    now = datetime.now(UTC).isoformat()
    data["prices_at"] = now
    data.setdefault("last_summary", {})["prices"] = summary
    _write_all(data)


def record_fundamentals_refresh(summary: dict) -> None:
    """Chamado depois de "Atualizar fundamentos da carteira".

    Também marca `valuation_at`/`trap_detection_at`: o botão de
    fundamentos sempre tenta recomputar essas análises junto (ver
    `DataRefreshService.refresh_portfolio_fundamentals`).
    """
    data = _read_all()
    now = datetime.now(UTC).isoformat()
    data["fundamentals_at"] = now
    data["valuation_at"] = now
    data["trap_detection_at"] = now
    data.setdefault("last_summary", {})["fundamentals"] = summary
    _write_all(data)


def record_watchlist_refresh(summary: dict) -> None:
    """Chamado depois de "Atualizar dados da watchlist".

    Também marca `valuation_at`/`trap_detection_at` pelo mesmo motivo de
    `record_fundamentals_refresh` — a coleta da watchlist também
    recomputa essas análises para os tickers aplicáveis.
    """
    data = _read_all()
    now = datetime.now(UTC).isoformat()
    data["watchlist_at"] = now
    data["valuation_at"] = now
    data["trap_detection_at"] = now
    data.setdefault("last_summary", {})["watchlist"] = summary
    _write_all(data)


def record_cache_cleared() -> None:
    """Chamado por "Limpar cache / Recarregar análises"."""
    data = _read_all()
    data["cache_cleared_at"] = datetime.now(UTC).isoformat()
    _write_all(data)
