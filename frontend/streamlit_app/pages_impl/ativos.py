"""Tela Ativos: cadastro mestre, status de preço, fundamentos e LG Score.

Consome AssetRepository, PriceRepository, FundamentalsRepository e
LGScoreService. Nenhum cálculo financeiro novo vive aqui — só leitura e
formatação, mais o cadastro de preço manual (grava um `Price` normal,
com `source="manual"`), o flag `is_manual` do ativo (Sprint 12) e a
coleta de fundamentos (Sprint 13), que faz a atualização automática em
lote pular esse ativo.
"""

from __future__ import annotations

import tempfile
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
import streamlit as st

from backend.app.infrastructure.database.models.price import Price
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.infrastructure.repositories.price_repository import PriceRepository
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.fundamentals_import import (
    FUNDAMENTALS_IMPORT_NUMERIC_FIELDS,
    FUNDAMENTALS_IMPORT_REQUIRED_COLUMNS,
)
from backend.app.services.conviction_score_service import ConvictionScoreService
from backend.app.services.data_coverage_service import DataCoverageService
from backend.app.services.data_quality_service import DataQualityService
from backend.app.services.fundamentals_analysis_service import FundamentalsAnalysisService
from backend.app.services.fundamentals_import_service import FundamentalsImportService
from backend.app.services.income_real_estate_service import IncomeRealEstateService
from backend.app.services.lg_score_service import LGScoreService
from backend.app.services.portfolio_adequacy_service import PortfolioAdequacyService
from backend.app.services.trap_detection_service import TrapDetectionService
from backend.app.services.valuation_service import ValuationService
from backend.app.services.valuation_v2_service import ValuationServiceV2
from frontend.streamlit_app.cache import clear_all_caches
from frontend.streamlit_app.components.badges import (
    adequacy_status_badge_html,
    classification_badge_html,
    confidence_badge_html,
    data_quality_badge_html,
    income_real_estate_status_badge_html,
    trap_severity_badge_html,
    valuation_status_badge_html,
)
from frontend.streamlit_app.components.patterns import empty_state, page_header
from frontend.streamlit_app.components.sections import section
from frontend.streamlit_app.db import session_scope
from frontend.streamlit_app.formatting import format_money, format_number, format_pct

# Sprint 26, Fase 7 — classes aplicáveis a cada bloco da Análise
# Fundamentalista, espelhando as regras já impostas pelos engines (nunca
# decidido de novo aqui): Valuation Engine 2.0 só ações; Análise de Renda
# Imobiliária só FII/REIT; Adequação de Carteira só ETF/cripto/Tesouro
# (`bond`); Trap Detection Engine cobre ações + FII/REIT.
_STOCK_CLASSES = ("stock",)
_INCOME_REAL_ESTATE_CLASSES = ("fii", "reit")
_NO_TRADITIONAL_VALUATION_CLASSES = ("etf", "crypto", "bond")

_PILLAR_LABELS_PT = {
    "quality": "Qualidade",
    "valuation": "Valuation",
    "growth": "Crescimento",
    "risk": "Risco",
    "capital_reinvestment": "Reinvestimento de capital",
}

_STATUS_LABELS = {
    "automatic": "🌐 Automático",
    "manual": "✍️ Manual",
    "missing": "📛 Sem preço",
}

# Mesmos campos de backend/app/services/fundamentals_service.py::_SNAPSHOT_FIELDS
# — duplicado deliberadamente para a UI não depender de símbolo interno do serviço.
_FUNDAMENTAL_FIELDS = (
    "roe",
    "roa",
    "net_margin",
    "ebitda_margin",
    "revenue",
    "net_income",
    "ebitda",
    "ebit",
    "free_cash_flow",
    "net_debt",
    "debt_to_ebitda",
    "pe_ratio",
    "pb_ratio",
    "ev_ebitda",
    "dividend_yield",
    "payout_ratio",
    "eps",
    "revenue_per_share",
    "beta",
    "market_cap",
    "enterprise_value",
    "forward_pe",
    "operating_margin",
    "total_debt",
    "total_cash",
    "operating_cash_flow",
    "gross_profit",
    "shares_outstanding",
)


def _price_status(asset, latest_price) -> str:
    if asset.is_manual:
        return "manual"
    if latest_price is None:
        return "missing"
    if latest_price.source == "manual":
        return "manual"
    return "automatic"


