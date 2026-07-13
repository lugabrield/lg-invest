"""Post-Allocation Constraints Engine (Sprint 29).

Bug corrigido: até esta sprint, o Decision Engine 3.0 só checava se um
ativo já estava sobreconcentrado ANTES do aporte (`eligibility.py`) e
distribuía o valor do aporte como fração DO PRÓPRIO APORTE (`allocation.py`,
`max_single_weight`/`max_new_asset_weight`) — nunca simulava o peso
resultante NA CARTEIRA depois de somar o aporte. Um aporte grande o
suficiente (ex.: R$ 1.000.000 numa carteira de R$ 40.000) conseguia
empurrar uma dimensão inteira (moeda, classe, país ou ativo) muito além
do limite máximo configurado — caso relatado: aporte de R$ 1.000.000
levou a exposição em USD a 97,23% quando o máximo configurado era 60%.

Este módulo é a correção: depois que `select_and_distribute` já decidiu
QUANTO cada ativo receberia (respeitando os limites por fração do
aporte, inalterados), este engine simula o peso de cada dimensão
aplicável (classe/moeda/país/ativo/exposição internacional) DEPOIS do
aporte e corta proporcionalmente qualquer dimensão que ultrapassaria seu
máximo configurado — nunca sugerindo venda, apenas deixando parte do
aporte sem alocar quando não há espaço.

Fórmula (pedida explicitamente pelo usuário):
    portfolio_value_after = portfolio_value_before + contribution_amount
    dimension_value_before = dimension.current_weight * portfolio_value_before
    max_dimension_value_after = dimension.max_weight * portfolio_value_after
    room = max(0, max_dimension_value_after - dimension_value_before)

Precedência de limite por dimensão (mesma regra já estabelecida em
`eligibility.py::filter_eligible_v3`, Sprint 25 Parte 1): regra
detalhada do Target Allocation Rule Engine v2 primeiro; Investment
Policy só como fallback quando não há regra detalhada com `max_weight`
para aquela dimensão; exposição internacional é sempre um limite da
Investment Policy (não existe uma 5ª dimensão detalhada para isso).

Engine pura: nenhum acesso a banco/rede. `DimensionCap`/`CappedDimension`
espelham exatamente os campos já resolvidos por
`engines/target_allocation/engine.py` e `services/decision_service.py`
— este módulo nunca recalcula um current_weight/max_weight por conta
própria, só agrega o que já foi resolvido por ativo em grupos por
dimensão e aplica a restrição pós-aporte.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

from backend.app.engines.decision.allocation import Allocation
from backend.app.engines.decision.inputs import DecisionInput, PolicyLimits, PortfolioAggregates

_CENTS = Decimal("0.01")
_MAX_ITERATIONS = 25

DIMENSION_LABELS = {
    "class": "classe",
    "currency": "moeda",
    "country": "país",
    "asset": "ativo",
    "international": "exposição internacional",
}

SOURCE_DETAILED_RULE = "regra_detalhada"
SOURCE_POLICY = "politica_geral"

_SOURCE_LABELS = {
    SOURCE_DETAILED_RULE: "regra detalhada de alocação-alvo",
    SOURCE_POLICY: "política geral de investimento",
}


def _round_down_cents(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_DOWN)


@dataclass(frozen=True)
class DimensionCap:
    """Limite máximo aplicável a UMA dimensão (classe/moeda/país/ativo/
    exposição internacional), já resolvido pelo chamador — nunca
    recalculado aqui."""

    dimension_type: str
    dimension_key: str
    current_weight: Decimal  # fração 0..1, peso da dimensão ANTES do aporte
    max_weight: Decimal  # fração 0..1
    source: str  # SOURCE_DETAILED_RULE | SOURCE_POLICY


@dataclass
class CappedDimension:
    """Uma dimensão que teve o aporte cortado nesta simulação — usado
    tanto para os `reasons` quanto para a seção "Como a carteira ficaria
    depois" da UI."""

    dimension_type: str
    dimension_key: str
    label: str
    weight_before: Decimal
    weight_after: Decimal
    max_weight: Decimal
    source: str


