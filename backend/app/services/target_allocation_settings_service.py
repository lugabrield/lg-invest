"""Serviço de configuração de alocação-alvo por classe de ativo (Sprint 17).

Persistência simples em arquivo JSON (`data/app_settings.json`), mesmo
padrão de `fx_settings_service.py` — evita migration nova para uma
configuração de uso pessoal, não uma entidade de domínio.

Não existe alocação-alvo padrão embutida no código: enquanto o usuário
não configurar metas, `get_target_allocation()` devolve um dicionário
vazio e o Target Allocation Engine trata isso como "sem meta definida",
nunca inventa uma alocação "recomendada" (Volume 18 §8 aplicado a
configuração, não só a dado de mercado).
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from backend.app.infrastructure.database.models.asset import ASSET_CLASSES

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS_PATH = _PROJECT_ROOT / "data" / "app_settings.json"

_KEY_TARGET_ALLOCATION = "target_allocation"
_TOLERANCE = Decimal("0.001")


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


def get_target_allocation() -> dict[str, Decimal]:
    """Devolve a alocação-alvo configurada, ou `{}` se o usuário nunca configurou.

    Entradas inválidas (classe desconhecida, fração não numérica) são
    ignoradas silenciosamente em vez de quebrar a leitura inteira.
    """
    data = _read_all()
    raw = data.get(_KEY_TARGET_ALLOCATION)
    if not isinstance(raw, dict):
        return {}

    result: dict[str, Decimal] = {}
    for asset_class, raw_value in raw.items():
        if asset_class not in ASSET_CLASSES:
            continue
        try:
            value = Decimal(str(raw_value))
        except InvalidOperation:
            continue
        if value < 0:
            continue
        result[asset_class] = value
    return result


def set_target_allocation(allocation: dict[str, Decimal]) -> None:
    """Salva a alocação-alvo por classe. Deve somar 1.0 (100%) e usar
    apenas classes conhecidas (`ASSET_CLASSES`)."""
    unknown = [asset_class for asset_class in allocation if asset_class not in ASSET_CLASSES]
    if unknown:
        raise ValueError(f"Classe(s) de ativo desconhecida(s): {', '.join(unknown)}")

    negative = [asset_class for asset_class, value in allocation.items() if value < 0]
    if negative:
        raise ValueError(f"Alocação-alvo não pode ser negativa: {', '.join(negative)}")

    total = sum(allocation.values(), Decimal("0"))
    if abs(total - Decimal("1")) > _TOLERANCE:
        raise ValueError(f"A alocação-alvo deve somar 100% (atual: {total * 100:.1f}%).")

    data = _read_all()
    data[_KEY_TARGET_ALLOCATION] = {
        asset_class: str(value) for asset_class, value in allocation.items()
    }
    _write_all(data)


def clear_target_allocation() -> None:
    """Remove a alocação-alvo configurada (volta ao estado 'sem meta definida')."""
    data = _read_all()
    data.pop(_KEY_TARGET_ALLOCATION, None)
    _write_all(data)
