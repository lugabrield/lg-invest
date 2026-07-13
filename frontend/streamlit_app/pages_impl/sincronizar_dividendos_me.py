"""Tela Sincronizar Dividendos.me (Sprint 23).

Fluxo: Testar login -> Buscar carteira (preview, não grava nada) ->
escolher modo -> digitar a palavra de confirmação -> Confirmar
substituição -> resumo final.

Regras de segurança (nunca violar nesta tela):
- Nunca exibir e-mail/senha, cookie ou token — só "configurado: sim/não".
- Nunca rodar a sincronização automaticamente: tudo depende de clique
  explícito do usuário.
- Nunca habilitar o botão de substituição sem a palavra de confirmação
  exata digitada pelo usuário.
"""

from __future__ import annotations

import streamlit as st

from backend.app.infrastructure.repositories.external_sync_run_repository import (
    ExternalSyncRunRepository,
)
from backend.app.integrations.dividendos_me.auth import (
    DividendosMeAuthError,
    is_playwright_available,
)
from backend.app.integrations.dividendos_me.client import (
    DividendosMeClient,
    DividendosMeScrapingError,
)
from backend.app.integrations.dividendos_me.income_service import IncomeSyncService
from backend.app.integrations.dividendos_me.secrets import (
    get_dividendos_me_credentials,
    has_dividendos_me_credentials,
)
from backend.app.integrations.dividendos_me.service import (
    DividendosMeSyncService,
    ExtractionInvalidError,
    PortfolioNotFoundError,
    SyncConfirmationRequiredError,
)
from frontend.streamlit_app.components.import_preview import (
    render_full_preview,
    render_safety_block_warning,
)
from frontend.streamlit_app.components.income_preview import render_full_income_preview
from frontend.streamlit_app.components.monthly_summary_preview import (
    render_full_monthly_summary_preview,
)
from frontend.streamlit_app.components.patterns import (
    MetricCardSpec,
    info_box,
    metric_card_row,
    page_header,
)
from frontend.streamlit_app.db import session_scope

_PROVIDER = "dividendos_me"
_CONFIRM_WORD = {"replace": "SUBSTITUIR", "update": "ATUALIZAR"}


def _preview_key(portfolio_id: int) -> str:
    return f"dividendos_me_preview_{portfolio_id}"


def _income_monthly_preview_key(portfolio_id: int) -> str:
    return f"dividendos_me_income_monthly_preview_{portfolio_id}"


def _income_calendar_preview_key(portfolio_id: int) -> str:
    return f"dividendos_me_income_calendar_preview_{portfolio_id}"


def _make_client() -> DividendosMeClient | None:
    credentials = get_dividendos_me_credentials()
    if credentials is None:
        return None
    return DividendosMeClient(credentials.email, credentials.password, headless=True)


def _render_status(portfolio_id: int) -> None:
    st.subheader("Status da integração")

    creds_ok = has_dividendos_me_credentials()
    playwright_ok = is_playwright_available()

    with session_scope() as db:
        latest = ExternalSyncRunRepository(db).get_latest(portfolio_id, _PROVIDER)
    last_sync_value = (
        latest.finished_at.strftime("%d/%m/%Y %H:%M")
        if latest is not None and latest.finished_at
        else "Nunca"
    )

    cards: list[MetricCardSpec] = [
        {
            "label": "Credenciais configuradas",
            "value": "Sim" if creds_ok else "Não",
            "icon": "🔑",
            "status": "positive" if creds_ok else "attention",
        },
        {
            "label": "Playwright disponível",
            "value": "Sim" if playwright_ok else "Não",
            "icon": "🧩",
            "status": "positive" if playwright_ok else "attention",
        },
        {
            "label": "Última sincronização com sucesso",
            "value": last_sync_value,
            "icon": "🔄",
            "status": "neutral" if latest is not None else "muted",
        },
    ]
    metric_card_row(cards)

    if not creds_ok:
        info_box(
            "Credenciais não configuradas",
            "Configure `DIVIDENDOS_ME_EMAIL` e `DIVIDENDOS_ME_PASSWORD` no `.env` local "
            "(ou `[dividendos_me]` em `st.secrets` no Streamlit Cloud) para habilitar "
            "a sincronização. A senha nunca é salva no banco nem exibida aqui.",
        )
    if not playwright_ok:
        info_box(
            "Playwright indisponível neste ambiente",
            "A sincronização com o Dividendos.me só funciona rodando localmente — use "
            "`python -m scripts.sync_dividendos_me --portfolio-id "
            f"{portfolio_id} --mode dry-run` no seu computador.",
        )


