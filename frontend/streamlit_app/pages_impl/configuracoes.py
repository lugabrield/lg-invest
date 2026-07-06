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
from backend.app.infrastructure.database.models.investment_policy import RISK_TOLERANCES
from backend.app.infrastructure.database.models.target_allocation_rule import (
    TARGET_ALLOCATION_DIMENSIONS,
)
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.schemas.investment_policy import InvestmentPolicyUpdate
from backend.app.services import (
    fx_settings_service,
    simulation_assumptions_service,
    target_allocation_settings_service,
)
from backend.app.services.investment_policy_service import InvestmentPolicyService
from backend.app.services.target_allocation_rule_service import TargetAllocationRuleService
from frontend.streamlit_app.cache import clear_all_caches
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
            clear_all_caches()
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
                clear_all_caches()
                st.success("Alocação-alvo salva.")
            except ValueError as exc:
                st.error(str(exc))

        if st.button("Limpar meta de alocação"):
            target_allocation_settings_service.clear_target_allocation()
            clear_all_caches()
            st.success("Meta de alocação removida.")

    st.divider()
    _render_investment_policy_section(portfolio_id)

    st.divider()
    _render_target_allocation_rules_section(portfolio_id)

    st.divider()
    _render_simulation_assumptions_section()


def _render_investment_policy_section(portfolio_id: int) -> None:
    """Investment Policy (Sprint 24, Fase 3) — perfil e limites usados como
    guardrails pelo Decision Engine e (no futuro) pelo Simulation Engine.
    Os valores exibidos na primeira vez são um PONTO DE PARTIDA sugerido com
    base no perfil descrito pelo usuário, nunca uma recomendação financeira
    — e sempre editáveis aqui."""
    st.subheader("Política de investimento")
    st.caption(
        "Perfil, limites e parâmetros que orientam o Decision Engine e o Target "
        "Allocation Engine. Isto NÃO é uma recomendação financeira — é a sua própria "
        "configuração, com um ponto de partida sugerido na primeira vez que esta tela "
        "é aberta. Edite livremente."
    )

    with session_scope() as db:
        service = InvestmentPolicyService(db)
        policy = service.get_or_create(portfolio_id)

    with st.expander("Ver / editar política de investimento", expanded=False):
        if policy.notes:
            st.info(policy.notes)

        col1, col2 = st.columns(2)
        with col1:
            investor_profile = st.text_input("Perfil do investidor", value=policy.investor_profile)
            horizon_years = st.number_input(
                "Horizonte (anos)", min_value=1, max_value=100, value=policy.horizon_years
            )
            base_currency = st.text_input("Moeda base", value=policy.base_currency, max_chars=3)
            risk_tolerance = st.selectbox(
                "Tolerância a risco",
                options=list(RISK_TOLERANCES),
                index=(
                    list(RISK_TOLERANCES).index(policy.risk_tolerance)
                    if policy.risk_tolerance in RISK_TOLERANCES
                    else 0
                ),
            )
            rebalance_threshold = st.number_input(
                "Limiar de rebalanceamento (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(policy.rebalance_threshold) * 100,
                step=1.0,
            )
            monthly_contribution_default = st.number_input(
                "Aporte mensal padrão",
                min_value=0.0,
                value=float(policy.monthly_contribution_default),
                step=100.0,
            )
        with col2:
            max_asset_weight = st.number_input(
                "Peso máximo por ativo (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(policy.max_asset_weight) * 100,
                step=1.0,
            )
            max_crypto_weight = st.number_input(
                "Peso máximo em cripto (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(policy.max_crypto_weight) * 100,
                step=1.0,
            )
            target_international_min = st.number_input(
                "Exposição internacional mínima (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(policy.target_international_min) * 100,
                step=1.0,
            )
            target_international_max = st.number_input(
                "Exposição internacional máxima (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(policy.target_international_max) * 100,
                step=1.0,
            )
            target_fii_max = st.number_input(
                "Peso máximo em FIIs (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(policy.target_fii_max) * 100,
                step=1.0,
            )

        st.caption("Metas de referência por classe/mercado (informativas)")
        col3, col4, col5 = st.columns(3)
        with col3:
            target_brazil_equity = st.number_input(
                "Ações BR (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(policy.target_brazil_equity) * 100,
                step=1.0,
            )
            target_us_equity = st.number_input(
                "Ações EUA (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(policy.target_us_equity) * 100,
                step=1.0,
            )
        with col4:
            target_etf = st.number_input(
                "ETFs (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(policy.target_etf) * 100,
                step=1.0,
            )
            target_reit = st.number_input(
                "REITs (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(policy.target_reit) * 100,
                step=1.0,
            )
        with col5:
            target_fixed_income = st.number_input(
                "Renda fixa (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(policy.target_fixed_income) * 100,
                step=1.0,
            )

        notes = st.text_area("Notas", value=policy.notes or "")

        if st.button("Salvar política de investimento"):
            update = InvestmentPolicyUpdate(
                investor_profile=investor_profile,
                horizon_years=int(horizon_years),
                base_currency=base_currency.upper(),
                risk_tolerance=risk_tolerance,
                max_asset_weight=Decimal(str(max_asset_weight / 100)),
                max_crypto_weight=Decimal(str(max_crypto_weight / 100)),
                target_international_min=Decimal(str(target_international_min / 100)),
                target_international_max=Decimal(str(target_international_max / 100)),
                target_fii_max=Decimal(str(target_fii_max / 100)),
                target_brazil_equity=Decimal(str(target_brazil_equity / 100)),
                target_us_equity=Decimal(str(target_us_equity / 100)),
                target_etf=Decimal(str(target_etf / 100)),
                target_reit=Decimal(str(target_reit / 100)),
                target_fixed_income=Decimal(str(target_fixed_income / 100)),
                rebalance_threshold=Decimal(str(rebalance_threshold / 100)),
                monthly_contribution_default=Decimal(str(monthly_contribution_default)),
                notes=notes or None,
            )
            with session_scope() as db:
                InvestmentPolicyService(db).update(portfolio_id, update)
            clear_all_caches()
            st.success("Política de investimento salva.")


