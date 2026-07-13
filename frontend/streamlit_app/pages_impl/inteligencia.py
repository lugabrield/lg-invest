"""Tela Inteligência: LG Conviction Score v2 + alocação-alvo por classe (Sprint 19; Sprint 21).

Consome `intelligence_dashboard_service`, que só compõe o que o
Conviction Score Engine (Sprint 17/21) e o Target Allocation Engine
(Sprint 17) já calcularam — nenhuma regra nova de decisão vive aqui.
Ativos sem Conviction Score calculável aparecem com o motivo explícito,
nunca com um valor inventado (Volume 18 §8).

Sprint 21: reformulação completa — de uma tabela+gráfico simples para
um painel de decisão organizado por classificação (Aportar/Candidato/
Manter/Monitorar/Evitar/Dados insuficientes), rankings por dimensão
(mais baratos, maior qualidade, maior crescimento, maior risco) e uma
seção "Por que esse ativo?" com diagnóstico completo por ativo.
"""

from __future__ import annotations

from decimal import Decimal

import streamlit as st

from backend.app.engines.growth.thresholds import APPLICABLE_CLASSES as GROWTH_APPLICABLE_CLASSES
from backend.app.engines.quality.thresholds import (
    APPLICABLE_CLASSES as QUALITY_APPLICABLE_CLASSES,
)
from backend.app.engines.valuation.thresholds import (
    APPLICABLE_CLASSES as VALUATION_APPLICABLE_CLASSES,
)
from backend.app.schemas.intelligence_dashboard import AssetIntelligence
from frontend.streamlit_app.cache import cached_intelligence_bundle
from frontend.streamlit_app.charts.intelligence_charts import chart_conviction_by_asset
from frontend.streamlit_app.components.badges import (
    classification_badge_html,
    confidence_badge_html,
)
from frontend.streamlit_app.components.cards import KpiCard, render_kpi_grid
from frontend.streamlit_app.components.patterns import empty_state, page_header
from frontend.streamlit_app.components.sections import section
from frontend.streamlit_app.formatting import format_brl, format_pct
from frontend.streamlit_app.styles.theme import classification_label_pt

# Classes de ativo onde cada pilar reflete uma medida REAL do engine
# correspondente, não o proxy de preço v1 usado como fallback quando o
# engine devolve "indeterminado"/"não aplicável" (ver
# `engines/ids_methodology/pillars.py`). Os rankings abaixo (Sprint 22)
# só consideram um ativo numa dimensão quando ela é aplicável à classe
# dele — caso contrário, um número alto ali é só o proxy de preço v1
# genérico (ex.: BTC-USD parecendo "barato" por valuation), não uma
# leitura real daquela dimensão. Risco não tem filtro: mesmo via
# fallback, o proxy v1 (volatilidade + drawdown) é direcionalmente
# plausível para qualquer classe, e cripto tem risco "alto" por
# política (não fallback) — ver docs/QUALITY_GROWTH_RISK_ENGINES.md.
_RANKING_APPLICABLE_CLASSES: dict[str, tuple[str, ...]] = {
    "valuation": VALUATION_APPLICABLE_CLASSES,
    "quality": QUALITY_APPLICABLE_CLASSES,
    "growth": GROWTH_APPLICABLE_CLASSES,
}

# Ordem de exibição dos buckets — do mais forte ao mais fraco, com
# "Dados insuficientes" separado no fim (não é um nível de convicção,
# é ausência de informação).
_BUCKET_ORDER = ["strong_buy", "buy", "hold", "watch", "avoid"]
_BUCKET_ICONS = {
    "strong_buy": "🟢",
    "buy": "🔵",
    "hold": "⚪",
    "watch": "🟡",
    "avoid": "🔴",
}

_PILLAR_LABELS_PT = {
    "quality": "Qualidade",
    "valuation": "Valuation",
    "growth": "Crescimento",
    "risk": "Risco",
    "capital_reinvestment": "Reinvestimento de capital",
}


def _bucket_assets(assets: list[AssetIntelligence]) -> dict[str, list[AssetIntelligence]]:
    buckets: dict[str, list[AssetIntelligence]] = {
        key: [] for key in [*_BUCKET_ORDER, "insufficient_data"]
    }
    for a in assets:
        if not a.has_conviction_score:
            buckets["insufficient_data"].append(a)
            continue
        key = a.classification if a.classification in buckets else "insufficient_data"
        buckets[key].append(a)
    for key, items in buckets.items():
        if key != "insufficient_data":
            items.sort(key=lambda a: a.conviction_score, reverse=True)
    return buckets


