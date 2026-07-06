"""Renderização do preview de sincronização externa (Sprint 23).

Só apresentação: recebe um `SyncPreview` já calculado pelo
`DividendosMeSyncService` e desenha KPIs, diff e tabela de posições.
Nenhuma chamada de rede, banco ou Playwright vive aqui.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from backend.app.integrations.dividendos_me.schemas import SyncPreview
from backend.app.integrations.dividendos_me.service import (
    EXTRACTION_INCOMPLETE_SECTIONS_MESSAGE,
    EXTRACTION_INVALID_MESSAGE,
    extraction_blocking_reasons,
    has_section_gap,
    strong_alert_sections,
)
from frontend.streamlit_app.formatting import format_brl, format_pct, format_quantity

_SECTION_LABELS = {
    "brasil": "Brasil (Renda Variável)",
    "eua": "EUA (Renda Variável)",
    "criptomoedas": "Criptomoedas",
    "renda_fixa": "Renda Fixa",
}

_STATUS_LABELS = {
    "success": "Sucesso",
    "partial": "Parcial",
    "failed": "Falhou",
}


def render_sync_kpis(preview: SyncPreview) -> None:
    cols = st.columns(5)
    patrimonio_label = (
        "Patrimônio encontrado"
        if preview.total_patrimonio_status == "consolidated"
        else "Patrimônio encontrado (PARCIAL)"
    )
    cols[0].metric("Status da extração", _STATUS_LABELS.get(preview.status, preview.status))
    cols[1].metric(patrimonio_label, format_brl(preview.total_patrimonio))
    cols[2].metric("Ativos válidos encontrados", preview.total_assets)
    cols[3].metric("Para revisão manual", len(preview.review_required_tickers))
    cols[4].metric("Seções com falha", len(preview.sections_failed))

    if preview.sections_expected:
        expected_labels = ", ".join(_SECTION_LABELS.get(s, s) for s in preview.sections_expected)
        st.caption(f"Seções esperadas (com base na carteira atual): {expected_labels}")

    if preview.total_patrimonio_status == "partial":
        st.warning(
            "O patrimônio total acima é **parcial**, não consolidado: uma ou mais seções "
            "esperadas não vieram nesta extração. Não trate este valor como o patrimônio "
            "total real da carteira até que todas as seções esperadas sejam extraídas com "
            "sucesso."
        )

    if preview.status == "failed":
        st.error(
            "A extração falhou: não há ativos válidos suficientes para confiar neste "
            "preview. Não confirme nenhuma substituição/atualização com este resultado — "
            "rode novamente ou investigue antes."
        )
    elif preview.status == "partial":
        st.warning(
            "A extração ficou parcial: poucos ativos válidos e/ou alguma seção falhou. "
            "Revise com atenção antes de confirmar qualquer alteração."
        )


def render_sections_failed_warning(preview: SyncPreview) -> None:
    if not preview.sections_failed:
        return
    labels = ", ".join(_SECTION_LABELS.get(s, s) for s in preview.sections_failed)
    strong = strong_alert_sections(preview)
    message = (
        f"Não foi possível extrair: **{labels}**. Os ativos dessas seções não aparecem "
        "neste preview e, se você confirmar a substituição agora, as posições "
        "correspondentes que já existem na LG INVEST serão removidas sem substituto "
        "(o Dividendos.me não retornou dado nenhum para elas nesta execução). "
        "Recomendado: rode novamente antes de confirmar, ou substitua só depois de "
        "confirmar que essas seções voltaram a funcionar."
    )
    if strong:
        strong_labels = ", ".join(_SECTION_LABELS.get(s, s) for s in strong)
        st.error(
            f"⚠️ Atenção especial: **{strong_labels}** falhou nesta extração. Essas seções "
            "guardam ativos que normalmente não aparecem em nenhum outro lugar do preview "
            "(Criptomoedas/Renda Fixa não têm sobreposição com Brasil/EUA) — confirmar "
            "agora arrisca remover esses ativos da carteira sem qualquer substituto.\n\n" + message
        )
    else:
        st.warning(message)


def render_diagnostics(preview: SyncPreview) -> None:
    """Prioridade 4 do usuário: diagnóstico por seção — linhas brutas
    detectadas, válidas, rejeitadas, motivo e seletor usado. Nunca mostra
    HTML bruto nem qualquer dado sensível, só contagens e motivos já
    sanitizados (vêm de `NormalizedTicker.review_reason`)."""
    if not preview.diagnostics:
        return
    with st.expander("Diagnóstico da extração (por seção)"):
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


def render_safety_block_warning(preview: SyncPreview, *, mode: str) -> list[str]:
    """Mostra (se houver) os motivos que bloqueariam `replace`/`update` com
    este preview, usando exatamente a mesma lógica do `service.py` — devolve
    a lista de motivos para a tela decidir se desabilita o botão de
    confirmação (Prioridade 1/5: nunca substituir com extração inválida)."""
    reasons = extraction_blocking_reasons(preview, mode=mode)
    if reasons:
        message = (
            EXTRACTION_INCOMPLETE_SECTIONS_MESSAGE
            if mode == "replace" and has_section_gap(preview)
            else EXTRACTION_INVALID_MESSAGE
        )
        st.error(f"**{message}**\n\nMotivo(s):\n" + "\n".join(f"- {r}" for r in reasons))
    return reasons


def render_review_required_warning(preview: SyncPreview) -> None:
    if not preview.review_required_tickers:
        return
    st.warning(
        "Ativos que não puderam ser classificados automaticamente e por isso **não serão "
        "criados/atualizados** em nenhum modo (ficam de fora da substituição até revisão "
        "manual): " + ", ".join(preview.review_required_tickers)
    )


def render_diff_summary(preview: SyncPreview) -> None:
    diff = preview.diff
    cols = st.columns(4)
    cols[0].metric("Mantidos", len(diff.kept))
    cols[1].metric("Serão atualizados", len(diff.updated))
    cols[2].metric("Novos ativos", len(diff.created))
    cols[3].metric("Serão removidos (replace)", len(diff.missing_in_source))

    with st.expander("Detalhe do diff por ticker"):
        if diff.kept:
            st.write("**Mantidos (sem mudança):** " + ", ".join(diff.kept))
        if diff.updated:
            st.write("**Serão atualizados:** " + ", ".join(diff.updated))
        if diff.created:
            st.write("**Novos (serão criados):** " + ", ".join(diff.created))
        if diff.missing_in_source:
            st.write(
                "**Existem na LG INVEST mas não vieram do Dividendos.me — "
                "serão removidos apenas no modo replace:** " + ", ".join(diff.missing_in_source)
            )


def render_positions_preview_table(preview: SyncPreview) -> None:
    if not preview.positions:
        st.info("Nenhuma posição encontrada no Dividendos.me.")
        return

    rows = []
    for p in preview.positions:
        rows.append(
            {
                "Revisar?": "⚠️" if p.review_required else "",
                "Ticker": p.ticker,
                "Classe": p.asset_class,
                "Moeda": p.currency,
                "Quantidade": format_quantity(p.quantity, p.asset_class, p.currency),
                "Preço médio": format_brl(p.average_price) if p.average_price is not None else "—",
                "Preço atual": format_brl(p.current_price) if p.current_price is not None else "—",
                "Valor atual": format_brl(p.current_value) if p.current_value is not None else "—",
                "Rentab. %": (
                    format_pct(p.return_pct, signed=True) if p.return_pct is not None else "—"
                ),
                "Origem": p.origin,
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)


def render_full_preview(preview: SyncPreview) -> None:
    render_sync_kpis(preview)
    render_sections_failed_warning(preview)
    render_review_required_warning(preview)
    render_diagnostics(preview)
    st.divider()
    st.subheader("Diferença em relação à LG INVEST hoje")
    render_diff_summary(preview)
    st.divider()
    st.subheader("Posições encontradas no Dividendos.me")
    render_positions_preview_table(preview)
