"""LG Terminal — interface Streamlit da LG INVEST (MVP, Sprint 8+).

Camada de apresentação: cada tela consome os serviços/engines do
backend e apenas renderiza. Nenhum cálculo financeiro vive aqui
(Volume 20, prompt 11).

Rodar com:
    streamlit run frontend/streamlit_app/app.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
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
from frontend.streamlit_app.version import APP_NAME, APP_VERSION  # noqa: E402

# Sprint 30 (Product Design, Parte 2) — sidebar agrupada em vez de uma lista
# plana de 10 páginas. Grupos pedidos pelo usuário: Principal (visão geral
# e ação do dia a dia), Análise (telas de inteligência/pesquisa), Operação
# (sincronização e configuração). "Journal" entra em Análise: é memória de
# decisão, não uma tela operacional.
NAV_GROUPS: list[tuple[str, list[str]]] = [
    ("Principal", ["Dashboard", "Carteira", "Aporte"]),
    ("Análise", ["Inteligência", "Ativos", "Radar", "Simulação", "Journal"]),
    ("Operação", ["Sincronizar Dividendos.me", "Configurações"]),
]
PAGES = [page for _, pages in NAV_GROUPS for page in pages]


def _render_sidebar_nav() -> str:
    """Navegação por grupos com uma única página "ativa" por vez.

    Streamlit não tem grupo nativo para `st.radio`, então cada grupo vira
    o próprio radio (com rótulo de seção acima) e sincronizamos os três
    manualmente via `session_state`: sempre que um radio muda, os outros
    dois grupos são "desmarcados" (`None`) para sobrar só uma seleção
    visível — a mesma sensação de um menu único, sem forçar Streamlit a
    algo que ele não suporta.
    """
    nav_page = st.session_state.get("nav_page", "Dashboard")

    # Detecta se algum radio de grupo mudou nesta execução (o valor já vem
    # atualizado pelo próprio Streamlit antes do script rodar de novo).
    for group_name, options in NAV_GROUPS:
        key = f"nav_{group_name}"
        value = st.session_state.get(key)
        if value is not None and value != nav_page and value in options:
            nav_page = value
            break
    st.session_state["nav_page"] = nav_page

    # Sincroniza os três radios com a página ativa antes de instanciá-los.
    for group_name, options in NAV_GROUPS:
        key = f"nav_{group_name}"
        st.session_state[key] = nav_page if nav_page in options else None

    for group_name, options in NAV_GROUPS:
        st.sidebar.markdown(
            f'<div class="lg-sidebar-group-label">{group_name}</div>',
            unsafe_allow_html=True,
        )
        st.sidebar.radio(
            group_name,
            options,
            key=f"nav_{group_name}",
            index=None,
            label_visibility="collapsed",
        )

    return st.session_state["nav_page"]


def _render_sidebar_footer(portfolio_id: int) -> None:
    """Rodapé fixo pedido na Sprint 30 Parte 2: versão, ambiente e última
    sincronização externa (Dividendos.me). Nunca deve derrubar o app —
    se a consulta falhar (banco sem tabela, portfólio inexistente etc.),
    simplesmente omite a linha de última sincronização."""
    last_sync_html = ""
    try:
        from backend.app.infrastructure.repositories.external_sync_run_repository import (
            ExternalSyncRunRepository,
        )
        from frontend.streamlit_app.db import session_scope

        with session_scope() as db:
            run = ExternalSyncRunRepository(db).get_latest(portfolio_id, "dividendos_me")
        if run is not None:
            when = run.finished_at or run.created_at
            delta = datetime.now() - when
            if delta < timedelta(minutes=1):
                when_label = "agora há pouco"
            elif delta < timedelta(hours=1):
                when_label = f"há {int(delta.total_seconds() // 60)} min"
            elif delta < timedelta(days=1):
                when_label = f"há {int(delta.total_seconds() // 3600)} h"
            else:
                when_label = when.strftime("%d/%m/%Y")
            last_sync_html = f"<div>Última sync: {when_label}</div>"
    except Exception:  # noqa: BLE001 - rodapé é informativo, nunca crítico
        last_sync_html = ""

    # HTML numa única linha (sem indentação/quebra interna) — uma f-string
    # multi-linha indentada aqui faz o Markdown do Streamlit tratar o HTML
    # como bloco de código literal em vez de renderizar, mesmo com
    # unsafe_allow_html=True (mesmo bug corrigido em components/patterns.py
    # e components/cards.py na Sprint 31).
    footer_html = (
        '<div class="lg-sidebar-footer">'
        f"<div>{APP_NAME} v{APP_VERSION}</div>"
        "<div>Ambiente: Local</div>"
        f"{last_sync_html}"
        "</div>"
    )
    st.sidebar.markdown(footer_html, unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="LG INVEST", page_icon="📈", layout="wide")
    inject_custom_css()
    st.sidebar.title("LG INVEST")
    st.sidebar.caption("Investment Intelligence Platform")

    portfolio_id = st.sidebar.number_input("Carteira (id)", min_value=1, value=1, step=1)
    page = _render_sidebar_nav()
    _render_sidebar_footer(int(portfolio_id))

    if page == "Dashboard":
        dashboard.render(int(portfolio_id))
    elif page == "Carteira":
        carteira.render(int(portfolio_id))
    elif page == "Ativos":
        ativos.render(int(portfolio_id))
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
