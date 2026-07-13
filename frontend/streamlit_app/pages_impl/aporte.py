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
from frontend.streamlit_app.components.badges import badge_html
from frontend.streamlit_app.components.patterns import (
    empty_state,
    page_header,
    recommendation_card,
    warning_box,
)
from frontend.streamlit_app.components.sections import section
from frontend.streamlit_app.db import session_scope
from frontend.streamlit_app.formatting import format_brl, format_pct
from frontend.streamlit_app.styles.theme import ALERT, ATTENTION, INFO, NEUTRAL, POSITIVE, PRIMARY

# Sprint 25, Parte 4 (explicabilidade do Aporte v3): rótulos em português
# para `IgnoredItem.block_source` — mesmo vocabulário usado por
# `engines/decision/eligibility.py` e por `engines/target_allocation/
# precedence.py` (regra detalhada > política geral), só traduzido para
# exibição. `None` (chamador antigo sem essa informação) cai no "—".
_BLOCK_SOURCE_LABELS = {
    "bloqueio_manual": "Bloqueio manual",
    "sobreconcentracao": "Sobreconcentração",
    "regra_detalhada": "Regra detalhada (alocação-alvo)",
    "politica_geral": "Política geral de investimento",
}

# Sprint 29 (Post-Allocation Constraints): rótulos em português para
# `CappedDimensionResult.dimension_type` — mesmo vocabulário de
# `engines/decision/post_allocation.py::DIMENSION_LABELS`, só capitalizado
# para exibição em tabela.
DIMENSION_TYPE_LABELS = {
    "class": "Classe",
    "currency": "Moeda",
    "country": "País",
    "asset": "Ativo",
    "international": "Exposição internacional",
}


def _score_breakdown_chart(factors, ticker: str) -> go.Figure:
    """Gráfico de barras horizontal com a contribuição de cada fator para
    o score de compra (Sprint 25, Parte 4) — mesma decomposição já
    presente em `reasons`, só visual. Fatores negativos (ex.: ajuste por
    confiança do dado abaixo de 100%) aparecem na cor neutra."""
    labels = [f.label for f in factors]
    values = [float(f.contribution) for f in factors]
    colors = [PRIMARY if v >= 0 else NEUTRAL for v in values]
    fig = go.Figure(data=[go.Bar(y=labels, x=values, orientation="h", marker_color=colors)])
    fig.update_layout(
        title=f"Composição do score — {ticker}",
        margin=dict(t=48, b=8, l=8, r=8),
        height=max(200, 40 * len(labels)),
        xaxis_title="Contribuição para o score de compra",
    )
    return apply_dark_layout(fig)


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


def _render_item_card(i) -> None:
    """RecommendationCard por ativo (Sprint 30, Parte 4) — no lugar de uma
    linha de tabela. Motivo principal em destaque; motivos extras e o
    breakdown do score ficam num expander 'Ver detalhes técnicos' logo
    abaixo, sem virar um relatório gigante sem hierarquia."""
    badges_html = badge_html(f"LG Score {float(i.lg_score):.0f}", INFO)
    if i.conviction_score is not None:
        badges_html += badge_html(f"Conviction {float(i.conviction_score):.0f}", INFO)
    if i.item_confidence is not None:
        conf_pct = float(i.item_confidence) * 100
        conf_color = POSITIVE if conf_pct >= 80 else ATTENTION if conf_pct >= 50 else ALERT
        badges_html += badge_html(f"Confiança do dado {conf_pct:.0f}%", conf_color)
    tag_html = (
        badge_html("Novo candidato", ATTENTION)
        if i.is_new_from_watchlist
        else badge_html("Já tenho", POSITIVE)
    )
    reason = i.reasons[0] if i.reasons else "Sem motivo detalhado disponível."

    recommendation_card(
        ticker=i.ticker,
        amount=format_brl(i.amount),
        weight=format_pct(i.weight),
        reason=reason,
        badges_html=badges_html,
        tag_html=tag_html,
    )
    if i.watchlist_reason:
        st.caption(f"🆕 {i.watchlist_reason}")

    extra_reasons = i.reasons[1:]
    if extra_reasons or i.score_breakdown:
        with st.expander(f"Ver detalhes técnicos — {i.ticker}"):
            for r in extra_reasons:
                st.caption(f"· {r}")
            if i.score_breakdown:
                st.plotly_chart(
                    _score_breakdown_chart(i.score_breakdown, i.ticker),
                    use_container_width=True,
                )
                st.caption("Soma das contribuições = score de compra do ativo.")


