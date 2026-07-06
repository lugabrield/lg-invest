"""Tela Dashboard: visão geral, composição, destaques, riscos e diagnóstico.

Consome o PortfolioService (Portfolio Engine) através do
dashboard_view_service, que adiciona só aqui — nunca na engine — a
conversão de câmbio USD->BRL, o fallback de preço para ativos sem
cotação de mercado e a origem do preço (automático/manual/estimado).
Decision Engine, LG Score e o CLI de resumo continuam lendo
PortfolioService.get_summary sem nenhuma dessas coisas.

Nenhum cálculo financeiro vive nesta tela: os cards e gráficos só
formatam e desenham o que os serviços/engines já calcularam.
"""

from __future__ import annotations

from decimal import Decimal

import streamlit as st

from backend.app.engines.portfolio_diagnostics import thresholds as dq_thresholds
from backend.app.schemas.dashboard_view import DashboardView
from backend.app.services import fx_settings_service
from backend.app.services.dashboard_view_service import GROUP_ORDER
from frontend.streamlit_app.cache import cached_dashboard_bundle, clear_all_caches
from frontend.streamlit_app.charts.allocation_charts import (
    chart_allocation_by_class,
    chart_allocation_by_currency,
    chart_brazil_vs_international,
    chart_brl_usd_comparison,
    chart_distribution_by_type,
)
from frontend.streamlit_app.charts.concentration_charts import chart_concentration_by_asset
from frontend.streamlit_app.charts.performance_charts import (
    chart_return_by_asset,
    chart_top_positions,
)
from frontend.streamlit_app.components.badges import badge_html, classification_badge_html
from frontend.streamlit_app.components.cards import KpiCard, render_insight_list, render_kpi_grid
from frontend.streamlit_app.components.sections import section
from frontend.streamlit_app.components.tables import (
    render_grouped_positions,
    render_positions_table,
)
from frontend.streamlit_app.formatting import format_brl, format_pct, format_usd
from frontend.streamlit_app.styles.theme import ALERT, ATTENTION, INFO, NEUTRAL, POSITIVE

_ZERO = Decimal("0")

_HEALTH_COLOR = {
    "crítica": ALERT,
    "atenção": ATTENTION,
    "boa": INFO,
    "excelente": POSITIVE,
    "indeterminado": NEUTRAL,
}
_RISK_COLOR = {
    "baixo": POSITIVE,
    "moderado": INFO,
    "moderado-alto": ATTENTION,
    "alto": ALERT,
    "indeterminado": NEUTRAL,
}


def _dominant_group(view: DashboardView) -> tuple[str, Decimal] | None:
    weights: dict[str, Decimal] = {}
    for p in view.positions:
        weights[p.group_label] = weights.get(p.group_label, _ZERO) + p.weight
    if not weights:
        return None
    label, weight = max(weights.items(), key=lambda kv: kv[1])
    return label, weight


def _best_and_worst_performers(view: DashboardView):
    ranked = [p for p in view.positions if p.return_pct is not None and not p.is_price_estimated]
    if not ranked:
        return None, None
    best = max(ranked, key=lambda p: p.return_pct)
    worst = min(ranked, key=lambda p: p.return_pct)
    return best, worst


def _international_weight(view: DashboardView) -> Decimal:
    return sum((c.weight for c in view.currency_exposure if c.currency != "BRL"), _ZERO)