def _ranking(
    assets: list[AssetIntelligence], field: str, *, reverse: bool, top_n: int = 5
) -> list[AssetIntelligence]:
    """Ranking por pilar, restrito a ativos onde essa dimensão é uma medida real.

    Sprint 22: dois filtros de consistência financeira, além do já
    existente `is not None`:
    1. Exclui a classe do ativo quando ela não é aplicável ao pilar
       (`_RANKING_APPLICABLE_CLASSES`) — ex.: cripto nunca entra nos
       rankings de valuation, ETF nunca entra nos de crescimento.
    2. Exclui ativos com dados insuficientes (`insufficient_data` ou
       sem Conviction Score calculável) — um ativo sem confiança
       suficiente não deve aparecer como se fosse uma oportunidade ou
       risco forte.
    """
    applicable_classes = _RANKING_APPLICABLE_CLASSES.get(field)
    scored = [
        a
        for a in assets
        if getattr(a, field, None) is not None
        and a.has_conviction_score
        and a.classification != "insufficient_data"
        and (applicable_classes is None or a.asset_class in applicable_classes)
    ]
    scored.sort(key=lambda a: getattr(a, field), reverse=reverse)
    return scored[:top_n]


def _render_asset_line(a: AssetIntelligence, *, value_label: str, value: Decimal | None) -> None:
    value_str = f"{float(value):.1f}" if value is not None else "—"
    st.markdown(
        f"{classification_badge_html(a.classification or 'insufficient_data')} "
        f"**{a.ticker}** ({a.asset_class}) — {value_label}: {value_str}",
        unsafe_allow_html=True,
    )


def _why_this_asset(a: AssetIntelligence) -> None:
    st.markdown(
        f'<div class="lg-highlight-box">'
        f"<strong>{a.ticker}</strong> ({a.asset_class}) &nbsp; "
        f"{classification_badge_html(a.classification or 'insufficient_data')} "
        f"{confidence_badge_html(a.confidence_label) if a.confidence_label else ''}"
        f"</div>",
        unsafe_allow_html=True,
    )

    if not a.has_conviction_score:
        st.warning(a.unavailable_reason or "Conviction Score indisponível para este ativo.")
        return

    st.write(f"**Conviction Score:** {float(a.conviction_score):.1f} / 100")
    if a.recommendation_hint:
        st.info(a.recommendation_hint)

    st.markdown("**Pilares**")
    pillar_scores = {p.name: p for p in a.explanation}
    cols = st.columns(len(a.explanation)) if a.explanation else []
    for col, pillar in zip(cols, a.explanation, strict=False):
        col.metric(_PILLAR_LABELS_PT.get(pillar.name, pillar.name), f"{float(pillar.score):.1f}")

    with st.expander("Motivos por pilar", expanded=False):
        for pillar in a.explanation:
            st.markdown(f"**{_PILLAR_LABELS_PT.get(pillar.name, pillar.name)}**")
            for reason in pillar.reasons:
                st.caption(f"· {reason}")

    if pillar_scores:
        strongest = max(pillar_scores.values(), key=lambda p: p.score)
        weakest = min(pillar_scores.values(), key=lambda p: p.score)
        st.markdown("**O que moveria a nota**")
        st.caption(
            f"Pilar mais forte hoje: {_PILLAR_LABELS_PT.get(strongest.name, strongest.name)} "
            f"({float(strongest.score):.1f}) — perder força aqui é o que mais pioraria a nota."
        )
        st.caption(
            f"Pilar mais fraco hoje: {_PILLAR_LABELS_PT.get(weakest.name, weakest.name)} "
            f"({float(weakest.score):.1f}) — é o que, se melhorar, mais aumentaria a nota."
        )
        low_confidence_pillars = [
            _PILLAR_LABELS_PT.get(p.name, p.name)
            for p in a.explanation
            if p.confidence < Decimal("0.4")
        ]
        if low_confidence_pillars:
            st.caption(
                "Pilares com confiança baixa (mais fundamentos coletados melhorariam a "
                "precisão, não necessariamente a nota): " + ", ".join(low_confidence_pillars)
            )


