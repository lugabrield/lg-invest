"""Design System interno da LG INVEST (Sprint 30 — Product Design / UX Polish).

Componentes reutilizáveis para que cada tela pare de inventar seu
próprio estilo improvisado (cada `st.markdown` com HTML solto, cada
`st.warning` genérico). Só renderização — nenhum cálculo mora aqui, e
nenhum componente decide nada sozinho: cada tela decide QUANDO e COM
QUE DADO usar cada peça.

Componentes:
- `page_header` — cabeçalho padronizado de página (título + descrição +
  status opcional + ação principal opcional).
- `metric_card` / `metric_card_row` — card de métrica "premium" (hero do
  Dashboard, resumos executivos), com faixa de status colorida.
- `alert_box` (+ `warning_box`/`info_box`/`success_box`/`error_box`) —
  alternativa mais "de produto" ao `st.warning`/`st.info` nativos.
- `recommendation_card` — card de ativo recomendado (Aporte v3).
- `data_quality_box` — disponível / ausente / confiança / impacto.
- `empty_state` — tela ou seção sem dados ainda, com CTA opcional.

Todas as cores vêm de `styles/theme.py`; todo CSS vem de
`styles/custom_css.py` — nenhuma tela deve injetar `<style>` própria.

Padrão de renderização (Sprint 31 — RC v1.0, bugfix de HTML cru): todo
componente aqui **renderiza a si mesmo** via `st.markdown(html,
unsafe_allow_html=True)` internamente — a tela nunca recebe HTML de
volta para renderizar por conta própria. Um segundo ponto, mais sutil,
é o que causava o vazamento de HTML cru: o `st.markdown` do Streamlit
passa o texto por um parser Markdown (CommonMark) *antes* de decidir o
que é HTML — `unsafe_allow_html=True` só libera tags HTML de serem
escapadas, não desliga esse parser. Duas armadilhas do CommonMark
mordem HTML gerado por f-string multi-linha "bonitinha" (indentada):
1) uma linha que começa com 4+ espaços de indentação vira um "indented
   code block" (texto literal, não HTML) se ela for o início de um
   bloco nesse ponto do parsing (ex.: string começando com `\n        <div>`,
   onde a primeira linha fica vazia e a segunda entra indentada);
2) uma linha em branco (mesmo só com espaços) fecha o bloco de HTML que
   estava sendo lido — o que faz o CONTEÚDO seguinte, se indentado, cair
   na armadilha (1). Por isso, toda função abaixo monta o HTML numa
   única linha (sem quebras de linha internas) antes de passar para
   `st.markdown` — nunca uma f-string multi-linha indentada.
"""

from __future__ import annotations

from typing import Literal, TypedDict

import streamlit as st

from frontend.streamlit_app.styles.theme import ALERT, ATTENTION, INFO, POSITIVE, TEXT_MUTED

AlertKind = Literal["success", "info", "warning", "error"]

_ALERT_ICON: dict[AlertKind, str] = {
    "success": "✅",
    "info": "ℹ️",
    "warning": "⚠️",
    "error": "🚨",
}
_ALERT_COLOR: dict[AlertKind, str] = {
    "success": POSITIVE,
    "info": INFO,
    "warning": ATTENTION,
    "error": ALERT,
}

_METRIC_STATUS_COLOR = {
    "positive": POSITIVE,
    "neutral": INFO,
    "attention": ATTENTION,
    "critical": ALERT,
    "muted": TEXT_MUTED,
}


