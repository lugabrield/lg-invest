"""Limiares do Diagnóstico da Carteira (Sprint 11).

Constantes simples e nomeadas — nenhuma "opinião" da IA, só regras
documentadas que qualquer pessoa pode ler, questionar e ajustar depois.
Todas as frações são 0..1.
"""

from __future__ import annotations

from decimal import Decimal

# Concentração por ativo (maior posição sobre o total convertido).
SINGLE_POSITION_WARN = Decimal("0.15")  # acima disso: "merece atenção"
SINGLE_POSITION_ALERT = Decimal("0.25")  # acima disso: alerta de concentração

# Classe/grupo dominante (soma das posições do mesmo grupo).
DOMINANT_GROUP_WARN = Decimal("0.50")

# Diversificação efetiva (Nº efetivo de ativos = 1/HHI).
LOW_DIVERSIFICATION_N = Decimal("5")
MODERATE_DIVERSIFICATION_N = Decimal("10")

# Exposição internacional (peso de moedas != BRL sobre o total convertido).
INTERNATIONAL_EXPOSURE_LOW = Decimal("0.20")

# Pesos por grupo que merecem um comentário à parte.
FII_WEIGHT_WARN = Decimal("0.30")
CRYPTO_WEIGHT_WARN = Decimal("0.10")

# Qualidade dos dados de preço (fração do patrimônio com preço automático,
# ou seja, price_source == "yahoo"). Abaixo de WARN: alerta; entre WARN e
# GOOD: atenção; a partir de GOOD: positivo (Sprint 12).
DATA_QUALITY_AUTOMATIC_GOOD = Decimal("0.90")
DATA_QUALITY_AUTOMATIC_WARN = Decimal("0.70")
