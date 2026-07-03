"""Testes do target_allocation_settings_service (persistência em JSON).

Isola o arquivo real (`data/app_settings.json`) via monkeypatch, para não
gravar nada no ambiente de desenvolvimento durante os testes.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.services import target_allocation_settings_service as svc


@pytest.fixture(autouse=True)
def _isolated_settings_file(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "_SETTINGS_PATH", tmp_path / "app_settings.json")


def test_empty_when_no_file():
    assert svc.get_target_allocation() == {}


def test_set_and_get_roundtrip():
    allocation = {
        "stock": Decimal("0.40"),
        "fii": Decimal("0.20"),
        "etf": Decimal("0.15"),
        "reit": Decimal("0.10"),
        "crypto": Decimal("0.05"),
        "bond": Decimal("0.05"),
        "cash": Decimal("0.05"),
    }
    svc.set_target_allocation(allocation)
    saved = svc.get_target_allocation()
    assert saved == allocation


def test_rejects_allocation_not_summing_to_one():
    with pytest.raises(ValueError, match="100%"):
        svc.set_target_allocation({"stock": Decimal("0.5")})


def test_rejects_unknown_asset_class():
    with pytest.raises(ValueError, match="desconhecida"):
        svc.set_target_allocation({"stock": Decimal("0.5"), "nft": Decimal("0.5")})


def test_rejects_negative_allocation():
    with pytest.raises(ValueError, match="negativa"):
        svc.set_target_allocation({"stock": Decimal("1.5"), "fii": Decimal("-0.5")})


def test_clear_target_allocation():
    svc.set_target_allocation({"stock": Decimal("1.0")})
    assert svc.get_target_allocation() != {}
    svc.clear_target_allocation()
    assert svc.get_target_allocation() == {}


def test_ignores_unknown_class_when_reading(tmp_path, monkeypatch):
    import json

    path = tmp_path / "app_settings.json"
    monkeypatch.setattr(svc, "_SETTINGS_PATH", path)
    path.write_text(
        json.dumps({"target_allocation": {"stock": "0.5", "nft": "0.5"}}), encoding="utf-8"
    )
    result = svc.get_target_allocation()
    assert result == {"stock": Decimal("0.5")}
