"""Tela Configurações: informações do ambiente, câmbio, atualização de
preços e as três camadas de alocação-alvo (ajuste UX Configurações/
alocação, pós-Sprint 25).

Câmbio e preços via provedores externos (BCB, Yahoo Finance) requerem
internet; por isso são ações explícitas, com aviso e fallback visível.

A LG INVEST tem três formas independentes de configurar meta de
alocação — alocação simples por classe, regras detalhadas por classe/
moeda/país/ativo, e a política de investimento geral. Esta tela deixa
explícita a diferença entre elas e a precedência entre camadas (regra
detalhada > política geral > nenhum limite) — ver
`backend/app/engines/target_allocation/precedence.py`.
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
from backend.app.schemas.target_allocation import EFFECTIVE_LIMIT_SOURCE_LABELS
from backend.app.services import (
    allocation_presets_service,
    fx_settings_service,
    simulation_assumptions_service,
    target_allocation_settings_service,
)
from backend.app.services.allocation_overview_service import build_allocation_overview
from backend.app.services.investment_policy_service import InvestmentPolicyService
from backend.app.services.target_allocation_rule_service import TargetAllocationRuleService
from frontend.streamlit_app.cache import clear_all_caches
from frontend.streamlit_app.components.patterns import info_box, page_header, warning_box
from frontend.streamlit_app.db import session_scope
from frontend.streamlit_app.formatting import format_pct

_FX_SOURCE_LABELS = {"bcb": "BCB (PTAX)", "yahoo": "Yahoo Finance", "manual": "Manual"}

# Mascara usuário:senha em URLs de banco (ex.: postgresql+psycopg2://user:pass@host/db)
# antes de exibir na tela — a URL real pode conter credenciais de produção
# (Supabase) e esta tela é visível em qualquer app publicado (Sprint 20).
_DB_URL_CREDENTIALS_RE = re.compile(r"://([^:/@]+):([^@/]+)@")

# Aviso fixo (ajuste UX Configurações/alocação): repetido em toda seção que
# lida com alocação-alvo — regra de ouro do projeto, nunca implícita.
_NEVER_SELLS_DISCLAIMER = (
    "Essas regras orientam aportes, não geram venda automática. A LG INVEST "
    "nunca recomenda vender uma posição existente — quando uma dimensão está "
    "acima do alvo/máximo, o único efeito é pausar novos aportes ali."
)

_DIMENSION_TYPE_LABELS = {
    "class": "Classe",
    "currency": "Moeda",
    "country": "País",
    "asset": "Ativo",
}

# Cadastro rápido (ajuste UX Configurações/alocação): só preenche o
# formulário de regra detalhada com dimensão/chave — nunca salva sozinho,
# o usuário ainda define os pesos e clica em "Salvar regra".
_QUICK_RULE_PRESETS = (
    ("USD", "currency", "USD"),
    ("BRL", "currency", "BRL"),
    ("FIIs", "class", "fii"),
    ("ETFs", "class", "etf"),
    ("BTC", "asset", "BTC-USD"),
    ("Tesouro", "class", "bond"),
    ("VOO", "asset", "VOO"),
    ("QQQ", "asset", "QQQ"),
)


def _redact_database_url(url: str) -> str:
    return _DB_URL_CREDENTIALS_RE.sub(r"://\1:***@", url)


def _render_system_section(portfolio_id: int) -> None:
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
        except Exception:  # noqa: BLE001 - nunca vazar detalhe de exceção não prevista
            st.error(
                "Não foi possível atualizar o câmbio automaticamente agora — sem internet ou "
                "fonte indisponível. Tente novamente em alguns instantes, ou defina o câmbio "
                "manualmente abaixo."
            )

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
        except Exception:  # noqa: BLE001 - nunca vazar detalhe de exceção não prevista
            st.error(
                "Não foi possível atualizar os preços agora — sem internet ou fonte "
                "indisponível. Tente novamente em alguns instantes."
            )


def render(portfolio_id: int) -> None:
    page_header(
        "Configurações",
        "Câmbio, atualização de preços e as três camadas de alocação-alvo — "
        "regra detalhada > política geral > nenhum limite.",
        icon="⚙️",
    )

    tab_visao, tab_simples, tab_regras, tab_politica, tab_simulacao, tab_sistema = st.tabs(
        [
            "🎯 Visão geral",
            "📐 Alocação simples",
            "🧩 Regras detalhadas",
            "🧭 Política de investimento",
            "🎲 Simulação",
            "⚙️ Sistema",
        ]
    )

    with tab_visao:
        _render_allocation_overview_intro()
        st.divider()
        _render_effective_limits_and_conflicts(portfolio_id)

    with tab_simples:
        _render_simple_allocation_section()

    with tab_regras:
        _render_target_allocation_rules_section(portfolio_id)

    with tab_politica:
        _render_investment_policy_section(portfolio_id)

    with tab_simulacao:
        _render_simulation_assumptions_section()

    with tab_sistema:
        _render_system_section(portfolio_id)


def _render_allocation_overview_intro() -> None:
    """Explica as três camadas de alocação-alvo e a precedência entre elas
    ANTES de qualquer formulário — para o usuário nunca configurar uma
    regra "achando" que ela vale sozinha (ajuste UX Configurações/
    alocação, requisito 1/2)."""
    st.subheader("Como funciona a alocação-alvo")
    warning_box("Nunca gera venda automática", _NEVER_SELLS_DISCLAIMER)
    with st.expander("As 3 camadas e a ordem de precedência", expanded=False):
        st.markdown(
            "**1. Alocação-alvo simples (por classe)** — um número por classe "
            "(ex.: FIIs = 20%). Rápida de configurar, mas só cobre classe — "
            "não diferencia moeda, país ou ativo individual.\n\n"
            "**2. Regras detalhadas (Classe / Moeda / País / Ativo)** — mínimo, "
            "alvo e máximo por dimensão, com prioridade manual de aporte. Mais "
            "granular; quando existe, tem PRECEDÊNCIA sobre a política geral "
            "para a mesma dimensão.\n\n"
            "**3. Política de investimento geral** — parâmetros amplos (perfil, "
            "peso máximo por ativo, peso máximo em cripto/FIIs, exposição "
            "internacional). Funciona como um limite padrão (fallback) só "
            "para as dimensões que NÃO têm uma regra detalhada própria.\n\n"
            "**Ordem de precedência para o limite máximo de uma dimensão:** "
            "regra detalhada > política geral > nenhum limite (a LG INVEST "
            "nunca inventa um limite que você não configurou em nenhuma "
            "camada). A seção **Limite efetivo por dimensão**, mais abaixo, "
            "mostra exatamente qual camada está valendo hoje."
        )


def _render_simple_allocation_section() -> None:
    st.subheader("Camada 1 — Alocação-alvo simples por classe")
    st.caption(
        "Meta pessoal de alocação por classe de ativo (Sprint 17). Não existe alocação "
        "padrão embutida: enquanto você não salvar uma meta, o Target Allocation Engine "
        "não compara nada — ele nunca inventa uma alocação 'recomendada'. As porcentagens "
        "devem somar 100%."
    )

    current_target = target_allocation_settings_service.get_target_allocation()

    with st.expander("Aplicar um modelo pronto (preset)"):
        st.caption(
            "Cada modelo é só um PONTO DE PARTIDA comum, não uma recomendação financeira — "
            "nunca é aplicado sozinho: pré-visualize antes e confirme numa etapa separada."
        )
        presets = allocation_presets_service.list_presets()
        preset_labels = {p.key: p.label for p in presets}
        selected_key = st.selectbox(
            "Modelo",
            options=list(preset_labels.keys()),
            format_func=lambda k: preset_labels[k],
            key="allocation_preset_select",
        )
        selected = allocation_presets_service.get_preset(selected_key)
        st.write(selected.description)

        if selected.allocation is None:
            st.info("Este modelo não aplica nada — configure manualmente abaixo.")
        else:
            st.table(
                [
                    {"Classe": asset_class, "Alocação": format_pct(pct, decimals=0)}
                    for asset_class, pct in selected.allocation.items()
                ]
            )
            if st.button("Pré-visualizar aplicação", key="preview_preset"):
                st.session_state["preset_preview_key"] = selected_key
            if st.session_state.get("preset_preview_key") == selected_key:
                st.warning(
                    f"Confirmar substitui a alocação-alvo simples atual pelo modelo "
                    f"'{selected.label}'. Você pode editar cada classe livremente depois."
                )
                if st.button("Confirmar aplicação do preset", key="confirm_preset"):
                    target_allocation_settings_service.set_target_allocation(selected.allocation)
                    clear_all_caches()
                    st.session_state.pop("preset_preview_key", None)
                    st.success(f"Modelo '{selected.label}' aplicado à alocação-alvo simples.")

    if current_target:
        st.write(
            "Meta atual: "
            + ", ".join(
                f"{cls}: {format_pct(current_target.get(cls, Decimal('0')), decimals=1)}"
                for cls in ASSET_CLASSES
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
        if abs(total_pct - 100) < 0.05:
            st.success(f"Soma atual: {total_pct:.1f}% ✓")
        else:
            st.warning(f"Soma atual: {total_pct:.1f}% — precisa ser 100% para salvar.")

        if st.button("Salvar alocação-alvo", type="primary"):
            try:
                allocation = {
                    asset_class: Decimal(str(pct / 100)) for asset_class, pct in inputs.items()
                }
                target_allocation_settings_service.set_target_allocation(allocation)
                clear_all_caches()
                st.success("Alocação-alvo salva.")
            except ValueError as exc:
                st.error(str(exc))

        # Ação destrutiva (remove a meta salva) — exige confirmação em duas
        # etapas, no mesmo padrão já usado para presets (linha ~273) e para
        # "Atualizar tudo" no Dashboard: primeiro clique só avisa, o botão
        # de confirmação é que executa de fato (Sprint 31, Parte 4).
        if st.button("Limpar meta de alocação", key="clear_target_allocation_btn"):
            st.session_state["confirm_clear_target_allocation"] = True
        if st.session_state.get("confirm_clear_target_allocation"):
            st.warning("Isso remove a meta de alocação-alvo salva. Confirma?")
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("✅ Confirmar remoção", key="confirm_clear_target_allocation_btn"):
                    target_allocation_settings_service.clear_target_allocation()
                    clear_all_caches()
                    st.session_state["confirm_clear_target_allocation"] = False
                    st.success("Meta de alocação removida.")
            with cancel_col:
                if st.button("Cancelar", key="cancel_clear_target_allocation_btn"):
                    st.session_state["confirm_clear_target_allocation"] = False
                    st.rerun()


def _render_investment_policy_section(portfolio_id: int) -> None:
    """Investment Policy (Sprint 24, Fase 3) — perfil e limites usados como
    guardrails pelo Decision Engine e (no futuro) pelo Simulation Engine.
    Os valores exibidos na primeira vez são um PONTO DE PARTIDA sugerido com
    base no perfil descrito pelo usuário, nunca uma recomendação financeira
    — e sempre editáveis aqui."""
    st.subheader("Camada 3 — Política de investimento geral")
    st.caption(
        "Perfil, limites e parâmetros amplos que orientam o Decision Engine e servem de "
        "FALLBACK para dimensões sem regra detalhada própria (Camada 2). Isto NÃO é uma "
        "recomendação financeira — é a sua própria configuração, com um ponto de partida "
        "sugerido na primeira vez que esta tela é aberta. Edite livremente."
    )
    info_box("Nunca gera venda automática", _NEVER_SELLS_DISCLAIMER)

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
                help=(
                    "Fallback: só vale para um ativo se ele NÃO tiver uma regra "
                    "detalhada própria (Camada 2, dimensão Ativo) com máximo definido."
                ),
            )
            max_crypto_weight = st.number_input(
                "Peso máximo em cripto (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(policy.max_crypto_weight) * 100,
                step=1.0,
                help=(
                    "Fallback: só vale se a classe 'crypto' NÃO tiver uma regra "
                    "detalhada própria (Camada 2) com máximo definido."
                ),
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
                help=(
                    "Fallback: só vale se a classe 'fii' NÃO tiver uma regra "
                    "detalhada própria (Camada 2) com máximo definido."
                ),
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


def _prefill_rule_form(rule) -> None:
    """Popula o formulário "Adicionar/editar regra" com os valores de uma
    regra existente — permite editar sem remover/recriar (a escrita já é
    upsert no backend; isto só evita o usuário ter que redigitar tudo)."""
    st.session_state["rule_dimension_type"] = rule.dimension_type
    st.session_state["rule_dimension_key"] = rule.dimension_key
    st.session_state["rule_min_set"] = rule.min_weight is not None
    st.session_state["rule_min"] = (
        float(rule.min_weight) * 100 if rule.min_weight is not None else 0.0
    )
    st.session_state["rule_target_set"] = rule.target_weight is not None
    st.session_state["rule_target"] = (
        float(rule.target_weight) * 100 if rule.target_weight is not None else 0.0
    )
    st.session_state["rule_max_set"] = rule.max_weight is not None
    st.session_state["rule_max"] = (
        float(rule.max_weight) * 100 if rule.max_weight is not None else 0.0
    )
    st.session_state["rule_priority"] = rule.priority
    st.session_state["rule_form_expanded"] = True


def _render_target_allocation_rules_section(portfolio_id: int) -> None:
    """Target Allocation Rules v2 (Sprint 24, Fase 3) — metas granulares por
    classe, moeda, país ou ativo individual. Nenhuma regra é pré-cadastrada
    com valor inventado: a lista começa vazia até o usuário configurar."""
    st.subheader("Camada 2 — Regras detalhadas (Classe / Moeda / País / Ativo)")
    st.caption(
        "Metas granulares por dimensão (Sprint 24). Cada regra vale para UMA dimensão "
        "só (nunca mistura classe com moeda, por exemplo). Nenhuma regra existe até você "
        "cadastrar — a LG INVEST nunca inventa uma meta 'recomendada'. Quando existe, tem "
        "precedência sobre a política geral (Camada 3) para a mesma dimensão."
    )
    info_box("Nunca gera venda automática", _NEVER_SELLS_DISCLAIMER)

    with session_scope() as db:
        rules = TargetAllocationRuleService(db).list_rules(portfolio_id)

    if rules:
        st.markdown("**Regras cadastradas, agrupadas por dimensão**")
        for dimension_type in TARGET_ALLOCATION_DIMENSIONS:
            dim_rules = [r for r in rules if r.dimension_type == dimension_type]
            if not dim_rules:
                continue
            st.markdown(f"_{_DIMENSION_TYPE_LABELS[dimension_type]}_")
            header = st.columns([2, 1, 1, 1, 1, 1])
            for col, label in zip(
                header, ("Chave", "Mínimo", "Alvo", "Máximo", "Prioridade", ""), strict=False
            ):
                col.markdown(f"**{label}**")
            for r in dim_rules:
                row = st.columns([2, 1, 1, 1, 1, 1])
                row[0].write(r.dimension_key)
                row[1].write(format_pct(r.min_weight, decimals=1))
                row[2].write(format_pct(r.target_weight, decimals=1))
                row[3].write(format_pct(r.max_weight, decimals=1))
                row[4].write(str(r.priority))
                if row[5].button("Editar", key=f"edit_rule_{dimension_type}_{r.dimension_key}"):
                    _prefill_rule_form(r)
                    st.rerun()
    else:
        st.write("Nenhuma regra de alocação detalhada configurada ainda.")

    with st.expander(
        "Adicionar / editar regra",
        expanded=st.session_state.get("rule_form_expanded", False),
    ):
        st.caption(
            "Cadastro rápido: preenche a dimensão/chave abaixo — você ainda define os "
            "pesos e clica em 'Salvar regra' (nunca salva sozinho)."
        )
        quick_cols = st.columns(len(_QUICK_RULE_PRESETS))
        for col, (label, dim_type, dim_key) in zip(quick_cols, _QUICK_RULE_PRESETS, strict=False):
            if col.button(label, key=f"quick_rule_{dim_type}_{dim_key}"):
                st.session_state["rule_dimension_type"] = dim_type
                st.session_state["rule_dimension_key"] = dim_key
                st.session_state["rule_form_expanded"] = True
                st.rerun()

        dimension_type = st.selectbox(
            "Dimensão (Classe / Moeda / País / Ativo)",
            options=list(TARGET_ALLOCATION_DIMENSIONS),
            format_func=lambda d: _DIMENSION_TYPE_LABELS.get(d, d),
            key="rule_dimension_type",
        )
        dimension_key = st.text_input(
            "Ativo/Classe/Moeda/País (ex.: fii, USD, BR, VOO)", key="rule_dimension_key"
        )

        rcol1, rcol2, rcol3, rcol4 = st.columns(4)
        with rcol1:
            set_min = st.checkbox("Definir mínimo", key="rule_min_set")
            min_pct = st.number_input(
                "Mínimo (%)",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                key="rule_min",
                disabled=not set_min,
            )
        with rcol2:
            set_target = st.checkbox("Definir alvo", key="rule_target_set")
            target_pct = st.number_input(
                "Alvo (%)",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                key="rule_target",
                disabled=not set_target,
            )
        with rcol3:
            set_max = st.checkbox("Definir máximo", key="rule_max_set")
            max_pct = st.number_input(
                "Máximo (%)",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                key="rule_max",
                disabled=not set_max,
            )
        with rcol4:
            priority = st.number_input(
                "Prioridade", min_value=0, max_value=100, step=1, key="rule_priority"
            )

        if st.button("Salvar regra"):
            try:
                with session_scope() as db:
                    TargetAllocationRuleService(db).set_rule(
                        portfolio_id,
                        dimension_type=dimension_type,
                        dimension_key=dimension_key,
                        min_weight=Decimal(str(min_pct / 100)) if set_min else None,
                        target_weight=Decimal(str(target_pct / 100)) if set_target else None,
                        max_weight=Decimal(str(max_pct / 100)) if set_max else None,
                        priority=int(priority),
                    )
                clear_all_caches()
                st.session_state["rule_form_expanded"] = False
                label = _DIMENSION_TYPE_LABELS.get(dimension_type, dimension_type)
                st.success(f"Regra salva: {label} = {dimension_key}.")
            except ValueError as exc:
                st.error(str(exc))

        st.caption("Remover regra existente")
        rem_col1, rem_col2 = st.columns(2)
        with rem_col1:
            rem_dimension_type = st.selectbox(
                "Dimensão a remover",
                options=list(TARGET_ALLOCATION_DIMENSIONS),
                format_func=lambda d: _DIMENSION_TYPE_LABELS.get(d, d),
                key="rule_remove_dimension_type",
            )
        with rem_col2:
            rem_dimension_key = st.text_input("Chave a remover", key="rule_remove_dimension_key")
        # Ação destrutiva — mesmo padrão de confirmação em duas etapas usado
        # para "Limpar meta de alocação" acima (Sprint 31, Parte 4).
        if st.button("Remover regra", key="remove_rule_btn"):
            st.session_state["confirm_remove_rule"] = (rem_dimension_type, rem_dimension_key)
        pending_removal = st.session_state.get("confirm_remove_rule")
        if pending_removal == (rem_dimension_type, rem_dimension_key):
            label = _DIMENSION_TYPE_LABELS.get(rem_dimension_type, rem_dimension_type)
            st.warning(f"Isso remove a regra de '{label} = {rem_dimension_key}'. Confirma?")
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("✅ Confirmar remoção", key="confirm_remove_rule_btn"):
                    with session_scope() as db:
                        removed = TargetAllocationRuleService(db).delete_rule(
                            portfolio_id, rem_dimension_type, rem_dimension_key
                        )
                    st.session_state["confirm_remove_rule"] = None
                    if removed:
                        clear_all_caches()
                        st.success("Regra removida.")
                    else:
                        st.warning("Nenhuma regra encontrada com essa dimensão/chave.")
            with cancel_col:
                if st.button("Cancelar", key="cancel_remove_rule_btn"):
                    st.session_state["confirm_remove_rule"] = None
                    st.rerun()


def _render_effective_limits_and_conflicts(portfolio_id: int) -> None:
    """Mostra, de forma explícita, qual camada está valendo em cada
    dimensão (precedência) e quaisquer inconsistências detectadas entre
    as três camadas — nunca corrige nada sozinho, só avisa."""
    st.subheader("Limite efetivo por dimensão e conflitos")
    st.caption(
        "Resumo de qual camada está valendo hoje para cada dimensão com limite máximo "
        "configurado (regra detalhada > política geral), e de qualquer inconsistência "
        "entre as três camadas — só para você revisar, nada aqui é corrigido sozinho."
    )

    with session_scope() as db:
        overview = build_allocation_overview(db, portfolio_id)

    if overview.effective_limits:
        st.table(
            [
                {
                    "Dimensão": _DIMENSION_TYPE_LABELS.get(el.dimension_type, el.dimension_type),
                    "Chave": el.dimension_key,
                    "Limite máximo": format_pct(el.max_weight, decimals=1),
                    "Origem": EFFECTIVE_LIMIT_SOURCE_LABELS.get(el.source, el.source),
                    "Política sobrescrita": (
                        format_pct(el.overridden_policy_value, decimals=1)
                        if el.overridden_policy_value is not None
                        else "—"
                    ),
                }
                for el in overview.effective_limits
            ]
        )
    else:
        st.write("Nenhum limite máximo configurado ainda (nem regra detalhada, nem política).")

    if overview.conflicts:
        st.warning("Conflitos/avisos detectados entre as camadas de alocação:")
        for conflict in overview.conflicts:
            st.write(f"- {conflict.message}")
    else:
        st.write("Nenhum conflito detectado entre as camadas configuradas.")


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
            if st.button("Salvar premissa", type="primary"):
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
            # Ação destrutiva (descarta a premissa customizada) — mesmo
            # padrão de confirmação em duas etapas (Sprint 31, Parte 4).
            if st.button("Resetar para o default", key="reset_assumption_btn"):
                st.session_state["confirm_reset_assumption"] = asset_class
            if st.session_state.get("confirm_reset_assumption") == asset_class:
                st.warning(f"Isso descarta a premissa customizada de '{asset_class}'. Confirma?")
                confirm_col, cancel_col = st.columns(2)
                with confirm_col:
                    if st.button("✅ Confirmar reset", key="confirm_reset_assumption_btn"):
                        simulation_assumptions_service.reset_assumption(asset_class)
                        clear_all_caches()
                        st.session_state["confirm_reset_assumption"] = None
                        st.success(
                            f"Premissa de '{asset_class}' resetada para o default do sistema."
                        )
                with cancel_col:
                    if st.button("Cancelar", key="cancel_reset_assumption_btn"):
                        st.session_state["confirm_reset_assumption"] = None
                        st.rerun()
