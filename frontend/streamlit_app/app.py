"""LG Terminal — interface Streamlit da LG INVEST (MVP, Sprint 8+).

Camada de apresentação: cada tela consome os serviços/engines do
backend e apenas renderiza. Nenhum cálculo financeiro vive aqui
(Volume 20, prompt 11).

Rodar com:
    streamlit run frontend/streamlit_app/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path, independentemente de
# onde o Streamlit for iniciado. O Streamlit adiciona ao path a pasta do
# app.py (frontend/streamlit_app), não a raiz — sem este ajuste, os
# imports absolutos `frontend...` e `backend...` falhariam.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st  # noqa: E402

from frontend.streamlit_app.pages_impl import (  # noqa: E402
    aporte,
    ativos,
    carteira,
    configuracoes,
    dashboard,
    inteligencia,
    journal,
    radar,
    simulacao,
    sincronizar_dividendos_me,
)
from frontend.streamlit_app.styles.custom_css import inject_custom_css  # noqa: E402

PAGES = [
    "Dashboard",
    "Carteira",
    "Ativos",
    "Inteligência",
    "Aporte",
    "Simulação",
    "Radar",
    "Journal",
    "Sincronizar Dividendos.me",
    "Configurações",
]


def main() -> None:
    st.set_page_config(page_title="LG INVEST", page_icon="📈", layout="wide")
    inject_custom_css()
    st.sidebar.title("LG INVEST")
    st.sidebar.caption("Investment Intelligence Platform")

    portfolio_id = st.sidebar.number_input("Carteira (id)", min_value=1, value=1, step=1)
    page = st.sidebar.radio("Navegação", PAGES)

    if page == "Dashboard":
        dashboard.render(int(portfolio_id))
    elif page == "Carteira":
        carteira.render(int(portfolio_id))
    elif page == "Ativos":
        ativos.render()
    elif page == "Inteligência":
        inteligencia.render(int(portfolio_id))
    elif page == "Aporte":
        aporte.render(int(portfolio_id))
    elif page == "Simulação":
        simulacao.render(int(portfolio_id))
    elif page == "Radar":
        radar.render(int(portfolio_id))
    elif page == "Journal":
        journal.render()
    elif page == "Sincronizar Dividendos.me":
        sincronizar_dividendos_me.render(int(portfolio_id))
    elif page == "Configurações":
        configuracoes.render(int(portfolio_id))


if __name__ == "__main__":
    main()
