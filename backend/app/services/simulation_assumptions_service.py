"""Serviço de premissas de retorno/volatilidade do Monte Carlo Simulation
Engine (Sprint 24, Fase 5).

Guarda premissas de retorno esperado e volatilidade anual por classe de
ativo, usadas apenas pela simulação Monte Carlo (não afeta LG Score,
Decision Engine, Portfolio Engine ou qualquer outra engine).

Persistência simples em `data/app_settings.json` (mesmo arquivo e mesmo
padrão de `fx_settings_service.py`/`target_allocation_settings_service.py`),
sem migration nova — configuração de uso pessoal, não entidade de domínio.

Os defaults abaixo são premissas de mercado de longo prazo (aproximações
didáticas, não dados históricos reais coletados, e nunca uma previsão
garantida de retorno futuro). Ficam sempre visíveis e editáveis pelo
usuário (nunca escondidos) — ver `docs/SIMULATION_ENGINE.md` para o
disclaimer completo.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from backend.app.engines.simulation.inputs import ClassAssumption
from backend.app.infrastructure.database.models.asset import ASSET_CLASSES

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS_PATH = _PROJECT_ROOT / "data" / "app_settings.json"

_KEY_SIMULATION_ASSUMPTIONS = "simulation_assumptions"

DISCLAIMER = (
    "Premissas de retorno e volatilidade são estimativas de longo prazo "
    "definidas por você (ou os defaults do sistema), não previsões de "
    "mercado nem recomendação financeira. Resultados passados não "
    "garantem retornos futuros."
)

# Defaults didáticos de longo prazo, um por classe suportada (ASSET_CLASSES).
# Nunca inventados a partir de dado real de mercado — são pontos de partida
# razoáveis para o perfil Buy and Hold do usuário, sempre editáveis.
_DEFAULT_ASSUMPTIONS: dict[str, tuple[str, str]] = {
    "stock": ("0.11", "0.22"),
    "fii": ("0.09", "0.14"),
    "etf": ("0.09", "0.16"),
    "reit": ("0.08", "0.18"),
    "crypto": ("0.15", "0.60"),
    "bond": ("0.10", "0.03"),
    "cash": ("0.08", "0.01"),
}


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


def get_all_assumptions() -> dict[str, ClassAssumption]:
    """Retorna a premissa (default ou editada pelo usuário) para cada classe
    suportada — sempre todas as `ASSET_CLASSES`, nunca uma lista parcial."""
    data = _read_all()
    saved = data.get(_KEY_SIMULATION_ASSUMPTIONS, {})
    if not isinstance(saved, dict):
        saved = {}

    result: dict[str, ClassAssumption] = {}
    for asset_class in ASSET_CLASSES:
        default_return, default_vol = _DEFAULT_ASSUMPTIONS.get(asset_class, ("0", "0"))
        entry = saved.get(asset_class)
        if isinstance(entry, dict) and "expected_return" in entry and "volatility" in entry:
            try:
                result[asset_class] = ClassAssumption(
                    asset_class=asset_class,
                    expected_return=Decimal(str(entry["expected_return"])),
                    volatility=Decimal(str(entry["volatility"])),
                    source="ajustado pelo usuário",
                )
                continue
            except InvalidOperation:
                pass
        result[asset_class] = ClassAssumption(
            asset_class=asset_class,
            expected_return=Decimal(default_return),
            volatility=Decimal(default_vol),
            source="default do sistema",
        )
    return result


def get_assumption(asset_class: str) -> ClassAssumption:
    """Retorna a premissa para uma única classe (default se não editada)."""
    return get_all_assumptions().get(
        asset_class,
        ClassAssumption(
            asset_class=asset_class,
            expected_return=Decimal("0"),
            volatility=Decimal("0"),
            source="classe sem premissa configurada",
        ),
    )


def set_assumption(asset_class: str, expected_return: Decimal, volatility: Decimal) -> None:
    """Salva uma premissa customizada pelo usuário para uma classe."""
    if asset_class not in ASSET_CLASSES:
        raise ValueError(
            f"Classe de ativo inválida: '{asset_class}'. Valores aceitos: {ASSET_CLASSES}."
        )
    if volatility < 0:
        raise ValueError("Volatilidade não pode ser negativa.")

    data = _read_all()
    saved = data.get(_KEY_SIMULATION_ASSUMPTIONS, {})
    if not isinstance(saved, dict):
        saved = {}
    saved[asset_class] = {
        "expected_return": str(expected_return),
        "volatility": str(volatility),
    }
    data[_KEY_SIMULATION_ASSUMPTIONS] = saved
    _write_all(data)


def reset_assumption(asset_class: str) -> None:
    """Remove a premissa customizada de uma classe, voltando ao default do sistema."""
    data = _read_all()
    saved = data.get(_KEY_SIMULATION_ASSUMPTIONS, {})
    if isinstance(saved, dict) and asset_class in saved:
        saved.pop(asset_class, None)
        data[_KEY_SIMULATION_ASSUMPTIONS] = saved
        _write_all(data)


def reset_all_assumptions() -> None:
    """Remove todas as premissas customizadas, voltando aos defaults do sistema."""
    data = _read_all()
    data.pop(_KEY_SIMULATION_ASSUMPTIONS, None)
    _write_all(data)
