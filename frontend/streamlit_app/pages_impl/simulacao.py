"""Tela Simulação: Monte Carlo Simulation Engine (Sprint 24, Fase 5/9).

Consome o `SimulationService`, que resolve o valor atual da carteira e as
premissas de retorno/volatilidade por classe (editáveis em
Configurações) e roda a simulação pura. Nenhum cálculo financeiro vive
nesta tela — só formata e desenha o que a engine já calculou.

Isto é uma ferramenta de projeção probabilística, não uma previsão real
de mercado nem uma recomendação financeira — o aviso fica sempre visível
no topo da tela.
"""

from __future__ import annotations

from decimal import Decimal

import streamlit as st

from backend.app.services.simulation_service import SimulationService
from frontend.streamlit_app.charts.simulation_charts import chart_simulation_percentiles
from frontend.streamlit_app.components.patterns import (
    MetricCardSpec,
    info_box,
    metric_card_row,
    page_header,
)
from frontend.streamlit_app.components.sections import section
from frontend.streamlit_app.db import session_scope
from frontend.streamlit_app.formatting import format_brl, format_pct


def render(portfolio_id: int) -> None:
    page_header(
        "Simulação",
        "Projeção probabilística de Monte Carlo para sua carteira.",
        icon="🎲",
    )
    info_box(
        "Isto não é uma previsão",
        "É uma projeção probabilística — não é uma previsão real de mercado nem "
        "recomendação financeira. As premissas de retorno/volatilidade por classe são "
        "editáveis em Configurações, e o resultado muda conforme essas hipóteses.",
    )

    col_a, col_b, col_c = st.columns(3)
    monthly_contribution = col_a.number_input(
        "Aporte mensal presumido (R$)", min_value=0.0, value=1000.0, step=100.0
    )
    horizon_years = col_b.number_input(
        "Horizonte (anos)", min_value=1, max_value=100, value=20, step=1
    )
    num_simulations = col_c.number_input(
        "Nº de simulações", min_value=100, max_value=20000, value=2000, step=100
    )
    reproducible = st.checkbox(
        "Usar semente fixa (resultado reproduzível)",
        value=False,
        help="Sem isso, cada execução sorteia trajetórias diferentes.",
    )

    if not st.button("Rodar simulação"):
        return

    with session_scope() as db:
        result = SimulationService(db).run_portfolio_simulation(
            portfolio_id,
            monthly_contribution=Decimal(str(monthly_contribution)),
            horizon_years=int(horizon_years),
            num_simulations=int(num_simulations),
            seed=42 if reproducible else None,
        )

    with section("Resultado da simulação", "🎲"):
        loss_status = (
            "critical"
            if result.probability_of_loss >= Decimal("0.30")
            else "attention" if result.probability_of_loss >= Decimal("0.10") else "positive"
        )
        cards: list[MetricCardSpec] = [
            {
                "label": "Valor inicial",
                "value": format_brl(result.initial_value),
                "icon": "💰",
                "status": "neutral",
            },
            {
                "label": "Total aportado (horizonte)",
                "value": format_brl(result.total_contributed),
                "icon": "➕",
                "status": "neutral",
            },
            {
                "label": "Mediana projetada",
                "value": format_brl(result.median_final_value),
                "icon": "📊",
                "status": "positive",
            },
            {
                "label": "Probabilidade de perda",
                "value": format_pct(result.probability_of_loss),
                "icon": "⚠️",
                "status": loss_status,
            },
        ]
        metric_card_row(cards)
        st.caption(
            "Probabilidade de perda: fração das simulações que terminaram abaixo do total "
            "efetivamente aportado."
        )

        if result.num_simulations > 0:
            st.plotly_chart(
                chart_simulation_percentiles(result.percentiles), use_container_width=True
            )
            st.dataframe(
                [
                    {"Percentil": p, "Valor projetado": format_brl(v)}
                    for p, v in result.percentiles.items()
                ],
                width="stretch",
                hide_index=True,
            )

        with st.expander("Premissas e simplificações usadas"):
            for reason in result.reasons:
                st.caption(f"· {reason}")
        for warning in result.warnings:
            st.warning(warning)
