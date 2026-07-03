"""Contrato de entrada do LG Score Engine (Volume 6 / Volume 17 §9).

`ScoreInput` carrega apenas dados já tratados. A engine não acessa
banco nem rede — o serviço resolve o histórico de preços, o peso atual
na carteira e o peso-alvo (quando existir) e entrega esta estrutura.

No v1 os pilares são proxies derivadas do que a plataforma já coleta
(classe do ativo e histórico de preços). Fundamentos (ROIC, margens,
CAGR de lucro) ainda não existem; sua ausência é tratada com
neutralidade e confiança reduzida, nunca com otimismo inventado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class ScoreInput:
    """Tudo o que a engine precisa para pontuar um ativo."""

    ticker: str
    asset_class: str
    # Histórico de preços de fechamento, do mais antigo ao mais recente.
    price_history: list[Decimal] = field(default_factory=list)
    # Peso atual do ativo na carteira (fração 0..1), se aplicável.
    current_weight: Decimal | None = None
    # Peso-alvo do ativo na carteira (fração 0..1), se o usuário definiu.
    target_weight: Decimal | None = None
