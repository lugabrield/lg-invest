"""Gráficos de concentração/risco (Sprint 11).

Usa os mesmos limiares do Diagnóstico da Carteira
(`engines/portfolio_diagnostics/thresholds.py`) para desenhar a linha
de referência — não inventa um novo critério só para o gráfico.
"""

from __future__ import annotations

import plotly.graph_objects as go

from backend.app.engines.portfolio_diagnostics import thresholds as t
from backend.app.schemas.dashboard_view import ConvertedPosition
from frontend.streamlit_app.charts._theme import apply_dark_layout
from frontend.streamlit_app.styles.theme import ALERT, ATTENTION, POSITIVE


def chart_concentration_by_asset(positions: list[ConvertedPosition], top_n: int = 15) -> go.Figure:
    """Peso de cada posição sobre o total, com linhas de referência de atenção/alerta."""
    ranked = sorted(positions, key=lambda p: p.weight, reverse=True)[:top_n]
    ranked = list(reversed(ranked))

    warn = float(t.SINGLE_POSITION_WARN) * 100
    alert = float(t.SINGLE_POSITION_ALERT) * 100

    def color_for_weight(weight_pct: float) -> str:
        if weight_pct >= alert:
            return ALERT
        if weight_pct >= warn:
            return ATTENTION
        return POSITIVE

    weights_pct = [float(p.weight) * 100 for p in ranked]
    colors = [color_for_weight(w) for w in weights_pct]

    fig = go.Figure(
        data=[
            go.Bar(
                y=[p.ticker for p in ranked],
                x=weights_pct,
                orientation="h",
                marker_color=colors,
                text=[f"{w:.2f}%" for w in weights_pct],
                textposition="outside",
            )
        ]
    )
    fig.add_vline(x=warn, line_dash="dot", line_color=ATTENTION, annotation_text="atenção")
    fig.add_vline(x=alert, line_dash="dot", line_color=ALERT, annotation_text="alerta")
    fig.update_layout(
        title="Concentração por ativo (peso sobre o patrimônio convertido)",
        margin=dict(t=48, b=8, l=8, r=8),
        height=max(320, 28 * len(ranked)),
        xaxis_title="%",
    )
    return apply_dark_layout(fig)
