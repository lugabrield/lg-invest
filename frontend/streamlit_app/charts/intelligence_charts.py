"""Gráficos do painel de Inteligência (Sprint 19).

Foto do estado atual do LG Conviction Score v2 por ativo — sem série
temporal simulada, apenas o que `intelligence_dashboard_service` já
calculou.
"""

from __future__ import annotations

import plotly.graph_objects as go

from backend.app.schemas.intelligence_dashboard import AssetIntelligence
from frontend.streamlit_app.styles.theme import NEGATIVE, POSITIVE

_NEUTRAL = "#8A93A3"


def chart_conviction_by_asset(assets: list[AssetIntelligence]) -> go.Figure:
    """Conviction Score por ativo, ordenado do maior para o menor."""
    scored = [a for a in assets if a.has_conviction_score]
    scored.sort(key=lambda a: a.conviction_score, reverse=True)
    scored = list(reversed(scored))  # maior no topo da barra horizontal

    colors = []
    for a in scored:
        score = float(a.conviction_score)
        if score >= 70:
            colors.append(POSITIVE)
        elif score >= 40:
            colors.append(_NEUTRAL)
        else:
            colors.append(NEGATIVE)

    fig = go.Figure(
        data=[
            go.Bar(
                y=[a.ticker for a in scored],
                x=[float(a.conviction_score) for a in scored],
                orientation="h",
                marker_color=colors,
                text=[f"{float(a.conviction_score):.1f}" for a in scored],
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title="LG Conviction Score por ativo",
        margin=dict(t=48, b=8, l=8, r=8),
        height=max(320, 28 * len(scored)),
        xaxis_title="Score (0-100)",
        xaxis_range=[0, 105],
    )
    return fig