@dataclass
class PostAllocationResult:
    allocations: list[Allocation]
    unallocated_amount: Decimal
    capped_dimensions: list[CappedDimension] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def _dimension_caps_for_candidate(
    candidate: DecisionInput,
    policy: PolicyLimits | None,
    aggregates: PortfolioAggregates | None,
) -> list[DimensionCap]:
    """Resolve os limites aplicáveis a UM candidato, na mesma ordem de
    precedência de `eligibility.py::filter_eligible_v3`: regra detalhada
    (`rule_signals` com `max_weight` definido) primeiro; Investment
    Policy só como fallback para as combinações que ela cobre hoje
    (peso por ativo, classe `crypto`, classe `fii`); exposição
    internacional é sempre política (não existe regra detalhada
    equivalente)."""
    caps: list[DimensionCap] = []
    detailed_by_type = {
        s.dimension_type: s for s in candidate.rule_signals if s.max_weight is not None
    }

    dimension_keys = {
        "class": candidate.asset_class,
        "currency": candidate.currency,
        "country": candidate.country,
        "asset": candidate.ticker,
    }
    for dimension_type, fallback_key in dimension_keys.items():
        signal = detailed_by_type.get(dimension_type)
        if signal is not None:
            caps.append(
                DimensionCap(
                    dimension_type=dimension_type,
                    dimension_key=signal.dimension_key or fallback_key or "",
                    current_weight=signal.current_weight,
                    max_weight=signal.max_weight,
                    source=SOURCE_DETAILED_RULE,
                )
            )
            continue

        if policy is None:
            continue
        if dimension_type == "asset" and policy.max_asset_weight is not None:
            caps.append(
                DimensionCap(
                    dimension_type="asset",
                    dimension_key=candidate.ticker,
                    current_weight=candidate.current_weight,
                    max_weight=policy.max_asset_weight,
                    source=SOURCE_POLICY,
                )
            )
        elif (
            dimension_type == "class"
            and candidate.asset_class == "crypto"
            and policy.max_crypto_weight is not None
            and aggregates is not None
        ):
            caps.append(
                DimensionCap(
                    dimension_type="class",
                    dimension_key="crypto",
                    current_weight=aggregates.crypto_weight,
                    max_weight=policy.max_crypto_weight,
                    source=SOURCE_POLICY,
                )
            )
        elif (
            dimension_type == "class"
            and candidate.asset_class == "fii"
            and policy.target_fii_max is not None
            and aggregates is not None
        ):
            caps.append(
                DimensionCap(
                    dimension_type="class",
                    dimension_key="fii",
                    current_weight=aggregates.fii_weight,
                    max_weight=policy.target_fii_max,
                    source=SOURCE_POLICY,
                )
            )

    if (
        candidate.is_international
        and policy is not None
        and policy.target_international_max is not None
        and aggregates is not None
    ):
        caps.append(
            DimensionCap(
                dimension_type="international",
                dimension_key="internacional",
                current_weight=aggregates.international_weight,
                max_weight=policy.target_international_max,
                source=SOURCE_POLICY,
            )
        )

    return caps