def _render_target_allocation_rules_section(portfolio_id: int) -> None:
    """Target Allocation Rules v2 (Sprint 24, Fase 3) — metas granulares por
    classe, moeda, país ou ativo individual. Nenhuma regra é pré-cadastrada
    com valor inventado: a lista começa vazia até o usuário configurar."""
    st.subheader("Alocação-alvo detalhada (classe / moeda / país / ativo)")
    st.caption(
        "Metas granulares por dimensão (Sprint 24). Cada regra vale para UMA dimensão "
        "só (nunca mistura classe com moeda, por exemplo). Nenhuma regra existe até você "
        "cadastrar — a LG INVEST nunca inventa uma meta 'recomendada'. Usado pelo Target "
        "Allocation Engine v2 para calcular gap e prioridade de aporte, nunca para "
        "recomendar venda."
    )

    with session_scope() as db:
        rules = TargetAllocationRuleService(db).list_rules(portfolio_id)

    if rules:
        st.table(
            [
                {
                    "Dimensão": r.dimension_type,
                    "Chave": r.dimension_key,
                    "Mín.": (
                        f"{float(r.min_weight) * 100:.1f}%" if r.min_weight is not None else "—"
                    ),
                    "Alvo": (
                        f"{float(r.target_weight) * 100:.1f}%"
                        if r.target_weight is not None
                        else "—"
                    ),
                    "Máx.": (
                        f"{float(r.max_weight) * 100:.1f}%" if r.max_weight is not None else "—"
                    ),
                    "Prioridade": r.priority,
                }
                for r in rules
            ]
        )
    else:
        st.write("Nenhuma regra de alocação detalhada configurada ainda.")

    with st.expander("Adicionar / editar regra"):
        dimension_type = st.selectbox(
            "Dimensão", options=list(TARGET_ALLOCATION_DIMENSIONS), key="rule_dimension_type"
        )
        dimension_key = st.text_input("Chave (ex.: fii, USD, BR, VOO)", key="rule_dimension_key")
        rcol1, rcol2, rcol3, rcol4 = st.columns(4)
        with rcol1:
            min_pct = st.number_input(
                "Mín. (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0, key="rule_min"
            )
        with rcol2:
            target_pct = st.number_input(
                "Alvo (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0, key="rule_target"
            )
        with rcol3:
            max_pct = st.number_input(
                "Máx. (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0, key="rule_max"
            )
        with rcol4:
            priority = st.number_input(
                "Prioridade", min_value=0, max_value=100, value=0, step=1, key="rule_priority"
            )

        if st.button("Salvar regra"):
            try:
                with session_scope() as db:
                    TargetAllocationRuleService(db).set_rule(
                        portfolio_id,
                        dimension_type=dimension_type,
                        dimension_key=dimension_key,
                        min_weight=Decimal(str(min_pct / 100)) if min_pct > 0 else None,
                        target_weight=Decimal(str(target_pct / 100)) if target_pct > 0 else None,
                        max_weight=Decimal(str(max_pct / 100)) if max_pct > 0 else None,
                        priority=int(priority),
                    )
                clear_all_caches()
                st.success(f"Regra salva: {dimension_type}={dimension_key}.")
            except ValueError as exc:
                st.error(str(exc))

        st.caption("Remover regra existente")
        rem_col1, rem_col2 = st.columns(2)
        with rem_col1:
            rem_dimension_type = st.selectbox(
                "Dimensão a remover",
                options=list(TARGET_ALLOCATION_DIMENSIONS),
                key="rule_remove_dimension_type",
            )
        with rem_col2:
            rem_dimension_key = st.text_input("Chave a remover", key="rule_remove_dimension_key")
        if st.button("Remover regra"):
            with session_scope() as db:
                removed = TargetAllocationRuleService(db).delete_rule(
                    portfolio_id, rem_dimension_type, rem_dimension_key
                )
            if removed:
                clear_all_caches()
                st.success("Regra removida.")
            else:
                st.warning("Nenhuma regra encontrada com essa dimensão/chave.")


