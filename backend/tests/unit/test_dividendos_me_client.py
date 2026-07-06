"""Testes da extração/mapeamento de tabela e cards do Dividendos.me
(Sprint 23 / correção 23.1).

Usa uma `page` falsa (sem Playwright real) para testar a extração e o
mapeamento de linha->`ExtractedPosition` de forma isolada e rápida. A
Sprint 23.1 corrigiu dois bugs reais de produção (seta de ordenação no
cabeçalho + subcabeçalho não encontrado por não subir `parentElement`)
e adicionou extração baseada em cards para Criptomoedas/Renda Fixa —
estes testes cobrem o novo formato do cliente (navegação por clique,
`fetch_portfolio()` devolvendo uma tripla, diagnósticos por seção).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.app.integrations.dividendos_me import client as client_module
from backend.app.integrations.dividendos_me.client import (
    DividendosMeClient,
    DividendosMeScrapingError,
    _NavigationOutcome,
    _SectionSpec,
)
from backend.app.integrations.dividendos_me.schemas import (
    ORIGIN_B3,
    ORIGIN_CRYPTO,
    ExtractedPosition,
)


class _FakeLocator:
    def __init__(self, tracker: list[str], text: str):
        self._tracker = tracker
        self._text = text

    @property
    def first(self):
        return self

    def click(self, timeout=None):  # noqa: ARG002
        self._tracker.append(self._text)


class _FakePage:
    """Substitui a `Page` real do Playwright: nunca acessa rede/DOM real,
    só registra chamadas e devolve dados pré-programados via `evaluate`.

    Sprint 23.3: `evaluate_results` (opcional) permite programar uma
    SEQUÊNCIA de retornos por chamada — necessário para testar o
    retry-on-empty de `_extract_table_section`/`_extract_card_section`
    (primeira leitura vazia, segunda com dados). `url` simula
    `page.url`, lido por `_goto_section` para diagnóstico (Sprint 23.3)."""

    def __init__(
        self,
        *,
        table_rows=None,
        card_rows=None,
        has_table=True,
        evaluate_results=None,
        url="https://app.dividendos.me/renda-variavel/brasil/tabela-ativos",
    ):
        self._table_rows = table_rows
        self._card_rows = card_rows
        self._has_table = has_table
        self._evaluate_results = list(evaluate_results) if evaluate_results is not None else None
        self.url = url
        self.clicked_texts: list[str] = []
        self.clicked_hrefs: list[str] = []

    def get_by_text(self, text, exact=True):  # noqa: ARG002
        return _FakeLocator(self.clicked_texts, text)

    def click(self, selector, timeout=None):  # noqa: ARG002
        self.clicked_hrefs.append(selector)

    def wait_for_load_state(self, *_args, **_kwargs):
        pass

    def wait_for_timeout(self, _ms):
        pass

    def query_selector(self, _selector):
        return object() if self._has_table else None

    def wait_for_selector(self, *_args, **_kwargs):
        pass

    def evaluate(self, script):
        if self._evaluate_results is not None:
            return self._evaluate_results.pop(0) if self._evaluate_results else []
        if "Quantidade:" in script or "Valor atual" in script:
            return self._card_rows
        return self._table_rows


def _spec(key: str, kind: str = "table", accordion_label: str | None = None) -> _SectionSpec:
    return _SectionSpec(key, f"/{key}", accordion_label, kind)


# --- Navegação (correção do bug de `page.goto()` direto, Sprint 23.1) -----


def test_goto_section_clicks_accordion_when_present():
    page = _FakePage()
    client = DividendosMeClient("a@b.com", "senha")
    spec = _spec("eua", accordion_label="Estados Unidos")

    outcome = client._goto_section(page, spec)

    assert page.clicked_texts == ["Estados Unidos"]
    assert page.clicked_hrefs == ['a[href="/eua"]']
    assert isinstance(outcome, _NavigationOutcome)
    assert outcome.accordion_label == "Estados Unidos"
    assert outcome.accordion_clicked is True
    assert outcome.final_url == page.url


def test_goto_section_skips_accordion_when_none():
    page = _FakePage()
    client = DividendosMeClient("a@b.com", "senha")
    spec = _spec("brasil", accordion_label=None)

    outcome = client._goto_section(page, spec)

    assert page.clicked_texts == []
    assert page.clicked_hrefs == ['a[href="/brasil"]']
    assert outcome.accordion_label is None
    assert outcome.accordion_clicked is False
    assert outcome.final_url == page.url


def test_navigation_outcome_describe_reports_accordion_and_url():
    outcome = _NavigationOutcome(
        accordion_label="Estados Unidos", accordion_clicked=True, final_url="https://x/eua"
    )
    description = outcome.describe()
    assert "Estados Unidos" in description
    assert "clicado" in description
    assert "https://x/eua" in description


def test_navigation_outcome_describe_handles_missing_url_and_accordion():
    outcome = _NavigationOutcome(accordion_label=None, accordion_clicked=False, final_url=None)
    description = outcome.describe()
    assert "sem acordeão" in description
    assert "desconhecida" in description


def test_sections_use_correct_confirmed_urls():
    # Confirmado ao vivo nesta sprint: Criptomoedas/Renda Fixa não têm uma
    # "Tabela de Ativos" própria — usam Extrato/Meu Resumo, com cards.
    by_key = {s.key: s for s in client_module._SECTIONS}
    assert by_key["brasil"].href == "/renda-variavel/brasil/tabela-ativos"
    assert by_key["brasil"].kind == "table"
    assert by_key["eua"].href == "/renda-variavel/eua/tabela-ativos"
    assert by_key["eua"].kind == "table"
    assert by_key["criptomoedas"].href == "/criptos/extrato"
    assert by_key["criptomoedas"].kind == "cards"
    assert by_key["renda_fixa"].href == "/renda-fixa/meu-resumo"
    assert by_key["renda_fixa"].kind == "cards"


def test_crypto_section_never_uses_meu_resumo_as_position_source():
    # Sprint 23.2 (correção confirmada pelo usuário): a tela correta para
    # POSIÇÃO de cripto é "Criptomoedas → Extrato" — "Meu Resumo" nunca
    # deve ser usado como fonte principal de posição de cripto.
    crypto_spec = next(s for s in client_module._SECTIONS if s.key == "criptomoedas")
    assert crypto_spec.href == "/criptos/extrato"
    assert "meu-resumo" not in crypto_spec.href


# --- Extração de tabela ----------------------------------------------------


def test_extract_table_section_returns_rows_from_evaluate():
    rows = [{"ATIVO": "WEGE3", "QNT": "100", "__subheader": "Ações"}]
    page = _FakePage(table_rows=rows, has_table=True)
    client = DividendosMeClient("a@b.com", "senha")

    result, retried = client._extract_table_section(page)

    assert result == rows
    assert retried is False


def test_extract_table_section_handles_empty_result_after_retry():
    # Sprint 23.3: primeira leitura vazia -> tenta de novo (mesma seção,
    # após espera extra) antes de desistir. Aqui a segunda leitura
    # também vem vazia, então o resultado final é [] com retried=True.
    page = _FakePage(table_rows=None, has_table=False)
    client = DividendosMeClient("a@b.com", "senha")

    result, retried = client._extract_table_section(page)

    assert result == []
    assert retried is True


def test_extract_table_section_retries_once_and_succeeds_on_second_read():
    # Primeira leitura vazia, segunda (após retry) traz as linhas —
    # comportamento novo da Sprint 23.3 para lidar com seções que
    # navegam sem erro mas ainda não renderizaram o conteúdo.
    rows = [{"ATIVO": "WEGE3", "QNT": "100", "__subheader": "Ações"}]
    page = _FakePage(evaluate_results=[[], rows], has_table=True)
    client = DividendosMeClient("a@b.com", "senha")

    result, retried = client._extract_table_section(page)

    assert result == rows
    assert retried is True


def test_to_extracted_position_maps_fields_by_header_label():
    row = {
        "ATIVO": "WEGE3",
        "__subheader": "Ações",
        "QNT": "100",
        "P.M.": "38,20",
        "ATUAL": "40,10",
        "TOTAL": "4.010,00",
        "RENT": "4,97%",
        "VAR": "-1,20%",
        "DIV": "6,52%",
        "V/VP": "1,05",
    }
    client = DividendosMeClient("a@b.com", "senha")
    synced_at = datetime.now(UTC)

    position = client._to_extracted_position(row, "brasil", synced_at)

    assert position.ticker == "WEGE3.SA"
    assert position.asset_class == "stock"
    assert position.quantity == Decimal("100")
    assert position.average_price == Decimal("38.20")
    assert position.current_price == Decimal("40.10")
    assert position.current_value == Decimal("4010.00")
    assert position.return_pct == Decimal("4.97") / Decimal("100")
    assert position.daily_change_pct == Decimal("-1.20") / Decimal("100")
    assert position.dividend_yield_pct == Decimal("6.52") / Decimal("100")
    assert position.origin == ORIGIN_B3
    assert not position.review_required


def test_to_extracted_position_missing_optional_fields_stay_none():
    row = {"ATIVO": "WEGE3", "__subheader": "Ações", "QNT": "10"}
    client = DividendosMeClient("a@b.com", "senha")

    position = client._to_extracted_position(row, "brasil", datetime.now(UTC))

    assert position.average_price is None
    assert position.current_price is None
    assert position.current_value is None


def test_to_extracted_position_empty_ticker_is_review_required():
    # Regressão do bug real (Sprint 23.1): linha sem ticker nunca deve
    # virar uma posição "válida" silenciosa.
    row = {"ATIVO": "", "__subheader": "Ações", "QNT": "10"}
    client = DividendosMeClient("a@b.com", "senha")

    position = client._to_extracted_position(row, "brasil", datetime.now(UTC))

    assert position.ticker == ""
    assert position.review_required is True


# --- Extração de cards (Criptomoedas / Renda Fixa) -------------------------


def test_extract_card_section_uses_crypto_js_for_criptomoedas():
    rows = [["btc", "Quantidade:", "0,001", "Total:", "R$ 100,00"]]
    page = _FakePage(card_rows=rows)
    client = DividendosMeClient("a@b.com", "senha")
    spec = _spec("criptomoedas", kind="cards")

    result, retried = client._extract_card_section(page, spec)

    assert result == rows
    assert retried is False


def test_extract_card_section_uses_fixed_income_js_for_renda_fixa():
    rows = [["Tesouro IPCA+ 2050", "Valor atual", "R$ 5.483,53"]]
    page = _FakePage(card_rows=rows)
    client = DividendosMeClient("a@b.com", "senha")
    spec = _spec("renda_fixa", kind="cards")

    result, retried = client._extract_card_section(page, spec)

    assert result == rows
    assert retried is False


def test_extract_card_section_retries_once_and_succeeds_on_second_read():
    rows = [["btc", "Quantidade:", "0,001", "Total:", "R$ 100,00"]]
    page = _FakePage(evaluate_results=[[], rows])
    client = DividendosMeClient("a@b.com", "senha")
    spec = _spec("criptomoedas", kind="cards")

    result, retried = client._extract_card_section(page, spec)

    assert result == rows
    assert retried is True


def test_extract_card_section_gives_up_after_retry_when_still_empty():
    page = _FakePage(card_rows=None)
    client = DividendosMeClient("a@b.com", "senha")
    spec = _spec("renda_fixa", kind="cards")

    result, retried = client._extract_card_section(page, spec)

    assert result == []
    assert retried is True


def test_card_to_extracted_position_crypto():
    lines = [
        "btc",
        "Quantidade:",
        "0,00584925",
        "Preço Médio:",
        "R$ 76.308,58",
        "Preço Atual:",
        "R$ 700.000,00",
        "Total:",
        "R$ 4.093,00",
        "Ver Operações",
    ]
    client = DividendosMeClient("a@b.com", "senha")

    position = client._card_to_extracted_position(lines, "criptomoedas", datetime.now(UTC))

    assert position.ticker == "BTC-USD"
    assert position.asset_class == "crypto"
    # Sprint 24: os números da tela "Criptomoedas → Extrato" são USD,
    # apesar do símbolo visual "R$" — cripto tem origem própria
    # (ORIGIN_CRYPTO), separada de ações/ETFs/REITs internacionais.
    assert position.currency == "USD"
    assert position.origin == ORIGIN_CRYPTO
    assert position.quantity == Decimal("0.00584925")
    assert position.current_value == Decimal("4093.00")
    assert not position.review_required


def test_card_to_extracted_position_crypto_real_card_from_extrato_screen():
    # Card real confirmado ao vivo pelo usuário na tela "Criptomoedas →
    # Extrato" (nunca "Meu Resumo") — inclui o par "Carteira:"/"Carteira
    # Criptomoeda (Manual)" que precede o nome do ativo.
    lines = [
        "Carteira:",
        "Carteira Criptomoeda (Manual)",
        "btc",
        "Quantidade:",
        "0,00584925",
        "Preço Médio:",
        "R$ 76.308,58",
        "Preço Atual:",
        "R$ 62.404,96",
        "Total:",
        "R$ 365,02",
        "Rentabilidade:",
        "-18,22",
        "Ver Operações",
    ]
    client = DividendosMeClient("a@b.com", "senha")

    position = client._card_to_extracted_position(lines, "criptomoedas", datetime.now(UTC))

    assert position.ticker == "BTC-USD"
    assert position.asset_class == "crypto"
    assert position.quantity == Decimal("0.00584925")
    assert position.average_price == Decimal("76308.58")
    assert position.current_price == Decimal("62404.96")
    assert position.current_value == Decimal("365.02")
    assert position.currency == "USD"
    assert position.origin == ORIGIN_CRYPTO
    assert position.review_required is False


def test_card_to_extracted_position_fixed_income_quantity_defaults_to_one():
    # Cards de Tesouro só expõem "Valor atual" — nunca inventamos uma
    # quantidade real quando ela não vem do card (Sprint 23.1).
    lines = ["Tesouro IPCA+ 2050", "XP INVESTIMENTOS CCTVM S/A", "Valor atual", "R$ 5.483,53"]
    client = DividendosMeClient("a@b.com", "senha")

    position = client._card_to_extracted_position(lines, "renda_fixa", datetime.now(UTC))

    assert position.quantity == Decimal("1")
    assert position.current_value == Decimal("5483.53")
    assert position.asset_class == "bond"
    assert position.is_manual is True


def test_card_to_extracted_position_empty_name_is_review_required():
    lines = ["Quantidade:", "1", "Total:", "R$ 1,00"]
    client = DividendosMeClient("a@b.com", "senha")

    position = client._card_to_extracted_position(lines, "criptomoedas", datetime.now(UTC))

    assert position.ticker == ""
    assert position.review_required is True


# --- Sprint 23.2: correção do bug de card-boundary do BTC -------------------


def test_card_to_extracted_position_crypto_sets_section_field():
    # `section` precisa ser preservado mesmo com ticker vazio — é o que
    # permite a rede de segurança `_apply_btc_fallback` (service.py)
    # identificar que uma posição sem ticker veio da seção de criptos.
    lines = ["Quantidade:", "0,001", "Total:", "R$ 100,00"]
    client = DividendosMeClient("a@b.com", "senha")

    position = client._card_to_extracted_position(lines, "criptomoedas", datetime.now(UTC))

    assert position.section == "criptomoedas"
    assert position.ticker == ""
    assert position.review_required is True


def test_card_to_extracted_position_recognizes_bitcoin_by_name_lowercase():
    lines = [
        "btc",
        "Quantidade:",
        "0,001",
        "Total:",
        "R$ 100,00",
        "Ver Operações",
    ]
    client = DividendosMeClient("a@b.com", "senha")

    position = client._card_to_extracted_position(lines, "criptomoedas", datetime.now(UTC))

    assert position.ticker == "BTC-USD"
    assert position.review_required is False


# --- Diagnósticos (Prioridade 4 do usuário) --------------------------------


def _extracted(ticker: str, *, review_required: bool = False, review_reason=None):
    return ExtractedPosition(
        raw_ticker=ticker,
        ticker=ticker,
        asset_class="stock",
        country="BR",
        currency="BRL",
        review_required=review_required,
        review_reason=review_reason,
        quantity=Decimal("1"),
        origin=ORIGIN_B3,
        synced_at=datetime.now(UTC),
    )


def test_build_diagnostics_counts_valid_and_rejected():
    client = DividendosMeClient("a@b.com", "senha")
    spec = _spec("brasil", kind="table")
    positions = [
        _extracted("WEGE3.SA"),
        _extracted("", review_required=True, review_reason="ticker vazio"),
        _extracted("???", review_required=True, review_reason="subgrupo não reconhecido"),
    ]

    diag = client._build_diagnostics(spec, positions)

    assert diag.section == "brasil"
    assert diag.selector_used == "table (thead/tbody)"
    assert diag.raw_rows_detected == 3
    assert diag.valid_rows == 1
    assert diag.rejected_rows == 2
    assert "ticker vazio" in diag.rejection_reasons
    assert "subgrupo não reconhecido" in diag.rejection_reasons


def test_build_diagnostics_selector_label_for_cards():
    client = DividendosMeClient("a@b.com", "senha")
    spec = _spec("criptomoedas", kind="cards")

    diag = client._build_diagnostics(spec, [])

    assert diag.selector_used == "cards (div, por assinatura de texto)"
    assert diag.raw_rows_detected == 0
    assert diag.rejection_reasons == []


# --- Guardas de disponibilidade do Playwright ------------------------------


def test_require_playwright_raises_friendly_error_when_missing(monkeypatch):
    monkeypatch.setattr(client_module, "is_playwright_available", lambda: False)
    with pytest.raises(DividendosMeScrapingError):
        client_module._require_playwright()


def test_fetch_portfolio_requires_playwright(monkeypatch):
    monkeypatch.setattr(client_module, "is_playwright_available", lambda: False)
    client = DividendosMeClient("a@b.com", "senha")
    with pytest.raises(DividendosMeScrapingError):
        client.fetch_portfolio()


def test_test_login_requires_playwright(monkeypatch):
    monkeypatch.setattr(client_module, "is_playwright_available", lambda: False)
    client = DividendosMeClient("a@b.com", "senha")
    with pytest.raises(DividendosMeScrapingError):
        client.test_login()


def test_fetch_income_events_requires_playwright(monkeypatch):
    monkeypatch.setattr(client_module, "is_playwright_available", lambda: False)
    client = DividendosMeClient("a@b.com", "senha")
    with pytest.raises(DividendosMeScrapingError):
        client.fetch_income_events()


def test_fetch_income_monthly_summaries_requires_playwright(monkeypatch):
    # Sprint 23.3: método separado de `fetch_income_events()` — precisa da
    # mesma guarda de Playwright de forma independente.
    monkeypatch.setattr(client_module, "is_playwright_available", lambda: False)
    client = DividendosMeClient("a@b.com", "senha")
    with pytest.raises(DividendosMeScrapingError):
        client.fetch_income_monthly_summaries()
