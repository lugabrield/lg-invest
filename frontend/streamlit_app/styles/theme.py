"""Paleta e constantes visuais únicas da LG INVEST (Sprint 11; Sprint 21 — tema dark).

Centraliza cores para que cards, tabelas e gráficos (Plotly) usem
sempre a mesma identidade — em vez de cada tela escolher cores soltas.

Sprint 21: a paleta migrou de um tema claro fixo (cards brancos) para um
tema dark fixo, coerente com `.streamlit/config.toml`. Antes, o CSS
forçava fundo branco nos cards mas o texto herdava a cor do tema do
Streamlit — que em navegadores com preferência dark renderiza texto
claro, resultando em texto quase invisível sobre fundo branco (o bug de
contraste relatado). Fixar um tema dark ponta a ponta (config.toml +
esta paleta + custom_css.py) elimina a dependência da preferência do
visitante e garante contraste mínimo AA em todos os textos.
"""

from __future__ import annotations

# Fundo da aplicação (deve bater com [theme] em .streamlit/config.toml).
APP_BACKGROUND = "#0B0F17"
APP_BACKGROUND_SECONDARY = "#11151F"

# Cores de marca / cards.
PRIMARY = "#3B82F6"
PRIMARY_DARK = "#1D4ED8"
PRIMARY_SOFT = "#3B82F633"  # primary com alpha, para destaques sutis

CARD_BACKGROUND = "#151A24"
CARD_BACKGROUND_HOVER = "#1A2130"
BORDER = "#2A3242"
BORDER_SOFT = "#1F2733"

TEXT_PRIMARY = "#E9EDF4"
TEXT_MUTED = "#9AA6B8"
TEXT_FAINT = "#6B7688"

# Compatibilidade com código existente que ainda importa BACKGROUND_SOFT.
BACKGROUND_SOFT = APP_BACKGROUND_SECONDARY

# Semântica (positivo/negativo/neutro) — usada em rentabilidade e diagnóstico.
# Tons ajustados para contraste AA sobre fundo escuro (mais claros/saturados
# que a versão do tema claro original).
POSITIVE = "#3DD68C"
NEGATIVE = "#F0554A"
ATTENTION = "#F5A623"
ALERT = "#F0554A"
INFO = "#3B82F6"
NEUTRAL = "#8B96A8"

SEVERITY_COLORS = {
    "positive": POSITIVE,
    "info": INFO,
    "attention": ATTENTION,
    "alert": ALERT,
}

SEVERITY_ICONS = {
    "positive": "✅",
    "info": "ℹ️",
    "attention": "⚠️",
    "alert": "🚨",
}

# Cores de classificação (LG Conviction Score / Decision Engine) — usadas em
# badges.py e nas telas de Inteligência/Aporte/Ativos.
CLASSIFICATION_COLORS = {
    "strong_buy": POSITIVE,
    "buy": "#7DD69A",
    "hold": INFO,
    "watch": ATTENTION,
    "avoid": NEGATIVE,
    "insufficient_data": NEUTRAL,
}

CLASSIFICATION_LABELS_PT = {
    "strong_buy": "Aportar",
    "buy": "Candidato",
    "hold": "Manter",
    "watch": "Monitorar",
    "avoid": "Evitar",
    "insufficient_data": "Dados insuficientes",
}

# Cores por grupo de ativo (consistentes em todos os gráficos e tabelas).
GROUP_COLORS = {
    "Ações BR": "#3B82F6",
    "FIIs": "#A78BFA",
    "Ações EUA": "#2DD4BF",
    "ETFs": "#F5A623",
    "REITs": "#F0554A",
    "Cripto": "#FACC15",
    "Renda Fixa": "#8B96A8",
}

# Cores por moeda.
CURRENCY_COLORS = {
    "BRL": "#3B82F6",
    "USD": "#2DD4BF",
}

# Paleta de fallback (grupos/moedas não mapeados acima).
FALLBACK_PALETTE = [
    "#3B82F6",
    "#2DD4BF",
    "#A78BFA",
    "#F5A623",
    "#F0554A",
    "#FACC15",
    "#8B96A8",
    "#3DD68C",
]


def color_for(label: str, palette: dict[str, str]) -> str:
    """Cor consistente para um rótulo; cai num fallback determinístico se não mapeado."""
    if label in palette:
        return palette[label]
    index = abs(hash(label)) % len(FALLBACK_PALETTE)
    return FALLBACK_PALETTE[index]


def classification_color(classification: str) -> str:
    """Cor para uma classificação de conviction/decisão; cinza neutro se desconhecida."""
    return CLASSIFICATION_COLORS.get(classification, NEUTRAL)


def classification_label_pt(classification: str) -> str:
    """Rótulo em português para uma classificação; devolve o valor bruto se desconhecida."""
    return CLASSIFICATION_LABELS_PT.get(classification, classification)
