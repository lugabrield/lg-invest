"""Capital Reinvestment Engine v1 (Sprint 21) — engine PURA.

Extraído de `engines/ids_methodology/pillars.py::capital_reinvestment_pillar_v2`
(Sprint 17) para o mesmo padrão de pacote próprio dos demais engines de
fundamentos (Quality/Growth/Risk/Valuation) — schema de saída dedicado,
service próprio, mesma doutrina de dado ausente (Volume 18 §8). O
IDS Methodology (`ids_methodology/pillars.py`) passa a consumir este
engine em vez de calcular a fórmula inline.

Recebe o snapshot de fundamentos mais recente de um ativo (já carregado
pelo serviço). Não acessa banco, yfinance nem Streamlit.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.capital_reinvestment.thresholds import (
    APPLICABLE_CLASSES,
    STRONG_THRESHOLD,
    WEAK_THRESHOLD,
)
from backend.app.schemas.capital_reinvestment import ReinvestmentMetricVerdict, ReinvestmentResult
from backend.app.schemas.fundamentals import FundamentalSnapshotResult

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


def _clamp(value: Decimal) -> Decimal:
    return max(_ZERO, min(_HUNDRED, value))


class CapitalReinvestmentEngine:
    """Classifica a disciplina de reinvestimento de capital de um ativo."""

    def evaluate(
        self,
        ticker: str,
        asset_class: str,
        snapshot: FundamentalSnapshotResult | None,
    ) -> ReinvestmentResult:
        if asset_class not in APPLICABLE_CLASSES:
            return ReinvestmentResult(
                ticker=ticker,
                asset_class=asset_class,
                classification="nao_aplicavel",
                confidence="baixa",
                reason=(
                    f"reinvestimento de capital não aplicável à classe '{asset_class}': "
                    "FIIs/REITs são obrigados por regulação a distribuir a maior parte do "
                    "resultado, e cripto/renda fixa/caixa não têm payout ratio (não são "
                    "participação societária)."
                ),
            )

        if snapshot is None or snapshot.payout_ratio is None:
            return ReinvestmentResult(
                ticker=ticker,
                asset_class=asset_class,
                classification="indeterminado",
                confidence="baixa",
                reason="payout ratio indisponível nos fundamentos coletados",
            )

        payout_ratio = snapshot.payout_ratio
        retention = Decimal("1") - payout_ratio
        score = _clamp(Decimal("50") + retention * Decimal("50"))

        if score >= STRONG_THRESHOLD:
            classification = "forte"
        elif score <= WEAK_THRESHOLD:
            classification = "fraco"
        else:
            classification = "moderado"

        metrics = [
            ReinvestmentMetricVerdict(
                field="payout_ratio",
                label="Payout ratio",
                value=payout_ratio,
                verdict=classification,
                reason=(
                    f"payout {payout_ratio * 100:.1f}% -> retenção estimada "
                    f"{retention * 100:.1f}% -> nota {score:.1f}"
                ),
            )
        ]

        return ReinvestmentResult(
            ticker=ticker,
            asset_class=asset_class,
            classification=classification,
            score=score,
            metrics=metrics,
            confidence="média",
            reason=(
                "baseado só em payout ratio (proxy única disponível); prioriza retenção/"
                "reinvestimento sobre distribuição imediata, conforme o perfil de longo "
                "prazo do investidor — não é uma regra universal de 'melhor decisão de capital'"
            ),
        )
