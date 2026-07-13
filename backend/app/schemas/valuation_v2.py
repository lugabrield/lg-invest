"""Schema de saída do Valuation Engine 2.0 (Sprint 26, Fase 2).

Ao contrário do Valuation Engine v1 (`schemas/valuation.py` — classificação
por bandas fixas de múltiplo único), este schema nunca expõe um "preço
justo" pontual: sempre uma FAIXA (`fair_value_range`), construída a partir
de múltiplos métodos independentes (DCF em 3 cenários, múltiplos
normalizados pelo próprio histórico do ativo), com o Graham Number servindo
apenas como checagem de sanidade — nunca como método primário isolado
(Volume — princípio "nunca concluir com base em um único múltiplo").

Este motor NUNCA gera recomendação de compra/venda. A saída é sempre
análise: classificação de valuation, faixa de valor justo, margem de
segurança, expectativa implícita de mercado (reverse DCF), nível de
confiança e avisos. Quando os dados são insuficientes para qualquer
estimativa, `valuation_status` é "indeterminado" e `reason` traz
literalmente "Dados insuficientes para estimar valor justo com confiança."
(nunca um valor aproximado ou inventado — Volume 18 §8).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

VALUATION_STATUS_UNDERVALUED = "subvalorizado"
VALUATION_STATUS_FAIR = "valor_justo"
VALUATION_STATUS_OVERVALUED = "sobrevalorizado"
VALUATION_STATUS_INDETERMINATE = "indeterminado"
VALUATION_STATUSES = (
    VALUATION_STATUS_UNDERVALUED,
    VALUATION_STATUS_FAIR,
    VALUATION_STATUS_OVERVALUED,
    VALUATION_STATUS_INDETERMINATE,
)

CONFIDENCE_LEVELS = ("alta", "média", "baixa")

# Mensagem literal exigida quando não há dado suficiente para estimar valor
# justo com confiança — nunca aproximada, nunca reescrita (contrato com a UI
# e com o Decision Engine v3, que a usa para nunca bloquear/priorizar com
# base numa estimativa que não existe de verdade).
INSUFFICIENT_DATA_MESSAGE = "Dados insuficientes para estimar valor justo com confiança."


class FairValueRange(BaseModel):
    """Faixa de valor justo por ação — nunca um ponto único.

    `low`/`base`/`high` vêm da combinação dos métodos disponíveis (DCF
    pessimista/base/otimista e múltiplos normalizados pelo próprio
    histórico do ativo). Qualquer extremo pode ser `None` quando nenhum
    método contribuiu para aquele lado da faixa — nunca preenchido com
    aproximação."""

    low: Decimal | None = None
    base: Decimal | None = None
    high: Decimal | None = None


class ValuationScenario(BaseModel):
    """Uma estimativa individual (um método, um conjunto de premissas).

    `label` identifica o método/cenário (ex.: "DCF pessimista", "DCF base",
    "DCF otimista", "Múltiplos (histórico próprio)"). `fair_value` é o valor
    por ação estimado por ESTE método isoladamente — `None` quando o método
    não pôde ser aplicado, sempre com `reason` explicando o motivo.
    `assumptions` documenta as premissas usadas (taxa de desconto,
    crescimento assumido, etc.) para que a estimativa seja auditável."""

    label: str
    fair_value: Decimal | None = None
    assumptions: str
    reason: str | None = None  # motivo quando fair_value é None


class ValuationV2Result(BaseModel):
    """Resultado da Análise Fundamentalista / Valuation Engine 2.0.

    Nunca é uma recomendação de compra/venda — é análise: classificação,
    faixa de valor, riscos (via `warnings`) e confiança. `asset_class`
    fora do escopo desta fase (Sprint 26, Fase 2 cobre só `stock`) sempre
    resulta em `valuation_status="indeterminado"` com `reason` explícito;
    fases futuras (FIIs/REITs, ETFs, cripto, renda fixa) terão suas
    próprias regras (Volume — "FIIs não usam DCF de empresa", "ETFs não
    têm valuation tradicional", "BTC não tem valuation tradicional")."""

    ticker: str
    asset_class: str
    current_price: Decimal | None = None

    valuation_status: str = VALUATION_STATUS_INDETERMINATE
    fair_value_range: FairValueRange = FairValueRange()
    scenarios: list[ValuationScenario] = []

    margin_of_safety: Decimal | None = None  # fração; pode ser negativa (sobrevalorizado)
    required_margin_of_safety: Decimal | None = None  # escalada pela qualidade do ativo

    graham_sanity_check: Decimal | None = None  # Graham Number — só checagem, nunca método primário
    graham_reason: str | None = None

    implied_expectation: str | None = None  # texto do reverse DCF, em linguagem natural
    # Sprint 26, Fase 3 (Trap Detection Engine): mesmo resultado do reverse
    # DCF acima, mas como fração numérica — para a Growth Overpriced Trap
    # comparar com o crescimento histórico sem precisar reinterpretar texto.
    implied_growth_rate: Decimal | None = None

    confidence: str = "baixa"  # ver CONFIDENCE_LEVELS
    warnings: list[str] = []
    methodology: list[str] = []  # métodos que efetivamente contribuíram (ex.: "dcf", "multiplos")
    reason: str | None = None  # motivo geral quando indeterminado
