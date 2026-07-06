"""Filtro de elegibilidade do Decision Engine (Volume 7, seções 7 e 9).

Remove da seleção, com motivo explícito:
- ativos bloqueados pelo usuário;
- ativos sobreconcentrados (peso atual acima do limite).

Cada exclusão é registrada para a auditoria (Volume 18, seção 10).
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.engines.decision.inputs import (
    DecisionConfig,
    DecisionInput,
    PolicyLimits,
    PortfolioAggregates,
)


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


# --- Decision Engine 3.0 (Sprint 24, Fase 4) --------------------------------
#
# Bloqueio adicional por Investment Policy e por Target Allocation Rule
# Engine v2. Em todo caso, o bloqueio impede APENAS que o ativo receba um
# novo aporte nesta rodada — nunca gera, sugere ou aciona uma recomendação
# de venda (mesma regra de ouro do Target Allocation Engine v2 e da
# Investment Policy: "nunca forçar venda como recomendação padrão").


def filter_eligible_v3(
    candidates: list[DecisionInput],
    blocked: set[str],
    config: DecisionConfig,
    policy: PolicyLimits | None = None,
    aggregates: PortfolioAggregates | None = None,
) -> tuple[list[DecisionInput], list[IgnoredAsset]]:
    """Mesmo filtro do v1 (bloqueio manual + sobreconcentração), acrescido de:

    - limite por ativo (`policy.max_asset_weight`);
    - limite agregado de classe (`policy.max_crypto_weight` para `crypto`,
      `policy.target_fii_max` para `fii`), usando os pesos agregados da
      carteira inteira (`aggregates`), não o peso do ativo isolado;
    - qualquer sinal de `rule_signals` com `gap_status == "blocked"`
      (Target Allocation Rule Engine v2).
    """
    eligible, ignored = filter_eligible(candidates, blocked, config)

    still_eligible: list[DecisionInput] = []
    for c in eligible:
        reason = _policy_block_reason(c, policy, aggregates)
        if reason is not None:
            ignored.append(IgnoredAsset(c.ticker, reason))
            continue

        blocked_signal = next(
            (s for s in c.rule_signals if s.gap_status == "blocked"),
            None,
        )
        if blocked_signal is not None:
            ignored.append(
                IgnoredAsset(
                    c.ticker,
                    f"aporte bloqueado pela meta de alocação-alvo na dimensão "
                    f"'{blocked_signal.dimension_type}' (peso atual acima do máximo "
                    "configurado). Nenhuma venda é recomendada — apenas pausa de aporte.",
                )
            )
            continue

        still_eligible.append(c)

    return still_eligible, ignored


def _policy_block_reason(
    candidate: DecisionInput,
    policy: PolicyLimits | None,
    aggregates: PortfolioAggregates | None,
) -> str | None:
    if policy is None:
        return None

    if policy.max_asset_weight is not None and candidate.current_weight > policy.max_asset_weight:
        return (
            f"excede o peso máximo por ativo da política de investimento "
            f"({candidate.current_weight * 100:.1f}% > "
            f"{policy.max_asset_weight * 100:.1f}%). Aporte pausado, não é recomendação "
            "de venda."
        )

    if aggregates is None:
        return None

    if (
        candidate.asset_class == "crypto"
        and policy.max_crypto_weight is not None
        and aggregates.crypto_weight > policy.max_crypto_weight
    ):
        return (
            f"classe 'crypto' já acima do limite máximo da política "
            f"({aggregates.crypto_weight * 100:.1f}% > "
            f"{policy.max_crypto_weight * 100:.1f}%). Aporte pausado para toda a "
            "classe, não é recomendação de venda."
        )

    if (
        candidate.asset_class == "fii"
        and policy.target_fii_max is not None
        and aggregates.fii_weight > policy.target_fii_max
    ):
        return (
            f"classe 'fii' já acima do limite máximo da política "
            f"({aggregates.fii_weight * 100:.1f}% > {policy.target_fii_max * 100:.1f}%). "
            "Aporte pausado para toda a classe, não é recomendação de venda."
        )

    return None
