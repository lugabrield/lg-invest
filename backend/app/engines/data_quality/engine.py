"""Data Quality Engine (Sprint 21) — engine PURA.

Classifica sinais já resolvidos por outros serviços (fonte do preço,
contagem de campos de fundamentos preenchidos, classificação de
valuation, confiança do LG Conviction Score) em um veredito por
dimensão. Não acessa banco, yfinance nem Streamlit. Nunca inventa
"completo" quando falta dado — a regra é sempre conservadora: na
dúvida, classifica para baixo (ex.: fundamentos com só 1 campo
preenchido de 15 é "parcial", não "completo").
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.schemas.data_quality import AssetDataQuality, PortfolioDataQualitySummary

_ZERO = Decimal("0")

# Cobertura mínima de campos de fundamentos para considerar "completo"
# (ex.: 70% dos ~19 campos do FundamentalSnapshot preenchidos). Abaixo
# disso mas com pelo menos 1 campo, é "parcial". Threshold deliberado,
# não calibrado estatisticamente — documentado em docs/DATA_QUALITY.md.
_FUNDAMENTALS_COMPLETE_RATIO = Decimal("0.7")


def classify_price_status(
    price_source: str | None, is_estimated: bool, *, is_manual: bool = False
) -> str:
    """price_source vem de `Price.source`: 'yahoo' | 'manual' | None (sem cotação).

    `is_manual` vem de `Asset.is_manual` (ex.: Tesouro Direto) e tem
    prioridade sobre tudo: um ativo marcado como manual é sempre
    classificado "manual", mesmo que a linha de `Price` mais recente
    tenha `source` diferente de "manual" ou não exista ainda — nunca
    "ausente"/"estimado" para um ativo que o usuário já disse que
    gerencia manualmente (Sprint 22; mesma convenção já usada em
    `pages_impl/ativos.py::_price_status`).

    `is_estimated` reflete a mesma regra do `dashboard_view_service`: quando
    não há nenhuma cotação para o ativo, o preço médio é usado como
    aproximação só para exibição — isso é "estimado", não "ausente" (o
    usuário ainda vê um número, só que não é uma cotação real).
    """
    if is_manual:
        return "manual"
    if is_estimated:
        return "estimado"
    if price_source is None:
        return "ausente"
    if price_source == "manual":
        return "manual"
    return "automatico"


def classify_fundamentals_status(
    fields_available: int, fields_total: int, *, applicable: bool
) -> str:
    if not applicable:
        return "nao_aplicavel"
    if fields_total == 0 or fields_available == 0:
        return "ausente"
    ratio = Decimal(fields_available) / Decimal(fields_total)
    if ratio >= _FUNDAMENTALS_COMPLETE_RATIO:
        return "completo"
    return "parcial"


def classify_valuation_status(classification: str | None, *, applicable: bool) -> str:
    if not applicable:
        return "nao_aplicavel"
    if classification is None or classification == "indeterminado":
        return "ausente"
    return "real"


def classify_score_confidence(confidence_label: str | None) -> str:
    if confidence_label is None:
        return "indisponivel"
    if confidence_label in ("alta", "média", "baixa"):
        return confidence_label
    return "indisponivel"


def build_asset_data_quality(
    *,
    ticker: str,
    asset_class: str,
    price_source: str | None,
    is_price_estimated: bool,
    fundamentals_fields_available: int,
    fundamentals_fields_total: int,
    fundamentals_applicable: bool,
    valuation_classification: str | None,
    valuation_applicable: bool,
    score_confidence_label: str | None,
    is_manual: bool = False,
) -> AssetDataQuality:
    """Compõe o veredito de qualidade de dado de um ativo a partir de sinais já resolvidos."""
    price_status = classify_price_status(price_source, is_price_estimated, is_manual=is_manual)
    fundamentals_status = classify_fundamentals_status(
        fundamentals_fields_available, fundamentals_fields_total, applicable=fundamentals_applicable
    )
    valuation_status = classify_valuation_status(
        valuation_classification, applicable=valuation_applicable
    )
    score_confidence = classify_score_confidence(score_confidence_label)

    issues: list[str] = []
    if price_status == "estimado":
        issues.append("preço estimado (sem cotação real recente)")
    if price_status == "ausente":
        issues.append("sem preço cadastrado")
    if price_status == "manual" and price_source is None:
        issues.append("ativo manual sem preço cadastrado ainda — cadastre um preço em Ativos")
    if fundamentals_status == "ausente":
        issues.append("sem fundamentos coletados")
    elif fundamentals_status == "parcial":
        issues.append(
            f"fundamentos parciais ({fundamentals_fields_available}/{fundamentals_fields_total} campos)"
        )
    if valuation_status == "ausente":
        issues.append("valuation indeterminado por falta de múltiplos")
    if score_confidence == "baixa":
        issues.append("LG Conviction Score com confiança baixa")

    return AssetDataQuality(
        ticker=ticker,
        asset_class=asset_class,
        price_status=price_status,
        fundamentals_status=fundamentals_status,
        fundamentals_fields_available=fundamentals_fields_available,
        fundamentals_fields_total=fundamentals_fields_total,
        valuation_status=valuation_status,
        score_confidence=score_confidence,
        issues=issues,
    )


def build_portfolio_summary(
    assets: list[AssetDataQuality], weights: dict[str, Decimal]
) -> PortfolioDataQualitySummary:
    """Agrega os vereditos por ativo num resumo de carteira, ponderado por peso (quando disponível).

    `weights` é um dict ticker -> peso (0..1); tickers ausentes contam peso 0 (não quebra).
    Se `weights` for vazio (ex.: carteira vazia), os percentuais ficam 0 e a lista de
    ativos por bucket continua sendo preenchida — nunca lança exceção.
    """
    total_assets = len(assets)
    if total_assets == 0:
        return PortfolioDataQualitySummary()

    def _weight(ticker: str) -> Decimal:
        return weights.get(ticker, _ZERO)

    pct_price_automatic = sum(
        (_weight(a.ticker) for a in assets if a.price_status == "automatico"), _ZERO
    )
    pct_price_manual = sum((_weight(a.ticker) for a in assets if a.price_status == "manual"), _ZERO)
    pct_price_estimated = sum(
        (_weight(a.ticker) for a in assets if a.price_status == "estimado"), _ZERO
    )
    pct_fundamentals_available = sum(
        (_weight(a.ticker) for a in assets if a.fundamentals_status in ("completo", "parcial")),
        _ZERO,
    )
    pct_valuation_available = sum(
        (_weight(a.ticker) for a in assets if a.valuation_status in ("real", "proxy")), _ZERO
    )

    assets_insufficient_data = [
        a.ticker
        for a in assets
        if a.fundamentals_status == "ausente" and a.valuation_status == "ausente"
    ]
    assets_manual = [a.ticker for a in assets if a.price_status == "manual"]
    assets_price_estimated = [a.ticker for a in assets if a.price_status == "estimado"]
    assets_unsupported_by_provider = [
        a.ticker for a in assets if a.fundamentals_status == "nao_aplicavel"
    ]

    return PortfolioDataQualitySummary(
        total_assets=total_assets,
        pct_price_automatic=pct_price_automatic,
        pct_price_manual=pct_price_manual,
        pct_price_estimated=pct_price_estimated,
        pct_fundamentals_available=pct_fundamentals_available,
        pct_valuation_available=pct_valuation_available,
        assets_insufficient_data=assets_insufficient_data,
        assets_manual=assets_manual,
        assets_price_estimated=assets_price_estimated,
        assets_unsupported_by_provider=assets_unsupported_by_provider,
        per_asset=assets,
    )
