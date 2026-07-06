"""Contrato de entrada e configuração do Radar Engine (Sprint 25, Parte 2.4).

A engine é pura: não sabe o que é um `WatchlistAsset` ou uma
`Position` do ORM — só recebe `RadarCandidateInput` já resolvido pelo
`RadarService`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# As 6 classificações possíveis de um candidato do Radar. Nenhuma delas
# é ou implica uma recomendação de venda — mesmo "avoid" só significa
# "não iniciar posição nova agora", nunca "reduza o que já tem".
RADAR_CLASSIFICATIONS = (
    "current_holding_candidate",
    "new_candidate",
    "monitor",
    "avoid",
    "blocked",
    "insufficient_data",
)


@dataclass(frozen=True)
class RadarCandidateInput:
    """Um ativo (já na carteira ou só na Watchlist) já com todos os dados
    resolvidos pelo `RadarService` — a engine só classifica."""

    ticker: str
    name: str
    asset_class: str
    watchlist_status: str | None  # None quando o ativo é só uma posição, sem registro na watchlist
    is_current_holding: bool
    current_weight: Decimal | None = None  # fração 0..1, só quando is_current_holding

    lg_score: Decimal | None = None  # 0..100
    conviction_score: Decimal | None = None  # 0..100
    confidence: Decimal | None = None  # 0..1

    # True quando a dimensão (classe/moeda/país) deste candidato já está
    # "blocked" no Target Allocation Rule Engine v2 — ver
    # `RadarService._dimension_blocked`. Sempre None quando não há regra
    # detalhada configurada para nenhuma dimensão aplicável (nunca inventa
    # bloqueio).
    dimension_blocked: bool = False
    dimension_blocked_reason: str | None = None

    priority: int = 0
    thesis: str | None = None


@dataclass(frozen=True)
class RadarConfig:
    """Limiares de classificação do Radar Engine.

    Mesma escala 0..100 usada pelo LG Score/Conviction Score em todo o
    projeto. `min_confidence` espelha o limiar de baixa confiança usado
    no restante do projeto (Data Quality Layer / Watchlist / Decision
    Engine 3.0) — mantido consistente de propósito.
    """

    good_score_threshold: Decimal = Decimal("60")
    poor_score_threshold: Decimal = Decimal("40")
    min_confidence: Decimal = Decimal("0.5")


DEFAULT_RADAR_CONFIG = RadarConfig()