def _render_test_login(client: DividendosMeClient | None, disabled: bool) -> None:
    st.subheader("1. Testar login")
    st.caption("Só confirma que o e-mail/senha funcionam — não busca a carteira, não salva nada.")
    if st.button("Testar login", disabled=disabled, key="btn_test_login"):
        try:
            with st.spinner("Fazendo login no Dividendos.me..."):
                client.test_login()
            st.success("Login realizado com sucesso.")
        except DividendosMeAuthError as exc:
            st.error(str(exc))
        except DividendosMeScrapingError as exc:
            st.error(str(exc))
        except Exception:  # noqa: BLE001 - nunca vazar detalhe de exceção não prevista
            st.error("Falha inesperada ao testar login. Tente novamente em alguns instantes.")


def _render_fetch_portfolio(
    portfolio_id: int, client: DividendosMeClient | None, disabled: bool
) -> None:
    st.subheader("2. Buscar carteira")
    st.caption(
        "Faz login, lê todas as seções (Brasil + internacional) e monta um preview. "
        "Não altera nada na LG INVEST ainda."
    )
    if st.button("Buscar carteira", disabled=disabled, key="btn_fetch_portfolio"):
        try:
            with st.spinner("Buscando posições no Dividendos.me..."):
                with session_scope() as db:
                    service = DividendosMeSyncService(db)
                    preview = service.build_preview(portfolio_id, client)
            st.session_state[_preview_key(portfolio_id)] = preview
            if preview.status == "success":
                st.success(
                    f"{preview.total_assets} ativo(s) encontrado(s). Revise o preview abaixo."
                )
            else:
                st.warning(
                    f"{preview.total_assets} ativo(s) válido(s) encontrado(s), mas o status da "
                    f'extração é "{preview.status}". Revise com atenção antes de confirmar '
                    "qualquer alteração — veja os detalhes abaixo."
                )
        except PortfolioNotFoundError as exc:
            st.error(str(exc))
        except DividendosMeAuthError as exc:
            st.error(str(exc))
        except DividendosMeScrapingError as exc:
            st.error(str(exc))
        except Exception:  # noqa: BLE001
            st.error("Falha inesperada ao buscar a carteira. Tente novamente em alguns instantes.")


def _render_preview_and_confirmation(portfolio_id: int, client: DividendosMeClient | None) -> None:
    preview = st.session_state.get(_preview_key(portfolio_id))
    if preview is None:
        return

    st.divider()
    st.subheader("3. Preview da carteira do Dividendos.me")
    render_full_preview(preview)

    st.divider()
    st.subheader("4. Confirmar substituição da carteira")
    st.caption(
        "`replace` substitui 100% das posições desta carteira pelas do Dividendos.me "
        "(o que faltar aqui é removido). `update` só cria/atualiza, sem remover nada — "
        "modo opcional para uso futuro."
    )

    mode = st.radio(
        "Modo de sincronização",
        options=["replace", "update"],
        format_func=lambda m: (
            "Substituir 100% (recomendado)" if m == "replace" else "Atualizar sem remover"
        ),
        key=f"sync_mode_{portfolio_id}",
    )
    word = _CONFIRM_WORD[mode]

    if mode == "replace" and preview.diff.missing_in_source:
        st.error(
            f"Atenção: {len(preview.diff.missing_in_source)} posição(ões) hoje na LG INVEST "
            "não vieram do Dividendos.me nesta busca e serão REMOVIDAS ao confirmar: "
            + ", ".join(preview.diff.missing_in_source)
        )

    # Prioridade 1/5 do usuário: mesma checagem de segurança do service.py,
    # calculada aqui só para desabilitar o botão sem precisar tentar gravar
    # (o service.py também valida de novo antes de escrever — nunca confia
    # só nesta checagem do lado da UI).
    blocking_reasons = render_safety_block_warning(preview, mode=mode)

    confirmation_text = st.text_input(
        f'Para confirmar, digite exatamente: "{word}"',
        key=f"confirm_text_{portfolio_id}",
    )
    confirmed = confirmation_text.strip() == word

    if st.button(
        "Confirmar substituição da carteira" if mode == "replace" else "Confirmar atualização",
        disabled=not confirmed or bool(blocking_reasons),
        type="primary",
        key="btn_confirm_sync",
    ):
        try:
            with st.spinner("Gravando alterações na LG INVEST..."):
                with session_scope() as db:
                    service = DividendosMeSyncService(db)
                    if mode == "replace":
                        result = service.replace(portfolio_id, client, confirm=True)
                    else:
                        result = service.update(portfolio_id, client, confirm=True)

            del st.session_state[_preview_key(portfolio_id)]

            if result.status == "success":
                st.success(
                    f"Sincronização concluída. Criadas: {result.positions_created} · "
                    f"Atualizadas: {result.positions_updated} · "
                    f"Removidas: {result.positions_removed}."
                )
                if result.errors:
                    st.warning("Avisos:\n\n" + "\n".join(f"- {e}" for e in result.errors))
                st.info(
                    "Sugestão: vá em **Configurações** e clique em **Atualizar preços agora** "
                    "para trazer cotações/fundamentos dos ativos novos antes de olhar o "
                    "Dashboard e a Inteligência."
                )
            else:
                st.error(
                    "A sincronização falhou e nenhuma alteração foi gravada (rollback "
                    "automático). Detalhes: " + "; ".join(result.errors)
                )
        except SyncConfirmationRequiredError as exc:
            st.error(str(exc))
        except ExtractionInvalidError as exc:
            st.error(str(exc))
        except PortfolioNotFoundError as exc:
            st.error(str(exc))
        except DividendosMeAuthError as exc:
            st.error(str(exc))
        except DividendosMeScrapingError as exc:
            st.error(str(exc))
        except Exception:  # noqa: BLE001
            st.error("Falha inesperada ao aplicar a sincronização. Nenhuma alteração foi salva.")