def page_header(
    title: str,
    description: str,
    icon: str = "",
    status_badge: str | None = None,
) -> None:
    """Cabeçalho padronizado de página (pedido da Sprint 30, Parte 2):
    toda tela começa com título claro + descrição curta do que ela faz,
    e opcionalmente um badge de status (HTML já pronto, ex.: de
    `components/badges.py`). A ação principal da página continua sendo
    um `st.button` normal logo abaixo — não faz sentido forçar isso
    dentro do cabeçalho, cada tela tem uma ação diferente."""
    icon_html = f"{icon} " if icon else ""
    status_html = f" {status_badge}" if status_badge else ""
    html = (
        '<div class="lg-page-header">'
        f"<h1>{icon_html}{title}{status_html}</h1>"
        f'<div class="lg-page-description">{description}</div>'
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


class MetricCardSpec(TypedDict, total=False):
    label: str
    value: str
    icon: str
    delta: str | None
    status: Literal["positive", "neutral", "attention", "critical", "muted"]
    help: str | None


def metric_card_row(cards: list[MetricCardSpec]) -> None:
    """Grade responsiva de `MetricCard` (Sprint 30, Parte 1) — usada na
    área hero do Dashboard e em resumos executivos. Diferente do
    `st.metric` padrão (já estilizado em `custom_css.py`), aceita uma cor
    de status por card (positivo/atenção/crítico/neutro) para reforçar a
    hierarquia visual sem depender só do texto."""
    if not cards:
        return
    items_html = []
    for card in cards:
        color = _METRIC_STATUS_COLOR.get(card.get("status", "neutral"), INFO)
        icon = f"{card['icon']} " if card.get("icon") else ""
        delta_html = (
            f'<div class="lg-metric-delta">{card["delta"]}</div>' if card.get("delta") else ""
        )
        title_attr = f' title="{card["help"]}"' if card.get("help") else ""
        # Uma única linha por card, sem quebra de linha interna — ver nota
        # no docstring do módulo sobre por que isso é obrigatório (uma
        # linha em branco entre cards fecharia o bloco de HTML do
        # Markdown e faria os cards seguintes aparecerem como texto cru).
        items_html.append(
            f'<div class="lg-metric-card" style="--lg-metric-accent: {color};"{title_attr}>'
            f'<div class="lg-metric-label">{icon}{card["label"]}</div>'
            f'<div class="lg-metric-value">{card["value"]}</div>'
            f"{delta_html}"
            "</div>"
        )
    html = f'<div class="lg-metric-card-row">{"".join(items_html)}</div>'
    st.markdown(html, unsafe_allow_html=True)


def metric_card(
    label: str,
    value: str,
    icon: str = "",
    delta: str | None = None,
    status: Literal["positive", "neutral", "attention", "critical", "muted"] = "neutral",
    help: str | None = None,  # noqa: A002 - nome espelha o parâmetro de st.metric
) -> None:
    """Um único `MetricCard` — atalho para quando não faz sentido montar uma grade."""
    metric_card_row(
        [
            {
                "label": label,
                "value": value,
                "icon": icon,
                "delta": delta,
                "status": status,
                "help": help,
            }
        ]
    )


def alert_box(kind: AlertKind, title: str, message: str | None = None) -> None:
    """WarningBox / InfoBox / SuccessBox / ErrorBox (Sprint 30, Parte 1):
    caixa de alerta com título em destaque, em vez do `st.warning`/`st.info`
    nativos (que só aceitam um bloco de texto corrido). Usar quando o
    alerta merece um título curto separado da explicação — para um aviso
    de uma linha só, `st.caption`/`st.info` nativo continua ok."""
    icon = _ALERT_ICON[kind]
    color = _ALERT_COLOR[kind]
    message_html = f'<div class="lg-alert-message">{message}</div>' if message else ""
    html = (
        '<div class="lg-alert-box" '
        f'style="--lg-alert-bg: {color}14; --lg-alert-border: {color}55;">'
        f'<div class="lg-alert-title">{icon} {title}</div>'
        f"{message_html}"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def success_box(title: str, message: str | None = None) -> None:
    alert_box("success", title, message)


def info_box(title: str, message: str | None = None) -> None:
    alert_box("info", title, message)


def warning_box(title: str, message: str | None = None) -> None:
    alert_box("warning", title, message)


def error_box(title: str, message: str | None = None) -> None:
    alert_box("error", title, message)


def recommendation_card(
    ticker: str,
    amount: str,
    weight: str,
    reason: str,
    name: str | None = None,
    badges_html: str = "",
    tag_html: str = "",
) -> None:
    """Card de um ativo recomendado (Aporte v3, Sprint 30 Parte 4) — no
    lugar de só uma linha de tabela. `badges_html`/`tag_html` recebem HTML
    já pronto (ex.: de `components/badges.py`) para não duplicar a lógica
    de cor/rótulo aqui."""
    name_html = f'<div class="lg-rec-name">{name}</div>' if name else ""
    tag_block = f" {tag_html}" if tag_html else ""
    html = (
        '<div class="lg-recommendation-card">'
        '<div class="lg-rec-header">'
        "<div>"
        f'<span class="lg-rec-ticker">{ticker}</span>{tag_block}'
        f"{name_html}"
        "</div>"
        "<div>"
        f'<div class="lg-rec-amount">{amount}</div>'
        f'<div class="lg-rec-weight">{weight} do aporte</div>'
        "</div>"
        "</div>"
        f'<div class="lg-rec-reason">{reason}</div>'
        f'<div class="lg-rec-badges">{badges_html}</div>'
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


class DataQualityRow(TypedDict):
    label: str
    value: str


def data_quality_box(
    title: str,
    available: list[str],
    missing: list[str],
    confidence_label: str | None = None,
    impact: str | None = None,
) -> None:
    """DataQualityBox (Sprint 30, Parte 1) — mostra de forma clara o que
    a análise usou, o que faltou e o efeito disso na confiança. Usado em
    Ativos (Análise Fundamentalista) e no Aporte v3 (candidatos com dado
    frágil)."""
    rows_html = []
    if available:
        rows_html.append(
            f'<div class="lg-dq-row"><span class="lg-dq-label">Disponíveis</span>'
            f'<span class="lg-dq-value">{", ".join(available)}</span></div>'
        )
    if missing:
        rows_html.append(
            f'<div class="lg-dq-row"><span class="lg-dq-label">Ausentes</span>'
            f'<span class="lg-dq-value">{", ".join(missing)}</span></div>'
        )
    if confidence_label:
        rows_html.append(
            f'<div class="lg-dq-row"><span class="lg-dq-label">Confiança</span>'
            f'<span class="lg-dq-value">{confidence_label}</span></div>'
        )
    if impact:
        rows_html.append(
            f'<div class="lg-dq-row"><span class="lg-dq-label">Impacto</span>'
            f'<span class="lg-dq-value">{impact}</span></div>'
        )
    html = (
        '<div class="lg-data-quality-box">'
        f'<div class="lg-dq-title">📋 {title}</div>'
        f'{"".join(rows_html)}'
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def empty_state(
    title: str,
    message: str,
    icon: str = "📭",
    cta_label: str | None = None,
    cta_key: str | None = None,
) -> bool:
    """EmptyState (Sprint 30, Parte 1) — tela ou seção sem dados ainda.
    Devolve `True` quando o botão de ação (`cta_label`) foi clicado, para
    a tela decidir o que fazer (nunca decide sozinho)."""
    html = (
        '<div class="lg-empty-state">'
        f'<div class="lg-empty-icon">{icon}</div>'
        f'<div class="lg-empty-title">{title}</div>'
        f'<div class="lg-empty-message">{message}</div>'
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    if cta_label:
        _, mid, _ = st.columns([1, 1, 1])
        with mid:
            return st.button(cta_label, use_container_width=True, key=cta_key)
    return False
