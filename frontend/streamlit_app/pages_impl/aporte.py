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
from frontend.streamlit_app.charts._theme import apply_dark_layout
from frontend.streamlit_app.components.sections import section
from frontend.streamlit_app.db import session_scope
from frontend.streamlit_app.formatting import format_brl, format_pct
from frontend.streamlit_app.styles.theme import NEUTRAL, PRIMARY


def _before_after_chart(comparisons: list[WeightComparison], title: str) -> go.Figure:
    labels = [c.label for c in comparisons]
    fig = go.Figure(
        data=[
            go.Bar(
                name="Antes",
                y=labels,
                x=[float(c.weight_before) * 100 for c in comparisons],
                orientation="h",
                marker_color=NEUTRAL,
            ),
            go.Bar(
                name="Depois",
                y=labels,
                x=[float(c.weight_after) * 100 for c in comparisons],
                orientation="h",
                marker_color=PRIMARY,
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
    return apply_dark_layout(fig)


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
    engine_version = st.radio(
        "Motor de recomendação",
        options=["v1", "v2", "v3"],
        index=0,
        horizontal=True,
        help=(
            "v1: LG Score + gap de alocação por classe + concentração (padrão, inalterado). "
            "v2: prioriza o LG Conviction Score quando calculável, com bônus por classe "
            "subalocada em relação à meta configurada em Configurações. "
            "v3 (Fase 4): score multi-fator (fundamentos + alocação-alvo multi-dimensão + "
            "concentração + internacionalização, escalado pela confiança do dado) e respeita "
            "os bloqueios da Política de Investimento e da Alocação-alvo detalhada — nenhuma "
            "versão jamais recomenda venda, apenas pausa aporte."
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
        recommend_fn = {
            "v1": service.recommend,
            "v2": service.recommend_v2,
            "v3": service.recommend_v3,
        }[engine_version]
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
                            if engine_version in ("v2", "v3")
                            else {}
                        ),
                        "Confiança do dado": (
                            f"{float(i.item_confidence) * 100:.0f}%"
                            if i.item_confidence is not None
                            else "—"
                        ),
                    }
                    for i in result.items
                ],
                width="stretch",
                hide_index=True,
            )
            with st.expander("Justificativa por ativo"):
                for i in result.items:
                    confidence_note = (
                        f" (confiança do dado: {float(i.item_confidence) * 100:.0f}%)"
                        if i.item_confidence is not None
                        else ""
                    )
                    st.markdown(f"**{i.ticker}** — {format_brl(i.amount)}{confidence_note}")
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

            col3, col4 = st.columns(2)
            hhi_delta = float(
                projection.concentration_hhi_after - projection.concentration_hhi_before
            )
            col3.metric(
                "Concentração (HHI)",
                f"{float(projection.concentration_hhi_after):.3f}",
                delta=f"{hhi_delta:+.3f}",
                delta_color="inverse",
                help="Índice de Herfindahl-Hirschman: quanto menor, mais diversificada a "
                "carteira. Delta negativo = aporte reduziu a concentração.",
            )
            intl_delta = float(
                projection.international_weight_after - projection.international_weight_before
            )
            col4.metric(
                "Exposição internacional",
                format_pct(projection.international_weight_after),
                delta=f"{intl_delta * 100:+.2f} p.p.",
                help="Fração do patrimônio em moedas diferentes de BRL, antes x depois do aporte.",
            )

            st.plotly_chart(
                _before_after_chart(projection.by_group, "Peso por classe: antes x depois"),
                use_container_width=True,
            )