def _render_income_monthly_section(
    portfolio_id: int, client: DividendosMeClient | None, disabled: bool
) -> None:
    st.subheader("5A. Proventos — Histórico mensal")
    st.caption(
        "Extrai o agregado mensal já recebido de **Central de Proventos → Renda Variável → "
        "Brasil → Análise**, por carteira (ex.: Carteira (B3), Carteira Dólar). Cada linha "
        "gravada é um mês/carteira/moeda — nunca um evento por ativo/data (a fonte só "
        "entrega o agregado, então nunca inventamos o detalhe por ativo). Gravado em uma "
        "tabela própria (`income_monthly_summaries`), nunca junto do calendário futuro "
        "abaixo. Uma falha aqui nunca bloqueia a sincronização da carteira nem o calendário."
    )

    if st.button("Buscar histórico mensal", disabled=disabled, key="btn_fetch_income_monthly"):
        try:
            with st.spinner("Buscando histórico mensal de proventos no Dividendos.me..."):
                with session_scope() as db:
                    income_service = IncomeSyncService(db)
                    preview = income_service.build_monthly_preview(portfolio_id, client)
            st.session_state[_income_monthly_preview_key(portfolio_id)] = preview
            if preview.sections_failed:
                st.warning(
                    "Carteira extraída, mas o histórico mensal não foi extraído completamente. "
                    "Revise os detalhes abaixo."
                )
            else:
                st.success(f"{preview.summaries_valid} mês(es) de histórico encontrado(s).")
        except PortfolioNotFoundError as exc:
            st.error(str(exc))
        except DividendosMeAuthError as exc:
            st.error(str(exc))
        except DividendosMeScrapingError as exc:
            st.error(str(exc))
        except Exception:  # noqa: BLE001
            st.warning("Carteira sincronizada, mas o histórico mensal não foi extraído.")

    preview = st.session_state.get(_income_monthly_preview_key(portfolio_id))
    if preview is None:
        return

    st.divider()
    render_full_monthly_summary_preview(preview)

    st.divider()
    st.caption(
        "Importar só ADICIONA meses novos por carteira/moeda (nunca duplica, nunca remove "
        "histórico já salvo) — não precisa de palavra de confirmação."
    )
    if st.button("Importar histórico mensal encontrado", key="btn_import_income_monthly"):
        try:
            with st.spinner("Gravando histórico mensal na LG INVEST..."):
                with session_scope() as db:
                    income_service = IncomeSyncService(db)
                    result = income_service.import_monthly_summaries(portfolio_id, client)
            st.success(
                f"Importação concluída. Novos: {result.summaries_created} · "
                f"Já existentes (ignorados): {result.summaries_skipped_duplicate}."
            )
            if result.errors:
                st.warning("Avisos:\n\n" + "\n".join(f"- {e}" for e in result.errors))
        except PortfolioNotFoundError as exc:
            st.error(str(exc))
        except DividendosMeAuthError as exc:
            st.error(str(exc))
        except DividendosMeScrapingError as exc:
            st.error(str(exc))
        except Exception:  # noqa: BLE001
            st.warning("Carteira sincronizada, mas o histórico mensal não foi extraído.")


