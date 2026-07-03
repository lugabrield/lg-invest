"""Gráficos de composição da carteira (Sprint 11).

Usa os dados já calculados em `DashboardView` — nenhum gráfico aqui
inventa ou simula histórico. Plotly por causa dos donuts (Streamlit
nativo não tem gráfico de pizza/donut).
"""

from __future__ import annotations

from decimal import Decimal

import plotly.graph_objects as go

from backend.app.schemas.dashboard_view import ConvertedPosition, CurrencyExposure, DashboardView
from frontend.streamlit_app.styles.theme import CURRENCY_COLORS, GROUP_COLORS, color_for

_ZERO = Decimal("0")


def _donut(labels: list[str], values: list[float], colors: list[str], title: str) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.55,
                marker=dict(colors=colors),
                textinfo="label+percent",
                sort=False,
            )
        ]
    )
    fig.update_layout(
        title=title,
        margin=dict(t=48, b=8, l=8, r=8),
        legend=dict(orientation="h", yanchor="bottom", y=-0.15),
        height=340,
    )
    return fig


def chart_allocation_by_class(positions: list[ConvertedPosition]) -> go.Figure:
    """Alocação por classe de ativo (asset_class bruto: stock, fii, etf, reit, crypto, bond, cash)."""
    totals: dict[str, Decimal] = {}
    for p in positions:
        totals[p.asset_class] = totals.get(p.asset_class, _ZERO) + p.position_value_brl
    labels = list(totals.keys())
    values = [float(v) for v in totals.values()]
    colors = [color_for(label, GROUP_COLORS) for label in labels]
    return _donut(labels, values, colors, "Alocação por classe")


def chart_distribution_by_type(positions: list[ConvertedPosition]) -> go.Figure:
    """Distribuição pelos 7 grupos visuais (Ações BR, FIIs, Ações EUA, ETFs, REITs, Cripto, Renda Fixa)."""
    totals: dict[str, Decimal] = {}
    for p in positions:
        totals[p.group_label] = totals.get(p.group_label, _ZERO) + p.position_value_brl
    labels = list(totals.keys())
    values = [float(v) for v in totals.values()]
    colors = [color_for(label, GROUP_COLORS) for label in labels]
    return _donut(labels, values, colors, "Distribuição por tipo de ativo")


def chart_allocation_by_currency(currency_exposure: list[CurrencyExposure]) -> go.Figure:
    labels = [c.currency for c in currency_exposure]
    values = [float(c.value_brl) for c in currency_exposure]
    colors = [color_for(label, CURRENCY_COLORS) for label in labels]
    return _donut(labels, values, colors, "Exposição por moeda")


def chart_brazil_vs_international(currency_exposure: list[CurrencyExposure]) -> go.Figure:
    """Brasil (BRL) x Exterior (demais moedas), como barra horizontal simples."""
    brazil_value = sum((c.value_brl for c in currency_exposure if c.currency == "BRL"), _ZERO)
    international_value = sum(
        (c.value_brl for c in currency_exposure if c.currency != "BRL"), _ZERO
    )
    fig = go.Figure(
        data=[
            go.Bar(
                y=["Brasil x Exterior"],
                x=[float(brazil_value)],
                name="Brasil",
                orientation="h",
                marker_color=CURRENCY_COLORS["BRL"],
            ),
            go.Bar(
                y=["Brasil x Exterior"],
                x=[float(international_value)],
                name="Exterior",
                orientation="h",
                marker_color=CURRENCY_COLORS["USD"],
            ),
        ]
    )
    fig.update_layout(
        title="Brasil x Exterior (convertido)",
        barmode="stack",
        margin=dict(t=48, b=8, l=8, r=8),
        height=180,
        legend=dict(orientation="h", yanchor="bottom", y=-0.4),
        xaxis_title="R$",
    )
    return fig


def chart_brl_usd_comparison(view: DashboardView) -> go.Figure:
    """Compara patrimônio nominal em BRL x patrimônio em USD já convertido para BRL."""
    usd_converted = view.total_converted_brl - view.total_brl
    fig = go.Figure(
        data=[
            go.Bar(
                x=["Patrimônio em BRL", "Patrimônio em USD (convertido)"],
                y=[float(view.total_brl), float(usd_converted)],
                marker_color=[CURRENCY_COLORS["BRL"], CURRENCY_COLORS["USD"]],
                text=[f"R$ {float(view.total_brl):,.0f}", f"R$ {float(usd_converted):,.0f}"],
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title="Patrimônio convertido em BRL, por moeda de origem",
        margin=dict(t=48, b=8, l=8, r=8),
        height=320,
        yaxis_title="R$",
        showlegend=False,
    )
    return fig
