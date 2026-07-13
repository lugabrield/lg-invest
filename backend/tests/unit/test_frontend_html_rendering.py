"""Regressão do bug de HTML cru na interface (Sprint 31 — RC v1.0).

Bug relatado pelo usuário na validação manual: vários componentes do
Design System (`components/patterns.py`, `components/cards.py`, o
rodapé da sidebar em `app.py`) mostravam código HTML cru na tela em vez
de renderizar. Causa raiz: essas funções montavam o HTML como f-string
multi-linha *indentada* (aspas triplas seguidas de quebra de linha e
8 espaços antes da tag); o `st.markdown` do Streamlit passa o texto
por um parser Markdown (CommonMark) antes de
decidir o que é HTML, e uma linha que começa com 4+ espaços vira um
bloco de código literal — `unsafe_allow_html=True` não evita isso, só
evita que as tags sejam escapadas quando o HTML É reconhecido como tal.
`metric_card_row` tinha um problema adicional: concatenar o HTML de
vários cards deixava uma linha em branco entre eles, fechando o bloco
de HTML depois do primeiro card e fazendo os cards seguintes caírem na
mesma armadilha.

Este arquivo garante duas coisas, para não regredir:
1. Cada componente chama `st.markdown(html, unsafe_allow_html=True)`
   com um `html` que nunca contém quebra de linha (`\\n`) — a forma mais
   simples e robusta de garantir que o Markdown do Streamlit não tem
   como confundir o bloco de HTML com um bloco de código.
2. Uma varredura no código-fonte dos arquivos que gera HTML garante que
   ninguém reintroduz o padrão de f-string multi-linha dentro de
   `st.markdown(...)` nem usa `st.write`/`st.code`/`st.text` para
   exibir HTML.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from frontend.streamlit_app import app
from frontend.streamlit_app.components import cards, patterns

_COMPONENT_SOURCE_FILES = [
    Path("frontend/streamlit_app/components/patterns.py"),
    Path("frontend/streamlit_app/components/cards.py"),
]
_ALL_HTML_RENDERING_FILES = [
    *_COMPONENT_SOURCE_FILES,
    Path("frontend/streamlit_app/app.py"),
]

# Repositório-raiz — os testes rodam com `testpaths = ["backend/tests"]`,
# mas o cwd do pytest é a raiz do projeto (onde está o `pyproject.toml`).
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _capture_markdown(monkeypatch, module):
    """Substitui `module.st.markdown` por um espião que só grava os
    argumentos recebidos — não depende de um ScriptRunContext do
    Streamlit rodando (o que exigiria um servidor real)."""
    calls: list[tuple[str, dict]] = []

    def fake_markdown(html, **kwargs):
        calls.append((html, kwargs))

    monkeypatch.setattr(module.st, "markdown", fake_markdown)
    return calls


def _assert_clean_html(html: str, *, must_start_with: str = "<") -> None:
    """As duas garantias que importam: nada de quebra de linha (o gatilho
    do bug) e o HTML começa imediatamente com uma tag, sem espaço em
    branco à frente (outro jeito de cair no mesmo bloco de código)."""
    assert "\n" not in html, f"HTML com quebra de linha interna (gatilho do bug): {html!r}"
    assert html == html.strip(), f"HTML com espaço em branco nas bordas: {html!r}"
    assert html.startswith(must_start_with), html


class TestPatternsComponentsRenderCleanHtml:
    def test_page_header(self, monkeypatch):
        calls = _capture_markdown(monkeypatch, patterns)
        patterns.page_header("Dashboard", "Visão geral da carteira", icon="📊")
        assert len(calls) == 1
        html, kwargs = calls[0]
        assert kwargs.get("unsafe_allow_html") is True
        _assert_clean_html(html)
        assert 'class="lg-page-header"' in html

    def test_metric_card_row_single_card(self, monkeypatch):
        calls = _capture_markdown(monkeypatch, patterns)
        patterns.metric_card_row([{"label": "Patrimônio", "value": "R$ 100.000,00"}])
        html, kwargs = calls[0]
        assert kwargs.get("unsafe_allow_html") is True
        _assert_clean_html(html)
        assert html.count('class="lg-metric-card"') == 1

    def test_metric_card_row_multiple_cards_do_not_break_html_block(self, monkeypatch):
        """Regressão específica do bug relatado: com 2+ cards, uma linha em
        branco entre eles fechava o bloco de HTML e os cards a partir do
        segundo apareciam como texto cru — daí testar explicitamente com
        6 cards (o tamanho real do hero do Dashboard)."""
        calls = _capture_markdown(monkeypatch, patterns)
        cards_spec = [
            {"label": f"Card {i}", "value": str(i), "status": "positive"} for i in range(6)
        ]
        patterns.metric_card_row(cards_spec)
        html, kwargs = calls[0]
        assert kwargs.get("unsafe_allow_html") is True
        _assert_clean_html(html)
        assert html.count('class="lg-metric-card"') == 6
        assert html.startswith('<div class="lg-metric-card-row">')
        assert html.endswith("</div>")

    def test_metric_card_single_shortcut(self, monkeypatch):
        calls = _capture_markdown(monkeypatch, patterns)
        patterns.metric_card("Risco", "Moderado", status="attention")
        html, kwargs = calls[0]
        assert kwargs.get("unsafe_allow_html") is True
        _assert_clean_html(html)

    @pytest.mark.parametrize(
        "kind_fn",
        [patterns.success_box, patterns.info_box, patterns.warning_box, patterns.error_box],
    )
    def test_alert_box_variants(self, monkeypatch, kind_fn):
        calls = _capture_markdown(monkeypatch, patterns)
        kind_fn("Título do alerta", "Mensagem explicando o alerta.")
        html, kwargs = calls[0]
        assert kwargs.get("unsafe_allow_html") is True
        _assert_clean_html(html)
        assert 'class="lg-alert-box"' in html

    def test_alert_box_without_message(self, monkeypatch):
        calls = _capture_markdown(monkeypatch, patterns)
        patterns.warning_box("Só o título, sem mensagem")
        html, _ = calls[0]
        _assert_clean_html(html)

    def test_recommendation_card(self, monkeypatch):
        calls = _capture_markdown(monkeypatch, patterns)
        patterns.recommendation_card(
            ticker="WEGE3.SA",
            amount="R$ 500,00",
            weight="25%",
            reason="Melhor Conviction Score na classe.",
            name="WEG S.A.",
            badges_html='<span class="lg-badge">Bom</span>',
            tag_html='<span class="lg-badge">Já tenho</span>',
        )
        html, kwargs = calls[0]
        assert kwargs.get("unsafe_allow_html") is True
        _assert_clean_html(html)
        assert 'class="lg-recommendation-card"' in html
        # Badges/tag (HTML já pronto de outro componente) precisam ter
        # sobrevivido inteiros dentro do card, sem quebra de linha.
        assert '<span class="lg-badge">Bom</span>' in html
        assert '<span class="lg-badge">Já tenho</span>' in html

    def test_data_quality_box(self, monkeypatch):
        calls = _capture_markdown(monkeypatch, patterns)
        patterns.data_quality_box(
            "Qualidade do dado",
            available=["Preço", "Fundamentos"],
            missing=["Valuation"],
            confidence_label="Confiança média",
            impact="Score calculado com dados parciais.",
        )
        html, kwargs = calls[0]
        assert kwargs.get("unsafe_allow_html") is True
        _assert_clean_html(html)
        assert 'class="lg-data-quality-box"' in html

    def test_empty_state_without_cta(self, monkeypatch):
        calls = _capture_markdown(monkeypatch, patterns)
        clicked = patterns.empty_state("Nada por aqui", "Cadastre um ativo para começar.")
        assert clicked is False
        html, kwargs = calls[0]
        assert kwargs.get("unsafe_allow_html") is True
        _assert_clean_html(html)
        assert 'class="lg-empty-state"' in html


class TestCardsComponentRendersCleanHtml:
    def test_render_insight_list(self, monkeypatch):
        from backend.app.schemas.portfolio_diagnostics import DiagnosticInsight

        calls = _capture_markdown(monkeypatch, cards)
        insights = [
            DiagnosticInsight(
                code="concentration_single_asset",
                severity="attention",
                title="Concentração alta",
                message="WEGE3.SA representa mais de 20% da carteira.",
            ),
            DiagnosticInsight(
                code="diversification_ok",
                severity="info",
                title="Diversificação ok",
                message="Nenhuma concentração relevante encontrada.",
            ),
        ]
        cards.render_insight_list(insights)
        assert len(calls) == 2
        for html, kwargs in calls:
            assert kwargs.get("unsafe_allow_html") is True
            _assert_clean_html(html)
            assert 'class="lg-insight-card"' in html

    def test_render_insight_list_empty_uses_caption_not_markdown(self, monkeypatch):
        calls = _capture_markdown(monkeypatch, cards)
        cards.render_insight_list([])
        assert calls == []


class TestAppSidebarFooterRendersCleanHtml:
    def test_sidebar_footer_html_has_no_embedded_newlines(self, monkeypatch):
        # `session_scope` é importado localmente dentro da função — forçar
        # uma exceção aqui exercita o caminho seguro (sem sincronização
        # ainda) sem precisar de um banco real neste teste unitário.
        def _raise():
            raise RuntimeError("sem banco neste teste")

        monkeypatch.setattr("frontend.streamlit_app.db.session_scope", _raise)

        # O rodapé usa `st.sidebar.markdown`, não `st.markdown` — um alvo
        # diferente do resto do módulo (`st.sidebar` é outro objeto).
        calls: list[tuple[str, dict]] = []
        monkeypatch.setattr(app.st.sidebar, "markdown", lambda html, **kw: calls.append((html, kw)))
        app._render_sidebar_footer(portfolio_id=1)
        assert len(calls) == 1
        html, kwargs = calls[0]
        assert kwargs.get("unsafe_allow_html") is True
        _assert_clean_html(html)
        assert 'class="lg-sidebar-footer"' in html


class TestNoRawHtmlLeakRegression:
    """Varredura estática: garante que ninguém reintroduz o padrão que
    causou o bug (f-string multi-linha indentada em `st.markdown`) nem
    usa `st.write`/`st.code`/`st.text` para exibir HTML nos arquivos que
    compõem o Design System."""

    @pytest.mark.parametrize("relative_path", _ALL_HTML_RENDERING_FILES)
    def test_no_multiline_indented_markdown_fstring(self, relative_path):
        source = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")
        # O padrão exato que causou o bug: `st.markdown(` seguido (depois de
        # espaço em branco) por uma f-string/string que começa com aspas
        # triplas e quebra de linha logo em seguida.
        offending = re.search(r'st\.markdown\(\s*\n\s*f?"""', source)
        assert offending is None, (
            f"{relative_path} tem st.markdown com f-string multi-linha — "
            "esse padrão faz o Streamlit tratar o HTML como bloco de "
            "código literal em vez de renderizar (ver docstring deste "
            "arquivo de teste)."
        )

    @pytest.mark.parametrize("relative_path", _COMPONENT_SOURCE_FILES)
    def test_no_st_write_or_code_or_text_for_html(self, relative_path):
        source = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")
        for forbidden in ("st.write(", "st.code(", "st.text("):
            assert forbidden not in source, (
                f"{relative_path} usa `{forbidden}` — componentes de HTML devem "
                "sempre renderizar via `st.markdown(html, unsafe_allow_html=True)`."
            )
