"""Tela Radar: Watchlist de ativos candidatos + comparação com a carteira
atual (Sprint 25, Parte 2.6; ajustes de status/UX na sprint seguinte).

Consome WatchlistService (CRUD + coleta de dados + troca de status) e
RadarService (classificação pura, sem efeitos colaterais). Esta tela
NUNCA cria uma `Position` nem altera o patrimônio calculado pelo
Portfolio Engine — ela só cadastra candidatos e mostra como eles se
comparam à carteira atual. Nenhuma ação aqui é uma ordem de compra.

Troca de status: qualquer transição (watching/candidate/blocked/
discarded/bought, em qualquer direção) usa `WatchlistService.set_status`
— nunca recria o registro, nunca duplica o ticker. Depois de qualquer
mutação (status, coleta, remoção, cadastro), o cache de leitura do
Streamlit é invalidado (`clear_all_caches`) para refletir na hora.
"""

from __future__ import annotations

from collections import Counter

import streamlit as st

from backend.app.infrastructure.database.models.asset import ASSET_CLASSES
from backend.app.infrastructure.database.models.watchlist_asset import WATCHLIST_STATUSES
from backend.app.schemas.watchlist import WatchlistAssetCreate
from backend.app.services.radar_service import RadarService
from backend.app.services.watchlist_service import WatchlistService
from frontend.streamlit_app.cache import clear_all_caches
from frontend.streamlit_app.components.patterns import (
    MetricCardSpec,
    empty_state,
    metric_card_row,
    page_header,
)
from frontend.streamlit_app.components.sections import section
from frontend.streamlit_app.db import session_scope

# Sprint 30 (Parte 7 — Radar como funil): ícone + status do MetricCard por
# estágio da Watchlist. "bought"/"discarded" são estados finais (positivo/
# neutro), os demais são estágios do funil em andamento.
_STATUS_ICON = {
    "watching": "👁️",
    "candidate": "⭐",
    "blocked": "🚫",
    "discarded": "🗑️",
    "bought": "✅",
}
_STATUS_METRIC_STATUS = {
    "watching": "neutral",
    "candidate": "attention",
    "blocked": "critical",
    "discarded": "muted",
    "bought": "positive",
}

