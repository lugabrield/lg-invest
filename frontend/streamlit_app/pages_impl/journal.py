"""Tela Journal: diário livre, teses de investimento e revisões.

Consome JournalService (diário) e ThesisService (teses/revisões).
Nenhum cálculo financeiro aqui.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from backend.app.infrastructure.database.models.investment_thesis import THESIS_STATUSES
from backend.app.infrastructure.database.models.journal_entry import JOURNAL_ACTIONS
from backend.app.infrastructure.database.models.thesis_review import REVIEW_CLASSIFICATIONS
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.services.journal_service import JournalService
from backend.app.services.thesis_service import ThesisService
from frontend.streamlit_app.db import session_scope


def render() -> None:
    st.title("Journal")
    st.caption("Memória é vantagem de longo prazo: registre o porquê de cada decisão.")

    with session_scope() as db:
        assets = AssetRepository(db).list_all()
    if not assets:
        st.info("Cadastre ativos antes de registrar teses.")
        return
    tickers = [a.ticker for a in assets]

    tab_diary, tab_theses, tab_reviews = st.tabs(["Diário", "Teses", "Revisões"])

    with tab_diary:
        _render_diary(tickers)
    with tab_theses:
        _render_theses(tickers)
    with tab_reviews:
        _render_reviews()


def _render_diary(tickers: list[str]) -> None:
    st.subheader("Nova entrada de diário")
    ticker = st.selectbox("Ativo", tickers, key="diary_ticker")
    action = st.selectbox("Ação", list(JOURNAL_ACTIONS), key="diary_action")
    entry_date = st.date_input("Data", value=date.today(), key="diary_date")
    thesis = st.text_area("Nota / tese", key="diary_thesis")
    expected = st.text_area("Resultado esperado (opcional)", key="diary_expected")

    if st.button("Salvar entrada", key="diary_save"):
        if not thesis.strip():
            st.error("A nota não pode ficar vazia.")
        else:
            with session_scope() as db:
                entry = JournalService(db).add_by_ticker(
                    ticker=ticker,
                    action=action,
                    thesis=thesis.strip(),
                    entry_date=entry_date,
                    expected_outcome=expected.strip() or None,
                )
            st.success("Entrada registrada.") if entry else st.error("Ativo não encontrado.")

    st.divider()
    st.subheader("Histórico do diário")
    with session_scope() as db:
        entries = JournalService(db).list_all()
        asset_by_id = {a.id: a for a in AssetRepository(db).list_all()}
    if not entries:
        st.info("Nenhuma entrada ainda.")
        return
    st.dataframe(
        [
            {
                "Data": str(e.date),
                "Ativo": (
                    asset_by_id[e.asset_id].ticker if e.asset_id in asset_by_id else e.asset_id
                ),
                "Ação": e.action,
                "Nota": e.thesis,
                "Esperado": e.expected_outcome or "—",
            }
            for e in entries
        ],
        width="stretch",
        hide_index=True,
    )


def _render_theses(tickers: list[str]) -> None:
    st.subheader("Nova tese de investimento")
    ticker = st.selectbox("Ativo", tickers, key="thesis_ticker")
    thesis_date = st.date_input("Data da tese", value=date.today(), key="thesis_date")
    hypothesis = st.text_area("Hipótese principal", key="thesis_hypothesis")
    drivers = st.text_area("Drivers de retorno (opcional)", key="thesis_drivers")
    risks = st.text_area("Riscos principais (opcional)", key="thesis_risks")
    horizon = st.text_input("Horizonte (opcional)", key="thesis_horizon")
    criteria = st.text_area("Critérios de revisão (opcional)", key="thesis_criteria")

    if st.button("Criar tese", key="thesis_create"):
        if not hypothesis.strip():
            st.error("A hipótese não pode ficar vazia.")
        else:
            with session_scope() as db:
                created = ThesisService(db).create_by_ticker(
                    ticker,
                    {
                        "thesis_date": thesis_date,
                        "hypothesis": hypothesis.strip(),
                        "return_drivers": drivers.strip() or None,
                        "main_risks": risks.strip() or None,
                        "horizon": horizon.strip() or None,
                        "review_criteria": criteria.strip() or None,
                    },
                )
            st.success("Tese criada.") if created else st.error("Ativo não encontrado.")

    st.divider()
    st.subheader("Teses registradas")
    with session_scope() as db:
        theses = ThesisService(db).list_theses()
        asset_by_id = {a.id: a for a in AssetRepository(db).list_all()}
    if not theses:
        st.info("Nenhuma tese ainda.")
        return
    st.dataframe(
        [
            {
                "ID": t.id,
                "Data": str(t.thesis_date),
                "Ativo": (
                    asset_by_id[t.asset_id].ticker if t.asset_id in asset_by_id else t.asset_id
                ),
                "Status": t.status,
                "Hipótese": t.hypothesis,
                "Horizonte": t.horizon or "—",
            }
            for t in theses
        ],
        width="stretch",
        hide_index=True,
    )
    st.caption(f"Status possíveis: {', '.join(THESIS_STATUSES)}")


def _render_reviews() -> None:
    st.subheader("Revisar uma tese")
    with session_scope() as db:
        theses = ThesisService(db).list_theses()
        asset_by_id = {a.id: a for a in AssetRepository(db).list_all()}

    if not theses:
        st.info("Crie uma tese antes de revisar.")
        return

    options = {
        f"#{t.id} · {asset_by_id[t.asset_id].ticker if t.asset_id in asset_by_id else t.asset_id} · {t.status}": t.id
        for t in theses
    }
    label = st.selectbox("Tese", list(options.keys()), key="review_thesis")
    review_date = st.date_input("Data da revisão", value=date.today(), key="review_date")
    classification = st.selectbox("Classificação", list(REVIEW_CLASSIFICATIONS), key="review_class")
    notes = st.text_area("Notas da revisão (opcional)", key="review_notes")

    if st.button("Registrar revisão", key="review_save"):
        from backend.app.schemas.thesis import ThesisReviewCreate

        with session_scope() as db:
            review = ThesisService(db).review_thesis(
                ThesisReviewCreate(
                    thesis_id=options[label],
                    review_date=review_date,
                    classification=classification,
                    notes=notes.strip() or None,
                )
            )
        if review:
            st.success("Revisão registrada. Status da tese atualizado.")
        else:
            st.error("Tese não encontrada.")
