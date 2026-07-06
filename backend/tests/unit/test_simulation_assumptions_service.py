"""Testes do serviço de premissas do Monte Carlo Simulation Engine
(Sprint 24, Fase 5) — persistência em JSON, isolada por arquivo temporário."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.services import simulation_assumptions_service as svc


@pytest.fixture(autouse=True)
def _isolated_settings_file(tmp_path, monkeypatch):
    settings_path = tmp_path / "app_settings.json"
    monkeypatch.setattr(svc, "_SETTINGS_PATH", settings_path)
    yield settings_path


def test_defaults_returned_for_all_asset_classes_when_unset():
    assumptions = svc.get_all_assumptions()
    from backend.app.infrastructure.database.models.asset import ASSET_CLASSES

    assert set(assumptions.keys()) == set(ASSET_CLASSES)
    for assumption in assumptions.values():
        assert assumption.source == "default do sistema"


def test_set_assumption_persists_and_overrides_default():
    svc.set_assumption("stock", Decimal("0.13"), Decimal("0.25"))
    assumption = svc.get_assumption("stock")
    assert assumption.expected_return == Decimal("0.13")
    assert assumption.volatility == Decimal("0.25")
    assert assumption.source == "ajustado pelo usuário"


def test_set_assumption_rejects_unknown_asset_class():
    with pytest.raises(ValueError):
        svc.set_assumption("nao_existe", Decimal("0.1"), Decimal("0.1"))


def test_set_assumption_rejects_negative_volatility():
    with pytest.raises(ValueError):
        svc.set_assumption("stock", Decimal("0.1"), Decimal("-0.1"))


def test_reset_assumption_restores_default():
    svc.set_assumption("bond", Decimal("0.20"), Decimal("0.20"))
    svc.reset_assumption("bond")
    assumption = svc.get_assumption("bond")
    assert assumption.source == "default do sistema"


def test_reset_all_assumptions_restores_every_default():
    svc.set_assumption("stock", Decimal("0.13"), Decimal("0.25"))
    svc.set_assumption("crypto", Decimal("0.30"), Decimal("0.80"))
    svc.reset_all_assumptions()
    assumptions = svc.get_all_assumptions()
    assert all(a.source == "default do sistema" for a in assumptions.values())


def test_other_classes_unaffected_by_single_class_update():
    svc.set_assumption("stock", Decimal("0.13"), Decimal("0.25"))
    bond = svc.get_assumption("bond")
    assert bond.source == "default do sistema"