def _render_simulation_assumptions_section() -> None:
    """Premissas de retorno/volatilidade do Monte Carlo Simulation Engine
    (Sprint 24, Fase 5), reaproveitadas pelo fator de volatilidade do
    Portfolio Risk Engine (Fase 6). Defaults didáticos de longo prazo,
    nunca dados históricos reais coletados — sempre editáveis aqui."""
    st.subheader("Premissas do Monte Carlo (retorno e volatilidade por classe)")
    st.caption(simulation_assumptions_service.DISCLAIMER)

    assumptions = simulation_assumptions_service.get_all_assumptions()
    st.table(
        [
            {
                "Classe": asset_class,
                "Retorno esperado/ano": f"{float(a.expected_return) * 100:.1f}%",
                "Volatilidade/ano": f"{float(a.volatility) * 100:.1f}%",
                "Origem": a.source,
            }
            for asset_class, a in assumptions.items()
        ]
    )

    with st.expander("Editar premissa de uma classe"):
        asset_class = st.selectbox(
            "Classe", options=list(ASSET_CLASSES), key="sim_assumption_class"
        )
        current = assumptions[asset_class]
        col1, col2 = st.columns(2)
        with col1:
            expected_return_pct = st.number_input(
                "Retorno esperado/ano (%)",
                value=float(current.expected_return) * 100,
                step=0.5,
                key="sim_assumption_return",
            )
        with col2:
            volatility_pct = st.number_input(
                "Volatilidade/ano (%)",
                min_value=0.0,
                value=float(current.volatility) * 100,
                step=0.5,
                key="sim_assumption_volatility",
            )

        col3, col4 = st.columns(2)
        with col3:
            if st.button("Salvar premissa"):
                try:
                    simulation_assumptions_service.set_assumption(
                        asset_class,
                        Decimal(str(expected_return_pct / 100)),
                        Decimal(str(volatility_pct / 100)),
                    )
                    clear_all_caches()
                    st.success(f"Premissa de '{asset_class}' salva.")
                except ValueError as exc:
                    st.error(str(exc))
        with col4:
            if st.button("Resetar para o default"):
                simulation_assumptions_service.reset_assumption(asset_class)
                clear_all_caches()
                st.success(f"Premissa de '{asset_class}' resetada para o default do sistema.")
