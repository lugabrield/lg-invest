"""Diagnóstico da Carteira (Sprint 11) — engine pura.

Recebe o `DashboardView` já pronto (conversão cambial e fallback de
preço já aplicados por `dashboard_view_service`) e devolve uma lista de
insights explicáveis, baseados em regras simples de peso e
concentração. Segue o mesmo padrão dos demais engines do projeto: sem
banco, sem yfinance, sem Streamlit (`test_engine_purity.py` cobre isso
automaticamente); determinística; sem IA generativa e sem opinião
inventada — cada mensagem cita um número calculado e, quando
aplicável, um limiar de `thresholds.py`.

`DashboardView` é um schema Pydantic simples (decimal/datetime), sem
qualquer dependência de infraestrutura — importá-lo aqui não fere a
pureza do engine.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.portfolio_diagnostics import thresholds as t
from backend.app.schemas.dashboard_view import DashboardView
from backend.app.schemas.portfolio_diagnostics import (
    SEVERITY_ALERT,
    SEVERITY_ATTENTION,
    SEVERITY_INFO,
    SEVERITY_POSITIVE,
    DiagnosticInsight,
    PortfolioDiagnostics,
)

_ZERO = Decimal("0")


def _pct(value: Decimal) -> str:
    """Formata como percentual em padrão brasileiro (vírgula decimal).

    Duplicado deliberadamente em vez de importar `frontend.streamlit_app.formatting`:
    engines não podem depender de código de apresentação (Streamlit).
    """
    return f"{float(value) * 100:.2f}".replace(".", ",") + "%"


def _group_weights(view: DashboardView) -> dict[str, Decimal]:
    weights: dict[str, Decimal] = {}
    for p in view.positions:
        weights[p.group_label] = weights.get(p.group_label, _ZERO) + p.weight
    return weights


def _international_weight(view: DashboardView) -> Decimal:
    return sum(
        (c.weight for c in view.currency_exposure if c.currency != "BRL"),
        _ZERO,
    )


def _concentration_insight(view: DashboardView) -> DiagnosticInsight | None:
    if not view.positions or view.largest_position_ticker is None:
        return None
    largest = next((p for p in view.positions if p.ticker == view.largest_position_ticker), None)
    if largest is None:
        return None
    weight = largest.weight
    if weight >= t.SINGLE_POSITION_ALERT:
        return DiagnosticInsight(
            code="concentration_single_asset",
            severity=SEVERITY_ALERT,
            title="Concentração em uma posição",
            message=(
                f"{largest.ticker} representa {_pct(weight)} do patrimônio, acima do "
                f"limite de {_pct(t.SINGLE_POSITION_ALERT)} — concentração relevante em um único ativo."
            ),
        )
    if weight >= t.SINGLE_POSITION_WARN:
        return DiagnosticInsight(
            code="concentration_single_asset",
            severity=SEVERITY_ATTENTION,
            title="Concentração em uma posição",
            message=(
                f"{largest.ticker} é sua maior posição, com {_pct(weight)} do patrimônio "
                f"— acima de {_pct(t.SINGLE_POSITION_WARN)}, vale acompanhar."
            ),
        )
    return DiagnosticInsight(
        code="concentration_single_asset",
        severity=SEVERITY_POSITIVE,
        title="Concentração em uma posição",
        message=(
            f"Nenhuma posição individual concentra mais que {_pct(t.SINGLE_POSITION_WARN)} "
            f"do patrimônio (maior é {largest.ticker}, com {_pct(weight)})."
        ),
    )


def _dominant_group_insight(view: DashboardView) -> DiagnosticInsight | None:
    weights = _group_weights(view)
    if not weights:
        return None
    label, weight = max(weights.items(), key=lambda kv: kv[1])
    if weight >= t.DOMINANT_GROUP_WARN:
        return DiagnosticInsight(
            code="dominant_group",
            severity=SEVERITY_ATTENTION,
            title="Classe dominante",
            message=(
                f"{label} domina a composição, com {_pct(weight)} da carteira — "
                f"acima de {_pct(t.DOMINANT_GROUP_WARN)}."
            ),
        )
    return DiagnosticInsight(
        code="dominant_group",
        severity=SEVERITY_INFO,
        title="Classe dominante",
        message=f"{label} é a classe com maior peso na carteira: {_pct(weight)}.",
    )


def _diversification_insight(view: DashboardView) -> DiagnosticInsight | None:
    n_eff = view.effective_number_of_assets
    if n_eff is None:
        return None
    if n_eff < t.LOW_DIVERSIFICATION_N:
        return DiagnosticInsight(
            code="diversification",
            severity=SEVERITY_ATTENTION,
            title="Diversificação",
            message=(
                f"O número efetivo de ativos é {float(n_eff):.1f} — sua carteira se comporta "
                f"como se tivesse poucos ativos igualmente pesados. Diversificação ainda baixa."
            ),
        )
    if n_eff < t.MODERATE_DIVERSIFICATION_N:
        return DiagnosticInsight(
            code="diversification",
            severity=SEVERITY_INFO,
            title="Diversificação",
            message=(f"Número efetivo de ativos: {float(n_eff):.1f} — diversificação moderada."),
        )
    return DiagnosticInsight(
        code="diversification",
        severity=SEVERITY_POSITIVE,
        title="Diversificação",
        message=(
            f"Número efetivo de ativos: {float(n_eff):.1f} — boa diversificação entre as posições."
        ),
    )


def _international_exposure_insight(view: DashboardView) -> DiagnosticInsight | None:
    if not view.currency_exposure:
        return None
    international = _international_weight(view)
    brazil = Decimal("1") - international
    base_message = (
        f"Exposição internacional: {_pct(international)} · Exposição ao Brasil: {_pct(brazil)}."
    )
    if international < t.INTERNATIONAL_EXPOSURE_LOW:
        return DiagnosticInsight(
            code="international_exposure",
            severity=SEVERITY_ATTENTION,
            title="Brasil x Exterior",
            message=(
                f"{base_message} Sua carteira possui boa diversificação entre ativos, mas ainda "
                "está majoritariamente exposta ao Brasil. Seu perfil de longo prazo busca aumentar "
                "a exposição internacional ao longo do tempo — ainda há espaço para crescer nessa direção."
            ),
        )
    return DiagnosticInsight(
        code="international_exposure",
        severity=SEVERITY_INFO,
        title="Brasil x Exterior",
        message=base_message,
    )


def _group_weight_comments(view: DashboardView) -> list[DiagnosticInsight]:
    weights = _group_weights(view)
    insights: list[DiagnosticInsight] = []

    fii_weight = weights.get("FIIs", _ZERO)
    if fii_weight > 0:
        severity = SEVERITY_ATTENTION if fii_weight >= t.FII_WEIGHT_WARN else SEVERITY_INFO
        message = f"FIIs representam {_pct(fii_weight)} da carteira."
        if fii_weight >= t.FII_WEIGHT_WARN:
            message += (
                f" Acima de {_pct(t.FII_WEIGHT_WARN)}, isso pode aumentar a dependência de "
                "renda imobiliária local."
            )
        insights.append(
            DiagnosticInsight(
                code="weight_fiis", severity=severity, title="Peso de FIIs", message=message
            )
        )

    crypto_weight = weights.get("Cripto", _ZERO)
    if crypto_weight > 0:
        severity = SEVERITY_ATTENTION if crypto_weight >= t.CRYPTO_WEIGHT_WARN else SEVERITY_INFO
        message = f"Cripto representa {_pct(crypto_weight)} da carteira."
        if crypto_weight >= t.CRYPTO_WEIGHT_WARN:
            message += (
                f" Acima de {_pct(t.CRYPTO_WEIGHT_WARN)}, essa classe costuma trazer volatilidade "
                "maior que o restante da carteira."
            )
        insights.append(
            DiagnosticInsight(
                code="weight_crypto", severity=severity, title="Peso de Cripto", message=message
            )
        )

    for group_label, code, title in (
        ("Ações BR", "weight_stocks_br", "Peso de Ações BR"),
        ("Ações EUA", "weight_stocks_us", "Peso de Ações EUA"),
        ("ETFs", "weight_etfs", "Peso de ETFs"),
        ("REITs", "weight_reits", "Peso de REITs"),
        ("Renda Fixa", "weight_fixed_income", "Peso de Renda Fixa"),
    ):
        weight = weights.get(group_label, _ZERO)
        if weight > 0:
            insights.append(
                DiagnosticInsight(
                    code=code,
                    severity=SEVERITY_INFO,
                    title=title,
                    message=f"{group_label} representa {_pct(weight)} da carteira.",
                )
            )

    return insights


def _multi_currency_insight(view: DashboardView) -> DiagnosticInsight | None:
    if not view.is_multi_currency:
        return None
    return DiagnosticInsight(
        code="multi_currency",
        severity=SEVERITY_INFO,
        title="Múltiplas moedas",
        message=(
            f"Sua carteira tem ativos em mais de uma moeda. O câmbio USD/BRL usado para "
            f"consolidar o patrimônio é {float(view.exchange_rate):.4f} e é definido manualmente "
            "em Configurações — a conversão é só para exibição."
        ),
    )


def _manual_and_estimated_prices_insight(view: DashboardView) -> DiagnosticInsight | None:
    if not view.estimated_price_tickers and not view.manual_price_tickers:
        return None
    parts = []
    if view.manual_price_tickers:
        parts.append(
            "tratados como ativo manual (preço cadastrado por você): "
            + ", ".join(view.manual_price_tickers)
        )
    if view.estimated_price_tickers:
        parts.append(
            "sem nenhuma cotação ainda, usando o preço médio como estimativa temporária: "
            + ", ".join(view.estimated_price_tickers)
        )
    severity = SEVERITY_ATTENTION if view.estimated_price_tickers else SEVERITY_INFO
    text = " · ".join(parts) + "."
    return DiagnosticInsight(
        code="manual_or_estimated_prices",
        severity=severity,
        title="Ativos sem preço automático",
        message=text[0].upper() + text[1:],
    )


def _cash_position_insight(view: DashboardView) -> DiagnosticInsight | None:
    cash_positions = [p for p in view.positions if p.asset_class == "cash"]
    if not cash_positions:
        return None
    cash_value = sum((p.position_value_brl for p in cash_positions), _ZERO)
    return DiagnosticInsight(
        code="cash_position",
        severity=SEVERITY_INFO,
        title="Caixa disponível",
        message=(
            f"Você tem {_pct(cash_value / view.total_converted_brl)} da carteira em caixa, "
            "disponível para um próximo aporte."
            if view.total_converted_brl > 0
            else "Há posição em caixa cadastrada."
        ),
    )


def _data_quality_insight(view: DashboardView) -> DiagnosticInsight | None:
    """Fração do patrimônio com preço automático (Sprint 12).

    Complementa `_manual_and_estimated_prices_insight` (que lista os
    tickers): aqui o foco é o número agregado, para dar uma leitura
    rápida de quanto da carteira depende de dado confiável.
    """
    if not view.positions:
        return None
    automatic_weight = sum((p.weight for p in view.positions if p.price_source == "yahoo"), _ZERO)
    if automatic_weight >= t.DATA_QUALITY_AUTOMATIC_GOOD:
        return DiagnosticInsight(
            code="data_quality",
            severity=SEVERITY_POSITIVE,
            title="Qualidade dos dados de preço",
            message=(
                f"{_pct(automatic_weight)} do patrimônio está com preço automático "
                "(Yahoo Finance), atualizado e confiável."
            ),
        )
    severity = (
        SEVERITY_ATTENTION if automatic_weight >= t.DATA_QUALITY_AUTOMATIC_WARN else SEVERITY_ALERT
    )
    return DiagnosticInsight(
        code="data_quality",
        severity=severity,
        title="Qualidade dos dados de preço",
        message=(
            f"Apenas {_pct(automatic_weight)} do patrimônio está com preço automático — "
            "o restante depende de preço manual ou estimado, o que reduz a confiabilidade "
            "da rentabilidade e dos scores calculados."
        ),
    )


def build_diagnostics(view: DashboardView) -> PortfolioDiagnostics:
    """Gera o Diagnóstico da Carteira a partir do view-model do Dashboard."""
    candidates = [
        _concentration_insight(view),
        _dominant_group_insight(view),
        _diversification_insight(view),
        _international_exposure_insight(view),
        *_group_weight_comments(view),
        _multi_currency_insight(view),
        _manual_and_estimated_prices_insight(view),
        _data_quality_insight(view),
        _cash_position_insight(view),
    ]
    insights = [c for c in candidates if c is not None]
    return PortfolioDiagnostics(insights=insights)
