"""Badges reutilizáveis: classificação, confiança e qualidade de dados (Sprint 21).

Só renderização (HTML+CSS via `st.markdown`) — nenhum cálculo aqui. As
cores vêm de `styles/theme.py` para ficarem consistentes com gráficos e
cards. Usados em Ativos, Inteligência, Aporte e Dashboard.
"""

from __future__ import annotations

import streamlit as st

from frontend.streamlit_app.styles.custom_css import BADGE_BACKGROUND_BY_COLOR
from frontend.streamlit_app.styles.theme import (
    ALERT,
    ATTENTION,
    BORDER,
    BORDER_SOFT,
    INFO,
    NEUTRAL,
    POSITIVE,
    classification_color,
    classification_label_pt,
)

_CONFIDENCE_COLOR = {"alta": POSITIVE, "média": ATTENTION, "baixa": ALERT}
_CONFIDENCE_LABEL = {
    "alta": "Confiança alta",
    "média": "Confiança média",
    "baixa": "Confiança baixa",
}

_DATA_QUALITY_COLOR = {
    "automatico": POSITIVE,
    "manual": INFO,
    "estimado": ATTENTION,
    "ausente": ALERT,
    "completo": POSITIVE,
    "parcial": ATTENTION,
    "proxy": ATTENTION,
    "nao_aplicavel": NEUTRAL,
}


def _badge_html(label: str, color: str) -> str:
    bg = BADGE_BACKGROUND_BY_COLOR.get(color, BORDER_SOFT)
    return (
        f'<span class="lg-badge" style="--lg-badge-bg:{bg}; --lg-badge-border:{color}66;">'
        f"{label}</span>"
    )


def render_badge(label: str, color: str = BORDER) -> None:
    """Badge genérico com cor arbitrária (cai no cinza padrão se não informado)."""
    st.markdown(_badge_html(label, color), unsafe_allow_html=True)


def badge_html(label: str, color: str = BORDER) -> str:
    """Versão string do badge, para compor dentro de outros blocos de HTML."""
    return _badge_html(label, color)


def classification_badge_html(classification: str) -> str:
    """Badge de classificação do LG Conviction Score / Decision Engine."""
    return _badge_html(
        classification_label_pt(classification), classification_color(classification)
    )


def confidence_badge_html(confidence_label: str) -> str:
    """Badge de confiança (alta/média/baixa)."""
    color = _CONFIDENCE_COLOR.get(confidence_label, NEUTRAL)
    label = _CONFIDENCE_LABEL.get(confidence_label, f"Confiança {confidence_label}")
    return _badge_html(label, color)


def data_quality_badge_html(status: str, label: str | None = None) -> str:
    """Badge de qualidade de dado (preço/fundamentos/valuation)."""
    color = _DATA_QUALITY_COLOR.get(status, NEUTRAL)
    return _badge_html(label or status.replace("_", " ").capitalize(), color)
