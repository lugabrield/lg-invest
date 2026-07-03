"""Tela Ativos: cadastro mestre, status de preço, fundamentos e LG Score.

Consome AssetRepository, PriceRepository, FundamentalsRepository e
LGScoreService. Nenhum cálculo financeiro novo vive aqui — só leitura e
formatação, mais o cadastro de preço manual (grava um `Price` normal,
com `source="manual"`), o flag `is_manual` do ativo (Sprint 12) e a
coleta de fundamentos (Sprint 13), que faz a atualização automática em
lote pular esse ativo.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from backend.app.infrastructure.database.models.price import Price
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.infrastructure.repositories.price_repository import PriceRepository
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.services.fundamentals_analysis_service import FundamentalsAnalysisService
from backend.app.services.lg_score_service import LGScoreService
from backend.app.services.valuation_service import ValuationService
from frontend.streamlit_app.components.sections import section
from frontend.streamlit_app.db import session_scope
from frontend.streamlit_app.formatting import format_money, format_number, format_pct

_STATUS_LABELS = {
    "automatic": "🌐 Automático",
    "manual": "✍️ Manual",
    "missing": "📛 Sem preço",
}

# Mesmos campos de backend/app/services/fundamentals_service.py::_SNAPSHOT_FIELDS
# — duplicado deliberadamente para a UI não depender de símbolo interno do serviço.
_FUNDAMENTAL_FIELDS = (
    "roe",
    "roa",
    "net_margin",
    "ebitda_margin",
    "revenue",
    "net_income",
    "ebitda",
    "ebit",
    "free_cash_flow",
    "net_debt",
    "debt_to_ebitda",
    "pe_ratio",
    "pb_ratio",
    "ev_ebitda",
    "dividend_yield",
    "payout_ratio",
    "eps",
    "revenue_per_share",
    "beta",
)


def _price_status(asset, latest_price) -> str:
    if asset.is_manual:
        return "manual"
    if latest_price is None:
        return "missing"
    if latest_price.source == "manual":
        return "manual"
    return "automatic"


def _asset_row(asset, latest_price) -> dict:
    status = _price_status(asset, latest_price)
    updated = (
        latest_price.updated_at.strftime("%d/%m/%Y %H:%M")
        if latest_price is not None and latest_price.updated_at
        else "—"
    )
    price_str = (
        format_money(latest_price.close, asset.currency) if latest_price is not None else "—"
    )
    return {
        "Ticker": asset.ticker,
        "Nome": asset.name,
        "Classe": asset.asset_class,
        "País": asset.country,
        "Moeda": asset.currency,
        "Setor": asset.sector or "—",
        "Preço atual": price_str,
        "Status do preço": _STATUS_LABELS[status],
        "Atualizado em": updated,
    }


def _snapshot_result(ticker: str, snapshot) -> FundamentalSnapshotResult:
    return FundamentalSnapshotResult(
        ticker=ticker,
        period_end=snapshot.period_end,
        source=snapshot.source,
        collected_at=snapshot.updated_at,
        **{field: getattr(snapshot, field) for field in _FUNDAMENTAL_FIELDS},
    )


def render() -> None:
    st.title("Ativos")
    st.caption(
        "Cadastro mestre dos seus ativos: preço atual, status do dado, fundamentos e "
        "LG Score, quando disponível."
    )

    with session_scope() as db:
        assets = AssetRepository(db).list_all()
        prices = PriceRepository(db)
        rows = [_asset_row(a, prices.get_latest(a.id)) for a in assets]

    if not assets:
        st.info("Nenhum ativo cadastrado. Rode o seed ou importe uma carteira.")
        return

    with section("Ativos cadastrados", "🗂️"):
        st.dataframe(
            pd.DataFrame(rows),
            width="stretch",
            hide_index=True,
        )
        missing = [r["Ticker"] for r in rows if r["Status do preço"] == _STATUS_LABELS["missing"]]
        if missing:
            st.warning("Sem nenhum preço cadastrado ainda: " + ", ".join(missing))

    tickers = [a.ticker for a in assets]

    with section("LG Score de um ativo", "🧮"):
        ticker = st.selectbox("Ativo", tickers)
        if st.button("Calcular LG Score"):
            with session_scope() as db:
                result = LGScoreService(db).score_ticker(ticker)

            if result is None:
                st.error("Ativo não encontrado.")
                return

            col1, col2, col3 = st.columns(3)
            col1.metric("LG Score", f"{float(result.lg_score):.1f}")
            col2.metric("Classificação", result.classification)
            col3.metric("Confiança", result.confidence_label)

            st.write(
                f"Qualidade {float(result.quality):.0f} · "
                f"Valuation {float(result.valuation):.0f} · "
                f"Crescimento {float(result.growth):.0f} · "
                f"Risco {float(result.risk):.0f} · "
                f"Alocação {float(result.allocation):.0f}"
            )

            with st.expander("Por que essa nota? (explicação por fator)"):
                for pillar in result.explanation:
                    st.markdown(f"**{pillar.name}** — {float(pillar.score):.0f}")
                    for reason in pillar.reasons:
                        st.caption(f"· {reason}")

    with section(
        "Atualizar preço automático de um ativo",
        "🔄",
        caption=(
            "Usa o Yahoo Finance e requer internet. Ativos marcados como manuais são "
            "ignorados aqui — cadastre o preço deles na seção abaixo."
        ),
    ):
        update_ticker = st.selectbox("Ativo", tickers, key="update_price_ticker")
        if st.button("Atualizar agora"):
            try:
                from backend.app.etl.providers.yahoo_provider import YahooFinanceProvider
                from backend.app.services.market_data_service import MarketDataService

                with session_scope() as db:
                    service = MarketDataService(db, YahooFinanceProvider())
                    result = service.update_asset_prices(update_ticker)
                if result.skipped_manual:
                    st.info(
                        f"{update_ticker} está marcado como manual — cadastre o preço na "
                        "seção 'Cadastrar preço atual manual' abaixo."
                    )
                elif result.error:
                    st.error(f"Não foi possível atualizar {update_ticker}: {result.error}")
                else:
                    st.success(
                        f"{update_ticker} atualizado: +{result.inserted} inserido(s), "
                        f"{result.updated} atualizado(s), {result.rejected} rejeitado(s)."
                    )
            except Exception as exc:  # noqa: BLE001 - mostrar o erro ao usuário no MVP
                st.error(f"Não foi possível atualizar: {exc}")

    with section(
        "Fundamentos",
        "📚",
        caption=(
            "Coleta via Yahoo Finance (proxy MVP, sem custo). Cobertura varia por classe e "
            "ticker — campos ausentes aparecem como indisponível, nunca são inventados."
        ),
    ):
        fund_ticker = st.selectbox("Ativo", tickers, key="fundamentals_ticker")
        col_a, col_b = st.columns(2)
        if col_a.button("Coletar fundamentos deste ativo"):
            try:
                from backend.app.etl.providers.yahoo_fundamentals_provider import (
                    YahooFundamentalsProvider,
                )
                from backend.app.services.fundamentals_service import FundamentalsService

                with session_scope() as db:
                    result = FundamentalsService(db, YahooFundamentalsProvider()).collect_for_asset(
                        fund_ticker
                    )
                if result.collected:
                    st.success(
                        f"Fundamentos de {fund_ticker} coletados (período mais recente: "
                        f"{result.period_end})."
                    )
                elif result.error:
                    st.error(f"Falha ao coletar {fund_ticker}: {result.error}")
                else:
                    st.info(f"{fund_ticker} não coletado: {result.reason}.")
            except Exception as exc:  # noqa: BLE001 - mostrar o erro ao usuário no MVP
                st.error(f"Não foi possível coletar fundamentos: {exc}")

        if col_b.button("Coletar fundamentos de todos os ativos"):
            try:
                from backend.app.etl.providers.yahoo_fundamentals_provider import (
                    YahooFundamentalsProvider,
                )
                from backend.app.services.fundamentals_service import FundamentalsService

                with session_scope() as db:
                    batch = FundamentalsService(db, YahooFundamentalsProvider()).collect_all()
                st.success(
                    f"Coleta em lote concluída: {batch.total_collected} coletado(s), "
                    f"{batch.total_skipped} pulado(s) (manuais/classe não aplicável)."
                )
                if batch.failed:
                    st.warning("Falhas: " + ", ".join(batch.failed))
            except Exception as exc:  # noqa: BLE001 - mostrar o erro ao usuário no MVP
                st.error(f"Não foi possível coletar fundamentos: {exc}")

        with session_scope() as db:
            fund_asset = AssetRepository(db).get_by_ticker(fund_ticker)
            latest_snapshot = (
                FundamentalsRepository(db).get_latest(fund_asset.id) if fund_asset else None
            )
            snapshot_view = (
                _snapshot_result(fund_ticker, latest_snapshot) if latest_snapshot else None
            )

        if snapshot_view is None:
            st.info(f"Nenhum fundamento coletado ainda para {fund_ticker}.")
        else:
            st.caption(
                f"Período de referência: {snapshot_view.period_end.strftime('%d/%m/%Y')} · "
                f"Cobertura: {format_pct(snapshot_view.coverage_pct)} dos indicadores"
            )
            col1, col2, col3 = st.columns(3)
            col1.metric(
                "ROE", format_pct(snapshot_view.roe) if snapshot_view.roe is not None else "—"
            )
            col1.metric(
                "Margem líquida",
                (
                    format_pct(snapshot_view.net_margin)
                    if snapshot_view.net_margin is not None
                    else "—"
                ),
            )
            col2.metric(
                "P/L",
                (
                    format_number(snapshot_view.pe_ratio, 2)
                    if snapshot_view.pe_ratio is not None
                    else "—"
                ),
            )
            col2.metric(
                "P/VP",
                (
                    format_number(snapshot_view.pb_ratio, 2)
                    if snapshot_view.pb_ratio is not None
                    else "—"
                ),
            )
            col3.metric(
                "Dividend Yield",
                (
                    format_pct(snapshot_view.dividend_yield)
                    if snapshot_view.dividend_yield is not None
                    else "—"
                ),
            )
            col3.metric(
                "Dívida/EBITDA",
                (
                    format_number(snapshot_view.debt_to_ebitda, 2)
                    if snapshot_view.debt_to_ebitda is not None
                    else "—"
                ),
            )
            if snapshot_view.missing_fields:
                st.caption("Indisponíveis: " + ", ".join(snapshot_view.missing_fields))

            with session_scope() as db:
                analysis = FundamentalsAnalysisService(db).analyze_ticker(fund_ticker)

            if analysis is not None and analysis.periods_used > 0:
                st.markdown("**Crescimento (CAGR entre períodos coletados)**")
                cagr_col1, cagr_col2, cagr_col3 = st.columns(3)
                cagr_col1.metric(
                    "Receita",
                    format_pct(analysis.revenue_cagr) if analysis.revenue_cagr is not None else "—",
                )
                cagr_col2.metric(
                    "Lucro líquido",
                    (
                        format_pct(analysis.net_income_cagr)
                        if analysis.net_income_cagr is not None
                        else "—"
                    ),
                )
                cagr_col3.metric(
                    "FCF",
                    format_pct(analysis.fcf_cagr) if analysis.fcf_cagr is not None else "—",
                )
                st.caption(
                    f"Tendência de margem: {analysis.margin_trend} · "
                    f"Confiança: {analysis.confidence} · "
                    f"{analysis.periods_used} período(s) usado(s) no cálculo."
                )

            with session_scope() as db:
                valuation = ValuationService(db).evaluate_ticker(fund_ticker)

            if valuation is not None:
                _VALUATION_LABELS = {
                    "barato": "🟢 Barato",
                    "neutro": "🟡 Neutro",
                    "caro": "🔴 Caro",
                    "indeterminado": "⚪ Indeterminado",
                }
                st.markdown("**Valuation por múltiplos (heurística MVP, sem DCF)**")
                st.write(
                    f"{_VALUATION_LABELS.get(valuation.classification, valuation.classification)} "
                    f"· Confiança: {valuation.confidence}"
                )
                if valuation.reason:
                    st.caption(valuation.reason)
                elif valuation.metrics:
                    detalhes = ", ".join(
                        f"{m.label}: {m.verdict}"
                        + (f" ({format_number(m.value, 2)})" if m.value is not None else "")
                        for m in valuation.metrics
                    )
                    st.caption(detalhes)

    with section(
        "Marcar ativo como manual",
        "🏷️",
        caption=(
            "Ativos sem cotação de mercado (ex.: Tesouro Direto) devem ser marcados como "
            "manuais: a atualização automática de preços passa a pular esse ativo, e o "
            "preço é sempre cadastrado por você na seção abaixo."
        ),
    ):
        flag_ticker = st.selectbox("Ativo", tickers, key="manual_flag_ticker")
        with session_scope() as db:
            flag_asset = AssetRepository(db).get_by_ticker(flag_ticker)
            current_flag = flag_asset.is_manual if flag_asset is not None else False
        new_flag = st.checkbox(
            "Este ativo não tem cotação automática",
            value=current_flag,
            key=f"manual_flag_checkbox_{flag_ticker}",
        )
        if st.button("Salvar status manual"):
            with session_scope() as db:
                flag_asset = AssetRepository(db).get_by_ticker(flag_ticker)
                if flag_asset is None:
                    st.error("Ativo não encontrado.")
                else:
                    flag_asset.is_manual = new_flag
                    db.commit()
                    estado = "manual" if new_flag else "automático"
                    st.success(f"{flag_ticker} marcado como {estado}.")

    with section(
        "Cadastrar preço atual manual",
        "✍️",
        caption=(
            "Para ativos sem cotação via Yahoo Finance (ex.: Tesouro Direto). Grava um preço "
            "com origem 'manual' na data de hoje — Dashboard e Carteira passam a mostrá-lo "
            "como preço real, não como estimativa."
        ),
    ):
        manual_ticker = st.selectbox("Ativo", tickers, key="manual_price_ticker")
        manual_price_str = st.text_input("Preço atual", key="manual_price_value")
        if st.button("Salvar preço manual"):
            try:
                manual_price = Decimal(manual_price_str.replace(",", "."))
                if manual_price <= 0:
                    raise ValueError("o preço deve ser maior que zero.")
            except (InvalidOperation, ValueError) as exc:
                st.error(f"Preço inválido: {exc}")
            else:
                with session_scope() as db:
                    asset = AssetRepository(db).get_by_ticker(manual_ticker)
                    if asset is None:
                        st.error("Ativo não encontrado.")
                    else:
                        today = date.today()
                        price_repo = PriceRepository(db)
                        existing = price_repo.get_by_asset_and_date(asset.id, today)
                        if existing is not None:
                            existing.close = manual_price
                            existing.source = "manual"
                            db.commit()
                        else:
                            price_repo.create(
                                Price(
                                    asset_id=asset.id,
                                    date=today,
                                    close=manual_price,
                                    source="manual",
                                )
                            )
                        st.success(
                            f"Preço atual de {manual_ticker} salvo: {manual_price} (manual)."
                        )
