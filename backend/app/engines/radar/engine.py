"""Radar Engine puro (Sprint 25, Parte 2.4).

Classifica cada `RadarCandidateInput` em uma das 6 categorias de
`RADAR_CLASSIFICATIONS`. Regra de ouro preservada aqui também: nenhuma
classificação é ou implica uma recomendação de venda — mesmo um ativo
já na carteira com score fraco vira "monitor", nunca "avoid" (esse
rótulo é reservado a candidatos NOVOS, que ainda não têm posição).

Ordem de precedência das checagens (mesma lógica de "regra mais
específica primeiro" usada no Decision Engine 3.0, Sprint 25 Parte 1):

1. `watchlist_status == "blocked"` (decisão explícita do usuário) OU
   `dimension_blocked` (limite de classe/moeda/país já ultrapassado na
   regra detalhada de alocação-alvo) -> "blocked".
2. Dado insuficiente (sem nenhum score, ou confiança abaixo do limiar)
   -> "insufficient_data".
3. Já é uma posição (`is_current_holding`) -> "current_holding_candidate"
   se o score é bom, senão "monitor" (nunca "avoid").
4. Candidato novo: "new_candidate" se `watchlist_status == "candidate"`
   e score bom; "avoid" se score fraco; "monitor" no meio-termo.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.radar.inputs import (
    DEFAULT_RADAR_CONFIG,
    RadarCandidateInput,
    RadarConfig,
)
from backend.app.schemas.radar import RadarClassificationResult, RadarEvaluation


def _effective_score(candidate: RadarCandidateInput) -> tuple[Decimal | None, str | None]:
    """Cadeia de fallback: Conviction Score primeiro (mais completo),
    LG Score em seguida — mesma ideia do fallback de fundamentos do
    Decision Engine 3.0. Nunca inventa um valor: `None` quando nenhum
    dos dois está disponível."""
    if candidate.conviction_score is not None:
        return candidate.conviction_score, "conviction_score"
    if candidate.lg_score is not None:
        return candidate.lg_score, "lg_score"
    return None, None


def _classify_one(candidate: RadarCandidateInput, config: RadarConfig) -> RadarClassificationResult:
    reasons: list[str] = []
    score, score_source = _effective_score(candidate)

    if candidate.watchlist_status == "blocked":
        reasons.append("Ativo bloqueado manualmente pelo usuário na Watchlist.")
        return RadarClassificationResult(
            ticker=candidate.ticker,
            name=candidate.name,
            asset_class=candidate.asset_class,
            watchlist_status=candidate.watchlist_status,
            is_current_holding=candidate.is_current_holding,
            current_weight=candidate.current_weight,
            classification="blocked",
            effective_score=score,
            score_source=score_source,
            confidence=candidate.confidence,
            reasons=reasons,
        )

    if candidate.dimension_blocked:
        reasons.append(
            candidate.dimension_blocked_reason
            or "Dimensão (classe/moeda/país) já no limite máximo configurado."
        )
        return RadarClassificationResult(
            ticker=candidate.ticker,
            name=candidate.name,
            asset_class=candidate.asset_class,
            watchlist_status=candidate.watchlist_status,
            is_current_holding=candidate.is_current_holding,
            current_weight=candidate.current_weight,
            classification="blocked",
            effective_score=score,
            score_source=score_source,
            confidence=candidate.confidence,
            reasons=reasons,
        )

    low_confidence = candidate.confidence is None or candidate.confidence < config.min_confidence
    if score is None or low_confidence:
        if score is None:
            reasons.append("Sem LG Score nem Conviction Score calculado ainda.")
        if low_confidence:
            reasons.append(
                "Confiança do dado abaixo do limiar mínimo para uma classificação primária."
            )
        return RadarClassificationResult(
            ticker=candidate.ticker,
            name=candidate.name,
            asset_class=candidate.asset_class,
            watchlist_status=candidate.watchlist_status,
            is_current_holding=candidate.is_current_holding,
            current_weight=candidate.current_weight,
            classification="insufficient_data",
            effective_score=score,
            score_source=score_source,
            confidence=candidate.confidence,
            reasons=reasons,
        )

    if candidate.is_current_holding:
        if score >= config.good_score_threshold:
            reasons.append(
                f"Já é uma posição na carteira e o score ({score_source}) segue bom "
                f"({score:.1f} >= {config.good_score_threshold}) — candidato a receber mais aporte."
            )
            classification = "current_holding_candidate"
        else:
            reasons.append(
                f"Já é uma posição na carteira; score ({score_source}) atual não justifica "
                "priorizar novo aporte aqui, mas nenhuma venda é sugerida."
            )
            classification = "monitor"
        return RadarClassificationResult(
            ticker=candidate.ticker,
            name=candidate.name,
            asset_class=candidate.asset_class,
            watchlist_status=candidate.watchlist_status,
            is_current_holding=True,
            current_weight=candidate.current_weight,
            classification=classification,
            effective_score=score,
            score_source=score_source,
            confidence=candidate.confidence,
            reasons=reasons,
        )

    # Candidato novo (nunca teve/tem posição na carteira).
    if score >= config.good_score_threshold and candidate.watchlist_status == "candidate":
        reasons.append(
            f"Candidato novo com score ({score_source}) bom ({score:.1f}) e status "
            "'candidate' na Watchlist — considerar iniciar posição, respeitando o "
            "limite de alocação inicial para ativos novos."
        )
        classification = "new_candidate"
    elif score < config.poor_score_threshold:
        reasons.append(
            f"Candidato novo com score ({score_source}) fraco ({score:.1f} < "
            f"{config.poor_score_threshold}) — não recomendado iniciar posição agora."
        )
        classification = "avoid"
    else:
        reasons.append(
            f"Candidato novo com score ({score_source}) intermediário ({score:.1f}) — "
            "continuar observando antes de decidir."
        )
        classification = "monitor"

    return RadarClassificationResult(
        ticker=candidate.ticker,
        name=candidate.name,
        asset_class=candidate.asset_class,
        watchlist_status=candidate.watchlist_status,
        is_current_holding=False,
        current_weight=None,
        classification=classification,
        effective_score=score,
        score_source=score_source,
        confidence=candidate.confidence,
        reasons=reasons,
    )


def evaluate_radar(
    candidates: list[RadarCandidateInput], config: RadarConfig = DEFAULT_RADAR_CONFIG
) -> RadarEvaluation:
    """Classifica todos os candidatos (posições + Watchlist) — pura,
    sem banco/rede."""
    return RadarEvaluation(candidates=[_classify_one(c, config) for c in candidates])