def render(portfolio_id: int) -> None:
    st.title("Dashboard")
    st.caption(
        "Sua carteira, de forma rápida de entender: quanto, onde e o que precisa de atenção."
    )

    exchange_rate = fx_settings_service.get_usd_brl_rate()
    _, refresh_col = st.columns([5, 1])
    with refresh_col:
        if st.button("🔄 Atualizar dados", help="Ignora o cache de 5 minutos e recalcula agora."):
            clear_all_caches()
            st.rerun()

    (
        view,
        diagnostics,
        intelligence,
        data_quality,
        health_result,
        risk_result,
    ) = cached_dashboard_bundle(portfolio_id, exchange_rate)

    if not view.positions:
        st.info("Carteira vazia. Importe posições na tela Carteira.")
        return

    automatic_weight = sum((p.weight for p in view.positions if p.price_source == "yahoo"), _ZERO)
    if automatic_weight < dq_thresholds.DATA_QUALITY_AUTOMATIC_WARN:
        st.warning(
            f"Apenas {format_pct(automatic_weight)} do patrimônio está com preço automático "
            "(Yahoo Finance) — o restante depende de preço manual ou estimado, o que reduz a "
            "confiabilidade dos números abaixo. Veja detalhes em Diagnóstico da Carteira."
        )

    largest = next((p for p in view.positions if p.ticker == view.largest_position_ticker), None)
    dominant = _dominant_group(view)
    best, worst = _best_and_worst_performers(view)
    international = _international_weight(view)

    cards: list[KpiCard] = [
        {"label": "Patrimônio total (convertido)", "value": format_brl(view.total_converted_brl)},
        {"label": "Patrimônio em BRL", "value": format_brl(view.total_brl)},
        {"label": "Patrimônio em USD", "value": format_usd(view.total_usd)},
        {
            "label": "Rentabilidade total aproximada",
            "value": (
                format_pct(view.total_return_pct, signed=True)
                if view.total_return_pct is not None
                else "—"
            ),
            "help": "Preço atual vs. preço médio, ponderado pelo valor convertido.",
        },
        {
            "label": "Exposição internacional",
            "value": format_pct(international),
            "help": "Fração do patrimônio convertido em moedas diferentes de BRL.",
        },
        {
            "label": "Maior posição",
            "value": f"{largest.ticker} ({format_pct(largest.weight)})" if largest else "—",
        },
        {
            "label": "Classe dominante",
            "value": f"{dominant[0]} ({format_pct(dominant[1])})" if dominant else "—",
        },
        {
            "label": "Câmbio USD/BRL utilizado",
            "value": f"{float(view.exchange_rate):.4f}".replace(".", ","),
        },
        {
            "label": "Ativo com maior alta",
            "value": f"{best.ticker} ({format_pct(best.return_pct, signed=True)})" if best else "—",
        },
        {
            "label": "Ativo com maior queda",
            "value": (
                f"{worst.ticker} ({format_pct(worst.return_pct, signed=True)})" if worst else "—"
            ),
        },
    ]
    with section("Visão Geral", "📊"):
        render_kpi_grid(cards, columns=4)
        if view.is_multi_currency:
            st.caption(
                "Conversão aplicada apenas para exibição, com o câmbio manual configurado em "
                "Configurações. Decision Engine e LG Score continuam usando valores nominais "
                "por moeda, sem conversão."
            )

    with section(
        "Saúde da Carteira",
        "🩺✨",
        caption="Resume 5 sinais de engines diferentes (Fase 8) em um único score. "
        "Relatório informativo — nunca uma recomendação de compra ou venda.",
    ):
        health_color = _HEALTH_COLOR.get(health_result.overall_classification, NEUTRAL)
        st.markdown(
            f"### {badge_html(health_result.overall_classification.capitalize(), health_color)} "
            f"— Score: {float(health_result.overall_score):.1f}/100",
            unsafe_allow_html=True,
        )
        available_factors = [f for f in health_result.factors if f.available]
        if available_factors:
            cols = st.columns(len(available_factors))
            for col, factor in zip(cols, available_factors, strict=False):
                col.metric(factor.name.replace("_", " ").capitalize(), f"{float(factor.score):.0f}")
        with st.expander("Detalhes por pilar"):
            for factor in health_result.factors:
                status = f"{float(factor.score):.0f}" if factor.available else "indisponível"
                st.caption(f"**{factor.name.replace('_', ' ')}** ({status}): {factor.reason}")
        for warning in health_result.warnings:
            st.caption(f"⚠️ {warning}")

    with section(
        "Risco da Carteira",
        "🎲",
        caption="Score agregado de risco (Fase 6): volatilidade, concentração, risco "
        "estrutural por ativo e risco de cauda (quando uma simulação Monte Carlo foi "
        "rodada em Simulação).",
    ):
        risk_color = _RISK_COLOR.get(risk_result.overall_classification, NEUTRAL)
        tolerance_note = (
            f" · Tolerância declarada: **{risk_result.declared_risk_tolerance}**"
            if risk_result.declared_risk_tolerance
            else ""
        )
        st.markdown(
            f"**Risco medido:** {badge_html(risk_result.overall_classification, risk_color)}"
            + tolerance_note,
            unsafe_allow_html=True,
        )
        if risk_result.tolerance_alert:
            st.info(risk_result.tolerance_alert)
        available_risk_factors = [f for f in risk_result.factors if f.available]
        if available_risk_factors:
            cols = st.columns(len(available_risk_factors))
            for col, factor in zip(cols, available_risk_factors, strict=False):
                col.metric(factor.name.replace("_", " ").capitalize(), f"{float(factor.score):.0f}")
        with st.expander("Detalhes por fator de risco"):
            for factor in risk_result.factors:
                status = f"{float(factor.score):.0f}" if factor.available else "indisponível"
                st.caption(f"**{factor.name.replace('_', ' ')}** ({status}): {factor.reason}")

    with section(
        "Oportunidades & Riscos",
        "🧭",
        caption="Resumo de decisão baseado no LG Conviction Score v2 e na alocação-alvo — "
        "veja a análise completa por ativo na aba Inteligência.",
    ):
        scored = [a for a in intelligence.assets if a.has_conviction_score]
        top_opportunities = sorted(
            [a for a in scored if a.classification in ("strong_buy", "buy")],
            key=lambda a: a.conviction_score,
            reverse=True,
        )[:3]
        top_risks = sorted(
            [a for a in scored if a.classification in ("avoid", "watch")],
            key=lambda a: a.conviction_score,
        )[:3]
        insufficient = [a for a in intelligence.assets if not a.has_conviction_score]

        col_opp, col_risk = st.columns(2)
        with col_opp:
            st.markdown("**Oportunidades**")
            if top_opportunities:
                for a in top_opportunities:
                    st.markdown(
                        f"{classification_badge_html(a.classification)} **{a.ticker}** — "
                        f"score {float(a.conviction_score):.1f}",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("Nenhum ativo em 'Aportar'/'Candidato' no momento.")
        with col_risk:
            st.markdown("**Riscos principais**")
            if top_risks:
                for a in top_risks:
                    st.markdown(
                        f"{classification_badge_html(a.classification)} **{a.ticker}** — "
                        f"score {float(a.conviction_score):.1f}",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("Nenhum ativo em 'Evitar'/'Monitorar' no momento.")

        if (
            intelligence.allocation_drift.has_target
            and intelligence.allocation_drift.most_underweight_class
        ):
            st.info(
                f"Classe mais subalocada em relação à meta: "
                f"**{intelligence.allocation_drift.most_underweight_class}** — candidata natural "
                "ao próximo aporte. Simule em **Aporte**."
            )
        else:
            st.caption(
                "Nenhuma meta de alocação configurada — defina uma em Configurações para o "
                "Dashboard e o Decision Engine 2.0 considerarem desvio de classe."
            )

        dq_col1, dq_col2, dq_col3 = st.columns(3)
        dq_col1.metric(
            "Carteira com preço automático", format_pct(data_quality.pct_price_automatic)
        )
        dq_col2.metric(
            "Com fundamentos coletados", format_pct(data_quality.pct_fundamentals_available)
        )
        dq_col3.metric("Com valuation calculável", format_pct(data_quality.pct_valuation_available))
        if insufficient or data_quality.assets_insufficient_data:
            tickers = sorted(
                {a.ticker for a in insufficient} | set(data_quality.assets_insufficient_data)
            )
            st.caption(
                "Dados insuficientes para conviction/valuation confiáveis: " + ", ".join(tickers)
            )

    with section("Composição", "🧩"):
        col1, col2 = st.columns(2)
        col1.plotly_chart(chart_allocation_by_class(view.positions), use_container_width=True)
        col2.plotly_chart(
            chart_allocation_by_currency(view.currency_exposure), use_container_width=True
        )

        col3, col4 = st.columns(2)
        col3.plotly_chart(chart_distribution_by_type(view.positions), use_container_width=True)
        col4.plotly_chart(
            chart_brazil_vs_international(view.currency_exposure), use_container_width=True
        )

        st.plotly_chart(chart_brl_usd_comparison(view), use_container_width=True)

    col_destaques, col_riscos = st.columns(2)
    with col_destaques:
        with section("Destaques", "🏆"):
            st.plotly_chart(chart_top_positions(view.positions), use_container_width=True)
            st.plotly_chart(chart_return_by_asset(view.positions), use_container_width=True)
    with col_riscos:
        with section("Riscos & Concentração", "⚠️"):
            if view.effective_number_of_assets is not None:
                st.write(
                    f"HHI: {float(view.concentration_hhi):.3f}  ·  "
                    f"Nº efetivo de ativos: {float(view.effective_number_of_assets):.2f}"
                )
            st.plotly_chart(chart_concentration_by_asset(view.positions), use_container_width=True)

    with section(
        "Diagnóstico da Carteira",
        "🩺",
        caption="Regras simples e transparentes — sem IA generativa.",
    ):
        render_insight_list(diagnostics.insights)

    with section("Posições", "📋", caption="Clique no cabeçalho de uma coluna para ordenar."):
        render_positions_table(view.positions, view.largest_position_ticker)
        st.subheader("Por classe")
        render_grouped_positions(view.positions, GROUP_ORDER, view.largest_position_ticker)

    if view.manual_price_tickers or view.estimated_price_tickers:
        with section("Atenção: preços manuais/estimados", "🔎"):
            if view.manual_price_tickers:
                st.info(
                    "Preço manual (cadastrado por você): " + ", ".join(view.manual_price_tickers)
                )
            if view.estimated_price_tickers:
                st.warning(
                    "Sem cotação nenhuma ainda — usando preço médio como estimativa temporária: "
                    + ", ".join(view.estimated_price_tickers)
                    + ". Cadastre um preço atual manual na tela Ativos para substituir a estimativa."
                )

    with section("Próximos passos", "➡️"):
        st.write("Quer simular onde alocar o próximo aporte com base na sua carteira atual?")
        if st.button("Simular aporte"):
            st.info("Abra a tela **Aporte** no menu lateral para simular a distribuição sugerida.")
