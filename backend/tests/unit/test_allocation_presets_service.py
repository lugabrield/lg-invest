"""Testes de `allocation_presets_service.py` (ajuste UX Configurações/alocação).

Garante que cada preset é internamente consistente (soma 100%, só usa
classes conhecidas) e que "Personalizado" nunca aplica nada sozinho —
a aplicação real (chamar `target_allocation_settings_service.
set_target_allocation`) é responsabilidade da UI, sempre atrás de uma
confirmação explícita separada da pré-visualização.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.infrastructure.database.models.asset import ASSET_CLASSES
from backend.app.services.allocation_presets_service import (
    ALLOCATION_PRESETS,
    get_preset,
    list_presets,
)


def test_list_presets_returns_all_five_presets():
    presets = list_presets()
    keys = {p.key for p in presets}
    assert keys == {
        "conservador",
        "moderado",
        "crescimento_global",
        "buy_and_hold_internacional",
        "personalizado",
    }


@pytest.mark.parametrize(
    "key",
    ["conservador", "moderado", "crescimento_global", "buy_and_hold_internacional"],
)
def test_preset_allocation_sums_to_100_percent(key):
    preset = get_preset(key)
    total = sum(preset.allocation.values(), Decimal("0"))
    assert abs(total - Decimal("1")) < Decimal("0.001")


@pytest.mark.parametrize(
    "key",
    ["conservador", "moderado", "crescimento_global", "buy_and_hold_internacional"],
)
def test_preset_allocation_only_uses_known_asset_classes(key):
    preset = get_preset(key)
    assert all(asset_class in ASSET_CLASSES for asset_class in preset.allocation)


def test_personalizado_preset_has_no_allocation():
    preset = get_preset("personalizado")
    assert preset.allocation is None


def test_get_preset_raises_for_unknown_key():
    with pytest.raises(ValueError):
        get_preset("agressivo_alavancado")


def test_all_presets_have_label_and_description():
    for preset in ALLOCATION_PRESETS.values():
        assert preset.label
        assert preset.description
