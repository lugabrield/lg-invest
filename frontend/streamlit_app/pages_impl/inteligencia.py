"""Tela Inteligência: LG Conviction Score v2 + alocação-alvo por classe (Sprint 19).

Consome `intelligence_dashboard_service`, que só compõe o que o
Conviction Score Engine (Sprint 17) e o Target Allocation Engine
(Sprint 17) já calcularam — nenhuma regra nova de decisão vive aqui.
Ativos sem Conviction Score calculável aparecem com o motivo explícito,
nunca com um valor inventado (Volume 18 §8).
"""

from __future__ import annotations

import streamlit as st

from backend.app.schemas.intelligence_dashboard import AssetIntelligence
from backend.app.services.intelligence_dashboard_service import build_intelligence_dashboard
from frontend.streamlit_app.charts.intelligence_charts import chart_conviction_by_asset
from frontend.streamlit_app.components.cards import KpiCard, render_kpi_grid
from frontend.streamlit_app.components.sections import section
from frontend.streamlit_app.db import session_scope
from frontend.streamlit_app.formatting import format_pct

_CLASSIFICATION_ORDER = ["Exceptional", "Excellent", "Good", "Neutral", "Weak", "Avoid"]


def _asset_row(a: AssetIntelligence) -> dict:
    return {
        "Ticker": a.ticker,
        "Classe": a.asset_class,
        "Peso atual": format_pct(a.current_weight),
        "Conviction Score": f"{float(a.conviction_score):.1f}" if a.has_conviction_score else "—",
        "Classificação": a.classification or "Indisponível",
        "Confiança": a.confidence_label or "—",
    }


def render(portfolio_id: int) -> None:
    st.title("Inteligência")
    st.caption(
        "LG Conviction Score v2 por ativo e alocação-alvo por classe — a mesma base que o "
        "Decision Engine 2.0 usa para recomendar aportes (tela Aporte)."
    )

    with session_scope() as db:
        view = build_intelligence_dashboard(db, portfolio_id)

    if not view.assets:
        st.info("Carteira vazia. Importe posições na tela Carteira.")
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
    with section("Visão Geral", "🧠"):
        render_kpi_grid(cards, columns=4)
        if view.coverage_pct < 1:
            st.caption(
                "Ativos sem histórico de preço suficiente ficam de fora da cobertura acima — "
                "veja o motivo na tabela abaixo, nunca é um score inventado."
            )

    with section("Conviction Score por ativo", "📊"):
        st.plotly_chart(chart_conviction_by_asset(view.assets), use_container_width=True)

        if view.classification_counts:
            counts_line = "  ·  ".join(
                f"{label}: {view.classification_counts[label]}"
                for label in _CLASSIFICATION_ORDER
                if label in view.classification_counts
            )
            st.caption(counts_line)

        st.dataframe(
            [_asset_row(a) for a in view.assets],
            width="stretch",
            hide_index=True,
        )

        with st.expander("Justificativa por pilar (ativo a ativo)"):
            for a in view.assets:
                if not a.has_conviction_score:
                    st.markdown(f"**{a.ticker}** — {a.unavailable_reason}")
                    continue
                st.markdown(
                    f"**{a.ticker}** — Conviction Score {float(a.conviction_score):.1f} "
                    f"({a.classification}, confiança {a.confidence_label})"
                )
                for pillar in a.explanation:
                    st.caption(
                        f"· {pillar.name}: {float(pillar.score):.1f} — {'; '.join(pillar.reasons)}"
                    )

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
