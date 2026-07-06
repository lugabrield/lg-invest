"""Gráfico do Monte Carlo Simulation Engine (Sprint 24, Fase 9).

A engine devolve só os percentis do valor final (não uma trajetória
ano-a-ano), então o gráfico mostra a distribuição do valor final como
uma faixa horizontal: p10–p90 (faixa clara) com p25–p75 destacado
(faixa cheia) e a mediana (p50) marcada.
"""

from __future__ import annotations

from decimal import Decimal

import plotly.graph_objects as go

from frontend.streamlit_app.charts._theme import apply_dark_layout
from frontend.streamlit_app.styles.theme import NEUTRAL, POSITIVE, PRIMARY


def chart_simulation_percentiles(percentiles: dict[str, Decimal]) -> go.Figure:
    p10 = float(percentiles["p10"])
    p25 = float(percentiles["p25"])
    p50 = float(percentiles["p50"])
    p75 = float(percentiles["p75"])
    p90 = float(percentiles["p90"])

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=[p90 - p10],
            y=["Patrimônio projetado"],
            base=[p10],
            orientation="h",
            marker_color=NEUTRAL,
            name="Faixa p10–p90",
            width=0.5,
        )
    )
    fig.add_trace(
        go.Bar(
            x=[p75 - p25],
            y=["Patrimônio projetado"],
            base=[p25],
            orientation="h",
            marker_color=PRIMARY,
            name="Faixa p25–p75",
            width=0.5,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[p50],
            y=["Patrimônio projetado"],
            mode="markers",
            marker=dict(color=POSITIVE, size=16, symbol="line-ns-open", line=dict(width=3)),
            name="Mediana (p50)",
        )
    )
    fig.update_layout(
        title="Distribuição do patrimônio projetado ao final do horizonte",
        barmode="overlay",
        xaxis_title="R$",
        height=220,
        margin=dict(t=48, b=8, l=8, r=8),
        showlegend=True,
    )
    return apply_dark_layout(fig)
