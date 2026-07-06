"""Gráficos de destaques/performance da carteira (Sprint 11).

Sem histórico simulado: tudo aqui é uma foto do estado atual das
posições (valor convertido e rentabilidade vs. preço médio), nunca uma
série temporal inventada.
"""

from __future__ import annotations

import plotly.graph_objects as go

from backend.app.schemas.dashboard_view import ConvertedPosition
from frontend.streamlit_app.charts._theme import apply_dark_layout
from frontend.streamlit_app.styles.theme import NEGATIVE, POSITIVE, PRIMARY


def chart_top_positions(positions: list[ConvertedPosition], top_n: int = 10) -> go.Figure:
    """Top N maiores posições por valor convertido em BRL."""
    ranked = sorted(positions, key=lambda p: p.position_value_brl, reverse=True)[:top_n]
    ranked = list(reversed(ranked))  # maior no topo da barra horizontal
    fig = go.Figure(
        data=[
            go.Bar(
                y=[p.ticker for p in ranked],
                x=[float(p.position_value_brl) for p in ranked],
                orientation="h",
                marker_color=PRIMARY,
                text=[f"R$ {float(p.position_value_brl):,.0f}" for p in ranked],
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title=f"Top {min(top_n, len(ranked))} maiores posições",
        margin=dict(t=48, b=8, l=8, r=8),
        height=max(320, 28 * len(ranked)),
        xaxis_title="R$",
    )
    return apply_dark_layout(fig)


def chart_return_by_asset(positions: list[ConvertedPosition]) -> go.Figure:
    """Rentabilidade por ativo (vs. preço médio). Exclui posições com preço estimado
    (sem cotação real, retorno seria artificial)."""
    ranked = [p for p in positions if p.return_pct is not None and not p.is_price_estimated]
    ranked.sort(key=lambda p: p.return_pct, reverse=True)
    colors = [POSITIVE if p.return_pct >= 0 else NEGATIVE for p in ranked]
    fig = go.Figure(
        data=[
            go.Bar(
                y=[p.ticker for p in ranked],
                x=[float(p.return_pct) * 100 for p in ranked],
                orientation="h",
                marker_color=colors,
                text=[f"{float(p.return_pct) * 100:.2f}%" for p in ranked],
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title="Rentabilidade por ativo (vs. preço médio)",
        margin=dict(t=48, b=8, l=8, r=8),
        height=max(320, 28 * len(ranked)),
        xaxis_title="%",
    )
    return apply_dark_layout(fig)
