"""Limiares do Portfolio Risk Engine (Sprint 24, Fase 6).

Constantes simples e nomeadas, documentadas e ajustáveis — nenhuma
"opinião" da IA. Bandas próprias desta engine, deliberadamente
independentes das de `engines/portfolio_diagnostics/thresholds.py` (que
já bandeia número efetivo de ativos para fins de *insight* textual, não
de score) — evita acoplar as duas engines entre si.
"""

from __future__ import annotations

from decimal import Decimal

# Volatilidade anual ponderada da carteira (Σ peso_classe * volatilidade_classe).
VOLATILITY_LOW = Decimal("0.10")  # abaixo: risco "baixo"
VOLATILITY_HIGH = Decimal("0.20")  # acima: risco "alto"; entre os dois: "médio"

# Concentração (HHI, 0..1 — soma dos pesos ao quadrado).
HHI_LOW = Decimal("0.10")
HHI_HIGH = Decimal("0.25")

# Risco estrutural por classe (Risk Engine v1): baixo=1, médio=2, alto=3,
# média ponderada pelo peso de cada ativo (indeterminados excluídos).
ASSET_CLASS_RISK_SCORE = {"baixo": Decimal("1"), "médio": Decimal("2"), "alto": Decimal("3")}
ASSET_CLASS_RISK_LOW = Decimal("1.5")
ASSET_CLASS_RISK_HIGH = Decimal("2.5")

# Risco de cauda: probabilidade de a carteira terminar a simulação Monte
# Carlo (Fase 5) abaixo do total efetivamente aportado.
DRAWDOWN_LOW = Decimal("0.05")
DRAWDOWN_HIGH = Decimal("0.20")

# Score composto final (0..100, maior = mais arriscado) mapeado nas mesmas
# 4 faixas de `RISK_TOLERANCES` (Investment Policy, Fase 3) — permite
# comparar diretamente o risco medido da carteira com a tolerância
# declarada pelo usuário.
COMPOSITE_BAIXO_MAX = Decimal("30")
COMPOSITE_MODERADO_MAX = Decimal("55")
COMPOSITE_MODERADO_ALTO_MAX = Decimal("75")
# acima de COMPOSITE_MODERADO_ALTO_MAX: "alto"


def classify_by_bands(value: Decimal, low: Decimal, high: Decimal) -> str:
    """Classifica um valor em baixo/médio/alto a partir de duas bandas."""
    if value < low:
        return "baixo"
    if value > high:
        return "alto"
    return "médio"


def classify_composite_score(score: Decimal) -> str:
    """Classifica o score composto (0..100) nas 4 faixas de `RISK_TOLERANCES`."""
    if score <= COMPOSITE_BAIXO_MAX:
        return "baixo"
    if score <= COMPOSITE_MODERADO_MAX:
        return "moderado"
    if score <= COMPOSITE_MODERADO_ALTO_MAX:
        return "moderado-alto"
    return "alto"