def _render_income_calendar_section(
    portfolio_id: int, client: DividendosMeClient | None, disabled: bool
) -> None:
    st.subheader("5B. Proventos — Calendário futuro")
    st.caption(
        "Extrai o calendário de próximos dividendos anunciados por ativo, da tela "
        '"Próximos Dividendos". **Não há, hoje, um evento por ativo já pago com data '
        "exata** — essa é uma limitação da fonte, não desta tela (ver documentação). "
        "Gravado em `income_events`, separado do histórico mensal acima. Uma falha aqui "
        "nunca bloqueia a sincronização da carteira nem o histórico mensal."
    )

    if st.button("Buscar calendário futuro", disabled=disabled, key="btn_fetch_income_calendar"):
        try:
            with st.spinner("Buscando calendário futuro de proventos no Dividendos.me..."):
                with session_scope() as db:
                    income_service = IncomeSyncService(db)
                    preview = income_service.build_preview(portfolio_id, client)
            st.session_state[_income_calendar_preview_key(portfolio_id)] = preview
            if preview.sections_failed:
                st.warning(
                    "Carteira extraída, mas o calendário futuro não foi extraído completamente. "
                    "Revise os detalhes abaixo."
                )
            else:
                st.success(f"{preview.events_valid} evento(s) futuro(s) encontrado(s).")
        except PortfolioNotFoundError as exc:
            st.error(str(exc))
        except DividendosMeAuthError as exc:
            st.error(str(exc))
        except DividendosMeScrapingError as exc:
            st.error(str(exc))
        except Exception:  # noqa: BLE001
            st.warning("Carteira sincronizada, mas o calendário futuro não foi extraído.")

    preview = st.session_state.get(_income_calendar_preview_key(portfolio_id))
    if preview is None:
        return

    st.divider()
    render_full_income_preview(preview)

    st.divider()
    st.caption(
        "Importar só ADICIONA eventos futuros novos (nunca duplica, nunca remove histórico "
        "já salvo) — não precisa de palavra de confirmação."
    )
    if st.button("Importar calendário encontrado", key="btn_import_income_calendar"):
        try:
            with st.spinner("Gravando calendário futuro na LG INVEST..."):
                with session_scope() as db:
                    income_service = IncomeSyncService(db)
                    result = income_service.import_events(portfolio_id, client)
            st.success(
                f"Importação concluída. Novos: {result.events_created} · "
                f"Já existentes (ignorados): {result.events_skipped_duplicate}."
            )
            if result.errors:
                st.warning("Avisos:\n\n" + "\n".join(f"- {e}" for e in result.errors))
        except PortfolioNotFoundError as exc:
            st.error(str(exc))
        except DividendosMeAuthError as exc:
            st.error(str(exc))
        except DividendosMeScrapingError as exc:
            st.error(str(exc))
        except Exception:  # noqa: BLE001
            st.warning("Carteira sincronizada, mas o calendário futuro não foi extraído.")


def _render_income_by_asset_placeholder() -> None:
    st.subheader("5C. Proventos — Por ativo/mês")
    st.info(
        "Fonte detectada, extração ainda não disponível. O Dividendos.me tem uma tela "
        '("Renda Variável → Brasil → Gráficos → Dividendos por Ativo") que mostra o total '
        "de proventos por classe/ativo/mês num gráfico empilhado, mas os dados dela vivem "
        "dentro de um gráfico (Highcharts/ApexCharts), não numa tabela HTML simples como as "
        "outras fontes desta tela. Extrair de um gráfico de forma confiável (sem inventar "
        "valor) exige inspecionar a estrutura interna dele ao vivo, o que não foi possível "
        "confirmar nesta sprint. Enquanto isso não for validado contra dado real, a LG "
        "INVEST não grava nem estima renda por ativo/mês — só o agregado mensal por "
        "carteira (seção 5A) e o calendário futuro por ativo (seção 5B). "
        "Ver `docs/DIVIDENDOS_ME_INCOME_SOURCES.md` para detalhes."
    )


def render(portfolio_id: int) -> None:
    page_header(
        "Sincronizar Dividendos.me",
        "Dividendos.me é a fonte oficial das suas posições reais. A LG INVEST continua "
        "sendo a camada de análise (LG Conviction Score, decisões, projeções) — esta tela "
        "só traz as posições atualizadas para a carteira consolidada "
        f"(portfolio_id {portfolio_id}).",
        icon="🔄",
    )

    _render_status(portfolio_id)
    st.divider()

    client = _make_client()
    buttons_disabled = client is None or not is_playwright_available()

    _render_test_login(client, buttons_disabled)
    st.divider()
    _render_fetch_portfolio(portfolio_id, client, buttons_disabled)
    _render_preview_and_confirmation(portfolio_id, client)
    st.divider()
    _render_income_monthly_section(portfolio_id, client, buttons_disabled)
    st.divider()
    _render_income_by_asset_placeholder()
    st.divider()
    _render_income_calendar_section(portfolio_id, client, buttons_disabled)
