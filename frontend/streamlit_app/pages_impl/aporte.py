"""Tela Aporte: informa um valor e recebe a recomendação de distribuição.

Consome o DecisionService (Decision Engine, inalterado) e o
allocation_projection_service (camada de apresentação que só explica
como os pesos mudariam se a recomendação fosse aplicada — não decide
nada). Nenhuma regra de decisão vive aqui.
"""

from __future__ import annotations

from decimal import Decimal

import plotly.graph_objects as go
import streamlit as st

from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.schemas.allocation_projection import WeightComparison
from backend.app.services import fx_settings_service
from backend.app.services.allocation_projection_service import build_allocation_projection
from backend.app.services.dashboard_view_service import build_dashboard_view
from backend.app.services.decision_service import DecisionService
from frontend.streamlit_app.components.sections import section
from frontend.streamlit_app.db import session_scope
from frontend.streamlit_app.formatting import format_brl, format_pct


def _before_after_chart(comparisons: list[WeightComparison], title: str) -> go.Figure:
    labels = [c.label for c in comparisons]
    fig = go.Figure(
        data=[
            go.Bar(
                name="Antes",
                y=labels,
                x=[float(c.weight_before) * 100 for c in comparisons],
                orientation="h",
                marker_color="#8A93A3",
            ),
            go.Bar(
                name="Depois",
                y=labels,
                x=[float(c.weight_after) * 100 for c in comparisons],
                orientation="h",
                marker_color="#1F6FEB",
            ),
        ]
    )
    fig.update_layout(
        title=title,
        barmode="group",
        margin=dict(t=48, b=8, l=8, r=8),
        height=max(280, 40 * len(labels)),
        xaxis_title="%",
    )
    return fig


def render(portfolio_id: int) -> None:
    st.title("Aporte")
    st.caption(
        "Informe o valor do aporte e veja a distribuição sugerida, o motivo de cada escolha "
        "e como sua carteira ficaria depois."
    )

    with session_scope() as db:
        tickers = [a.ticker for a in AssetRepository(db).list_all()]

    amount = st.number_input("Valor do aporte (R$)", min_value=0.0, value=1000.0, step=100.0)
    blocked = st.multiselect("Ativos bloqueados (opcional)", tickers)
    use_v2 = st.checkbox(
        "Usar Decision Engine 2.0 (LG Conviction Score + alocação-alvo)",
        value=False,
        help=(
            "v2 prioriza o LG Conviction Score (Sprint 17) no lugar do LG Score puro quando "
            "calculável, e dá bônus a classes subalocadas em relação à meta configurada em "
            "Configurações. Sem meta configurada, o bônus de classe não se aplica a nenhum "
            "ativo. v1 (padrão) continua disponível e inalterado."
        ),
    )
    persist = st.checkbox("Salvar recomendação (auditoria)", value=True)

    if not st.button("Gerar recomendação"):
        return
    if amount <= 0:
        st.error("O valor do aporte deve ser positivo.")
        return

    exchange_rate = fx_settings_service.get_usd_brl_rate()
    with session_scope() as db:
        view_before = build_dashboard_view(db, portfolio_id, exchange_rate)
        service = DecisionService(db)
        recommend_fn = service.recommend_v2 if use_v2 else service.recommend
        result = recommend_fn(
            portfolio_id,
            Decimal(str(amount)),
            blocked={t.upper() for t in blocked},
            persist=persist,
        )

    with section("Resultado da recomendação", "🧭"):
        st.write(result.explanation)
        col1, col2 = st.columns(2)
        col1.metric("Alocado", format_brl(result.allocated_amount))
        col2.metric("Confiança", result.confidence_label)
        if result.allocated_amount < Decimal(str(amount)):
            st.caption(
                "O Decision Engine ainda tem alcance limitado no MVP: nem todo o valor "
                "informado necessariamente é distribuído — veja 'Ativos ignorados' abaixo."
            )

    if result.items:
        with section("Distribuição sugerida", "📥"):
            st.dataframe(
                [
                    {
                        "Ticker": i.ticker,
                        "Valor": format_brl(i.amount),
                        "% do aporte": format_pct(i.weight),
                        "Score compra": f"{float(i.buy_score):.2f}",
                        "LG Score": f"{float(i.lg_score):.1f}",
                        **(
                            {
                                "Conviction Score": (
                                    f"{float(i.conviction_score):.1f}"
                                    if i.conviction_score is not None
                                    else "—"
                                )
                            }
                            if use_v2
                            else {}
                        ),
                    }
                    for i in result.items
                ],
                width="stretch",
                hide_index=True,
            )
            with st.expander("Justificativa por ativo"):
                for i in result.items:
                    st.markdown(f"**{i.ticker}** — {format_brl(i.amount)}")
                    for reason in i.reasons:
                        st.caption(f"· {reason}")

    for alert in result.alerts:
        st.warning(alert)

    if result.ignored:
        with section("Ativos evitados", "🚫"):
            st.dataframe(
                [{"Ticker": ig.ticker, "Motivo": ig.reason} for ig in result.ignored],
                width="stretch",
                hide_index=True,
            )

    if result.items:
        projection = build_allocation_projection(view_before, result)
        with section("Como a carteira ficaria depois", "🔄"):
            col1, col2 = st.columns(2)
            col1.metric("Patrimônio antes", format_brl(projection.total_before_brl))
            col2.metric("Patrimônio depois", format_brl(projection.total_after_brl))

            st.plotly_chart(
                _before_after_chart(projection.by_group, "Peso por classe: antes x depois"),
                use_container_width=True,
            )
            st.plotly_chart(
                _before_after_chart(projection.by_currency, "Peso por moeda: antes x depois"),
                use_container_width=True,
            )

            st.caption(
                "Simplificação: o valor do aporte é somado ao valor já convertido da posição "
                "recomendada — não simula custos de câmbio nem a compra em moeda estrangeira."
            )
