"""Graham Number — checagem de sanidade, nunca método primário (Sprint 26, Fase 2).

Fórmula clássica de Benjamin Graham: sqrt(22.5 x EPS x VPA). Usada aqui
SOMENTE como cross-check de sanidade contra a faixa de valor justo
combinada (DCF + múltiplos) — nunca como estimativa isolada que por si só
justificaria uma conclusão de "barato"/"caro" (Volume — proibição de
concluir com base em um único múltiplo). Nunca aplicada quando EPS ou VPA
não são positivos: lucro/patrimônio negativo não produz "preço justo
negativo com sinal invertido", produz "não aplicável".
"""

from __future__ import annotations

from decimal import Decimal


def graham_number(
    eps: Decimal | None, book_value_per_share: Decimal | None
) -> tuple[Decimal | None, str | None]:
    if eps is None or book_value_per_share is None:
        return None, "EPS ou valor patrimonial por ação indisponível"
    if eps <= 0 or book_value_per_share <= 0:
        return None, (
            "EPS ou valor patrimonial por ação não positivo — fórmula de Graham "
            "não é significativa"
        )
    product = Decimal("22.5") * eps * book_value_per_share
    # Decimal não tem raiz quadrada de alta precisão sem `decimal.Context.sqrt`;
    # usamos float só para a raiz (grandeza monetária, precisão de sobra) e
    # convertemos de volta — mesmo padrão já usado em `engines/fundamentals/cagr.py`.
    value = Decimal(str(float(product) ** 0.5))
    return value, None
