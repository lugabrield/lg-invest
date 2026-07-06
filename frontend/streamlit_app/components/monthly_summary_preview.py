"""Renderização do preview de HISTÓRICO MENSAL de proventos (Sprint 23.3).

Só apresentação: recebe um `IncomeMonthlySyncPreview` já calculado pelo
`IncomeSyncService.build_monthly_preview`/`dry_run_monthly` e desenha
KPIs, diagnóstico por seção e uma amostra do agregado mensal por
carteira. Nenhuma chamada de rede, banco ou Playwright vive aqui.

Fonte: aba "Central de Proventos → Renda Variável → Brasil → Análise"
(tabela ano x mês, uma linha por ano, uma coluna por mês, com um
seletor de carteira, ex.: "Carteira (B3)"/"Carteira Dólar"). Gravado em
`income_monthly_summaries` — nunca em `income_events` (essa tabela é só
para o calendário futuro, ver `income_preview.py`). Os dois nunca devem
ser misturados na mesma seção da tela.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from backend.app.integrations.dividendos_me.schemas import IncomeMonthlySyncPreview
from frontend.streamlit_app.formatting import format_money

_SECTION_LABELS = {
    "income_monthly": "Agregado mensal por carteira (Análise)",
}

_STATUS_LABELS = {
    "recebido": "Recebido",
    "anunciado": "Anunciado (mês corrente/futuro)",
}

_MONTH_LABELS = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Abr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Out",
    11: "Nov",
    12: "Dez",
}


def render_monthly_summary_kpis(preview: IncomeMonthlySyncPreview) -> None:
    cols = st.columns(5)
    cols[0].metric("Meses encontrados", preview.summaries_valid)
    cols[1].metric("Rejeitados", preview.summaries_rejected)
    cols[2].metric("Anos cobertos", len(preview.years_found))
    cols[3].metric("Carteiras", len(preview.wallets_found))
    cols[4].metric("Seções com falha", len(preview.sections_failed))

    if preview.wallets_found:
        st.caption("Carteiras encontradas: " + ", ".join(preview.wallets_found))

    if preview.total_by_currency:
        totals = " · ".join(
            format_money(v, k) for k, v in sorted(preview.total_by_currency.items())
        )
        st.caption(f"Total no histórico extraído: {totals}")


def render_monthly_summary_sections_failed_warning(preview: IncomeMonthlySyncPreview) -> None:
    if not preview.sections_failed:
        return
    labels = ", ".join(_SECTION_LABELS.get(s, s) for s in preview.sections_failed)
    st.warning(
        f"Carteira extraída, mas o histórico mensal de proventos não foi extraído "
        f"completamente: **{labels}**. Isso NÃO bloqueia a sincronização da carteira nem o "
        "calendário futuro — só significa que o histórico mensal ficou incompleto nesta "
        "execução."
    )


def render_monthly_summary_diagnostics(preview: IncomeMonthlySyncPreview) -> None:
    if not preview.diagnostics:
        return
    with st.expander("Diagnóstico da extração do histórico mensal (por seção)"):
        rows = [
            {
                "Seção": _SECTION_LABELS.get(d.section, d.section),
                "Seletor usado": d.selector_used,
                "Linhas brutas": d.raw_rows_detected,
                "Válidas": d.valid_rows,
                "Rejeitadas": d.rejected_rows,
                "Motivo(s) de rejeição": "; ".join(d.rejection_reasons) or "—",
            }
            for d in preview.diagnostics
        ]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_monthly_summary_table(preview: IncomeMonthlySyncPreview) -> None:
    if not preview.sample:
        st.info("Nenhum histórico mensal de proventos encontrado nesta busca.")
        return
    rows = [
        {
            "Carteira": s.wallet_name,
            "Ano": s.year,
            "Mês": _MONTH_LABELS.get(s.month, s.month),
            "Valor": format_money(s.amount_total, s.currency),
            "Status": _STATUS_LABELS.get(s.status, s.status),
            "Total do ano": (
                format_money(s.annual_total, s.currency) if s.annual_total is not None else "—"
            ),
            "Média do ano": (
                format_money(s.annual_average, s.currency) if s.annual_average is not None else "—"
            ),
        }
        for s in preview.sample
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.caption(
        f"Mostrando os primeiros {len(preview.sample)} de {preview.summaries_valid} mês(es) "
        "válido(s) encontrados."
    )


def render_full_monthly_summary_preview(preview: IncomeMonthlySyncPreview) -> None:
    render_monthly_summary_kpis(preview)
    render_monthly_summary_sections_failed_warning(preview)
    render_monthly_summary_diagnostics(preview)
    st.divider()
    st.subheader("Amostra do histórico mensal (Central de Proventos → Análise)")
    render_monthly_summary_table(preview)
