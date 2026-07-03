"""Tabela de posições compartilhada entre Dashboard e Carteira (Sprint 11).

Só renderização: recebe `ConvertedPosition` (já prontas pelo
`dashboard_view_service`) e desenha. Colunas numéricas usam
`column_config` (não strings pré-formatadas) para manter ordenação
correta ao clicar no cabeçalho — pedido explícito do item 4/8 da
Sprint 11.
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
import streamlit as st

from backend.app.schemas.dashboard_view import ConvertedPosition
from frontend.streamlit_app.formatting import format_brl

_ZERO = Decimal("0")

_NUMBER_COLUMN_CONFIG = {
    "Quantidade": st.column_config.NumberColumn(format="%.4f"),
    "Preço médio": st.column_config.NumberColumn(format="%.2f"),
    "Preço atual": st.column_config.NumberColumn(format="%.2f"),
    "Valor (moeda original)": st.column_config.NumberColumn(format="%.2f"),
    "Valor (R$ convertido)": st.column_config.NumberColumn(format="R$ %.2f"),
    "Peso %": st.column_config.NumberColumn(format="%.2f%%"),
    "Rentab. %": st.column_config.NumberColumn(format="%.2f%%"),
}

_PRICE_SOURCE_LABELS = {"yahoo": "Automático", "manual": "Manual", "estimated": "Estimado"}


def _position_row(p: ConvertedPosition, largest_ticker: str | None) -> dict:
    is_negative = p.return_pct is not None and p.return_pct < 0
    return {
        "🏆": "🏆" if p.ticker == largest_ticker else "",
        "Ticker": p.ticker,
        "Grupo": p.group_label,
        "Moeda": p.currency,
        "Quantidade": float(p.quantity),
        "Preço médio": float(p.average_price),
        "Preço atual": float(p.current_price),
        "Origem do preço": _PRICE_SOURCE_LABELS.get(p.price_source, p.price_source),
        "Alerta": "📉 em queda" if is_negative else "",
        "Valor (moeda original)": float(p.position_value),
        "Valor (R$ convertido)": float(p.position_value_brl),
        "Peso %": float(p.weight) * 100,
        "Rentab. %": (float(p.return_pct) * 100) if p.return_pct is not None else None,
    }


def render_positions_table(
    positions: list[ConvertedPosition],
    largest_ticker: str | None = None,
    key: str | None = None,
) -> None:
    """Tabela única com todas as posições, ordenável por qualquer coluna (clique no cabeçalho)."""
    if not positions:
        st.info("Nenhuma posição para exibir.")
        return
    rows = [_position_row(p, largest_ticker) for p in positions]
    st.dataframe(
        pd.DataFrame(rows),
        column_config=_NUMBER_COLUMN_CONFIG,
        width="stretch",
        hide_index=True,
        key=key,
    )


def render_grouped_positions(
    positions: list[ConvertedPosition],
    group_order: list[str],
    largest_ticker: str | None = None,
    expanded: bool = True,
) -> None:
    """Uma tabela por grupo (Ações BR, FIIs, ...), para separar visualmente as classes."""
    for group in group_order:
        group_positions = [p for p in positions if p.group_label == group]
        if not group_positions:
            continue
        group_total = sum((p.position_value_brl for p in group_positions), _ZERO)
        negative_count = sum(
            1 for p in group_positions if p.return_pct is not None and p.return_pct < 0
        )
        suffix = f" · {negative_count} em queda" if negative_count else ""
        with st.expander(f"{group} · {format_brl(group_total)}{suffix}", expanded=expanded):
            render_positions_table(group_positions, largest_ticker, key=f"table_{group}")
