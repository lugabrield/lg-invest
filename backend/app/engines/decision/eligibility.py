"""Filtro de elegibilidade do Decision Engine (Volume 7, seções 7 e 9).

Remove da seleção, com motivo explícito:
- ativos bloqueados pelo usuário;
- ativos sobreconcentrados (peso atual acima do limite).

Cada exclusão é registrada para a auditoria (Volume 18, seção 10).
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.engines.decision.inputs import DecisionConfig, DecisionInput


@dataclass
class IgnoredAsset:
    ticker: str
    reason: str


def filter_eligible(
    candidates: list[DecisionInput],
    blocked: set[str],
    config: DecisionConfig,
) -> tuple[list[DecisionInput], list[IgnoredAsset]]:
    """Separa candidatos elegíveis dos ignorados (com motivo)."""
    eligible: list[DecisionInput] = []
    ignored: list[IgnoredAsset] = []

    for c in candidates:
        if c.ticker in blocked:
            ignored.append(IgnoredAsset(c.ticker, "ativo bloqueado pelo usuário"))
            continue
        if c.current_weight > config.over_concentration_limit:
            ignored.append(
                IgnoredAsset(
                    c.ticker,
                    f"sobreconcentrado: peso atual {c.current_weight * 100:.1f}% "
                    f"acima do limite {config.over_concentration_limit * 100:.0f}%",
                )
            )
            continue
        eligible.append(c)

    return eligible, ignored
