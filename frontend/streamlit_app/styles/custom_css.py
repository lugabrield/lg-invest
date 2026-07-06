"""CSS global da LG INVEST (Sprint 11; Sprint 21 — tema dark + contraste).

Injetado uma vez no boot do app (`app.py`). Só estilo — nenhuma lógica
aqui. Deixa os `st.metric` parecendo cards de produto financeiro, dá
mais respiro entre blocos, destaca os headers de seção e badges de
classificação sem depender de nenhuma lib de componente externa.

Sprint 21: todo texto dentro de cards agora tem cor explícita
(`TEXT_PRIMARY`/`TEXT_MUTED`) em vez de herdar a cor de tema do
Streamlit — é isso que elimina o bug de "texto claro sobre fundo claro"
relatado nas telas. `.streamlit/config.toml` fixa o tema base como dark
para que o restante da UI do Streamlit (não coberto por este CSS) já
nasça com contraste correto.
"""

from __future__ import annotations

import streamlit as st

from frontend.streamlit_app.styles.theme import (
    ALERT,
    ATTENTION,
    BORDER,
    BORDER_SOFT,
    CARD_BACKGROUND,
    CARD_BACKGROUND_HOVER,
    INFO,
    POSITIVE,
    PRIMARY,
    TEXT_FAINT,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

_CSS = f"""
<style>
/* Cards de métrica (st.metric) com aparência de produto financeiro premium */
div[data-testid="stMetric"] {{
    background-color: {CARD_BACKGROUND};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 16px 18px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
    transition: border-color 0.15s ease;
}}
div[data-testid="stMetric"]:hover {{
    border-color: {PRIMARY}80;
    background-color: {CARD_BACKGROUND_HOVER};
}}
div[data-testid="stMetricLabel"] {{
    font-size: 0.82rem;
    color: {TEXT_MUTED} !important;
}}
div[data-testid="stMetricLabel"] p {{
    color: {TEXT_MUTED} !important;
}}
div[data-testid="stMetricValue"] {{
    font-size: 1.55rem;
    color: {TEXT_PRIMARY} !important;
}}
div[data-testid="stMetricDelta"] {{
    font-size: 0.85rem;
}}

/* Respiro geral entre blocos de conteúdo */
div.block-container {{
    padding-top: 1.6rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}}

/* Headers de seção (usados por components/sections.py) */
.lg-section-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 1.1rem;
    margin-bottom: 0.5rem;
    padding-bottom: 6px;
    border-bottom: 2px solid {PRIMARY}33;
}}
.lg-section-header h3 {{
    margin: 0;
    font-size: 1.15rem;
    color: {TEXT_PRIMARY};
}}
.lg-section-subtitle {{
    color: {TEXT_MUTED};
    font-size: 0.88rem;
    margin-top: -0.3rem;
    margin-bottom: 0.6rem;
}}

/* Cartão de insight (Diagnóstico da Carteira, Dashboard, Inteligência) */
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
    color: {TEXT_PRIMARY};
}}
.lg-insight-card .lg-insight-message {{
    font-size: 0.92rem;
    color: {TEXT_MUTED};
}}

/* Cartão de ativo (Inteligência, Ativos) — bloco maior com cabeçalho + corpo */
.lg-asset-card {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 12px;
    background-color: {CARD_BACKGROUND};
}}
.lg-asset-card .lg-asset-card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
}}
.lg-asset-card .lg-asset-ticker {{
    font-weight: 700;
    font-size: 1.05rem;
    color: {TEXT_PRIMARY};
}}
.lg-asset-card .lg-asset-meta {{
    color: {TEXT_MUTED};
    font-size: 0.85rem;
}}
.lg-asset-card ul {{
    margin: 4px 0 0 0;
    padding-left: 1.1rem;
}}
.lg-asset-card li {{
    color: {TEXT_MUTED};
    font-size: 0.88rem;
    margin-bottom: 2px;
}}

/* Badges de classificação/status (components/badges.py) */
.lg-badge {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    white-space: nowrap;
    color: {TEXT_PRIMARY};
    background-color: var(--lg-badge-bg, {BORDER_SOFT});
    border: 1px solid var(--lg-badge-border, {BORDER});
}}

/* Texto muted genérico, para uso em st.markdown() fora de cards */
.lg-muted {{
    color: {TEXT_MUTED};
    font-size: 0.88rem;
}}
.lg-faint {{
    color: {TEXT_FAINT};
    font-size: 0.8rem;
}}

/* Caixa de destaque (usada em "Por que esse ativo?" e no resumo de Aporte) */
.lg-highlight-box {{
    border: 1px solid {PRIMARY}55;
    background-color: {PRIMARY}14;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 12px;
    color: {TEXT_PRIMARY};
}}

/* Tabelas nativas do Streamlit (st.dataframe) — bordas sutis consistentes */
div[data-testid="stDataFrame"] {{
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

/* Expanders com leve destaque de fundo, alinhados ao restante dos cards */
div[data-testid="stExpander"] {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    background-color: {CARD_BACKGROUND};
}}
</style>
"""

# Cores de severidade/estado usadas por badges.py via CSS var --lg-badge-bg.
BADGE_BACKGROUND_BY_COLOR = {
    POSITIVE: f"{POSITIVE}26",
    INFO: f"{INFO}26",
    ATTENTION: f"{ATTENTION}26",
    ALERT: f"{ALERT}26",
}


def inject_custom_css() -> None:
    """Injeta o CSS global da LG INVEST. Chamar uma vez por execução do app."""
    st.markdown(_CSS, unsafe_allow_html=True)
