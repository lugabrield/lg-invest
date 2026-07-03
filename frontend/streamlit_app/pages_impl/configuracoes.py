"""Tela Configurações: informações do ambiente, câmbio e atualização de preços.

Câmbio e preços via provedores externos (BCB, Yahoo Finance) requerem
internet; por isso são ações explícitas, com aviso e fallback visível.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

import streamlit as st

from backend.app.core.config import settings
from backend.app.infrastructure.database.models.asset import ASSET_CLASSES
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.services import fx_settings_service, target_allocation_settings_service
from frontend.streamlit_app.db import session_scope

_FX_SOURCE_LABELS = {"bcb": "BCB (PTAX)", "yahoo": "Yahoo Finance", "manual": "Manual"}

# Mascara usuário:senha em URLs de banco (ex.: postgresql+psycopg2://user:pass@host/db)
# antes de exibir na tela — a URL real pode conter credenciais de produção
# (Supabase) e esta tela é visível em qualquer app publicado (Sprint 20).
_DB_URL_CREDENTIALS_RE = re.compile(r"://([^:/@]+):([^@/]+)@")


def _redact_database_url(url: str) -> str:
    return _DB_URL_CREDENTIALS_RE.sub(r"://\1:***@", url)


def render(portfolio_id: int) -> None:
    st.title("Configurações")

    st.subheader("Ambiente")
    st.write(f"Ambiente: `{settings.environment}`")
    st.write(f"Banco de dados: `{_redact_database_url(settings.database_url)}`")
    st.write(f"Carteira ativa: `{portfolio_id}`")

    with session_scope() as db:
        n_assets = len(AssetRepository(db).list_all())
    st.write(f"Ativos cadastrados: **{n_assets}**")

    st.divider()
    st.subheader("Câmbio USD/BRL")
    st.caption(
        "Câmbio usado apenas para exibição no Dashboard (converter posições em "
        "USD para BRL). Não afeta Decision Engine, LG Score nem o Portfolio Engine. "
        "Fonte automática: BCB PTAX -> Yahoo Finance -> última cotação salva."
    )

    quote = fx_settings_service.get_fx_quote()
    current_rate = fx_settings_service.get_usd_brl_rate()
    if quote is not None:
        source_label = _FX_SOURCE_LABELS.get(quote.source, quote.source)
        st.write(
            f"Câmbio em uso: **{float(quote.rate):.4f}** · Fonte: **{source_label}** · "
            f"Atualizado em: {quote.fetched_at.strftime('%d/%m/%Y %H:%M')}"
        )
    else:
        st.write(
            f"Câmbio em uso: **{float(current_rate):.4f}** (padrão, ainda sem histórico salvo)"
        )

    if st.button("Atualizar câmbio automático"):
        try:
            from backend.app.services.fx_service import update_usd_brl_rate

            new_quote = update_usd_brl_rate()
            source_label = _FX_SOURCE_LABELS.get(new_quote.source, new_quote.source)
            st.success(f"Câmbio atualizado: {float(new_quote.rate):.4f} via {source_label}.")
        except Exception as exc:  # noqa: BLE001 - mostrar o erro ao usuário no MVP
            st.error(f"Não foi possível atualizar o câmbio automaticamente: {exc}")

    with st.expander("Sobrescrever câmbio manualmente"):
        new_rate_str = st.text_input(
            "Câmbio USD/BRL",
            value=f"{current_rate:.4f}",
            help="Ex.: 5.35 significa 1 USD = R$ 5,35.",
        )
        if st.button("Salvar câmbio manual"):
            try:
                new_rate = Decimal(new_rate_str.replace(",", "."))
                fx_settings_service.set_usd_brl_rate(new_rate)
                st.success(f"Câmbio USD/BRL atualizado manualmente para {new_rate:.4f}.")
            except (InvalidOperation, ValueError) as exc:
                st.error(f"Câmbio inválido: {exc}")

    st.divider()
    st.subheader("Atualizar preços de mercado")
    st.caption(
        "Usa o Yahoo Finance e requer conexão à internet. A coleta é incremental e não "
        "duplica preços. Ativos marcados como manuais (ex.: Tesouro Direto) são pulados — "
        "cadastre o preço deles na tela Ativos."
    )
    if st.button("Atualizar preços agora"):
        try:
            from backend.app.etl.providers.yahoo_provider import YahooFinanceProvider
            from backend.app.services.market_data_service import MarketDataService

            with session_scope() as db:
                service = MarketDataService(db, YahooFinanceProvider())
                batch = service.update_all_active()
            st.success(
                f"Preços atualizados. Inseridos: {batch.total_inserted} · "
                f"Atualizados: {batch.total_updated} · "
                f"Manuais pulados: {batch.total_skipped_manual}"
            )
            if batch.failed:
                st.warning("Falhas: " + ", ".join(batch.failed))
        except Exception as exc:  # noqa: BLE001 - mostrar o erro ao usuário no MVP
            st.error(f"Não foi possível atualizar os preços: {exc}")

    st.divider()
    st.subheader("Alocação-alvo por classe")
    st.caption(
        "Meta pessoal de alocação por classe de ativo (Sprint 17). Não existe alocação "
        "padrão embutida: enquanto você não salvar uma meta, o Target Allocation Engine "
        "não compara nada — ele nunca inventa uma alocação 'recomendada'. As porcentagens "
        "devem somar 100%."
    )

    current_target = target_allocation_settings_service.get_target_allocation()
    if current_target:
        st.write(
            "Meta atual: "
            + ", ".join(
                f"{cls}: {float(current_target.get(cls, 0)) * 100:.1f}%" for cls in ASSET_CLASSES
            )
        )
    else:
        st.write("Nenhuma meta de alocação configurada ainda.")

    with st.expander("Definir/editar alocação-alvo"):
        inputs: dict[str, float] = {}
        for asset_class in ASSET_CLASSES:
            default_pct = float(current_target.get(asset_class, Decimal("0"))) * 100
            inputs[asset_class] = st.number_input(
                asset_class,
                min_value=0.0,
                max_value=100.0,
                value=default_pct,
                step=1.0,
                key=f"target_allocation_{asset_class}",
            )
        total_pct = sum(inputs.values())
        st.caption(f"Soma atual: {total_pct:.1f}%")

        if st.button("Salvar alocação-alvo"):
            try:
                allocation = {
                    asset_class: Decimal(str(pct / 100)) for asset_class, pct in inputs.items()
                }
                target_allocation_settings_service.set_target_allocation(allocation)
                st.success("Alocação-alvo salva.")
            except ValueError as exc:
                st.error(str(exc))

        if st.button("Limpar meta de alocação"):
            target_allocation_settings_service.clear_target_allocation()
            st.success("Meta de alocação removida.")
