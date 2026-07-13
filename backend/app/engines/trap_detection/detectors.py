"""Detectores puros de armadilha de valuation (Sprint 26, Fase 3).

Cada função recebe só os campos primitivos de que precisa (nunca o
snapshot inteiro) e devolve `TrapFlag | None` — `None` quando o padrão
não foi observado (nunca um flag "fraco" forçado só para preencher a
lista). Nenhuma função aqui decide compra/venda; cada uma só descreve um
padrão e como ele deveria pesar na leitura de confiança.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.trap_detection.thresholds import (
    FII_YIELD_SPIKE_RATIO_HIGH,
    FII_YIELD_SPIKE_RATIO_MEDIUM,
    GROWTH_OVERPRICED_GAP_HIGH,
    GROWTH_OVERPRICED_GAP_MEDIUM,
    HIGH_DY_THRESHOLD,
    HIGH_LEVERAGE_DEBT_TO_EBITDA,
    LOW_COVERAGE_PCT,
    LOW_INTEREST_COVERAGE,
    LOW_PB_THRESHOLD,
    LOW_PE_THRESHOLD,
    LOW_ROE_THRESHOLD,
    MIN_PERIODS_FOR_CONFIDENT_HISTORY,
    VERY_HIGH_DY_THRESHOLD,
    VERY_HIGH_LEVERAGE_DEBT_TO_EBITDA,
    VERY_LOW_COVERAGE_PCT,
    VERY_LOW_INTEREST_COVERAGE,
)
from backend.app.schemas.trap_detection import (
    CONFIDENCE_PENALTY_BY_SEVERITY,
    TRAP_SEVERITY_HIGH,
    TRAP_SEVERITY_MEDIUM,
    TRAP_TYPE_DATA_QUALITY,
    TRAP_TYPE_FII_YIELD,
    TRAP_TYPE_GROWTH_OVERPRICED,
    TRAP_TYPE_HIGH_DY,
    TRAP_TYPE_LEVERAGE,
    TRAP_TYPE_LOW_PB,
    TRAP_TYPE_LOW_PE,
    TrapFlag,
)


def _flag(
    trap_type: str,
    label: str,
    severity: str,
    affected_metric: str,
    explanation: str,
    impact_on_score: str,
    recommended_interpretation: str,
) -> TrapFlag:
    return TrapFlag(
        trap_type=trap_type,
        label=label,
        severity=severity,
        affected_metric=affected_metric,
        explanation=explanation,
        impact_on_score=impact_on_score,
        recommended_interpretation=recommended_interpretation,
        confidence_penalty=CONFIDENCE_PENALTY_BY_SEVERITY[severity],
    )


def detect_low_pe_trap(
    pe_ratio: Decimal | None,
    net_income_cagr: Decimal | None,
    margin_trend: str | None,
) -> TrapFlag | None:
    """P/L baixo isolado nunca é sinal — só vira flag quando some com
    lucro em queda (CAGR negativo) ou margem piorando: sinais de que o
    lucro que sustenta o P/L pode não se repetir."""
    if pe_ratio is None or pe_ratio <= 0 or pe_ratio >= LOW_PE_THRESHOLD:
        return None

    earnings_declining = net_income_cagr is not None and net_income_cagr < 0
    margin_worsening = margin_trend == "piorando"
    if not earnings_declining and not margin_worsening:
        return None

    severity = (
        TRAP_SEVERITY_HIGH if (earnings_declining and margin_worsening) else TRAP_SEVERITY_MEDIUM
    )
    signals = []
    if earnings_declining:
        signals.append(f"lucro líquido em queda (CAGR {net_income_cagr:.1%})")
    if margin_worsening:
        signals.append("margem líquida piorando ao longo do histórico")

    return _flag(
        trap_type=TRAP_TYPE_LOW_PE,
        label="Armadilha do P/L baixo",
        severity=severity,
        affected_metric="pe_ratio",
        explanation=(
            f"P/L de {pe_ratio} está abaixo de {LOW_PE_THRESHOLD}, mas " + " e ".join(signals) + "."
        ),
        impact_on_score=(
            "Reduz a confiança da leitura de 'barato' por múltiplo — o lucro atual pode "
            "não ser sustentável, então o P/L baixo pode refletir risco, não desconto."
        ),
        recommended_interpretation=(
            "Investigar se a queda de lucro/margem é pontual (não recorrente) ou estrutural "
            "antes de interpretar o P/L baixo como desconto."
        ),
    )


def detect_low_pb_trap(pb_ratio: Decimal | None, roe: Decimal | None) -> TrapFlag | None:
    """P/VP baixo isolado nunca é sinal — só vira flag quando o ROE mostra
    que o capital próprio não está gerando retorno condizente com um
    ativo "barato" (ativo pode estar barato porque o negócio é fraco)."""
    if pb_ratio is None or pb_ratio <= 0 or pb_ratio >= LOW_PB_THRESHOLD:
        return None
    if roe is None or roe >= LOW_ROE_THRESHOLD:
        return None

    severity = TRAP_SEVERITY_HIGH if roe < 0 else TRAP_SEVERITY_MEDIUM

    return _flag(
        trap_type=TRAP_TYPE_LOW_PB,
        label="Armadilha do P/VP baixo",
        severity=severity,
        affected_metric="pb_ratio",
        explanation=(
            f"P/VP de {pb_ratio} está abaixo de {LOW_PB_THRESHOLD}, mas o ROE de {roe:.1%} "
            f"está abaixo do mínimo de referência ({LOW_ROE_THRESHOLD:.0%})."
        ),
        impact_on_score=(
            "Reduz a confiança da leitura de 'barato' por P/VP — o valor patrimonial pode "
            "estar inflado frente à capacidade real do negócio de gerar retorno sobre ele."
        ),
        recommended_interpretation=(
            "Investigar se o ROE baixo é temporário (ciclo de investimento, por exemplo) "
            "ou reflete deterioração estrutural do retorno sobre o capital."
        ),
    )


def detect_growth_overpriced_trap(
    implied_growth_rate: Decimal | None,
    historical_growth_rate: Decimal | None,
    growth_source: str | None,
) -> TrapFlag | None:
    """Compara o crescimento que o preço atual já embute (reverse DCF)
    com o crescimento histórico real do próprio ativo — gap grande é o
    mercado precificando uma história que ainda não aconteceu."""
    if implied_growth_rate is None or historical_growth_rate is None:
        return None

    gap = implied_growth_rate - historical_growth_rate
    if gap < GROWTH_OVERPRICED_GAP_MEDIUM:
        return None

    severity = TRAP_SEVERITY_HIGH if gap >= GROWTH_OVERPRICED_GAP_HIGH else TRAP_SEVERITY_MEDIUM
    source_label = growth_source or "histórico"

    return _flag(
        trap_type=TRAP_TYPE_GROWTH_OVERPRICED,
        label="Crescimento supervalorizado",
        severity=severity,
        affected_metric="implied_growth_rate",
        explanation=(
            f"O preço atual embute crescimento implícito de {implied_growth_rate:.1%} a.a., "
            f"{gap:.1%} acima do crescimento histórico de {source_label} "
            f"({historical_growth_rate:.1%} a.a.)."
        ),
        impact_on_score=(
            "Reduz a confiança da faixa de valor justo — parte do valor 'justo' depende de "
            "uma aceleração de crescimento que ainda não foi demonstrada pelos números."
        ),
        recommended_interpretation=(
            "Investigar se há um catalisador concreto (novo produto, expansão, mudança de "
            "ciclo) que justifique crescimento acima do padrão histórico do próprio ativo."
        ),
    )


def detect_leverage_trap(
    debt_to_ebitda: Decimal | None, interest_coverage: Decimal | None
) -> TrapFlag | None:
    """Alavancagem alta pode estar escondida atrás de múltiplos
    aparentemente baratos (dívida reduz o P/L "de verdade" mais devagar
    que o P/L contábil sugere, e o risco de refinanciamento não aparece
    em nenhum múltiplo de preço)."""
    high_debt = debt_to_ebitda is not None and debt_to_ebitda > HIGH_LEVERAGE_DEBT_TO_EBITDA
    low_coverage = interest_coverage is not None and interest_coverage < LOW_INTEREST_COVERAGE
    if not high_debt and not low_coverage:
        return None

    very_high_debt = (
        debt_to_ebitda is not None and debt_to_ebitda > VERY_HIGH_LEVERAGE_DEBT_TO_EBITDA
    )
    very_low_coverage = (
        interest_coverage is not None and interest_coverage < VERY_LOW_INTEREST_COVERAGE
    )
    severity = (
        TRAP_SEVERITY_HIGH
        if (high_debt and low_coverage) or very_high_debt or very_low_coverage
        else TRAP_SEVERITY_MEDIUM
    )

    signals = []
    if high_debt:
        signals.append(
            f"dívida líquida/EBITDA de {debt_to_ebitda} (acima de {HIGH_LEVERAGE_DEBT_TO_EBITDA})"
        )
    if low_coverage:
        signals.append(
            f"cobertura de juros de {interest_coverage} (abaixo de {LOW_INTEREST_COVERAGE})"
        )

    return _flag(
        trap_type=TRAP_TYPE_LEVERAGE,
        label="Alavancagem elevada",
        severity=severity,
        affected_metric="debt_to_ebitda" if high_debt else "interest_coverage",
        explanation="Sinal de alavancagem elevada: " + " e ".join(signals) + ".",
        impact_on_score=(
            "Reduz a confiança de qualquer leitura de 'barato' por múltiplo de preço — "
            "risco financeiro elevado não aparece no P/L nem no P/VP."
        ),
        recommended_interpretation=(
            "Investigar o perfil de vencimento da dívida e a geração de caixa operacional "
            "frente ao serviço da dívida antes de considerar o ativo descontado."
        ),
    )


def detect_data_quality_trap(
    coverage_pct: Decimal | None, periods_used: int | None
) -> TrapFlag | None:
    """Qualquer conclusão de valuation feita em cima de dado incompleto
    ou histórico curto demais merece confiança reduzida, não importa o
    que os números disponíveis digam."""
    low_coverage = coverage_pct is not None and coverage_pct < LOW_COVERAGE_PCT
    short_history = periods_used is not None and periods_used < MIN_PERIODS_FOR_CONFIDENT_HISTORY
    if not low_coverage and not short_history:
        return None

    very_low_coverage = coverage_pct is not None and coverage_pct < VERY_LOW_COVERAGE_PCT
    severity = TRAP_SEVERITY_HIGH if very_low_coverage else TRAP_SEVERITY_MEDIUM

    signals = []
    if low_coverage:
        signals.append(f"cobertura de fundamentos de {coverage_pct:.0%}")
    if short_history:
        signals.append(f"apenas {periods_used} período(s) de histórico disponível")

    return _flag(
        trap_type=TRAP_TYPE_DATA_QUALITY,
        label="Dado insuficiente para confiança",
        severity=severity,
        affected_metric="coverage_pct",
        explanation="Base de dados limitada: " + " e ".join(signals) + ".",
        impact_on_score=(
            "Reduz a confiança de toda a análise — qualquer estimativa construída sobre "
            "dado incompleto herda essa incerteza, mesmo que os números disponíveis pareçam "
            "favoráveis."
        ),
        recommended_interpretation=(
            "Buscar mais períodos de fundamentos antes de dar peso alto a esta análise."
        ),
    )


def detect_high_dy_trap(dividend_yield: Decimal | None) -> TrapFlag | None:
    """DY anual muito alto isolado nunca é conclusão de 'renda boa' — pode
    refletir queda de preço recente, distribuição pontual de capital (não
    recorrente) ou insustentabilidade. Aplicável a FIIs/REITs."""
    if dividend_yield is None or dividend_yield < HIGH_DY_THRESHOLD:
        return None

    severity = (
        TRAP_SEVERITY_HIGH if dividend_yield >= VERY_HIGH_DY_THRESHOLD else TRAP_SEVERITY_MEDIUM
    )

    return _flag(
        trap_type=TRAP_TYPE_HIGH_DY,
        label="Dividend Yield muito alto",
        severity=severity,
        affected_metric="dividend_yield",
        explanation=(
            f"Dividend Yield de {dividend_yield:.1%} a.a. está acima do usual "
            f"(limiar de {HIGH_DY_THRESHOLD:.0%}) — merece verificação antes de ser lido "
            "como sinal positivo isolado."
        ),
        impact_on_score=(
            "Reduz a confiança de qualquer leitura de 'atrativo' baseada só no yield — "
            "yield muito alto pode ser sintoma de risco, não de oportunidade."
        ),
        recommended_interpretation=(
            "Investigar se o yield elevado reflete queda recente de preço, distribuição de "
            "ganho de capital não recorrente, ou geração de caixa real sustentável."
        ),
    )


def detect_fii_yield_trap(
    dividend_yield: Decimal | None, dy_own_history_average: Decimal | None
) -> TrapFlag | None:
    """Compara o DY do período mais recente com a média histórica do
    PRÓPRIO ativo — um pico muito acima da própria média costuma ser
    distribuição não recorrente (venda de ativo, ganho de capital pontual),
    não a renda regular que o yield sugere à primeira vista."""
    if dividend_yield is None or dy_own_history_average is None or dy_own_history_average <= 0:
        return None

    ratio = dividend_yield / dy_own_history_average
    if ratio < FII_YIELD_SPIKE_RATIO_MEDIUM:
        return None

    severity = TRAP_SEVERITY_HIGH if ratio >= FII_YIELD_SPIKE_RATIO_HIGH else TRAP_SEVERITY_MEDIUM

    return _flag(
        trap_type=TRAP_TYPE_FII_YIELD,
        label="Pico de yield não recorrente",
        severity=severity,
        affected_metric="dividend_yield",
        explanation=(
            f"DY atual de {dividend_yield:.1%} está {ratio:.1f}x acima da média histórica "
            f"do próprio ativo ({dy_own_history_average:.1%}) — pico pode não ser recorrente."
        ),
        impact_on_score=(
            "Reduz a confiança de tratar o yield do período mais recente como representativo "
            "da distribuição recorrente esperada do fundo/REIT."
        ),
        recommended_interpretation=(
            "Verificar se a distribuição do período incluiu venda de ativos ou resultado não "
            "recorrente antes de projetar esse yield para os próximos períodos."
        ),
    )
