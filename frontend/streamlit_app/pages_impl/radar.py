"""Tela Radar: Watchlist de ativos candidatos + comparação com a carteira
atual (Sprint 25, Parte 2.6).

Consome WatchlistService (CRUD + coleta de dados) e RadarService
(classificação pura, sem efeitos colaterais). Esta tela NUNCA cria uma
`Position` nem altera o patrimônio calculado pelo Portfolio Engine —
ela só cadastra candidatos e mostra como eles se comparam à carteira
atual. Nenhuma ação aqui é uma ordem de compra.
"""

from __future__ import annotations

from collections import Counter

import streamlit as st

from backend.app.infrastructure.database.models.asset import ASSET_CLASSES
from backend.app.infrastructure.database.models.watchlist_asset import WATCHLIST_STATUSES
from backend.app.schemas.watchlist import WatchlistAssetCreate
from backend.app.services.radar_service import RadarService
from backend.app.services.watchlist_service import WatchlistService
from frontend.streamlit_app.components.sections import section
from frontend.streamlit_app.db import session_scope

_CLASSIFICATION_LABELS: dict[str, str] = {
    "current_holding_candidate": "Ja tenho - bom para novo aporte",
    "new_candidate": "Novo candidato",
    "monitor": "Monitorar",
    "avoid": "Evitar (candidato novo)",
    "blocked": "Bloqueado",
    "insufficient_data": "Dado insuficiente",
}

_CLASSIFICATION_ORDER = (
    "current_holding_candidate",
    "new_candidate",
    "monitor",
    "avoid",
    "blocked",
    "insufficient_data",
)


def render(portfolio_id: int) -> None:
    st.title("Radar")
    st.caption(
        "Cadastre ativos candidatos e veja como eles se comparam a sua carteira atual. "
        "A Watchlist nunca cria uma posicao nem altera o patrimonio calculado - e nenhuma "
        "classificacao aqui e uma recomendacao de venda ou uma ordem de compra automatica."
    )

    with session_scope() as db:
        entries = WatchlistService(db).list_watchlist_assets(portfolio_id)

    _render_summary(entries)
    _render_registration_form(portfolio_id)
    _render_watchlist_table(portfolio_id, entries)
    _render_opportunity_radar(portfolio_id)


def _render_summary(entries) -> None:
    with section("Resumo da Watchlist", "resumo"):
        counts = Counter(e.status for e in entries)
        cols = st.columns(len(WATCHLIST_STATUSES))
        for col, status in zip(cols, WATCHLIST_STATUSES, strict=True):
            col.metric(status, counts.get(status, 0))


