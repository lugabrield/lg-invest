"""Presets de alocação-alvo simples por classe (ajuste UX Configurações/alocação).

Cada preset é só um PONTO DE PARTIDA comum — nunca uma recomendação
financeira e nunca aplicado sozinho: a tela sempre exige uma
pré-visualização e uma confirmação explícita separada antes de chamar
`target_allocation_settings_service.set_target_allocation`. Depois de
aplicado, o usuário pode editar livremente cada classe (mesmo fluxo da
alocação-alvo simples que já existia).

Este módulo é só dados + getters puros — nenhuma leitura/escrita de
banco ou arquivo mora aqui.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.app.infrastructure.database.models.asset import ASSET_CLASSES


@dataclass(frozen=True)
class AllocationPreset:
    key: str
    label: str
    description: str
    # `None` para o preset "Personalizado" — sinaliza "não aplica nada,
    # o usuário vai configurar manualmente".
    allocation: dict[str, Decimal] | None


ALLOCATION_PRESETS: dict[str, AllocationPreset] = {
    "conservador": AllocationPreset(
        key="conservador",
        label="Conservador",
        description=(
            "Prioriza renda fixa e baixa volatilidade: metade da carteira em renda "
            "fixa, exposição pequena a ações/FIIs/ETFs e nenhuma a cripto."
        ),
        allocation={
            "bond": Decimal("0.50"),
            "stock": Decimal("0.20"),
            "fii": Decimal("0.15"),
            "etf": Decimal("0.10"),
            "reit": Decimal("0.00"),
            "crypto": Decimal("0.00"),
            "cash": Decimal("0.05"),
        },
    ),
    "moderado": AllocationPreset(
        key="moderado",
        label="Moderado",
        description=(
            "Equilíbrio entre renda fixa e renda variável, com exposição "
            "internacional moderada (ETFs) e uma fatia pequena em cripto."
        ),
        allocation={
            "stock": Decimal("0.30"),
            "fii": Decimal("0.20"),
            "etf": Decimal("0.20"),
            "bond": Decimal("0.20"),
            "reit": Decimal("0.05"),
            "crypto": Decimal("0.05"),
            "cash": Decimal("0.00"),
        },
    ),
    "crescimento_global": AllocationPreset(
        key="crescimento_global",
        label="Crescimento global",
        description=(
            "Foco em crescimento de patrimônio de longo prazo via ETFs "
            "internacionais e ações, com pouca renda fixa."
        ),
        allocation={
            "etf": Decimal("0.35"),
            "stock": Decimal("0.25"),
            "reit": Decimal("0.10"),
            "crypto": Decimal("0.10"),
            "fii": Decimal("0.10"),
            "bond": Decimal("0.05"),
            "cash": Decimal("0.05"),
        },
    ),
    "buy_and_hold_internacional": AllocationPreset(
        key="buy_and_hold_internacional",
        label="Buy and Hold internacional",
        description=(
            "Maior peso em ETFs e REITs internacionais, reduzindo a dependência "
            "de FIIs/renda imobiliária local — alinhado a horizonte de "
            "longuíssimo prazo."
        ),
        allocation={
            "etf": Decimal("0.40"),
            "reit": Decimal("0.15"),
            "stock": Decimal("0.20"),
            "crypto": Decimal("0.10"),
            "fii": Decimal("0.05"),
            "bond": Decimal("0.05"),
            "cash": Decimal("0.05"),
        },
    ),
    "personalizado": AllocationPreset(
        key="personalizado",
        label="Personalizado",
        description="Não aplica nenhum modelo pronto — configure manualmente abaixo.",
        allocation=None,
    ),
}

# Confere, em tempo de import, que todo preset com alocação cobre só
# classes conhecidas e soma exatamente 100% — um preset mal somado é um
# bug de código, não um estado válido de runtime.
for _preset in ALLOCATION_PRESETS.values():
    if _preset.allocation is None:
        continue
    _unknown = [c for c in _preset.allocation if c not in ASSET_CLASSES]
    if _unknown:
        raise AssertionError(f"Preset {_preset.key!r} usa classe(s) desconhecida(s): {_unknown}")
    _total = sum(_preset.allocation.values(), Decimal("0"))
    if abs(_total - Decimal("1")) > Decimal("0.001"):
        raise AssertionError(f"Preset {_preset.key!r} não soma 100% (soma={_total}).")


def list_presets() -> list[AllocationPreset]:
    """Ordem estável para a UI — mesma ordem de definição acima."""
    return list(ALLOCATION_PRESETS.values())


def get_preset(key: str) -> AllocationPreset:
    if key not in ALLOCATION_PRESETS:
        raise ValueError(
            f"Preset desconhecido: {key!r} (esperado um de {list(ALLOCATION_PRESETS)})"
        )
    return ALLOCATION_PRESETS[key]