def render(portfolio_id: int) -> None:
    page_header(
        "Aporte",
        "Simule aportes respeitando sua política de alocação.",
        icon="💰",
    )

    with session_scope() as db:
        tickers = [a.ticker for a in AssetRepository(db).list_all()]

    if not tickers:
        # Sprint 31, Parte 5: sem nenhum ativo cadastrado, "Gerar recomendação"
        # rodaria com uma lista de candidatos vazia — sem crash, mas mostrando
        # um resultado confuso (tudo zerado, sem nenhuma explicação). Corta
        # aqui com uma orientação clara, mesmo padrão de `empty_state()` já
        # usado nas outras telas.
        empty_state(
            "Nenhum ativo cadastrado ainda",
            "Cadastre ativos e importe sua carteira na tela Carteira antes de simular um "
            "aporte — sem ativos, não há nada para recomendar.",
            icon="💰",
        )
        return

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

    allow_watchlist = False
    if engine_version == "v3":
        allow_watchlist = st.checkbox(
            "Permitir ativos novos da watchlist",
            value=False,
            help=(
                "Quando marcado, o motor v3 também considera candidatos NOVOS "
                "(sem posição na carteira) que o Radar já classificou como "
                "'new_candidate' — nunca um ativo com dado frágil ou já bloqueado. "
                "Um ativo novo nunca recebe mais do que um teto reduzido do aporte "
                "(hoje 25%), e a recomendação nunca cria a posição sozinha: cabe a "
                "você decidir se e quando iniciar. Cadastre e avalie candidatos na "
                "tela Radar."
            ),
        )

    if not st.button("Gerar recomendação"):
        return
    if amount <= 0:
        st.error("O valor do aporte deve ser positivo.")
        return

    exchange_rate = fx_settings_service.get_usd_brl_rate()
    with session_scope() as db:
        view_before = build_dashboard_view(db, portfolio_id, exchange_rate)
        service = DecisionService(db)
        if engine_version == "v3":
            result = service.recommend_v3(
                portfolio_id,
                Decimal(str(amount)),
                blocked={t.upper() for t in blocked},
                persist=persist,
                allow_watchlist_candidates=allow_watchlist,
            )
        else:
            recommend_fn = {
                "v1": service.recommend,
                "v2": service.recommend_v2,
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
        held_items = [i for i in result.items if not i.is_new_from_watchlist]
        new_items = [i for i in result.items if i.is_new_from_watchlist]

        if new_items:
            # Separação visual pedida na Sprint 25, Parte 2.5 (e reforçada na
            # Sprint 30, Parte 4): nunca misturar "já tenho" com "candidato
            # novo" na mesma lista sem distinção — e nunca usar linguagem de
            # "compra garantida" para o candidato novo.
            with section("Recomendações principais", "📌"):
                if held_items:
                    for i in held_items:
                        _render_item_card(i)
                else:
                    st.caption("Nenhum ativo já existente na carteira entrou nesta recomendação.")

            with section("Novos candidatos (Watchlist)", "🆕"):
                st.caption(
                    "Estes ativos ainda não são posição na sua carteira. A recomendação "
                    "aqui é só para você **considerar iniciar uma posição pequena** — "
                    "nada é comprado ou registrado automaticamente."
                )
                for i in new_items:
                    _render_item_card(i)
        else:
            with section("Recomendações principais", "📥"):
                for i in result.items:
                    _render_item_card(i)

    for alert in result.alerts:
        warning_box("Atenção", alert)

    if result.capped_dimensions:
        # Sprint 29: dimensões cortadas pelo Post-Allocation Constraints
        # Engine porque o peso RESULTANTE pós-aporte ultrapassaria o
        # máximo configurado — nunca detectável só olhando o peso antes
        # do aporte (era exatamente o bug relatado: 97,23% em USD com
        # máximo de 60%). Fica visível mesmo quando toda a alocação de
        # uma dimensão foi zerada (`result.items` pode ficar vazio).
        with section("Limites pós-aporte atingidos", "🚧"):
            st.caption(
                "Estas dimensões ultrapassariam o limite máximo configurado se o aporte "
                "fosse distribuído sem ajuste. O valor foi cortado para respeitar o "
                "limite — o restante não foi forçado em outro lugar só para chegar em "
                "100% do aporte; ficou como saldo não alocado."
            )
            st.dataframe(
                [
                    {
                        "Dimensão": DIMENSION_TYPE_LABELS.get(cd.dimension_type, cd.dimension_type),
                        "Item": cd.dimension_key,
                        "Atual": format_pct(cd.weight_before),
                        "Depois do aporte": format_pct(cd.weight_after),
                        "Limite máximo": format_pct(cd.max_weight),
                        "Origem do limite": _BLOCK_SOURCE_LABELS.get(cd.source, cd.source),
                        "Status": (
                            "Limite atingido"
                            if cd.weight_after >= cd.max_weight
                            else "Dentro do limite"
                        ),
                    }
                    for cd in result.capped_dimensions
                ],
                width="stretch",
                hide_index=True,
            )

        unallocated = result.contribution_amount - result.allocated_amount
        if unallocated > 0:
            with section("Saldo não alocado", "💤"):
                col1, col2 = st.columns(2)
                col1.metric("Alocado", format_brl(result.allocated_amount))
                col2.metric("Não alocado", format_brl(unallocated))
                dimension_names = ", ".join(
                    sorted({cd.dimension_key for cd in result.capped_dimensions})
                )
                warning_box(
                    f"{format_brl(unallocated)} não foi alocado",
                    f"Sua política de alocação impediria ultrapassar o limite de "
                    f"{dimension_names}. Nenhuma venda é sugerida — considere uma entrada "
                    "gradual ou revisar os limites em Configurações.",
                )

    if result.ignored:
        with section("Ativos evitados", "🚫"):
            st.dataframe(
                [
                    {
                        "Ticker": ig.ticker,
                        "Origem do bloqueio": _BLOCK_SOURCE_LABELS.get(ig.block_source, "—"),
                        "Motivo": ig.reason,
                    }
                    for ig in result.ignored
                ],
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
