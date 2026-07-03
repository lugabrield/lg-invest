"""Tela Carteira: posições importadas, organizadas para leitura rápida.

Consome PositionRepository (importação) e dashboard_view_service (para
mostrar as posições já com peso, grupo, rentabilidade e origem do
preço — os mesmos dados do Dashboard, reaproveitados via o componente
`components/tables.py`). Nenhum cálculo novo vive aqui.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from backend.app.infrastructure.database.models.portfolio import Portfolio
from backend.app.infrastructure.repositories.portfolio_repository import PortfolioRepository
from backend.app.services import fx_settings_service
from backend.app.services.dashboard_view_service import GROUP_ORDER, build_dashboard_view
from backend.app.services.portfolio_import_service import PortfolioImportService
from frontend.streamlit_app.components.sections import section
from frontend.streamlit_app.components.tables import (
    render_grouped_positions,
    render_positions_table,
)
from frontend.streamlit_app.db import session_scope
from frontend.streamlit_app.formatting import format_brl


def _ensure_portfolio(db, portfolio_id: int) -> Portfolio:
    repo = PortfolioRepository(db)
    portfolio = repo.get_by_id(portfolio_id)
    if portfolio is None:
        portfolio = repo.create(Portfolio(name=f"Carteira {portfolio_id}"))
    return portfolio


def render(portfolio_id: int) -> None:
    st.title("Carteira")

    exchange_rate = fx_settings_service.get_usd_brl_rate()
    with session_scope() as db:
        _ensure_portfolio(db, portfolio_id)
        view = build_dashboard_view(db, portfolio_id, exchange_rate)

    if view.positions:
        brazil_positions = [p for p in view.positions if p.currency == "BRL"]
        international_positions = [p for p in view.positions if p.currency != "BRL"]
        brazil_total = sum((p.position_value_brl for p in brazil_positions), view.total_brl * 0)
        international_total = view.total_converted_brl - brazil_total

        with section("Posições atuais", "📌"):
            col1, col2 = st.columns(2)
            col1.metric(
                f"Brasil (BRL) · {len(brazil_positions)} posições", format_brl(brazil_total)
            )
            col2.metric(
                f"Exterior · {len(international_positions)} posições",
                format_brl(international_total),
            )
            st.caption(
                "Clique no cabeçalho de uma coluna para ordenar por valor, peso, rentabilidade ou grupo."
            )
            render_positions_table(view.positions, view.largest_position_ticker)

            st.subheader("Agrupado por classe")
            render_grouped_positions(view.positions, GROUP_ORDER, view.largest_position_ticker)

            if view.estimated_price_tickers:
                st.warning(
                    "Sem cotação automática (usando preço médio como estimativa): "
                    + ", ".join(view.estimated_price_tickers)
                )
    else:
        with section("Posições atuais", "📌"):
            st.info("Nenhuma posição ainda. Importe um arquivo abaixo.")

    st.divider()
    with section("Importar posições (CSV ou Excel)", "📤"):
        st.caption(
            "Colunas esperadas: ticker, quantity, average_price, currency, opened_at. "
            "O ativo precisa estar cadastrado antes. Reimportar atualiza (não duplica)."
        )
        uploaded = st.file_uploader("Arquivo", type=["csv", "xlsx", "xls"])
        if uploaded is not None and st.button("Importar"):
            suffix = Path(uploaded.name).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.getbuffer())
                tmp_path = tmp.name
            with session_scope() as db:
                _ensure_portfolio(db, portfolio_id)
                result = PortfolioImportService(db).import_positions(portfolio_id, tmp_path)
            Path(tmp_path).unlink(missing_ok=True)

            st.subheader("Resumo da importação")
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Importadas", result.imported)
            col_b.metric("Atualizadas", result.updated)
            col_c.metric("Ignoradas", result.skipped)

            if result.errors:
                st.error(
                    f"{len(result.errors)} linha(s) com erro — corrija e reimporte. "
                    "Nenhuma posição válida foi perdida por causa das linhas com erro."
                )
                st.dataframe(
                    [e.as_dict() for e in result.errors],
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.success("Importação concluída sem erros.")
