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

# Sprint 26 (Análise Fundamentalista) — status do Valuation Engine 2.0
# (`schemas/valuation_v2.py::VALUATION_STATUSES`) e da Análise de Renda
# Imobiliária (`schemas/income_real_estate.py::STATUSES`) usam a mesma
# semântica de cor (barato/atrativo = positivo, caro/pouco atrativo =
# alerta), só o rótulo em português muda por domínio.
_VALUATION_STATUS_COLOR = {
    "subvalorizado": POSITIVE,
    "valor_justo": INFO,
    "sobrevalorizado": ALERT,
    "indeterminado": NEUTRAL,
}
_VALUATION_STATUS_LABEL = {
    "subvalorizado": "Subvalorizado",
    "valor_justo": "Valor justo",
    "sobrevalorizado": "Sobrevalorizado",
    "indeterminado": "Indeterminado",
}

_INCOME_REAL_ESTATE_STATUS_COLOR = {
    "atrativo": POSITIVE,
    "neutro": INFO,
    "pouco_atrativo": ALERT,
    "indeterminado": NEUTRAL,
}
_INCOME_REAL_ESTATE_STATUS_LABEL = {
    "atrativo": "Atrativo",
    "neutro": "Neutro",
    "pouco_atrativo": "Pouco atrativo",
    "indeterminado": "Indeterminado",
}

# Status de adequação à política de alocação (Portfolio Adequacy Engine,
# ETF/cripto/Tesouro) — nunca "barato/caro" (não há valuation tradicional
# aqui), e sim "espaço para aportar / neutro / acima do alvo / bloqueado".
_ADEQUACY_STATUS_COLOR = {
    "underweight": POSITIVE,
    "neutral": INFO,
    "overweight": ATTENTION,
    "blocked": ALERT,
    "indeterminado": NEUTRAL,
}
_ADEQUACY_STATUS_LABEL = {
    "underweight": "Abaixo do alvo",
    "neutral": "No alvo",
    "overweight": "Acima do alvo",
    "blocked": "Bloqueado",
    "indeterminado": "Indeterminado",
}

# Severidade de flag do Trap Detection Engine (`TRAP_SEVERITIES`).
_TRAP_SEVERITY_COLOR = {"baixa": INFO, "média": ATTENTION, "alta": ALERT}

# Sprint 30 (Product Design / UX Polish, Parte 1) — StatusBadge genérico.
# Cobre os 9 status pedidos explicitamente: bom / atenção / crítico /
# dados insuficientes / atualizado / desatualizado / bloqueado /
# monitorando / candidato. Um vocabulário só, reaproveitado em vez de
# cada tela inventar seu próprio rótulo para a mesma ideia.
_STATUS_COLOR = {
    "bom": POSITIVE,
    "atencao": ATTENTION,
    "critico": ALERT,
    "dados_insuficientes": NEUTRAL,
    "atualizado": POSITIVE,
    "desatualizado": ATTENTION,
    "bloqueado": ALERT,
    "monitorando": INFO,
    "candidato": ATTENTION,
}
_STATUS_LABEL = {
    "bom": "Bom",
    "atencao": "Atenção",
    "critico": "Crítico",
    "dados_insuficientes": "Dados insuficientes",
    "atualizado": "Atualizado",
    "desatualizado": "Desatualizado",
    "bloqueado": "Bloqueado",
    "monitorando": "Monitorando",
    "candidato": "Candidato",
}

# Risco agregado da carteira (`PortfolioRiskService`) — mesma paleta já
# usada ad-hoc no Dashboard antes da Sprint 30, agora centralizada aqui
# para não duplicar o dicionário em cada tela que precisa desse badge.
_RISK_COLOR = {
    "baixo": POSITIVE,
    "moderado": INFO,
    "moderado-alto": ATTENTION,
    "alto": ALERT,
    "indeterminado": NEUTRAL,
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


def valuation_status_badge_html(status: str) -> str:
    """Badge do status do Valuation Engine 2.0 (Sprint 26, Fase 2 — ações)."""
    color = _VALUATION_STATUS_COLOR.get(status, NEUTRAL)
    label = _VALUATION_STATUS_LABEL.get(status, status)
    return _badge_html(label, color)


def income_real_estate_status_badge_html(status: str) -> str:
    """Badge do status da Análise de Renda Imobiliária (Sprint 26, Fase 4 —
    FIIs/REITs)."""
    color = _INCOME_REAL_ESTATE_STATUS_COLOR.get(status, NEUTRAL)
    label = _INCOME_REAL_ESTATE_STATUS_LABEL.get(status, status)
    return _badge_html(label, color)


def adequacy_status_badge_html(status: str) -> str:
    """Badge do status de Adequação de Carteira (Sprint 26, Fase 5 —
    ETF/cripto/Tesouro)."""
    color = _ADEQUACY_STATUS_COLOR.get(status, NEUTRAL)
    label = _ADEQUACY_STATUS_LABEL.get(status, status)
    return _badge_html(label, color)


def trap_severity_badge_html(severity: str) -> str:
    """Badge de severidade de uma flag do Trap Detection Engine (Sprint 26,
    Fase 3/4)."""
    color = _TRAP_SEVERITY_COLOR.get(severity, NEUTRAL)
    return _badge_html(f"Severidade {severity}", color)


def status_badge_html(status: str, label: str | None = None) -> str:
    """StatusBadge genérico (Sprint 30, Parte 1) — aceita as 9 chaves de
    `_STATUS_COLOR` (com ou sem acento/espaço: "dados insuficientes" e
    "dados_insuficientes" resolvem igual) ou um `label` customizado com a
    cor já resolvida pela chave de status."""
    key = status.strip().lower().replace(" ", "_").replace("-", "_")
    # "moderado-alto" (risco) usa hífen de propósito — não normaliza.
    key = "moderado-alto" if status.strip().lower() == "moderado-alto" else key
    color = _STATUS_COLOR.get(key, NEUTRAL)
    return _badge_html(label or _STATUS_LABEL.get(key, status), color)


def risk_badge_html(classification: str) -> str:
    """RiskBadge (Sprint 30, Parte 1) — risco agregado da carteira
    (`PortfolioRiskService.overall_classification`): baixo/moderado/
    moderado-alto/alto/indeterminado."""
    color = _RISK_COLOR.get(classification, NEUTRAL)
    return _badge_html(classification.capitalize(), color)