def _render_registration_form(portfolio_id: int) -> None:
    with section("Cadastrar novo candidato", "novo"):
        with st.form("watchlist_add_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            ticker = col1.text_input("Ticker")
            name = col2.text_input("Nome")
            col3, col4, col5 = st.columns(3)
            asset_class = col3.selectbox("Classe", ASSET_CLASSES)
            country = col4.text_input("Pais (2 letras)", value="BR")
            currency = col5.text_input("Moeda (3 letras)", value="BRL")
            col6, col7 = st.columns(2)
            status = col6.selectbox("Status inicial", WATCHLIST_STATUSES, index=0)
            priority = col7.slider("Prioridade (0-10)", 0, 10, 0)
            sector = st.text_input("Setor (opcional)")
            thesis = st.text_area("Tese (opcional)")
            notes = st.text_area("Notas (opcional)")
            submitted = st.form_submit_button("Adicionar a Watchlist")

        if submitted:
            if not ticker.strip() or not name.strip():
                st.error("Ticker e nome sao obrigatorios.")
            else:
                try:
                    payload = WatchlistAssetCreate(
                        ticker=ticker,
                        name=name,
                        asset_class=asset_class,
                        country=country,
                        currency=currency,
                        sector=sector.strip() or None,
                        status=status,
                        priority=priority,
                        thesis=thesis.strip() or None,
                        notes=notes.strip() or None,
                    )
                    with session_scope() as db:
                        WatchlistService(db).add_watchlist_asset(portfolio_id, payload)
                    st.success(f"{ticker.upper()} adicionado a Watchlist.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))


def _render_watchlist_table(portfolio_id: int, entries) -> None:
    with section("Ativos na Watchlist", "lista"):
        if not entries:
            st.info("Nenhum ativo cadastrado ainda. Use o formulario acima.")
            return

        st.dataframe(
            [
                {
                    "Ticker": e.ticker,
                    "Nome": e.name,
                    "Classe": e.asset_class,
                    "Pais": e.country,
                    "Moeda": e.currency,
                    "Status": e.status,
                    "Prioridade": e.priority,
                    "Ja na carteira?": "Sim" if e.already_in_portfolio else "Nao",
                }
                for e in entries
            ],
            width="stretch",
            hide_index=True,
        )

        options = {f"{e.ticker} - {e.status}": e for e in entries}
        label = st.selectbox("Selecionar ativo para acao", list(options.keys()))
        selected = options[label]

        col1, col2, col3, col4, col5 = st.columns(5)
        if col1.button("Coletar dados", key="radar_collect_one"):
            with session_scope() as db:
                result = WatchlistService(db).collect_data_for_asset(portfolio_id, selected.id)
            _render_collection_result(result)
        if col2.button("Bloquear", key="radar_block"):
            with session_scope() as db:
                WatchlistService(db).block_asset(portfolio_id, selected.id)
            st.rerun()
        if col3.button("Descartar", key="radar_discard"):
            with session_scope() as db:
                WatchlistService(db).discard_asset(portfolio_id, selected.id)
            st.rerun()
        if col4.button("Marcar comprado", key="radar_bought"):
            with session_scope() as db:
                WatchlistService(db).mark_as_bought(portfolio_id, selected.id)
            st.rerun()
        if col5.button("Remover", key="radar_remove"):
            with session_scope() as db:
                WatchlistService(db).remove_watchlist_asset(portfolio_id, selected.id)
            st.rerun()

        if st.button("Coletar dados de todos", key="radar_collect_all"):
            with session_scope() as db:
                service = WatchlistService(db)
                results = [service.collect_data_for_asset(portfolio_id, e.id) for e in entries]
            for result in results:
                _render_collection_result(result)


def _render_collection_result(result) -> None:
    parts = [f"**{result.ticker}**"]
    if result.lg_score is not None:
        parts.append(f"LG Score: {float(result.lg_score):.1f}")
    if result.conviction_score is not None:
        parts.append(f"Conviction Score: {float(result.conviction_score):.1f}")
    if result.confidence is not None:
        parts.append(f"confianca: {float(result.confidence) * 100:.0f}%")
    st.markdown(" - ".join(parts))
    if result.low_confidence:
        st.caption("Atencao: confianca baixa - este dado nao deve ser motivo primario de aporte.")
    for note in result.notes:
        st.caption(f"- {note}")


def _render_opportunity_radar(portfolio_id: int) -> None:
    with section("Radar de oportunidades", "radar"):
        with session_scope() as db:
            evaluation = RadarService(db).evaluate(portfolio_id)

        if not evaluation.candidates:
            st.info(
                "Nada para comparar ainda - cadastre candidatos na Watchlist ou registre "
                "posicoes na carteira."
            )
            return

        for classification in _CLASSIFICATION_ORDER:
            subset = evaluation.by_classification(classification)
            if not subset:
                continue
            st.subheader(_CLASSIFICATION_LABELS[classification])
            st.dataframe(
                [
                    {
                        "Ticker": c.ticker,
                        "Nome": c.name,
                        "Classe": c.asset_class,
                        "Ja tenho?": "Sim" if c.is_current_holding else "Nao",
                        "Score": (
                            f"{float(c.effective_score):.1f}"
                            if c.effective_score is not None
                            else "-"
                        ),
                        "Confianca": (
                            f"{float(c.confidence) * 100:.0f}%" if c.confidence is not None else "-"
                        ),
                    }
                    for c in subset
                ],
                width="stretch",
                hide_index=True,
            )
            with st.expander(f"Explicacao - {_CLASSIFICATION_LABELS[classification]}"):
                for c in subset:
                    st.markdown(f"**{c.ticker}**")
                    for reason in c.reasons:
                        st.caption(f"- {reason}")
