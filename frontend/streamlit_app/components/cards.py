"""Componentes de card reutilizáveis (Sprint 11).

Só renderização — nenhum cálculo aqui. Consome valores já formatados
(strings prontas) pelas telas, que por sua vez usam `formatting.py`.
"""

from __future__ import annotations

from typing import TypedDict

import streamlit as st

from backend.app.schemas.portfolio_diagnostics import DiagnosticInsight
from frontend.streamlit_app.styles.theme import SEVERITY_COLORS, SEVERITY_ICONS


class KpiCard(TypedDict, total=False):
    label: str
    value: str
    delta: str | None
    help: str | None


def render_kpi_grid(items: list[KpiCard], columns: int = 4) -> None:
    """Renderiza uma grade de `st.metric` em linhas de até `columns` cards."""
    for start in range(0, len(items), columns):
        row_items = items[start : start + columns]
        cols = st.columns(len(row_items))
        for col, item in zip(cols, row_items, strict=False):
            col.metric(
                item["label"],
                item["value"],
                delta=item.get("delta"),
                help=item.get("help"),
            )


def render_insight_list(insights: list[DiagnosticInsight]) -> None:
    """Renderiza os insights do Diagnóstico da Carteira como cartões coloridos por severidade."""
    if not insights:
        st.caption("Nenhum insight disponível ainda — importe posições para gerar o diagnóstico.")
        return
    for insight in insights:
        color = SEVERITY_COLORS.get(insight.severity, SEVERITY_COLORS["info"])
        icon = SEVERITY_ICONS.get(insight.severity, "ℹ️")
        # HTML montado numa única linha, sem indentação/quebra interna: uma
        # f-string multi-linha indentada (o formato antigo aqui) faz o
        # Markdown do Streamlit tratar o HTML como bloco de código literal
        # em vez de renderizar — mesmo com unsafe_allow_html=True. Ver a
        # nota equivalente em components/patterns.py (Sprint 31, bugfix de
        # HTML cru na interface).
        html = (
            f'<div class="lg-insight-card" style="--lg-insight-color: {color};">'
            f'<div class="lg-insight-title">{icon} {insight.title}</div>'
            f'<div class="lg-insight-message">{insight.message}</div>'
            "</div>"
        )
        st.markdown(html, unsafe_allow_html=True)
