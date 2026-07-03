"""Os cinco pilares do LG Score v1 (Volume 6, seções 5–9).

Cada pilar é uma PROXY explícita derivada do que a plataforma já coleta
(classe do ativo e histórico de preços). Toda nota vem acompanhada das
razões que a justificam (explicabilidade) e de uma confiança local.

Regra de dados ausentes (Volume 18 §8 / Volume 20 prompt 9):
faltou dado -> nota neutra (50) + razão explícita + confiança baixa.
Nunca inventar fundamentos, nunca otimismo.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.app.engines.lg_score.inputs import ScoreInput
from backend.app.engines.lg_score.normalization import (
    NEUTRAL,
    cagr,
    clamp_score,
    max_drawdown,
    mean,
    volatility,
)

# Confiança mínima de histórico de preços: nº de pontos para confiar plenamente.
_FULL_HISTORY_POINTS = 60

# Mapa de qualidade base por classe de ativo (proxy v1).
# ETFs amplos e ações tendem a base mais alta; cripto, mais baixa.
_CLASS_QUALITY_BASE = {
    "etf": Decimal("75"),
    "stock": Decimal("65"),
    "fii": Decimal("60"),
    "reit": Decimal("60"),
    "bond": Decimal("70"),
    "cash": Decimal("80"),
    "crypto": Decimal("40"),
}


@dataclass
class PillarScore:
    score: Decimal  # 0..100
    confidence: Decimal  # 0..1
    reasons: list[str]


def _history_confidence(n: int) -> Decimal:
    """Confiança proporcional à cobertura do histórico de preços."""
    if n <= 1:
        return Decimal("0.1")
    ratio = Decimal(min(n, _FULL_HISTORY_POINTS)) / Decimal(_FULL_HISTORY_POINTS)
    # piso de 0.1 para não zerar.
    return max(Decimal("0.1"), ratio)


def quality_pillar(data: ScoreInput) -> PillarScore:
    """Qualidade: base por classe + ajuste leve por estabilidade de preço."""
    base = _CLASS_QUALITY_BASE.get(data.asset_class, NEUTRAL)
    reasons = [f"base de qualidade por classe '{data.asset_class}': {base}"]

    vol = volatility(data.price_history)
    if vol is not None:
        # Menor volatilidade -> pequeno bônus; maior -> pequena penalidade.
        # vol diária ~0.02 considerada normal; escala suave de +/-10.
        adjustment = (Decimal("0.02") - vol) * Decimal("500")
        adjustment = max(Decimal("-10"), min(Decimal("10"), adjustment))
        reasons.append(f"ajuste por estabilidade de preço: {adjustment:+.1f}")
        score = clamp_score(base + adjustment)
    else:
        reasons.append("sem histórico para avaliar estabilidade; usada base da classe")
        score = clamp_score(base)

    confidence = _history_confidence(len(data.price_history))
    return PillarScore(score=score, confidence=confidence, reasons=reasons)


def valuation_pillar(data: ScoreInput) -> PillarScore:
    """Valuation v1 (proxy): preço atual vs. média histórica do próprio ativo.

    Sem valor intrínseco (Valuation Engine é pós-MVP). Preço abaixo da
    média -> mais 'barato' -> nota maior; acima -> nota menor.
    """
    if len(data.price_history) < 2:
        return PillarScore(
            score=NEUTRAL,
            confidence=Decimal("0.1"),
            reasons=["dado ausente: sem histórico para valuation; usada neutralidade (50)"],
        )

    avg = mean(data.price_history)
    current = data.price_history[-1]
    if avg is None or avg <= 0:
        return PillarScore(
            score=NEUTRAL,
            confidence=Decimal("0.1"),
            reasons=["média histórica inválida; usada neutralidade (50)"],
        )

    # discount > 0 => abaixo da média (barato); < 0 => acima (caro).
    discount = (avg - current) / avg
    # Escala: 50 no preço médio; +/-2 pontos por 1% de desconto, limitado a 0..100.
    score = clamp_score(NEUTRAL + discount * Decimal("200"))
    reasons = [
        f"preço atual {current} vs. média {avg:.4f}",
        f"desconto relativo: {discount * 100:+.1f}% -> nota {score:.1f}",
        "proxy v1: sem valor intrínseco; usa média histórica do próprio ativo",
    ]
    return PillarScore(
        score=score,
        confidence=_history_confidence(len(data.price_history)),
        reasons=reasons,
    )


def growth_pillar(data: ScoreInput) -> PillarScore:
    """Crescimento (proxy): CAGR do preço no histórico disponível."""
    growth = cagr(data.price_history)
    if growth is None:
        return PillarScore(
            score=NEUTRAL,
            confidence=Decimal("0.1"),
            reasons=["dado ausente: histórico insuficiente para CAGR; neutralidade (50)"],
        )
    # 0% por período -> 50; cada 1% de CAGR por período move ~10 pontos.
    score = clamp_score(NEUTRAL + growth * Decimal("1000"))
    reasons = [
        f"CAGR de preço por período: {growth * 100:+.2f}%",
        "proxy v1: crescimento de preço, não de lucro/FCF (fundamentos pós-MVP)",
    ]
    return PillarScore(
        score=score,
        confidence=_history_confidence(len(data.price_history)),
        reasons=reasons,
    )


def risk_pillar(data: ScoreInput) -> PillarScore:
    """Risco (proxy): menos volatilidade e menos drawdown -> nota maior."""
    vol = volatility(data.price_history)
    dd = max_drawdown(data.price_history)
    if vol is None or dd is None:
        return PillarScore(
            score=NEUTRAL,
            confidence=Decimal("0.1"),
            reasons=["dado ausente: histórico insuficiente para risco; neutralidade (50)"],
        )

    # Volatilidade: 0.02/dia ~ neutro; penaliza acima disso.
    vol_score = clamp_score(NEUTRAL + (Decimal("0.02") - vol) * Decimal("1500"))
    # Drawdown: 0% -> 100; 50% -> 0.
    dd_score = clamp_score(_drawdown_to_score(dd))
    score = clamp_score((vol_score + dd_score) / Decimal("2"))
    reasons = [
        f"volatilidade por período: {vol * 100:.2f}% -> componente {vol_score:.1f}",
        f"max drawdown: {dd * 100:.1f}% -> componente {dd_score:.1f}",
    ]
    return PillarScore(
        score=score,
        confidence=_history_confidence(len(data.price_history)),
        reasons=reasons,
    )


def _drawdown_to_score(drawdown: Decimal) -> Decimal:
    """100 - (drawdown em %), para converter drawdown em nota."""
    return Decimal("100") - (drawdown * Decimal("100"))


def allocation_pillar(data: ScoreInput) -> PillarScore:
    """Alocação: favorece ativos subalocados em relação ao peso-alvo.

    Sem peso-alvo definido, retorna neutralidade (não há política para comparar).
    """
    if data.target_weight is None or data.current_weight is None:
        return PillarScore(
            score=NEUTRAL,
            confidence=Decimal("0.5"),
            reasons=["sem peso-alvo definido; alocação neutra (50)"],
        )

    gap = data.target_weight - data.current_weight  # >0 => subalocado
    # +1 ponto de nota por 1% de subalocação; centrado em 50.
    score = clamp_score(NEUTRAL + gap * Decimal("100") * Decimal("2"))
    estado = "subalocado" if gap > 0 else "sobrealocado" if gap < 0 else "no alvo"
    reasons = [
        f"peso atual {data.current_weight} vs. alvo {data.target_weight} ({estado})",
        f"gap de alocação: {gap * 100:+.1f}% -> nota {score:.1f}",
    ]
    return PillarScore(score=score, confidence=Decimal("0.8"), reasons=reasons)