def render(portfolio_id: int) -> None:
    page_header(
        "Inteligência",
        "LG Conviction Score v2 por ativo e alocação-alvo por classe — a mesma base que o "
        "Decision Engine 2.0 usa para recomendar aportes (tela Aporte).",
        icon="🧠",
    )

    view, income_result = cached_intelligence_bundle(portfolio_id)

    if not view.assets:
        empty_state(
            "Carteira vazia",
            "Importe posições na tela Carteira para ver a análise de convicção por ativo.",
            icon="🧠",
        )
        return

    cards: list[KpiCard] = [
        {
            "label": "Conviction Score médio",
            "value": (
                f"{float(view.average_conviction_score):.1f}"
                if view.average_conviction_score is not None
                else "—"
            ),
            "help": "Média simples entre os ativos com Conviction Score calculável.",
        },
        {
            "label": "Cobertura do score",
            "value": format_pct(view.coverage_pct),
            "help": "Fração do patrimônio com Conviction Score calculável (peso da carteira).",
        },
        {
            "label": "Maior convicção",
            "value": (
                f"{view.most_convicted.ticker} ({float(view.most_convicted.conviction_score):.1f})"
                if view.most_convicted
                else "—"
            ),
        },
        {
            "label": "Menor convicção",
            "value": (
                f"{view.least_convicted.ticker} ({float(view.least_convicted.conviction_score):.1f})"
                if view.least_convicted
                else "—"
            ),
        },
    ]
    with section("Resumo Executivo", "🧠"):
        render_kpi_grid(cards, columns=4)
        if view.coverage_pct < 1:
            st.caption(
                "Ativos sem histórico de preço suficiente ficam de fora da cobertura acima — "
                "veja o motivo na seção 'Dados insuficientes' abaixo, nunca é um score inventado."
            )
        st.plotly_chart(chart_conviction_by_asset(view.assets), use_container_width=True)

    buckets = _bucket_assets(view.assets)
    with section(
        "Classificação da carteira",
        "🗂️",
        caption="Mesma classificação usada pelo Decision Engine 2.0 na tela Aporte.",
    ):
        summary_line = "  ·  ".join(
            f"{_BUCKET_ICONS.get(key, '')} {classification_label_pt(key)}: {len(items)}"
            for key, items in buckets.items()
            if items
        )
        st.markdown(summary_line)

        for key in [*_BUCKET_ORDER, "insufficient_data"]:
            items = buckets[key]
            if not items:
                continue
            icon = _BUCKET_ICONS.get(key, "⬜")
            with st.expander(f"{icon} {classification_label_pt(key)} ({len(items)})"):
                for a in items:
                    if key == "insufficient_data":
                        st.markdown(f"**{a.ticker}** — {a.unavailable_reason}")
                    else:
                        st.markdown(
                            f"**{a.ticker}** ({a.asset_class}) — score "
                            f"{float(a.conviction_score):.1f} · peso {format_pct(a.current_weight)}"
                        )
                        if a.explanation:
                            top_reason = (
                                a.explanation[0].reasons[0] if a.explanation[0].reasons else ""
                            )
                            if top_reason:
                                st.caption(f"· {top_reason}")

    with section(
        "Rankings por dimensão",
        "📈",
        caption=(
            "Baseado nos pilares do Conviction Score v2. Cripto, ETF e renda fixa não entram "
            "nos rankings de valuation/qualidade/crescimento — para essas classes essas "
            "dimensões não são medidas reais (ver 'Por que esse ativo?' para o motivo "
            "específico de cada uma). Ativos com dados insuficientes também ficam de fora, "
            "para não parecerem oportunidades."
        ),
    ):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Mais baratos** (valuation)")
            for a in _ranking(view.assets, "valuation", reverse=True, top_n=5):
                _render_asset_line(a, value_label="valuation", value=a.valuation)
            st.caption(
                "Nota alta = 'barato' na classificação de múltiplos (Valuation Engine v1). "
                "Não é um valor justo numérico (fair value) — v1 não calcula range de preço "
                "justo, só classifica caro/neutro/barato por múltiplos relativos. Só ações, "
                "FIIs e REITs entram aqui — cripto/ETF/renda fixa não têm valuation por "
                "múltiplos aplicável."
            )
        with col2:
            st.markdown("**Maior qualidade**")
            for a in _ranking(view.assets, "quality", reverse=True, top_n=5):
                _render_asset_line(a, value_label="qualidade", value=a.quality)
            st.caption("Só ações e REITs — Quality Engine ainda não cobre as demais classes.")
        with col3:
            st.markdown("**Maior crescimento**")
            for a in _ranking(view.assets, "growth", reverse=True, top_n=5):
                _render_asset_line(a, value_label="crescimento", value=a.growth)
            st.caption("Só ações e REITs — CAGR de receita/lucro não se aplica às demais classes.")

        col4, col5 = st.columns(2)
        with col4:
            st.markdown("**Mais caros** (evitar aporte por valuation)")
            for a in _ranking(view.assets, "valuation", reverse=False, top_n=5):
                _render_asset_line(a, value_label="valuation", value=a.valuation)
        with col5:
            st.markdown("**Maior risco**")
            for a in _ranking(view.assets, "risk", reverse=False, top_n=5):
                _render_asset_line(a, value_label="risco (nota baixa = risco alto)", value=a.risk)

    with section(
        "Por que esse ativo?", "🔍", caption="Diagnóstico completo por ativo selecionado."
    ):
        tickers = [a.ticker for a in view.assets]
        selected = st.selectbox("Selecione um ativo", tickers)
        chosen = next((a for a in view.assets if a.ticker == selected), None)
        if chosen is not None:
            _why_this_asset(chosen)

    with section(
        "Alocação-alvo por classe",
        "🎯",
        caption="Configurada em Configurações. Sem meta configurada, nenhum desvio é mostrado.",
    ):
        if not view.allocation_drift.has_target:
            st.info(
                view.allocation_drift.reason
                or "Nenhuma meta de alocação configurada ainda — configure em Configurações."
            )
        else:
            st.dataframe(
                [
                    {
                        "Classe": c.asset_class,
                        "Atual": format_pct(c.current_pct),
                        "Meta": format_pct(c.target_pct),
                        "Desvio": format_pct(c.drift_pct, signed=True),
                        "Status": c.status,
                    }
                    for c in view.allocation_drift.classes
                ],
                width="stretch",
                hide_index=True,
            )
            if view.allocation_drift.most_underweight_class:
                st.caption(
                    "Classe mais subalocada: "
                    f"**{view.allocation_drift.most_underweight_class}** — candidata natural ao "
                    "próximo aporte (veja a tela Aporte com Decision Engine 2.0)."
                )

    with section(
        "Renda de Proventos",
        "💰",
        caption="Tendência agregada (Análise mensal) e renda por ativo (calendário) vêm de "
        "fontes diferentes e nunca são somadas entre si (Fase 7).",
    ):
        trend = income_result.trend
        col1, col2, col3 = st.columns(3)
        col1.metric("Renda últimos 12 meses", format_brl(trend.ttm_total))
        col2.metric(
            "Crescimento vs. período anterior",
            format_pct(trend.growth_pct, signed=True) if trend.growth_pct is not None else "—",
        )
        col3.metric("Projeção próximos 12 meses", format_brl(trend.projected_next_12_months))

        breakdown = income_result.breakdown
        if breakdown.rows:
            st.markdown(
                "**Yield on cost por ativo** (renda / custo de aquisição, não sobre o preço "
                "de mercado atual)"
            )
            st.dataframe(
                [
                    {
                        "Ticker": r.ticker,
                        "Renda (12m)": format_brl(r.ttm_income),
                        "Custo de aquisição": (
                            format_brl(r.cost_basis) if r.cost_basis is not None else "—"
                        ),
                        "Yield on cost": (
                            format_pct(r.yield_on_cost) if r.yield_on_cost is not None else "—"
                        ),
                    }
                    for r in breakdown.rows
                ],
                width="stretch",
                hide_index=True,
            )
            if breakdown.portfolio_yield_on_cost is not None:
                st.caption(
                    f"Yield on cost da carteira: {format_pct(breakdown.portfolio_yield_on_cost)}"
                )
        else:
            st.caption("Nenhum evento de renda por ativo registrado ainda para esta carteira.")

        for warning in income_result.warnings:
            st.caption(f"⚠️ {warning}")