def _asset_row(asset, latest_price) -> dict:
    status = _price_status(asset, latest_price)
    updated = (
        latest_price.updated_at.strftime("%d/%m/%Y %H:%M")
        if latest_price is not None and latest_price.updated_at
        else "—"
    )
    price_str = (
        format_money(latest_price.close, asset.currency) if latest_price is not None else "—"
    )
    return {
        "Ticker": asset.ticker,
        "Nome": asset.name,
        "Classe": asset.asset_class,
        "País": asset.country,
        "Moeda": asset.currency,
        "Setor": asset.sector or "—",
        "Preço atual": price_str,
        "Status do preço": _STATUS_LABELS[status],
        "Atualizado em": updated,
    }


def _snapshot_result(ticker: str, snapshot) -> FundamentalSnapshotResult:
    return FundamentalSnapshotResult(
        ticker=ticker,
        period_end=snapshot.period_end,
        source=snapshot.source,
        collected_at=snapshot.updated_at,
        **{field: getattr(snapshot, field) for field in _FUNDAMENTAL_FIELDS},
    )


def render(portfolio_id: int) -> None:
    page_header(
        "Ativos",
        "Cadastro mestre dos seus ativos: preço, status do dado, fundamentos e LG Score.",
        icon="🗂️",
    )

    with session_scope() as db:
        assets = AssetRepository(db).list_all()
        prices = PriceRepository(db)
        rows = [_asset_row(a, prices.get_latest(a.id)) for a in assets]

    if not assets:
        empty_state(
            "Nenhum ativo cadastrado",
            "Rode o seed ou importe uma carteira para começar a ver preços, fundamentos e "
            "LG Score aqui.",
            icon="🗂️",
        )
        return

    with section("Ativos cadastrados", "🗂️"):
        st.dataframe(
            pd.DataFrame(rows),
            width="stretch",
            hide_index=True,
        )
        missing = [r["Ticker"] for r in rows if r["Status do preço"] == _STATUS_LABELS["missing"]]
        if missing:
            st.warning("Sem nenhum preço cadastrado ainda: " + ", ".join(missing))

    tickers = [a.ticker for a in assets]

    with section("LG Score de um ativo", "🧮"):
        ticker = st.selectbox("Ativo", tickers)
        if st.button("Calcular LG Score"):
            with session_scope() as db:
                result = LGScoreService(db).score_ticker(ticker)

            if result is None:
                st.error("Ativo não encontrado.")
                return

            col1, col2, col3 = st.columns(3)
            col1.metric("LG Score", f"{float(result.lg_score):.1f}")
            col2.metric("Classificação", result.classification)
            col3.metric("Confiança", result.confidence_label)

            st.write(
                f"Qualidade {float(result.quality):.0f} · "
                f"Valuation {float(result.valuation):.0f} · "
                f"Crescimento {float(result.growth):.0f} · "
                f"Risco {float(result.risk):.0f} · "
                f"Alocação {float(result.allocation):.0f}"
            )

            with st.expander("Por que essa nota? (explicação por fator)"):
                for pillar in result.explanation:
                    st.markdown(f"**{pillar.name}** — {float(pillar.score):.0f}")
                    for reason in pillar.reasons:
                        st.caption(f"· {reason}")

    with section(
        "LG Conviction Score v2",
        "🧠",
        caption=(
            "Metodologia completa: Quality/Valuation/Growth/Risk/Capital Reinvestment, "
            "com pesos por classe de ativo (ver Inteligência para a carteira toda)."
        ),
    ):
        conviction_ticker = st.selectbox("Ativo", tickers, key="conviction_ticker")
        with session_scope() as db:
            conviction = ConvictionScoreService(db).score_ticker(conviction_ticker)
            asset_for_dq = AssetRepository(db).get_by_ticker(conviction_ticker)
            dq = (
                DataQualityService(db).evaluate_ticker(
                    conviction_ticker,
                    asset_for_dq.id,
                    asset_for_dq.asset_class,
                    is_manual=asset_for_dq.is_manual,
                )
                if asset_for_dq is not None
                else None
            )

        if conviction is None:
            st.info(
                f"Conviction Score indisponível para {conviction_ticker} (sem histórico de preço)."
            )
        else:
            st.markdown(
                f"{classification_badge_html(conviction.classification)} "
                f"{confidence_badge_html(conviction.confidence_label)} &nbsp; "
                f"**Score: {float(conviction.conviction_score):.1f} / 100**",
                unsafe_allow_html=True,
            )
            if conviction.recommendation_hint:
                st.caption(conviction.recommendation_hint)

            pillar_cols = st.columns(5)
            pillar_values = {
                "quality": conviction.quality,
                "valuation": conviction.valuation,
                "growth": conviction.growth,
                "risk": conviction.risk,
                "capital_reinvestment": conviction.capital_reinvestment,
            }
            for col, (key, value) in zip(pillar_cols, pillar_values.items(), strict=False):
                col.metric(_PILLAR_LABELS_PT[key], f"{float(value):.1f}")

            with st.expander("Motivos por pilar"):
                for pillar in conviction.explanation:
                    st.markdown(f"**{_PILLAR_LABELS_PT.get(pillar.name, pillar.name)}**")
                    for reason in pillar.reasons:
                        st.caption(f"· {reason}")

        if dq is not None:
            st.markdown("**Qualidade dos dados usados**")
            badges_html = " ".join(
                [
                    data_quality_badge_html(dq.price_status, f"Preço: {dq.price_status}"),
                    data_quality_badge_html(
                        dq.fundamentals_status, f"Fundamentos: {dq.fundamentals_status}"
                    ),
                    data_quality_badge_html(
                        dq.valuation_status, f"Valuation: {dq.valuation_status}"
                    ),
                ]
            )
            st.markdown(badges_html, unsafe_allow_html=True)
            if dq.issues:
                st.caption(" · ".join(dq.issues))

    with section(
        "Atualizar preço automático de um ativo",
        "🔄",
        caption=(
            "Usa o Yahoo Finance e requer internet. Ativos marcados como manuais são "
            "ignorados aqui — cadastre o preço deles na seção abaixo."
        ),
    ):
        update_ticker = st.selectbox("Ativo", tickers, key="update_price_ticker")
        if st.button("Atualizar agora"):
            try:
                from backend.app.etl.providers.yahoo_provider import YahooFinanceProvider
                from backend.app.services.market_data_service import MarketDataService

                with session_scope() as db:
                    service = MarketDataService(db, YahooFinanceProvider())
                    result = service.update_asset_prices(update_ticker)
                if result.skipped_manual:
                    st.info(
                        f"{update_ticker} está marcado como manual — cadastre o preço na "
                        "seção 'Cadastrar preço atual manual' abaixo."
                    )
                elif result.error:
                    st.error(f"Não foi possível atualizar {update_ticker}: {result.error}")
                else:
                    clear_all_caches()
                    st.success(
                        f"{update_ticker} atualizado: +{result.inserted} inserido(s), "
                        f"{result.updated} atualizado(s), {result.rejected} rejeitado(s)."
                    )
            except Exception:  # noqa: BLE001 - nunca vazar detalhe de exceção não prevista
                st.error(
                    "Não foi possível atualizar o preço agora — sem internet ou fonte "
                    "indisponível. Tente novamente em alguns instantes."
                )

    with section(
        "Fundamentos",
        "📚",
        caption=(
            "Coleta via Yahoo Finance (proxy MVP, sem custo). Cobertura varia por classe e "
            "ticker — campos ausentes aparecem como indisponível, nunca são inventados."
        ),
    ):
        fund_ticker = st.selectbox("Ativo", tickers, key="fundamentals_ticker")
        col_a, col_b = st.columns(2)
        if col_a.button("Coletar fundamentos deste ativo"):
            try:
                from backend.app.etl.providers.yahoo_fundamentals_provider import (
                    YahooFundamentalsProvider,
                )
                from backend.app.services.fundamentals_service import FundamentalsService

                with session_scope() as db:
                    result = FundamentalsService(db, YahooFundamentalsProvider()).collect_for_asset(
                        fund_ticker
                    )
                if result.collected:
                    clear_all_caches()
                    st.success(
                        f"Fundamentos de {fund_ticker} coletados (período mais recente: "
                        f"{result.period_end})."
                    )
                elif result.error:
                    st.error(f"Falha ao coletar {fund_ticker}: {result.error}")
                else:
                    st.info(f"{fund_ticker} não coletado: {result.reason}.")
            except Exception:  # noqa: BLE001 - nunca vazar detalhe de exceção não prevista
                st.error(
                    "Não foi possível coletar fundamentos agora — sem internet ou fonte "
                    "indisponível. Tente novamente em alguns instantes."
                )

        if col_b.button("Coletar fundamentos de todos os ativos"):
            try:
                from backend.app.etl.providers.yahoo_fundamentals_provider import (
                    YahooFundamentalsProvider,
                )
                from backend.app.services.fundamentals_service import FundamentalsService

                with session_scope() as db:
                    batch = FundamentalsService(db, YahooFundamentalsProvider()).collect_all()
                clear_all_caches()
                st.success(
                    f"Coleta em lote concluída: {batch.total_collected} coletado(s), "
                    f"{batch.total_skipped} pulado(s) (manuais/classe não aplicável)."
                )
                if batch.failed:
                    st.warning("Falhas: " + ", ".join(batch.failed))
            except Exception:  # noqa: BLE001 - nunca vazar detalhe de exceção não prevista
                st.error(
                    "Não foi possível coletar fundamentos agora — sem internet ou fonte "
                    "indisponível. Tente novamente em alguns instantes."
                )

        with session_scope() as db:
            fund_asset = AssetRepository(db).get_by_ticker(fund_ticker)
            latest_snapshot = (
                FundamentalsRepository(db).get_latest(fund_asset.id) if fund_asset else None
            )
            snapshot_view = (
                _snapshot_result(fund_ticker, latest_snapshot) if latest_snapshot else None
            )

        if snapshot_view is None:
            st.info(f"Nenhum fundamento coletado ainda para {fund_ticker}.")
        else:
            st.caption(
                f"Período de referência: {snapshot_view.period_end.strftime('%d/%m/%Y')} · "
                f"Cobertura: {format_pct(snapshot_view.coverage_pct)} dos indicadores"
            )
            if fund_asset.asset_class == "fii":
                st.info(
                    "FIIs são fundos, não empresas operacionais: ROE, P/L e margem "
                    "operacional abaixo são calculados pelo Yahoo Finance como se o FII "
                    "fosse uma ação comum — um **proxy do MVP** que costuma não ser um "
                    "indicador significativo para este tipo de ativo. Para avaliar um FII, "
                    "priorize **P/VP** e **Dividend Yield** (metricas realmente usadas para a "
                    "classe — ver `docs/QUALITY_GROWTH_RISK_ENGINES.md`); a cobertura de dado "
                    "e a confiança do LG Conviction Score para FIIs também são calculadas só "
                    "sobre essas duas métricas, não sobre os 28 campos completos."
                )
            col1, col2, col3 = st.columns(3)
            col1.metric(
                "ROE", format_pct(snapshot_view.roe) if snapshot_view.roe is not None else "—"
            )
            col1.metric(
                "Margem líquida",
                (
                    format_pct(snapshot_view.net_margin)
                    if snapshot_view.net_margin is not None
                    else "—"
                ),
            )
            col2.metric(
                "P/L",
                (
                    format_number(snapshot_view.pe_ratio, 2)
                    if snapshot_view.pe_ratio is not None
                    else "—"
                ),
            )
            col2.metric(
                "P/VP",
                (
                    format_number(snapshot_view.pb_ratio, 2)
                    if snapshot_view.pb_ratio is not None
                    else "—"
                ),
            )
            col3.metric(
                "Dividend Yield",
                (
                    format_pct(snapshot_view.dividend_yield)
                    if snapshot_view.dividend_yield is not None
                    else "—"
                ),
            )
            col3.metric(
                "Dívida/EBITDA",
                (
                    format_number(snapshot_view.debt_to_ebitda, 2)
                    if snapshot_view.debt_to_ebitda is not None
                    else "—"
                ),
            )
            col4, col5, col6 = st.columns(3)
            col4.metric(
                "Market Cap",
                (
                    format_money(snapshot_view.market_cap, fund_asset.currency)
                    if snapshot_view.market_cap is not None
                    else "—"
                ),
            )
            col5.metric(
                "Forward P/E",
                (
                    format_number(snapshot_view.forward_pe, 2)
                    if snapshot_view.forward_pe is not None
                    else "—"
                ),
            )
            col6.metric(
                "Margem operacional",
                (
                    format_pct(snapshot_view.operating_margin)
                    if snapshot_view.operating_margin is not None
                    else "—"
                ),
            )

            if snapshot_view.missing_fields:
                st.caption("Indisponíveis: " + ", ".join(snapshot_view.missing_fields))

            with session_scope() as db:
                analysis = FundamentalsAnalysisService(db).analyze_ticker(fund_ticker)

            if analysis is not None and analysis.periods_used > 0:
                st.markdown("**Crescimento (CAGR entre períodos coletados)**")
                cagr_col1, cagr_col2, cagr_col3 = st.columns(3)
                cagr_col1.metric(
                    "Receita",
                    format_pct(analysis.revenue_cagr) if analysis.revenue_cagr is not None else "—",
                )
                cagr_col2.metric(
                    "Lucro líquido",
                    (
                        format_pct(analysis.net_income_cagr)
                        if analysis.net_income_cagr is not None
                        else "—"
                    ),
                )
                cagr_col3.metric(
                    "FCF",
                    format_pct(analysis.fcf_cagr) if analysis.fcf_cagr is not None else "—",
                )
                st.caption(
                    f"Tendência de margem: {analysis.margin_trend} · "
                    f"Confiança: {analysis.confidence} · "
                    f"{analysis.periods_used} período(s) usado(s) no cálculo."
                )

            with session_scope() as db:
                valuation = ValuationService(db).evaluate_ticker(fund_ticker)

            if valuation is not None:
                _VALUATION_LABELS = {
                    "barato": "🟢 Barato",
                    "neutro": "🟡 Neutro",
                    "caro": "🔴 Caro",
                    "indeterminado": "⚪ Indeterminado",
                }
                st.markdown("**Valuation por múltiplos (heurística MVP, sem DCF)**")
                st.write(
                    f"{_VALUATION_LABELS.get(valuation.classification, valuation.classification)} "
                    f"· Confiança: {valuation.confidence}"
                )
                if valuation.reason:
                    st.caption(valuation.reason)
                elif valuation.metrics:
                    detalhes = ", ".join(
                        f"{m.label}: {m.verdict}"
                        + (f" ({format_number(m.value, 2)})" if m.value is not None else "")
                        for m in valuation.metrics
                    )
                    st.caption(detalhes)

    with section(
        "Análise Fundamentalista",
        "🔬",
        caption=(
            "Sprint 26: Valuation Engine 2.0 (faixa de valor justo por DCF, múltiplos e "
            "Graham — só ações), Análise de Renda Imobiliária (P/VP + DY + estabilidade — "
            "só FIIs/REITs), Adequação à Política de Alocação (ETFs, cripto e Tesouro, que "
            "não têm valuation tradicional) e Trap Detection Engine (armadilhas de "
            "valuation). Nunca uma recomendação de compra/venda — sempre análise, faixa e "
            "nível de confiança."
        ),
    ):
        fa_ticker = st.selectbox("Ativo", tickers, key="fundamental_analysis_ticker")

        with session_scope() as db:
            fa_asset = AssetRepository(db).get_by_ticker(fa_ticker)
            fa_asset_class = fa_asset.asset_class if fa_asset is not None else None
            fa_currency = fa_asset.currency if fa_asset is not None else None

            trap_result = TrapDetectionService(db).evaluate_ticker(fa_ticker)
            coverage = DataCoverageService(db).evaluate_ticker(fa_ticker)

            valuation_v2 = None
            income_re = None
            adequacy = None
            if fa_asset_class in _STOCK_CLASSES:
                valuation_v2 = ValuationServiceV2(db).evaluate_ticker(fa_ticker)
            elif fa_asset_class in _INCOME_REAL_ESTATE_CLASSES:
                income_re = IncomeRealEstateService(db).evaluate_ticker(fa_ticker)
            elif fa_asset_class in _NO_TRADITIONAL_VALUATION_CLASSES:
                adequacy = PortfolioAdequacyService(db).evaluate_ticker(fa_ticker, portfolio_id)

        if fa_asset is None:
            st.error("Ativo não encontrado.")
        else:
            if valuation_v2 is not None:
                st.markdown("**Valuation Engine 2.0 (DCF + múltiplos + Graham)**")
                st.markdown(
                    f"{valuation_status_badge_html(valuation_v2.valuation_status)} "
                    f"{confidence_badge_html(valuation_v2.confidence)}",
                    unsafe_allow_html=True,
                )
                if valuation_v2.reason:
                    st.caption(valuation_v2.reason)
                else:
                    fv = valuation_v2.fair_value_range
                    vcol1, vcol2, vcol3 = st.columns(3)
                    vcol1.metric(
                        "Faixa mínima",
                        format_money(fv.low, fa_currency) if fv.low is not None else "—",
                    )
                    vcol2.metric(
                        "Faixa base",
                        format_money(fv.base, fa_currency) if fv.base is not None else "—",
                    )
                    vcol3.metric(
                        "Faixa máxima",
                        format_money(fv.high, fa_currency) if fv.high is not None else "—",
                    )
                    if valuation_v2.current_price is not None:
                        st.caption(
                            "Preço atual: "
                            f"{format_money(valuation_v2.current_price, fa_currency)}"
                        )
                    if valuation_v2.margin_of_safety is not None:
                        margem = f"Margem de segurança: {format_pct(valuation_v2.margin_of_safety)}"
                        if valuation_v2.required_margin_of_safety is not None:
                            margem += (
                                " (exigida: "
                                f"{format_pct(valuation_v2.required_margin_of_safety)})"
                            )
                        st.caption(margem)
                    if valuation_v2.implied_expectation:
                        st.caption(
                            "Expectativa implícita de mercado (reverse DCF): "
                            f"{valuation_v2.implied_expectation}"
                        )
                    if valuation_v2.graham_sanity_check is not None:
                        st.caption(
                            "Graham Number (checagem de sanidade, não método primário): "
                            f"{format_money(valuation_v2.graham_sanity_check, fa_currency)}"
                        )
                    elif valuation_v2.graham_reason:
                        st.caption(f"Graham Number: {valuation_v2.graham_reason}")

                    if valuation_v2.scenarios:
                        with st.expander("Cenários individuais"):
                            for scenario in valuation_v2.scenarios:
                                value_str = (
                                    format_money(scenario.fair_value, fa_currency)
                                    if scenario.fair_value is not None
                                    else "indisponível"
                                )
                                st.markdown(f"**{scenario.label}**: {value_str}")
                                st.caption(scenario.assumptions)
                                if scenario.reason:
                                    st.caption(f"Motivo: {scenario.reason}")

                if valuation_v2.warnings:
                    st.warning(" · ".join(valuation_v2.warnings))
                if valuation_v2.methodology:
                    st.caption("Métodos usados: " + ", ".join(valuation_v2.methodology))

            elif income_re is not None:
                st.markdown("**Análise de Renda Imobiliária (P/VP + DY + estabilidade)**")
                st.markdown(
                    f"{income_real_estate_status_badge_html(income_re.status)} "
                    f"{confidence_badge_html(income_re.confidence)}",
                    unsafe_allow_html=True,
                )
                if income_re.reason:
                    st.caption(income_re.reason)
                icol1, icol2, icol3 = st.columns(3)
                icol1.metric(
                    "P/VP",
                    format_number(income_re.pvp, 2) if income_re.pvp is not None else "—",
                )
                icol2.metric(
                    "Dividend Yield",
                    (
                        format_pct(income_re.dividend_yield)
                        if income_re.dividend_yield is not None
                        else "—"
                    ),
                )
                icol3.metric(
                    "DY médio (histórico próprio)",
                    (
                        format_pct(income_re.dy_own_history_average)
                        if income_re.dy_own_history_average is not None
                        else "—"
                    ),
                )
                estabilidade = f"Estabilidade do DY: {income_re.dy_stability}"
                if income_re.dy_stability_reason:
                    estabilidade += f" — {income_re.dy_stability_reason}"
                st.caption(estabilidade)
                if income_re.warnings:
                    st.warning(" · ".join(income_re.warnings))
                if income_re.methodology:
                    st.caption("Métodos usados: " + ", ".join(income_re.methodology))

            elif adequacy is not None:
                st.markdown("**Adequação à Política de Alocação**")
                st.info(adequacy.valuation_note)
                st.markdown(
                    adequacy_status_badge_html(adequacy.adequacy_status),
                    unsafe_allow_html=True,
                )
                if adequacy.reason:
                    st.caption(adequacy.reason)
                acol1, acol2, acol3 = st.columns(3)
                acol1.metric(
                    "Peso atual",
                    (
                        format_pct(adequacy.current_weight)
                        if adequacy.current_weight is not None
                        else "—"
                    ),
                )
                acol2.metric(
                    "Peso-alvo",
                    (
                        format_pct(adequacy.target_weight)
                        if adequacy.target_weight is not None
                        else "—"
                    ),
                )
                acol3.metric(
                    "Gap ao alvo",
                    (
                        format_pct(adequacy.gap_to_target)
                        if adequacy.gap_to_target is not None
                        else "—"
                    ),
                )
                if adequacy.class_current_weight is not None:
                    classe_txt = (
                        f"Peso da classe '{fa_asset_class}' na carteira: "
                        f"{format_pct(adequacy.class_current_weight)}"
                    )
                    if adequacy.class_target_weight is not None:
                        classe_txt += f" (alvo: {format_pct(adequacy.class_target_weight)})"
                    st.caption(classe_txt)
                if adequacy.alert_message:
                    st.warning(adequacy.alert_message)
                if adequacy.extreme_overweight:
                    st.error(
                        "Concentração extrema nesta dimensão — considere pausar novos "
                        "aportes aqui (nunca uma sugestão de venda)."
                    )
                if adequacy.warnings:
                    st.warning(" · ".join(adequacy.warnings))
            else:
                st.info(f"Nenhuma análise fundamentalista disponível para {fa_ticker} ainda.")

            if trap_result is not None and trap_result.has_traps:
                st.markdown("**Possíveis armadilhas de valuation detectadas**")
                for flag in trap_result.flags:
                    st.markdown(
                        f"{trap_severity_badge_html(flag.severity)} **{flag.label}**",
                        unsafe_allow_html=True,
                    )
                    st.caption(flag.explanation)
                    st.caption(f"Como interpretar: {flag.recommended_interpretation}")
            elif trap_result is not None and trap_result.reason:
                st.caption(trap_result.reason)

            if coverage is not None:
                st.markdown("**Dados usados e dados ausentes**")
                st.caption(coverage.summary)
                purpose_cols = st.columns(5)
                purposes = (
                    ("Quality", coverage.quality),
                    ("Valuation", coverage.valuation),
                    ("Trap Detection", coverage.trap_detection),
                    ("Análise de Renda", coverage.income),
                    ("Decision Engine", coverage.decision_engine),
                )
                for col, (label, purpose) in zip(purpose_cols, purposes, strict=False):
                    if purpose.score is not None:
                        col.metric(label, f"{float(purpose.score):.0f}%", purpose.classification)
                    else:
                        col.metric(label, "—", "não aplicável")

                available_fields = [
                    f for f in coverage.fields if f.available and f.value is not None
                ]
                missing_fields = [f for f in coverage.fields if not f.available]

                with st.expander(f"Dados disponíveis ({len(available_fields)})"):
                    if not available_fields:
                        st.caption("Nenhum campo fundamentalista disponível ainda.")
                    for field in available_fields:
                        value_str = (
                            format_number(field.value, 2)
                            if isinstance(field.value, Decimal)
                            else str(field.value)
                        )
                        meta_parts = []
                        if field.source:
                            meta_parts.append(f"fonte {field.source}")
                        if field.updated_at:
                            meta_parts.append(
                                f"atualizado em {field.updated_at.strftime('%d/%m/%Y')}"
                            )
                        meta = f" — {', '.join(meta_parts)}" if meta_parts else ""
                        st.caption(f"**{field.label}**: {value_str}{meta}")

                with st.expander(
                    f"Dados ausentes ({len(missing_fields)})", expanded=bool(missing_fields)
                ):
                    if not missing_fields:
                        st.caption("Nenhum campo do relatório está ausente.")
                    for field in missing_fields:
                        st.caption(f"- {field.label}")
                    if coverage.valuation.missing_labels:
                        st.caption(
                            "Impacto: sem esses dados, a confiança do valuation permanece baixa."
                        )

    with section(
        "Marcar ativo como manual",
        "🏷️",
        caption=(
            "Ativos sem cotação de mercado (ex.: Tesouro Direto) devem ser marcados como "
            "manuais: a atualização automática de preços passa a pular esse ativo, e o "
            "preço é sempre cadastrado por você na seção abaixo."
        ),
    ):
        flag_ticker = st.selectbox("Ativo", tickers, key="manual_flag_ticker")
        with session_scope() as db:
            flag_asset = AssetRepository(db).get_by_ticker(flag_ticker)
            current_flag = flag_asset.is_manual if flag_asset is not None else False
        new_flag = st.checkbox(
            "Este ativo não tem cotação automática",
            value=current_flag,
            key=f"manual_flag_checkbox_{flag_ticker}",
        )
        if st.button("Salvar status manual"):
            with session_scope() as db:
                flag_asset = AssetRepository(db).get_by_ticker(flag_ticker)
                if flag_asset is None:
                    st.error("Ativo não encontrado.")
                else:
                    flag_asset.is_manual = new_flag
                    db.commit()
                    clear_all_caches()
                    estado = "manual" if new_flag else "automático"
                    st.success(f"{flag_ticker} marcado como {estado}.")

    with section(
        "Cadastrar preço atual manual",
        "✍️",
        caption=(
            "Para ativos sem cotação via Yahoo Finance (ex.: Tesouro Direto). Grava um preço "
            "com origem 'manual' na data de hoje — Dashboard e Carteira passam a mostrá-lo "
            "como preço real, não como estimativa."
        ),
    ):
        manual_ticker = st.selectbox("Ativo", tickers, key="manual_price_ticker")
        manual_price_str = st.text_input("Preço atual", key="manual_price_value")
        if st.button("Salvar preço manual"):
            try:
                manual_price = Decimal(manual_price_str.replace(",", "."))
                if manual_price <= 0:
                    raise ValueError("o preço deve ser maior que zero.")
            except (InvalidOperation, ValueError) as exc:
                st.error(f"Preço inválido: {exc}")
            else:
                with session_scope() as db:
                    asset = AssetRepository(db).get_by_ticker(manual_ticker)
                    if asset is None:
                        st.error("Ativo não encontrado.")
                    else:
                        today = date.today()
                        price_repo = PriceRepository(db)
                        existing = price_repo.get_by_asset_and_date(asset.id, today)
                        if existing is not None:
                            existing.close = manual_price
                            existing.source = "manual"
                            db.commit()
                        else:
                            price_repo.create(
                                Price(
                                    asset_id=asset.id,
                                    date=today,
                                    close=manual_price,
                                    source="manual",
                                )
                            )
                        clear_all_caches()
                        st.success(
                            f"Preço atual de {manual_ticker} salvo: {manual_price} (manual)."
                        )

    with section(
        "Importar fundamentos manualmente (CSV/Excel)",
        "📥",
        caption=(
            "Fallback para ativos sem cobertura no Yahoo Finance (comum em ações brasileiras "
            "menores). Preencha o modelo com dados de outra fonte (RI da empresa, CVM, "
            "Status Invest etc.) — o ticker já precisa estar cadastrado; nenhum ativo novo é "
            "criado por aqui. Depois de importar, valuation, traps e scores dos ativos "
            "afetados são recalculados automaticamente."
        ),
    ):
        template_columns = list(FUNDAMENTALS_IMPORT_REQUIRED_COLUMNS) + list(
            FUNDAMENTALS_IMPORT_NUMERIC_FIELDS
        )
        template_csv = ",".join(template_columns) + "\n"
        st.download_button(
            "Baixar modelo CSV",
            data=template_csv,
            file_name="modelo_fundamentos.csv",
            mime="text/csv",
        )

        uploaded = st.file_uploader(
            "Arquivo de fundamentos (.csv, .xlsx, .xls)",
            type=["csv", "xlsx", "xls"],
            key="fundamentals_import_file",
        )
        overwrite = st.checkbox(
            "Sobrescrever snapshots existentes que colidirem (mesmo ticker + período)",
            value=False,
            key="fundamentals_import_overwrite",
            help=(
                "Sem marcar isso, linhas que colidem com um snapshot já salvo ficam pendentes "
                "de confirmação e não são aplicadas — nada é sobrescrito sem essa confirmação "
                "explícita."
            ),
        )

        if uploaded is not None and st.button("Importar fundamentos"):
            suffix = Path(uploaded.name).suffix or ".csv"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name
            try:
                with session_scope() as db:
                    import_result = FundamentalsImportService(db).import_file(
                        tmp_path, portfolio_id, confirm_overwrite=overwrite
                    )
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            clear_all_caches()
            st.session_state["_last_fundamentals_import"] = import_result

        last_import = st.session_state.get("_last_fundamentals_import")
        if last_import is not None:
            cols = st.columns(4)
            cols[0].metric("Linhas no arquivo", last_import.total_rows)
            cols[1].metric("Aplicadas", last_import.imported)
            cols[2].metric("Pendentes de confirmação", last_import.conflicts_pending)
            cols[3].metric("Erros", len(last_import.errors))

            if last_import.tickers_recomputed:
                st.caption(
                    f"Recalculado para {len(last_import.tickers_recomputed)} ativo(s): "
                    f"valuation {last_import.valuation_recalculated} · "
                    f"traps {last_import.traps_recalculated} · "
                    f"scores {last_import.scores_recalculated}. "
                    f"Tickers: {', '.join(last_import.tickers_recomputed)}."
                )

            if last_import.has_pending_conflicts:
                st.warning(
                    "Existem linhas com dados já salvos para o mesmo ticker/período. Marque "
                    "'Sobrescrever snapshots existentes' e importe de novo para aplicá-las."
                )
                for outcome in last_import.outcomes:
                    if outcome.status == "conflict_pending_confirmation":
                        st.caption(f"Linha {outcome.line}: {outcome.message}")

            if last_import.has_errors:
                with st.expander(f"Erros de linha ({len(last_import.errors)})", expanded=True):
                    for err in last_import.errors:
                        field_part = f" [{err.field}]" if err.field else ""
                        st.caption(f"Linha {err.line}{field_part}: {err.message}")