def apply_post_allocation_constraints(
    allocations: list[Allocation],
    candidates_by_ticker: dict[str, DecisionInput],
    portfolio_value_before: Decimal,
    contribution_amount: Decimal,
    policy: PolicyLimits | None = None,
    aggregates: PortfolioAggregates | None = None,
) -> PostAllocationResult:
    """Corta a distribuição inicial (`allocations`, já decidida por
    `select_and_distribute`) para que nenhuma dimensão aplicável
    (classe/moeda/país/ativo/exposição internacional) ultrapasse seu
    peso máximo configurado DEPOIS do aporte — nunca só antes.

    `portfolio_value_before` precisa ser um valor real (patrimônio
    convertido da carteira); quando o chamador não tem esse dado
    disponível, deve simplesmente não chamar esta função (nunca inventa
    um patrimônio para simular a restrição)."""
    if not allocations:
        return PostAllocationResult(allocations=[], unallocated_amount=Decimal("0"))
    if portfolio_value_before < 0 or contribution_amount <= 0:
        return PostAllocationResult(allocations=list(allocations), unallocated_amount=Decimal("0"))

    portfolio_value_after = portfolio_value_before + contribution_amount

    # Agrupa tickers alocados por dimensão (uma dimensão pode ser
    # compartilhada por vários tickers — ex.: dois ETFs americanos
    # compartilham a mesma dimensão moeda=USD).
    groups: dict[tuple[str, str], dict] = {}
    for allocation in allocations:
        candidate = candidates_by_ticker.get(allocation.ticker)
        if candidate is None:
            continue
        for cap in _dimension_caps_for_candidate(candidate, policy, aggregates):
            key = (cap.dimension_type, cap.dimension_key)
            group = groups.setdefault(key, {"tickers": set(), "cap": cap})
            group["tickers"].add(allocation.ticker)

    remaining: dict[str, Decimal] = {a.ticker: a.amount for a in allocations}
    original_total = sum(remaining.values(), start=Decimal("0"))

    touched_keys: set[tuple[str, str]] = set()
    for _ in range(_MAX_ITERATIONS):
        changed = False
        for key, group in groups.items():
            cap: DimensionCap = group["cap"]
            room = (
                cap.max_weight * portfolio_value_after - cap.current_weight * portfolio_value_before
            )
            room = max(Decimal("0"), room)
            group_tickers = group["tickers"]
            group_total = sum(
                (remaining.get(t, Decimal("0")) for t in group_tickers), start=Decimal("0")
            )
            if group_total > room + _CENTS:
                changed = True
                touched_keys.add(key)
                scale = Decimal("0") if room <= 0 or group_total <= 0 else room / group_total
                for ticker in group_tickers:
                    if ticker in remaining:
                        remaining[ticker] = _round_down_cents(remaining[ticker] * scale)
        if not changed:
            break

    final_allocations = [
        Allocation(
            ticker=a.ticker, amount=remaining.get(a.ticker, Decimal("0")), buy_score=a.buy_score
        )
        for a in allocations
        if remaining.get(a.ticker, Decimal("0")) > 0
    ]
    final_total = sum((a.amount for a in final_allocations), start=Decimal("0"))
    unallocated = max(Decimal("0"), original_total - final_total)

    capped_dimensions: list[CappedDimension] = []
    reasons: list[str] = []
    for key in sorted(touched_keys):
        group = groups[key]
        cap: DimensionCap = group["cap"]
        final_group_total = sum(
            (remaining.get(t, Decimal("0")) for t in group["tickers"]), start=Decimal("0")
        )
        dimension_value_after = cap.current_weight * portfolio_value_before + final_group_total
        weight_after = (
            dimension_value_after / portfolio_value_after
            if portfolio_value_after > 0
            else Decimal("0")
        )
        label = DIMENSION_LABELS.get(cap.dimension_type, cap.dimension_type)
        source_label = _SOURCE_LABELS[cap.source]
        capped_dimensions.append(
            CappedDimension(
                dimension_type=cap.dimension_type,
                dimension_key=cap.dimension_key,
                label=f"{label} '{cap.dimension_key}'",
                weight_before=cap.current_weight,
                weight_after=weight_after,
                max_weight=cap.max_weight,
                source=cap.source,
            )
        )
        reasons.append(
            f"{label} '{cap.dimension_key}' atingiria {weight_after * 100:.1f}% da carteira "
            f"após o aporte, acima do limite máximo de {cap.max_weight * 100:.1f}% "
            f"({source_label}) — parte do aporte para ativo(s) dessa dimensão não foi "
            "alocada. Nenhuma venda é sugerida."
        )

    return PostAllocationResult(
        allocations=final_allocations,
        unallocated_amount=unallocated,
        capped_dimensions=capped_dimensions,
        reasons=reasons,
    )
