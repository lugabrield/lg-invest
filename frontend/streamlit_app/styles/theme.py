"""Paleta e constantes visuais únicas da LG INVEST (Sprint 11).

Centraliza cores para que cards, tabelas e gráficos (Plotly) usem
sempre a mesma identidade — em vez de cada tela escolher cores soltas.
"""

from __future__ import annotations

# Cores de marca / fundo.
PRIMARY = "#1F6FEB"
PRIMARY_DARK = "#0B3D91"
BACKGROUND_SOFT = "#F5F7FA"
CARD_BACKGROUND = "#FFFFFF"
BORDER = "#E3E8EF"
TEXT_MUTED = "#5B6472"

# Semântica (positivo/negativo/neutro) — usada em rentabilidade e diagnóstico.
POSITIVE = "#1B8A5A"
NEGATIVE = "#D0402B"
ATTENTION = "#C98A0A"
ALERT = "#D0402B"
INFO = "#1F6FEB"
NEUTRAL = "#8A93A3"

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

# Cores por grupo de ativo (consistentes em todos os gráficos e tabelas).
GROUP_COLORS = {
    "Ações BR": "#1F6FEB",
    "FIIs": "#8E44AD",
    "Ações EUA": "#12A594",
    "ETFs": "#E67E22",
    "REITs": "#C0392B",
    "Cripto": "#F1B60B",
    "Renda Fixa": "#5B6472",
}

# Cores por moeda.
CURRENCY_COLORS = {
    "BRL": "#1F6FEB",
    "USD": "#12A594",
}

# Paleta de fallback (grupos/moedas não mapeados acima).
FALLBACK_PALETTE = [
    "#1F6FEB",
    "#12A594",
    "#8E44AD",
    "#E67E22",
    "#C0392B",
    "#F1B60B",
    "#5B6472",
    "#2ECC71",
]


def color_for(label: str, palette: dict[str, str]) -> str:
    """Cor consistente para um rótulo; cai num fallback determinístico se não mapeado."""
    if label in palette:
        return palette[label]
    index = abs(hash(label)) % len(FALLBACK_PALETTE)
    return FALLBACK_PALETTE[index]