_CLASSIFICATION_LABELS: dict[str, str] = {
    "current_holding_candidate": "Já tenho — bom para novo aporte",
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
    page_header(
        "Radar",
        "Acompanhe ativos que você ainda não tem, sem alterar sua carteira.",
        icon="🎯",
    )

    with session_scope() as db:
        entries = WatchlistService(db).list_watchlist_assets(portfolio_id)
        radar_by_ticker = {c.ticker: c for c in RadarService(db).evaluate(portfolio_id).candidates}

    _render_summary(entries, radar_by_ticker)
    _render_registration_form(portfolio_id)
    _render_watchlist_table(portfolio_id, entries, radar_by_ticker)
    _render_opportunity_radar(portfolio_id)


def _render_summary(entries, radar_by_ticker) -> None:
    with section(
        "Resumo da Watchlist",
        "📌",
        caption="O funil: monitorando → candidato → comprado (ou bloqueado/descartado).",
    ):
        counts = Counter(e.status for e in entries)
        insufficient = sum(
            1
            for e in entries
            if radar_by_ticker.get(e.ticker) is None
            or radar_by_ticker[e.ticker].classification == "insufficient_data"
        )
        cards: list[MetricCardSpec] = [
            {
                "label": status.capitalize(),
                "value": str(counts.get(status, 0)),
                "icon": _STATUS_ICON.get(status, ""),
                "status": _STATUS_METRIC_STATUS.get(status, "neutral"),
            }
            for status in WATCHLIST_STATUSES
        ]
        cards.append(
            {
                "label": "Dados insuficientes",
                "value": str(insufficient),
                "icon": "❓",
                "status": "muted" if insufficient == 0 else "attention",
            }
        )
        metric_card_row(cards)


def _render_registration_form(portfolio_id: int) -> None:
    with section("Cadastrar novo candidato", "➕"):
        with st.form("watchlist_add_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            ticker = col1.text_input("Ticker")
            name = col2.text_input("Nome")
            col3, col4, col5 = st.columns(3)
            asset_class = col3.selectbox("Classe", ASSET_CLASSES)
            country = col4.text_input("País (2 letras)", value="BR")
            currency = col5.text_input("Moeda (3 letras)", value="BRL")
            col6, col7 = st.columns(2)
            status = col6.selectbox("Status inicial", WATCHLIST_STATUSES, index=0)
            priority = col7.slider("Prioridade (0-10)", 0, 10, 0)
            sector = st.text_input("Setor (opcional)")
            thesis = st.text_area("Tese (opcional)")
            notes = st.text_area("Notas (opcional)")
            submitted = st.form_submit_button("Adicionar à Watchlist")

        if submitted:
            if not ticker.strip() or not name.strip():
                st.error("Ticker e nome são obrigatórios.")
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
                    clear_all_caches()
                    st.success(f"{ticker.upper()} adicionado à Watchlist.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))


def _fmt_score(value) -> str:
    return f"{float(value):.1f}" if value is not None else "—"


def _fmt_pct(value) -> str:
    return f"{float(value) * 100:.0f}%" if value is not None else "—"


def _fmt_datetime(value) -> str:
    return value.strftime("%d/%m/%Y %H:%M") if value is not None else "—"


def _render_watchlist_table(portfolio_id: int, entries, radar_by_ticker) -> None:
    with section("Ativos na Watchlist", "📋"):
        if not entries:
            empty_state(
                "Você ainda não acompanha ativos novos",
                "Use o formulário 'Cadastrar novo candidato' acima para começar.",
                icon="📌",
            )
            return

        rows = []
        for e in entries:
            radar = radar_by_ticker.get(e.ticker)
            rows.append(
                {
                    "Ticker": e.ticker,
                    "Nome": e.name,
                    "Classe": e.asset_class,
                    "País": e.country,
                    "Moeda": e.currency,
                    "Status": e.status,
                    "Prioridade": e.priority,
                    "Já na carteira?": "Sim" if e.already_in_portfolio else "Não",
                    "Score": _fmt_score(radar.effective_score) if radar else "—",
                    "Confiança": _fmt_pct(radar.confidence) if radar else "—",
                    "Classificação do Radar": (
                        _CLASSIFICATION_LABELS.get(radar.classification, radar.classification)
                        if radar
                        else "—"
                    ),
                    "Última coleta": _fmt_datetime(e.last_collected_at),
                }
            )
        st.dataframe(rows, width="stretch", hide_index=True)

        options = {f"{e.ticker} - {e.status}": e for e in entries}
        label = st.selectbox("Selecionar ativo para ação", list(options.keys()))
        selected = options[label]

        col1, col2 = st.columns(2)
        if col1.button("Coletar dados", key="radar_collect_one"):
            with session_scope() as db:
                result = WatchlistService(db).collect_data_for_asset(portfolio_id, selected.id)
            clear_all_caches()
            _render_collection_result(result)
        if col2.button("Remover", key="radar_remove"):
            with session_scope() as db:
                WatchlistService(db).remove_watchlist_asset(portfolio_id, selected.id)
            clear_all_caches()
            st.success(f"{selected.ticker} removido da Watchlist.")
            st.rerun()

        st.markdown("**Alterar status**")
        st.caption(
            "Funciona para qualquer transição — watching, candidate, blocked, discarded "
            "ou bought — sem precisar remover e recadastrar o ativo. Só o status muda; "
            "nenhuma posição é criada ou removida e o patrimônio não é afetado."
        )
        col3, col4 = st.columns([3, 1])
        default_index = (
            WATCHLIST_STATUSES.index(selected.status)
            if selected.status in WATCHLIST_STATUSES
            else 0
        )
        new_status = col3.selectbox(
            "Novo status", WATCHLIST_STATUSES, index=default_index, key="radar_new_status"
        )
        if col4.button("Atualizar status", key="radar_update_status"):
            with session_scope() as db:
                WatchlistService(db).set_status(portfolio_id, selected.id, new_status)
            clear_all_caches()
            st.success(f"Status de {selected.ticker} atualizado para {new_status}.")
            st.rerun()

        if st.button("Coletar dados de todos", key="radar_collect_all"):
            with session_scope() as db:
                service = WatchlistService(db)
                results = [service.collect_data_for_asset(portfolio_id, e.id) for e in entries]
            clear_all_caches()
            for result in results:
                _render_collection_result(result)


def _render_collection_result(result) -> None:
    parts = [f"**{result.ticker}**"]
    if result.lg_score is not None:
        parts.append(f"LG Score: {float(result.lg_score):.1f}")
    if result.conviction_score is not None:
        parts.append(f"Conviction Score: {float(result.conviction_score):.1f}")
    if result.confidence is not None:
        parts.append(f"confiança: {float(result.confidence) * 100:.0f}%")
    st.markdown(" - ".join(parts))
    if result.low_confidence:
        st.caption("Atenção: confiança baixa — este dado não deve ser motivo primário de aporte.")
    for note in result.notes:
        st.caption(f"- {note}")


def _render_opportunity_radar(portfolio_id: int) -> None:
    with section("Radar de oportunidades", "🎯"):
        with session_scope() as db:
            evaluation = RadarService(db).evaluate(portfolio_id)

        if not evaluation.candidates:
            empty_state(
                "Nada para comparar ainda",
                "Cadastre candidatos na Watchlist ou registre posições na carteira.",
                icon="🎯",
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
                        "Já tenho?": "Sim" if c.is_current_holding else "Não",
                        "Score": _fmt_score(c.effective_score),
                        "Confiança": _fmt_pct(c.confidence),
                    }
                    for c in subset
                ],
                width="stretch",
                hide_index=True,
            )
            with st.expander(f"Explicação — {_CLASSIFICATION_LABELS[classification]}"):
                for c in subset:
                    st.markdown(f"**{c.ticker}**")
