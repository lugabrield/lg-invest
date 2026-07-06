"""Renderização do preview de CALENDÁRIO futuro de proventos (Sprint 23.2/23.3).

Só apresentação: recebe um `IncomeSyncPreview` já calculado pelo
`IncomeSyncService` e desenha KPIs, diagnóstico por seção e uma amostra
de eventos. Nenhuma chamada de rede, banco ou Playwright vive aqui.

Desde a Sprint 23.3, este componente cobre exclusivamente o calendário
futuro (aba "Próximos Dividendos", gravado em `income_events`) — o
histórico mensal agregado (aba "Análise", gravado em
`income_monthly_summaries`) tem seu próprio componente,
`monthly_summary_preview.py`. Os dois nunca devem ser misturados na
mesma seção da tela.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from backend.app.integrations.dividendos_me.schemas import IncomeSyncPreview
from frontend.streamlit_app.formatting import format_money

_SECTION_LABELS = {
    "income_calendar": "Calendário de próximos dividendos",
}

_EVENT_TYPE_LABELS = {
    "dividendo": "Dividendo",
    "jcp": "JCP",
    "rendimento_fii": "Rendimento (FII)",
    "amortizacao": "Amortização",
    "outro": "Outro",
}

_STATUS_LABELS = {
    "recebido": "Recebido",
    "provisionado": "Provisionado",
    "anunciado": "Anunciado (futuro)",
    "estimado": "Estimado",
}


def _format_amount(amount, currency: str) -> str:
    return format_money(amount, currency)


def render_income_kpis(preview: IncomeSyncPreview) -> None:
    cols = st.columns(4)
    cols[0].metric("Eventos encontrados", preview.events_valid)
    cols[1].metric("Rejeitados", preview.events_rejected)
    period = (
        f"{preview.period_start.strftime('%d/%m/%Y')} – {preview.period_end.strftime('%d/%m/%Y')}"
        if preview.period_start and preview.period_end
        else "—"
    )
    cols[2].metric("Período coberto", period)
    cols[3].metric("Seções com falha", len(preview.sections_failed))

    if preview.total_by_currency:
        totals = " · ".join(
            f"{_format_amount(v, k)}" for k, v in sorted(preview.total_by_currency.items())
        )
        st.caption(f"Total no período: {totals}")


def render_income_sections_failed_warning(preview: IncomeSyncPreview) -> None:
    if not preview.sections_failed:
        return
    labels = ", ".join(_SECTION_LABELS.get(s, s) for s in preview.sections_failed)
    st.warning(
        f"Carteira extraída, mas proventos não foram extraídos completamente: **{labels}**. "
        "Isso NÃO bloqueia a sincronização da carteira — só significa que o histórico/"
        "calendário de proventos ficou incompleto nesta execução."
    )


def render_income_diagnostics(preview: IncomeSyncPreview) -> None:
    if not preview.diagnostics:
        return
    with st.expander("Diagnóstico da extração de proventos (por seção)"):
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


def render_income_sample_table(preview: IncomeSyncPreview) -> None:
    if not preview.sample:
        st.info("Nenhum provento encontrado nesta busca.")
        return
    rows = [
        {
            "Ticker": s.ticker or "—",
            "Tipo": _EVENT_TYPE_LABELS.get(s.event_type, s.event_type),
            "Status": _STATUS_LABELS.get(s.status, s.status),
            "Data de pagamento": (s.payment_date.strftime("%d/%m/%Y") if s.payment_date else "—"),
            "Valor": _format_amount(s.amount_total, s.currency),
        }
        for s in preview.sample
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.caption(
        f"Mostrando os primeiros {len(preview.sample)} de {preview.events_valid} evento(s) "
        "válido(s) encontrados."
    )


def render_full_income_preview(preview: IncomeSyncPreview) -> None:
    render_income_kpis(preview)
    render_income_sections_failed_warning(preview)
    render_income_diagnostics(preview)
    st.divider()
    st.subheader("Amostra de eventos do calendário futuro")
    render_income_sample_table(preview)
