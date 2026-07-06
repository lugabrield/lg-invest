"""Layout Plotly compartilhado para o tema dark da LG INVEST (Sprint 21).

Antes do tema dark, os gráficos Plotly usavam o template padrão
("plotly", fundo branco), destoando do restante do app depois que
`custom_css.py`/`.streamlit/config.toml` passaram a fixar um tema
escuro — resultava em caixas brancas "flutuando" sobre o app escuro,
com pouco contraste entre título/eixos e o próprio card. Esta função é
aplicada por todo `chart_*()` como último passo antes do `return`, para
não duplicar as mesmas oito linhas de `update_layout` em cada gráfico.
"""

from __future__ import annotations

import plotly.graph_objects as go

from frontend.streamlit_app.styles.theme import BORDER, CARD_BACKGROUND, TEXT_MUTED, TEXT_PRIMARY


def apply_dark_layout(fig: go.Figure) -> go.Figure:
    """Aplica o template dark padrão da LG INVEST a uma figura Plotly já montada."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=CARD_BACKGROUND,
        plot_bgcolor=CARD_BACKGROUND,
        font=dict(color=TEXT_PRIMARY, size=12),
        title_font=dict(color=TEXT_PRIMARY, size=14),
        legend=dict(font=dict(color=TEXT_MUTED)),
    )
    fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER, color=TEXT_MUTED)
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER, color=TEXT_MUTED)
    return fig
