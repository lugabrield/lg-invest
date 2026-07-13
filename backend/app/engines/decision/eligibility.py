"""Filtro de elegibilidade do Decision Engine (Volume 7, seções 7 e 9).

Remove da seleção, com motivo explícito:
- ativos bloqueados pelo usuário;
- ativos sobreconcentrados (peso atual acima do limite).

Cada exclusão é registrada para a auditoria (Volume 18, seção 10).
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.engines.decision.inputs import (
    AllocationRuleSignal,
    DecisionConfig,
    DecisionInput,
    PolicyLimits,
    PortfolioAggregates,
)
from backend.app.schemas.recommendation_result import (
    BLOCK_SOURCE_DETAILED_RULE,
    BLOCK_SOURCE_MANUAL,
    BLOCK_SOURCE_OVER_CONCENTRATION,
    BLOCK_SOURCE_POLICY,
)

# Rótulos em português para a mensagem de bloqueio por regra detalhada
# (Sprint 25, Parte 1) — cobre as 4 dimensões do Target Allocation Rule
# Engine v2 (`engines/target_allocation/engine.py`).
_DIMENSION_LABELS = {
    "class": "classe",
    "currency": "moeda",
    "country": "país",
    "asset": "ativo",
}


@dataclass
class IgnoredAsset:
    ticker: str
    reason: str
    # Sprint 25, Parte 4: qual camada gerou o bloqueio — ver
    # `BLOCK_SOURCE_*` em `schemas/recommendation_result.py`. `None` só
    # para o caso (hoje inexistente) de um chamador externo construir
    # `IgnoredAsset` sem essa informação.
    block_source: str | None = None


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
            ignored.append(
                IgnoredAsset(c.ticker, "ativo bloqueado pelo usuário", BLOCK_SOURCE_MANUAL)
            )
            continue
        if c.current_weight > config.over_concentration_limit:
            ignored.append(
                IgnoredAsset(
                    c.ticker,
                    f"sobreconcentrado: peso atual {c.current_weight * 100:.1f}% "
                    f"acima do limite {config.over_concentration_limit * 100:.0f}%",
                    BLOCK_SOURCE_OVER_CONCENTRATION,
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

    - qualquer sinal de `rule_signals` com `gap_status == "blocked"`
      (Target Allocation Rule Engine v2, regra DETALHADA por classe,
      moeda, país ou ativo) — verificado PRIMEIRO;
    - limite por ativo (`policy.max_asset_weight`) e limite agregado de
      classe (`policy.max_crypto_weight` para `crypto`,
      `policy.target_fii_max` para `fii`) da Investment Policy, usados
      como FALLBACK apenas quando não existe uma regra detalhada com
      `max_weight` definido para a mesma dimensão.

    Precedência de limites (Sprint 25, Parte 1 — corrige bug em que o
    bloqueio usava, por engano, o limite genérico da política mesmo
    quando uma regra detalhada mais específica já existia, e a mensagem
    mostrava o limite errado para o usuário):

    1. Target Allocation Rule Engine v2 (regra detalhada) — se existir
       uma regra com `max_weight` para a dimensão (classe/moeda/país/
       ativo) do candidato, ela é a fonte de verdade do limite,
       independente do que a Investment Policy diga.
    2. Investment Policy — usada só quando NÃO existe regra detalhada
       com `max_weight` para aquela dimensão (hoje cobre `asset`, via
       `max_asset_weight`, e `class` para `crypto`/`fii`, via
       `max_crypto_weight`/`target_fii_max`).
    3. Sem regra detalhada e sem política configurada: nenhum limite é
       inventado — o candidato não é bloqueado por concentração de
       classe/ativo.
    """
    eligible, ignored = filter_eligible(candidates, blocked, config)

    still_eligible: list[DecisionInput] = []
    for c in eligible:
        blocked_signal = next(
            (s for s in c.rule_signals if s.gap_status == "blocked"),
            None,
        )
        if blocked_signal is not None:
            ignored.append(
                IgnoredAsset(
                    c.ticker,
                    _detailed_rule_block_message(blocked_signal),
                    BLOCK_SOURCE_DETAILED_RULE,
                )
            )
            continue

        dimensions_with_detailed_limit = {
            s.dimension_type for s in c.rule_signals if s.max_weight is not None
        }
        reason = _policy_block_reason(c, policy, aggregates, dimensions_with_detailed_limit)
        if reason is not None:
            ignored.append(IgnoredAsset(c.ticker, reason, BLOCK_SOURCE_POLICY))
            continue

        still_eligible.append(c)

    return still_eligible, ignored


def _detailed_rule_block_message(signal: AllocationRuleSignal) -> str:
    """Mensagem de bloqueio quando a fonte do limite é a regra detalhada
    (Target Allocation Rule Engine v2) — sempre cita 'regra detalhada' e o
    limite máximo configurado NELA, nunca o da Investment Policy."""
    label = _DIMENSION_LABELS.get(signal.dimension_type, signal.dimension_type)
    max_str = f"{signal.max_weight * 100:.1f}%" if signal.max_weight is not None else "configurado"
    return (
        f"{label} '{signal.dimension_key}' já acima do limite máximo configurado na regra "
        f"detalhada de alocação-alvo ({signal.current_weight * 100:.1f}% > {max_str}). "
        "Aporte pausado para essa dimensão, não é recomendação de venda."
    )


def _policy_block_reason(
    candidate: DecisionInput,
    policy: PolicyLimits | None,
    aggregates: PortfolioAggregates | None,
    dimensions_with_detailed_limit: set[str] | None = None,
) -> str | None:
    """Fallback da Investment Policy — só se aplica a uma dimensão quando
    NÃO existe regra detalhada com `max_weight` para ela (ver docstring de
    `filter_eligible_v3`); `dimensions_with_detailed_limit` chega vazio
    quando não há nenhum sinal de regra aplicável, preservando o
    comportamento anterior à Sprint 25 nesse caso."""
    if policy is None:
        return None

    dimensions_with_detailed_limit = dimensions_with_detailed_limit or set()

    if (
        "asset" not in dimensions_with_detailed_limit
        and policy.max_asset_weight is not None
        and candidate.current_weight > policy.max_asset_weight
    ):
        return (
            f"excede o peso máximo por ativo da política geral de investimento "
            f"({candidate.current_weight * 100:.1f}% > "
            f"{policy.max_asset_weight * 100:.1f}%). Aporte pausado, não é recomendação "
            "de venda."
        )

    if aggregates is None or "class" in dimensions_with_detailed_limit:
        return None

    if (
        candidate.asset_class == "crypto"
        and policy.max_crypto_weight is not None
        and aggregates.crypto_weight > policy.max_crypto_weight
    ):
        return (
            f"classe 'crypto' já acima do limite máximo da política geral "
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
            f"classe 'fii' já acima do limite máximo da política geral "
            f"({aggregates.fii_weight * 100:.1f}% > {policy.target_fii_max * 100:.1f}%). "
            "Aporte pausado para toda a classe, não é recomendação de venda."
        )

    return None
