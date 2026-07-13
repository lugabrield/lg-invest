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

/* ---------------------------------------------------------------------
   Sprint 30 (Product Design / UX Polish) — Design System interno.
   Componentes novos em components/patterns.py consomem estas classes.
   Tudo centralizado aqui: nenhuma tela injeta CSS solto. ------------- */

/* Título de página (components/patterns.py::page_header) — todo topo de
   tela segue o mesmo padrão: título + descrição curta + status opcional. */
.lg-page-header {{
    margin-bottom: 0.4rem;
}}
.lg-page-header h1 {{
    margin: 0;
    font-size: 1.85rem;
    color: {TEXT_PRIMARY};
    display: flex;
    align-items: center;
    gap: 10px;
}}
.lg-page-header .lg-page-description {{
    color: {TEXT_MUTED};
    font-size: 0.95rem;
    margin-top: 4px;
}}

/* MetricCard — card de métrica "premium" (hero do Dashboard e resumos),
   além do st.metric padrão já estilizado acima. Aceita uma faixa de
   status colorida na borda esquerda (positivo/atenção/crítico/neutro). */
.lg-metric-card-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
    margin-bottom: 4px;
}}
.lg-metric-card {{
    background-color: {CARD_BACKGROUND};
    border: 1px solid {BORDER};
    border-left: 3px solid var(--lg-metric-accent, {PRIMARY});
    border-radius: 12px;
    padding: 14px 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
}}
.lg-metric-card .lg-metric-label {{
    color: {TEXT_MUTED};
    font-size: 0.8rem;
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
}}
.lg-metric-card .lg-metric-value {{
    color: {TEXT_PRIMARY};
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1.2;
}}
.lg-metric-card .lg-metric-delta {{
    font-size: 0.82rem;
    margin-top: 3px;
    color: var(--lg-metric-accent, {TEXT_MUTED});
}}

/* WarningBox / InfoBox / SuccessBox / ErrorBox — alternativa mais
   "de produto" ao st.warning/st.info nativos, com título destacado. */
.lg-alert-box {{
    border-radius: 10px;
    border: 1px solid var(--lg-alert-border, {BORDER});
    background-color: var(--lg-alert-bg, {CARD_BACKGROUND});
    padding: 12px 16px;
    margin-bottom: 10px;
}}
.lg-alert-box .lg-alert-title {{
    font-weight: 600;
    color: {TEXT_PRIMARY};
    margin-bottom: 2px;
    display: flex;
    align-items: center;
    gap: 6px;
}}
.lg-alert-box .lg-alert-message {{
    color: {TEXT_MUTED};
    font-size: 0.9rem;
}}

/* RecommendationCard (Aporte v3) — um card por ativo recomendado. */
.lg-recommendation-card {{
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 12px;
    background-color: {CARD_BACKGROUND};
}}
.lg-recommendation-card .lg-rec-header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 10px;
    margin-bottom: 6px;
}}
.lg-recommendation-card .lg-rec-ticker {{
    font-size: 1.15rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
.lg-recommendation-card .lg-rec-name {{
    color: {TEXT_MUTED};
    font-size: 0.82rem;
}}
.lg-recommendation-card .lg-rec-amount {{
    font-size: 1.2rem;
    font-weight: 700;
    color: {POSITIVE};
    text-align: right;
}}
.lg-recommendation-card .lg-rec-weight {{
    color: {TEXT_MUTED};
    font-size: 0.82rem;
    text-align: right;
}}
.lg-recommendation-card .lg-rec-reason {{
    color: {TEXT_PRIMARY};
    font-size: 0.92rem;
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid {BORDER_SOFT};
}}
.lg-recommendation-card .lg-rec-badges {{
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 6px;
}}

/* DataQualityBox (Ativos, Aporte) — disponível / ausente / confiança. */
.lg-data-quality-box {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 10px;
    background-color: {CARD_BACKGROUND};
}}
.lg-data-quality-box .lg-dq-title {{
    font-weight: 600;
    color: {TEXT_PRIMARY};
    margin-bottom: 6px;
}}
.lg-data-quality-box .lg-dq-row {{
    display: flex;
    gap: 8px;
    font-size: 0.88rem;
    margin-bottom: 3px;
}}
.lg-data-quality-box .lg-dq-label {{
    color: {TEXT_MUTED};
    min-width: 110px;
}}
.lg-data-quality-box .lg-dq-value {{
    color: {TEXT_PRIMARY};
}}

/* EmptyState — telas/seções sem dados ainda. */
.lg-empty-state {{
    text-align: center;
    padding: 36px 20px;
    border: 1px dashed {BORDER};
    border-radius: 12px;
    background-color: {CARD_BACKGROUND};
    margin-bottom: 12px;
}}
.lg-empty-state .lg-empty-icon {{
    font-size: 2rem;
    margin-bottom: 8px;
}}
.lg-empty-state .lg-empty-title {{
    font-weight: 600;
    color: {TEXT_PRIMARY};
    font-size: 1.05rem;
    margin-bottom: 4px;
}}
.lg-empty-state .lg-empty-message {{
    color: {TEXT_MUTED};
    font-size: 0.9rem;
    max-width: 460px;
    margin: 0 auto;
}}

/* Sidebar: navegação em grupos + rodapé de versão/ambiente. */
.lg-sidebar-group-label {{
    color: {TEXT_FAINT};
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-top: 0.9rem;
    margin-bottom: 0.1rem;
}}
.lg-sidebar-footer {{
    color: {TEXT_FAINT};
    font-size: 0.75rem;
    line-height: 1.5;
    border-top: 1px solid {BORDER_SOFT};
    padding-top: 8px;
    margin-top: 12px;
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
