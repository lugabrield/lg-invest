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
from backend.app.services import data_refresh_status_service, fx_settings_service
from backend.app.services.dashboard_view_service import GROUP_ORDER
from backend.app.services.data_refresh_service import DataRefreshService
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
from frontend.streamlit_app.components.badges import (
    badge_html,
    classification_badge_html,
    risk_badge_html,
)
from frontend.streamlit_app.components.cards import KpiCard, render_insight_list, render_kpi_grid
from frontend.streamlit_app.components.patterns import (
    MetricCardSpec,
    alert_box,
    metric_card_row,
    page_header,
    success_box,
)
from frontend.streamlit_app.components.sections import section
from frontend.streamlit_app.components.tables import (
    render_grouped_positions,
    render_positions_table,
)
from frontend.streamlit_app.db import session_scope
from frontend.streamlit_app.formatting import format_brl, format_pct, format_usd
from frontend.streamlit_app.styles.theme import ALERT, ATTENTION, INFO, NEUTRAL, POSITIVE

_ZERO = Decimal("0")

# Escala do Portfolio Health Score (Fase 8) — diferente das 9 chaves
# genéricas do StatusBadge (components/badges.py): "excelente" e "boa" são
# dois patamares positivos distintos que a engine já calcula, então mantém
# a paleta própria em vez de forçar no vocabulário genérico e perder essa
# distinção.
_HEALTH_COLOR = {
    "crítica": ALERT,
    "atenção": ATTENTION,
    "boa": INFO,
    "excelente": POSITIVE,
    "indeterminado": NEUTRAL,
}
_HEALTH_METRIC_STATUS = {
    "crítica": "critical",
    "atenção": "attention",
    "boa": "positive",
    "excelente": "positive",
    "indeterminado": "muted",
}
_RISK_METRIC_STATUS = {
    "baixo": "positive",
    "moderado": "neutral",
    "moderado-alto": "attention",
    "alto": "critical",
    "indeterminado": "muted",
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


def _format_refresh_ts(value) -> str:
    if value is None:
        return "nunca"
    return value.strftime("%d/%m/%Y %H:%M")


def _render_single_refresh_summary(title: str, result) -> None:
    """Um bloco de resumo (Preços/Fundamentos/Watchlist) — contagens reais,
    nunca decorativas: lidas direto das propriedades do resultado
    (`schemas/data_refresh.py::_OutcomesSummaryMixin`)."""
    st.markdown(f"**{title}**")
    cols = st.columns(4)
    cols[0].metric("Processados", result.processed)
    cols[1].metric("Atualizados", result.updated)
    cols[2].metric("Dados insuficientes", result.insufficient_data)
    cols[3].metric("Falhas", result.failed)

    extra_lines: list[str] = []
    if result.sources_used:
        extra_lines.append("Fontes: " + ", ".join(result.sources_used))
    if result.valuation_recalculated or result.traps_recalculated or result.scores_recalculated:
        extra_lines.append(
            f"Valuation/análise recalculada: {result.valuation_recalculated} · "
            f"Traps recalculadas: {result.traps_recalculated} · "
            f"Scores recalculados: {result.scores_recalculated}"
        )
    if hasattr(result, "positions_created"):
        extra_lines.append(
            f"Posições criadas: {result.positions_created} · "
            f"Patrimônio alterado: {'sim' if result.patrimonio_changed else 'não'}"
        )
    if result.coverage_sufficient or result.coverage_partial or result.coverage_insufficient:
        extra_lines.append(
            f"Cobertura de dados — suficiente: {result.coverage_sufficient} · "
            f"parcial: {result.coverage_partial} · "
            f"insuficiente: {result.coverage_insufficient}"
        )
    if result.most_missing_fields:
        extra_lines.append("Campos mais ausentes: " + ", ".join(result.most_missing_fields))
    for line in extra_lines:
        st.caption(line)
    if result.failed_tickers:
        st.caption("Falharam: " + ", ".join(result.failed_tickers))


def _render_refresh_summary(kind: str, result) -> None:
    with st.expander("Resumo da última execução", expanded=True):
        if kind == "prices":
            _render_single_refresh_summary("Preços da carteira", result)
        elif kind == "fundamentals":
            _render_single_refresh_summary("Fundamentos da carteira", result)
        elif kind == "watchlist":
            _render_single_refresh_summary("Watchlist", result)
        elif kind == "all":
            _render_single_refresh_summary("Carteira — Preços", result.prices)
            _render_single_refresh_summary("Carteira — Fundamentos", result.fundamentals)
            _render_single_refresh_summary("Watchlist", result.watchlist)
        st.caption("Cache invalidado: sim")


def _freshest_refresh_label(last_status) -> str:
    """Rótulo curto para o título do expander — mostra a atualização mais
    recente entre preços/fundamentos/watchlist sem precisar abrir o painel."""
    timestamps = [
        t
        for t in (last_status.prices_at, last_status.fundamentals_at, last_status.watchlist_at)
        if t
    ]
    if not timestamps:
        return "nunca atualizado"
    return _format_refresh_ts(max(timestamps))


def _render_data_refresh_center(portfolio_id: int) -> None:
    """Central de Dados: 5 botões de atualização manual (Sprint 27).

    Nunca roda sozinha — só a partir de um clique explícito aqui. Cada
    botão chama o `DataRefreshService` (I/O real: preço/fundamentos via
    Yahoo Finance, recomputação de valuation/traps/scores) e mostra um
    resumo de execução real, nunca decorativo. Sprint 30 (Parte 3): vive
    dentro de um expander recolhido por padrão — a última atualização
    aparece discretamente no próprio título, sem precisar abrir o painel.
    """
    freshest = _freshest_refresh_label(DataRefreshService.get_last_refresh_status())
    with st.expander(f"🗄️ Atualizar dados e análises · última: {freshest}", expanded=False):
        st.caption(
            "Atualize preços, fundamentos, valuation, traps e dados da watchlist "
            "manualmente. Essas rotinas podem demorar e não são executadas automaticamente."
        )
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            if st.button(
                "💰 Preços da carteira",
                use_container_width=True,
                help="Atualiza preços só dos ativos com posição na carteira. Nunca toca a watchlist.",
            ):
                with st.spinner("Atualizando preços da carteira..."), session_scope() as db:
                    result = DataRefreshService(db).refresh_portfolio_prices(portfolio_id)
                clear_all_caches()
                st.session_state["_last_refresh_summary"] = ("prices", result)
                st.rerun()
        with col2:
            if st.button(
                "📊 Fundamentos da carteira",
                use_container_width=True,
                help="Coleta fundamentos e recomputa valuation, traps, LG Score e Conviction Score.",
            ):
                with (
                    st.spinner("Coletando fundamentos e recomputando análises..."),
                    session_scope() as db,
                ):
                    result = DataRefreshService(db).refresh_portfolio_fundamentals(portfolio_id)
                clear_all_caches()
                st.session_state["_last_refresh_summary"] = ("fundamentals", result)
                st.rerun()
        with col3:
            if st.button(
                "🔭 Dados da watchlist",
                use_container_width=True,
                help="Nunca cria posição nem altera o patrimônio — só atualiza os candidatos.",
            ):
                with st.spinner("Atualizando dados da watchlist..."), session_scope() as db:
                    result = DataRefreshService(db).refresh_watchlist_data(portfolio_id)
                clear_all_caches()
                st.session_state["_last_refresh_summary"] = ("watchlist", result)
                st.rerun()
        with col4:
            if st.button(
                "♻️ Atualizar tudo",
                use_container_width=True,
                type="primary",
                help="Carteira + watchlist completas. Pode demorar — pede confirmação.",
            ):
                st.session_state["confirm_refresh_all"] = True
                st.rerun()
        with col5:
            if st.button(
                "🧹 Limpar cache",
                use_container_width=True,
                help="Só invalida o cache e recarrega com os dados já salvos — não busca nada externo.",
            ):
                data_refresh_status_service.record_cache_cleared()
                clear_all_caches()
                st.rerun()

        if st.session_state.get("confirm_refresh_all"):
            st.warning(
                "Isso vai atualizar preços, fundamentos, valuation, traps e a watchlist "
                "inteira de uma vez — pode demorar bastante. Confirma?"
            )
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("✅ Confirmar atualização completa", use_container_width=True):
                    with (
                        st.spinner("Atualizando carteira e watchlist completas..."),
                        session_scope() as db,
                    ):
                        result = DataRefreshService(db).refresh_all_investment_data(portfolio_id)
                    clear_all_caches()
                    st.session_state["_last_refresh_summary"] = ("all", result)
                    st.session_state["confirm_refresh_all"] = False
                    st.rerun()
            with cancel_col:
                if st.button("Cancelar", use_container_width=True):
                    st.session_state["confirm_refresh_all"] = False
                    st.rerun()

        last_status = DataRefreshService.get_last_refresh_status()
        st.markdown("**Última atualização**")
        ts_cols = st.columns(5)
        ts_cols[0].caption(f"Preços: {_format_refresh_ts(last_status.prices_at)}")
        ts_cols[1].caption(f"Fundamentos: {_format_refresh_ts(last_status.fundamentals_at)}")
        ts_cols[2].caption(f"Watchlist: {_format_refresh_ts(last_status.watchlist_at)}")
        ts_cols[3].caption(f"Valuation: {_format_refresh_ts(last_status.valuation_at)}")
        ts_cols[4].caption(f"Trap Detection: {_format_refresh_ts(last_status.trap_detection_at)}")

        summary = st.session_state.get("_last_refresh_summary")
        if summary:
            kind, result = summary
            _render_refresh_summary(kind, result)


def render(portfolio_id: int) -> None:
    page_header(
        "Dashboard",
        "Visão geral da sua carteira, riscos, alocação e próximos passos.",
        icon="📊",
    )

    exchange_rate = fx_settings_service.get_usd_brl_rate()

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

    # Sprint 30 (Parte 3): os alertas não disparam mais na hora — são
    # coletados aqui e renderizados juntos na seção "Alertas", mais fácil
    # de escanear do que avisos espalhados pela tela inteira.
    alert_messages: list[tuple[str, str]] = []  # (kind, texto) — kind de alert_box

    automatic_weight = sum((p.weight for p in view.positions if p.price_source == "yahoo"), _ZERO)
    if automatic_weight < dq_thresholds.DATA_QUALITY_AUTOMATIC_WARN:
        alert_messages.append(
            (
                "warning",
                f"Apenas {format_pct(automatic_weight)} do patrimônio está com preço automático "
                "(Yahoo Finance) — o restante depende de preço manual ou estimado, o que reduz a "
                "confiabilidade dos números abaixo. Veja detalhes em Diagnóstico da Carteira.",
            )
        )

    largest = next((p for p in view.positions if p.ticker == view.largest_position_ticker), None)
    dominant = _dominant_group(view)
    best, worst = _best_and_worst_performers(view)
    international = _international_weight(view)

    # Movido para cima (era calculado só dentro de "Oportunidades & Riscos")
    # porque o hero e a seção "Decisão do mês" também precisam da melhor
    # oportunidade — mesma conta, um lugar só.
    scored_assets = [a for a in intelligence.assets if a.has_conviction_score]
    top_opportunities = sorted(
        [a for a in scored_assets if a.classification in ("strong_buy", "buy")],
        key=lambda a: a.conviction_score,
        reverse=True,
    )[:3]
    top_risks = sorted(
        [a for a in scored_assets if a.classification in ("avoid", "watch")],
        key=lambda a: a.conviction_score,
    )[:3]
    insufficient = [a for a in intelligence.assets if not a.has_conviction_score]

    hero_cards: list[MetricCardSpec] = [
        {
            "label": "Patrimônio total",
            "value": format_brl(view.total_converted_brl),
            "icon": "💰",
            "status": "neutral",
        },
        {
            "label": "Variação",
            "value": (
                format_pct(view.total_return_pct, signed=True)
                if view.total_return_pct is not None
                else "—"
            ),
            "icon": "📈",
            "status": (
                "positive"
                if view.total_return_pct is not None and view.total_return_pct >= _ZERO
                else "critical" if view.total_return_pct is not None else "muted"
            ),
        },
        {
            "label": "Exposição internacional",
            "value": format_pct(international),
            "icon": "🌎",
            "status": "neutral",
        },
        {
            "label": "Portfolio Health Score",
            "value": f"{float(health_result.overall_score):.0f}/100",
            "icon": "🩺",
            "delta": health_result.overall_classification.capitalize(),
            "status": _HEALTH_METRIC_STATUS.get(health_result.overall_classification, "muted"),
        },
        {
            "label": "Risco da carteira",
            "value": risk_result.overall_classification.capitalize(),
            "icon": "🎲",
            "status": _RISK_METRIC_STATUS.get(risk_result.overall_classification, "muted"),
        },
        {
            "label": "Próximo aporte sugerido",
            "value": top_opportunities[0].ticker if top_opportunities else "—",
            "icon": "➡️",
            "delta": (
                f"score {float(top_opportunities[0].conviction_score):.1f}"
                if top_opportunities
                else "simule em Aporte"
            ),
            "status": "positive" if top_opportunities else "muted",
        },
    ]
    metric_card_row(hero_cards)

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
    with section("Resumo Executivo", "📊"):
        render_kpi_grid(cards, columns=4)
        if view.is_multi_currency:
            st.caption(
                "Conversão aplicada apenas para exibição, com o câmbio manual configurado em "
                "Configurações. Decision Engine e LG Score continuam usando valores nominais "
                "por moeda, sem conversão."
            )

    with section(
        "Decisão do mês",
        "🎯",
        caption="Melhor oportunidade encontrada pelo LG Conviction Score v2 na carteira atual.",
    ):
        if top_opportunities:
            top = top_opportunities[0]
            st.markdown(
                f"{classification_badge_html(top.classification)} **{top.ticker}** é a "
                f"principal oportunidade agora, com score **{float(top.conviction_score):.1f}**.",
                unsafe_allow_html=True,
            )
        else:
            st.caption(
                "Nenhum ativo em 'Aportar'/'Candidato' no momento — isso não significa que não "
                "vale aportar, só que nenhum se destaca claramente pelo score atual."
            )
        if st.button("Simular aporte", type="primary"):
            st.info("Abra a tela **Aporte** no menu lateral para simular a distribuição sugerida.")

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
        tolerance_note = (
            f" · Tolerância declarada: **{risk_result.declared_risk_tolerance}**"
            if risk_result.declared_risk_tolerance
            else ""
        )
        st.markdown(
            f"**Risco medido:** {risk_badge_html(risk_result.overall_classification)}"
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
        # top_opportunities/top_risks/insufficient já calculados no topo de
        # render() — o hero e "Decisão do mês" também dependem deles.
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

    with section(
        "Alocação",
        "🧩",
        caption="Composição por classe, moeda e Brasil vs. exterior — e a distância até sua meta.",
    ):
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

        if (
            intelligence.allocation_drift.has_target
            and intelligence.allocation_drift.most_underweight_class
        ):
            st.info(
                f"Distância até a meta — classe mais abaixo do alvo: "
                f"**{intelligence.allocation_drift.most_underweight_class}** — candidata natural "
                "ao próximo aporte. Simule em **Aporte**."
            )
        else:
            st.caption(
                "Nenhuma meta de alocação configurada — defina uma em Configurações para o "
                "Dashboard e o Decision Engine 2.0 considerarem desvio de classe."
            )

    sync_status = DataRefreshService.get_last_refresh_status()
    freshest_sync = _freshest_refresh_label(sync_status)
    if freshest_sync == "nunca atualizado":
        alert_messages.append(
            ("info", "Seus dados nunca foram atualizados — abra 'Central de Dados' abaixo.")
        )

    insufficient_tickers = sorted(
        {a.ticker for a in insufficient} | set(data_quality.assets_insufficient_data)
    )
    if insufficient_tickers:
        alert_messages.append(
            (
                "warning",
                "Dados insuficientes para conviction/valuation confiáveis: "
                + ", ".join(insufficient_tickers),
            )
        )
    if view.manual_price_tickers:
        alert_messages.append(
            (
                "info",
                f"{len(view.manual_price_tickers)} ativo(s) com preço manual cadastrado — "
                "veja a lista completa em 'Atenção: preços manuais/estimados' abaixo.",
            )
        )
    if view.estimated_price_tickers:
        alert_messages.append(
            (
                "warning",
                f"{len(view.estimated_price_tickers)} ativo(s) sem cotação nenhuma, usando preço "
                "médio como estimativa temporária — veja a lista completa abaixo.",
            )
        )

    with section(
        "Alertas",
        "🚨",
        caption="Tudo que merece sua atenção agora, num só lugar.",
    ):
        if alert_messages:
            for kind, message in alert_messages:
                alert_box(kind, "Atenção" if kind != "info" else "Aviso", message)
        else:
            success_box("Tudo em ordem", "Nenhum alerta ativo no momento.")

        dq_col1, dq_col2, dq_col3 = st.columns(3)
        dq_col1.metric(
            "Carteira com preço automático", format_pct(data_quality.pct_price_automatic)
        )
        dq_col2.metric(
            "Com fundamentos coletados", format_pct(data_quality.pct_fundamentals_available)
        )
        dq_col3.metric("Com valuation calculável", format_pct(data_quality.pct_valuation_available))

    _render_data_refresh_center(portfolio_id)

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
