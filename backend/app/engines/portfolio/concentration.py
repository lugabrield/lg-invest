"""Concentração da carteira (Volume 8, seção 9 e 16.1).

Isolado em seu próprio módulo, como sugere a especificação técnica do
Volume 8 (concentration.py). Trabalha sobre pesos já calculados.
"""

from __future__ import annotations

from decimal import Decimal


def herfindahl_index(weights: list[Decimal]) -> Decimal:
    """Índice de Herfindahl-Hirschman (HHI) = soma dos pesos ao quadrado.

    - Carteira com 1 ativo => 1.0 (concentração máxima).
    - Carteira com N ativos de peso igual => 1/N.
    Espera pesos como frações (somando ~1.0). Retorna 0 se vazio.
    """
    if not weights:
        return Decimal("0")
    return sum((w * w for w in weights), start=Decimal("0"))


def effective_number_of_assets(hhi: Decimal) -> Decimal | None:
    """Número efetivo de ativos = 1 / HHI. None se HHI for zero."""
    if hhi <= 0:
        return None
    return Decimal("1") / hhi
