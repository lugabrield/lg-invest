"""CSS global da LG INVEST (Sprint 11).

Injetado uma vez no boot do app (`app.py`). Só estilo — nenhuma lógica
aqui. Deixa os `st.metric` parecendo cards de produto, dá mais respiro
entre blocos e destaca os headers de seção sem depender de nenhuma lib
de componente externa.
"""

from __future__ import annotations

import streamlit as st

from frontend.streamlit_app.styles.theme import BORDER, CARD_BACKGROUND, PRIMARY

_CSS = f"""
<style>
/* Cards de métrica (st.metric) com aparência de produto financeiro */
div[data-testid="stMetric"] {{
    background-color: {CARD_BACKGROUND};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 16px 18px;
    box-shadow: 0 1px 3px rgba(16, 24, 40, 0.06);
}}
div[data-testid="stMetricLabel"] {{
    font-size: 0.82rem;
    color: #5B6472;
}}
div[data-testid="stMetricValue"] {{
    font-size: 1.55rem;
}}

/* Respiro geral entre blocos de conteúdo */
div.block-container {{
    padding-top: 1.6rem;
    padding-bottom: 3rem;
}}

/* Headers de seção (usados por components/sections.py) */
.lg-section-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 0.6rem;
    margin-bottom: 0.4rem;
    padding-bottom: 6px;
    border-bottom: 2px solid {PRIMARY}20;
}}
.lg-section-header h3 {{
    margin: 0;
    font-size: 1.15rem;
}}

/* Cartão de insight do Diagnóstico da Carteira */
.lg-insight-card {{
    border: 1px solid {BORDER};
    border-left: 4px solid var(--lg-insight-color, {PRIMARY});
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 8px;
    background-color: {CARD_BACKGROUND};
}}
.lg-insight-card .lg-insight-title {{
    font-weight: 600;
    margin-bottom: 2px;
}}
.lg-insight-card .lg-insight-message {{
    font-size: 0.92rem;
    color: #333;
}}

/* Destaque de maior posição / linhas com atenção nas tabelas de posição */
.lg-badge {{
    display: inline-block;
    padding: 1px 8px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
}}
</style>
"""


def inject_custom_css() -> None:
    """Injeta o CSS global da LG INVEST. Chamar uma vez por execução do app."""
    st.markdown(_CSS, unsafe_allow_html=True)
