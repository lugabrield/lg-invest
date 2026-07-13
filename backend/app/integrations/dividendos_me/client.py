"""Cliente de extração da carteira do Dividendos.me via Playwright (Sprint 23).

Por que Playwright em vez de uma API JSON: investigação ao vivo (login
real + inspeção de rede) confirmou uma API REST parcial em
`api.dividendos.me/Portfolio/chart*` (só agregados de alocação), mas
nenhuma chamada de rede capturável carrega a tabela de posições
detalhada — ela é montada no cliente a partir de um mecanismo que não
aparece como request HTTP comum (indício forte de Firebase/Firestore
via listener em tempo real). Sem um endpoint estável para replicar,
extraímos do DOM já renderizado. Ver docs/DIVIDENDOS_ME_INTEGRATION.md.

Correção Sprint 23.1 (bug real em produção): navegar direto via
`page.goto(url)` para uma seção que não seja a ativa por padrão (EUA,
Criptomoedas, Renda Fixa) carrega uma página em branco/com dado errado
— o app guarda o "país"/carteira selecionado em estado interno do
cliente (não na URL), que só é atualizado corretamente por navegação
client-side (clique num link real da barra lateral). Por isso este
módulo nunca usa `page.goto()` para trocar de seção depois do login:
sempre expande o acordeão do país/categoria (quando necessário) e clica
no link real, replicando o que um usuário faria.

Duas seções (Brasil, EUA) usam tabelas `<table>` reais. As outras duas
(Criptomoedas, Renda Fixa) não têm uma "Tabela de Ativos" — a extração
usa a página "Extrato"/"Meu Resumo", cujos ativos aparecem como cards
(divs), não linhas de tabela. Este módulo não faz nenhum cálculo
financeiro nem grava no banco — só login (via `auth.py`) + navegação +
leitura do DOM + delega a normalização para `parser.py`.

Correção Sprint 23.3 (relatada pelo usuário — dry-run reportou "success"
com EUA/Criptomoedas/Renda Fixa vazios, sem nenhum erro): navegar sem
lançar exceção não significa que a seção carregou o conteúdo esperado —
o clique pode "funcionar" (elemento encontrado e clicável) mas o
conteúdo real (tabela/cards) ainda não ter renderizado no momento da
leitura. Duas mudanças: (1) `_goto_section` agora devolve um
`_NavigationOutcome` com o que de fato aconteceu (acordeão
encontrado/clicado, URL final após o clique) — nunca dado sensível, só
para diagnóstico; (2) `_extract_table_section`/`_extract_card_section`
tentam de novo (uma vez, com espera extra) se a primeira leitura vier
vazia, antes de desistir. Isso não resolve sozinho um problema de
navegação real (ex.: precisar de mais um clique/seleção que ainda não
identificamos ao vivo), mas elimina a hipótese mais simples (timing) e
deixa o diagnóstico explícito o bastante para a próxima investigação.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from backend.app.core.logging import get_logger
from backend.app.integrations.dividendos_me.auth import is_playwright_available, login
from backend.app.integrations.dividendos_me.income_parser import (
    NormalizedIncomeEvent,
    NormalizedMonthlySummary,
    parse_monthly_summary,
    parse_upcoming_dividends,
)
from backend.app.integrations.dividendos_me.parser import (
    normalize_position,
    origin_for_section,
    parse_card_lines,
    parse_number,
    parse_percentage,
)
from backend.app.integrations.dividendos_me.schemas import ExtractedPosition, SectionDiagnostics

logger = get_logger("lg_invest.integrations.dividendos_me.client")

BASE_URL = "https://app.dividendos.me"
DEFAULT_TIMEOUT_MS = 45_000

# Sprint 23.3: espera extra antes de tentar ler de novo uma seção que
# voltou vazia na primeira leitura — dá tempo para conteúdo carregado de
# forma assíncrona (ex.: um segundo request após a troca de aba) terminar
# de renderizar antes de desistirmos da seção.
_RETRY_WAIT_MS = 1_800

# "Central de Proventos" — link direto na barra lateral do Brasil (não
# precisa expandir acordeão extra, mesmo grupo de "Meu Resumo"/"Tabela de
# Ativos", confirmado ao vivo). Só mostra dado de Brasil/EUA em renda
# variável — nunca cripto/Tesouro (ver `income_parser.py`).
INCOME_HUB_HREF = "/dividends"

# Rótulos exatos das abas internas do hub de proventos (clique real,
# nunca `page.goto()` — o hub inteiro é uma única URL com estado de aba
# em memória do React). Confirmado ao vivo: clique via `element.click()`
# em JavaScript "puro" (não confiável/untrusted) NÃO troca de aba — só um
# clique de verdade (Playwright `page.click`/`get_by_text().click()`,
# que dispara eventos confiáveis no nível do SO via CDP) funciona.
_INCOME_TAB_ANALISE = "Análise"
_INCOME_TAB_UPCOMING = "Próximos Dividendos"
_INCOME_WALLET_LABELS = ("Carteira (B3)", "Carteira Dolar")

# Diagnóstico reforçado (ajuste pós-Sprint 25, Parte 3): rótulos conhecidos
# checados por presença na página, nunca inventados a partir de uma
# estrutura de DOM que não foi confirmada ao vivo — só reporta se um texto
# exato foi encontrado ou não.
_INCOME_KNOWN_TABS = (_INCOME_TAB_ANALISE, _INCOME_TAB_UPCOMING)

# Diretório padrão para snapshots de debug — só usado quando o modo debug
# é pedido explicitamente (CLI), nunca por padrão. Sempre local; nunca
# enviado a lugar nenhum por este módulo.
DEFAULT_DEBUG_DIR = "debug_dividendos_me"

_DIAGNOSE_PAGE_JS = """
() => {
  return {
    table_count: document.querySelectorAll('table').length,
    canvas_count: document.querySelectorAll('canvas').length,
    svg_count: document.querySelectorAll('svg').length,
  };
}
"""

# Remove <script>/<style> inteiros antes de salvar um snapshot de debug —
# o conteúdo desses blocos nunca é útil para diagnosticar layout e pode
# conter tokens/URLs incidentais que não precisam ir para um arquivo local.
_SCRIPT_OR_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_DEBUG_HTML_MAX_CHARS = 50_000


@dataclass(frozen=True)
class _SectionSpec:
    key: str
    href: str
    # Rótulo do item de menu de nível superior que precisa ser clicado
    # primeiro para revelar `href` na barra lateral (acordeão fechado por
    # padrão para tudo que não for Brasil, confirmado ao vivo). `None`
    # quando o link já está visível assim que o dashboard carrega.
    accordion_label: str | None
    kind: str  # "table" | "cards"


@dataclass(frozen=True)
class _NavigationOutcome:
    """Sprint 23.3 — o que realmente aconteceu ao tentar navegar até uma
    seção, para alimentar `SectionDiagnostics.navigation_detail`. Nunca
    contém HTML bruto nem dado sensível, só sinais binários e a URL final
    (a própria URL do Dividendos.me não é sensível — é a mesma que
    aparece na barra de endereço do usuário)."""

    accordion_label: str | None
    accordion_clicked: bool
    final_url: str | None

    def describe(self) -> str:
        accordion_part = (
            "sem acordeão"
            if self.accordion_label is None
            else f"acordeão {self.accordion_label!r} "
            + ("clicado" if self.accordion_clicked else "NÃO encontrado/clicado")
        )
        url_part = f"url final={self.final_url}" if self.final_url else "url final=desconhecida"
        return f"{accordion_part}; {url_part}"


# Seções confirmadas ao vivo nesta sprint (login real + navegação real,
# incluindo a correção de 23.1): Brasil e EUA usam a tela "Tabela de
# Ativos" (tabelas reais, uma por subgrupo — Fundos Imobiliários/Ações
# no Brasil; Ações/ETFs/REITs nos EUA). Criptomoedas e Renda Fixa não
# têm uma "Tabela de Ativos" própria — usam cards.
#
# Correção Sprint 23.2 (confirmada pelo usuário): Criptomoedas usa
# especificamente "Criptomoedas → Extrato" (`/criptos/extrato`) como
# fonte de POSIÇÃO — nunca "Criptomoedas → Meu Resumo". O card do BTC
# em "Extrato" tem o formato "Carteira: Carteira Criptomoeda (Manual)" /
# "btc" / "Quantidade:" / "Preço Médio:" / "Preço Atual:" / "Total:" /
# "Rentabilidade:" / "Ver Operações" (ver `parser.parse_card_lines`, que
# descarta o par "Carteira:"/valor antes de extrair o nome do ativo).
# Renda Fixa continua usando "Meu Resumo" (`/renda-fixa/meu-resumo`) —
# essa seção não tem uma tela "Extrato" equivalente.
_SECTIONS: tuple[_SectionSpec, ...] = (
    _SectionSpec("brasil", "/renda-variavel/brasil/tabela-ativos", None, "table"),
    _SectionSpec("eua", "/renda-variavel/eua/tabela-ativos", "Estados Unidos", "table"),
    _SectionSpec("criptomoedas", "/criptos/extrato", "Criptomoedas", "cards"),
    _SectionSpec("renda_fixa", "/renda-fixa/meu-resumo", "Renda Fixa", "cards"),
)

# Extrai por LABEL de cabeçalho (não por posição de coluna): mais
# resistente a mudanças de layout/ordem entre seções do que um índice
# fixo. Remove a seta de ordenação (ex.: "ATIVO\n↑") antes de comparar —
# sem isso, a coluna atualmente ordenada nunca bate com o rótulo
# esperado e a linha inteira vira ticker vazio (bug real, Sprint 23.1).
_EXTRACT_TABLE_JS = """
() => {
  const results = [];
  document.querySelectorAll('table').forEach(table => {
    const headerCells = Array.from(table.querySelectorAll('thead th')).map(th =>
      th.innerText.replace(/[\\u2191\\u2193\\u25B2\\u25BC]/g, '').replace(/\\s+/g, ' ').trim()
    );
    if (headerCells.length === 0) return;

    // Subcabeçalho do subgrupo (ex.: "Fundos Imobiliários"/"Ações"): não é
    // irmão direto da tabela, e sim irmão do WRAPPER da tabela (um nível
    // acima) — por isso o loop sobe para o parentElement entre cada
    // checagem de previousElementSibling (bug real corrigido, Sprint 23.1).
    let subheader = null;
    let node = table;
    for (let level = 0; level < 6 && node; level++) {
      if (node.previousElementSibling) {
        const text = (node.previousElementSibling.innerText || '').replace(/\\s+/g, ' ').trim();
        if (text) { subheader = text; break; }
      }
      node = node.parentElement;
    }

    table.querySelectorAll('tbody tr').forEach(tr => {
      const cells = Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
      if (cells.length === 0) return;
      const row = { __subheader: subheader };
      headerCells.forEach((label, idx) => {
        row[label] = cells[idx] !== undefined ? cells[idx] : null;
      });
      results.push(row);
    });
  });
  return results;
}
"""

# Criptomoedas/Renda Fixa não usam <table> — cada ativo é um card (div)
# identificado pelo conteúdo (não por classe CSS, que muda com estilo).
# Só o card mais interno que contém a assinatura é usado (evita capturar
# o wrapper inteiro da página, cujo innerText também "contém" o texto de
# todos os cards filhos).
#
# Correção Sprint 23.2 (bug real reportado pelo usuário — BTC saía com
# ticker vazio): o card de cripto tem uma div "stats" aninhada que TAMBÉM
# contém "Quantidade:"/"Preço Médio:"/"Total:" (sem o nome do ativo, que
# fica num nível acima). Como essa div interna também batia a assinatura
# antiga, ela era escolhida em vez do card completo — o nome ("btc") ficava
# de fora e a linha virava ticker vazio/`review_required`. Confirmado ao
# vivo: adicionar "Ver Operações" (rodapé de ação do card, que só existe
# no nível do card inteiro) à assinatura força a escolha do card certo.
_EXTRACT_CRYPTO_CARDS_JS = """
() => {
  const results = [];
  document.querySelectorAll('div').forEach(el => {
    const text = el.innerText || '';
    if (
      !text.includes('Quantidade:') ||
      !text.includes('Preço Médio:') ||
      !text.includes('Total:') ||
      !text.includes('Ver Opera')
    ) return;
    const hasMatchingChild = Array.from(el.querySelectorAll('div')).some(child => {
      const t = child.innerText || '';
      return (
        t.includes('Quantidade:') &&
        t.includes('Preço Médio:') &&
        t.includes('Total:') &&
        t.includes('Ver Opera')
      );
    });
    if (hasMatchingChild) return;
    results.push(text.split('\\n').map(s => s.trim()).filter(Boolean));
  });
  return results;
}
"""

# Cards de Renda Fixa (Tesouro) não repetem "Quantidade"/"Preço Médio" —
# só "Valor atual". O card com nome/emissor fica um nível acima do menor
# elemento que contém essa assinatura (confirmado ao vivo, Sprint 23.1).
_EXTRACT_FIXED_INCOME_CARDS_JS = """
() => {
  const results = [];
  document.querySelectorAll('div').forEach(el => {
    const text = el.innerText || '';
    if (!text.includes('Valor atual')) return;
    const hasMatchingChild = Array.from(el.querySelectorAll('div')).some(
      child => (child.innerText || '').includes('Valor atual')
    );
    if (hasMatchingChild) return;
    const card = el.parentElement || el;
    results.push(card.innerText.split('\\n').map(s => s.trim()).filter(Boolean));
  });
  return results;
}
"""


# Aba "Análise" do hub de proventos: tabela real (thead/tbody) ano x mês,
# uma tabela por vez para a carteira (BR/Dólar) atualmente selecionada no
# toggle — por isso o cliente clica em cada rótulo de carteira e chama
# esta extração de novo a cada clique.
_EXTRACT_MONTHLY_TABLE_JS = """
() => {
  const table = document.querySelector('table');
  if (!table) return [];
  const headerCells = Array.from(table.querySelectorAll('thead th')).map(th =>
    th.innerText.replace(/\\s+/g, ' ').trim()
  );
  const rows = [];
  table.querySelectorAll('tbody tr').forEach(tr => {
    const cells = Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
    if (cells.length === 0) return;
    const row = {};
    headerCells.forEach((label, idx) => {
      row[label] = cells[idx] !== undefined ? cells[idx] : null;
    });
    rows.push(row);
  });
  return rows;
}
"""

# Aba "Próximos Dividendos" (aba padrão do hub): lista agrupada por dia de
# pagamento, cards div (não tabela). Cada card mostra DOIS valores: um
# convertido para BRL (negrito) e um na moeda nativa do ativo (cinza,
# menor) — ver `income_parser._detect_currency_and_amount`. Agrupamento
# por dia feito por ORDEM NO DOCUMENTO (o cabeçalho "Data de Pagamento"
# aparece imediatamente antes das linhas daquele dia), não por ancestralidade
# direta — mais resistente a mudanças de wrapper/nesting.
_EXTRACT_UPCOMING_DIVIDENDS_JS = """
() => {
  const allDivs = Array.from(document.querySelectorAll('div'));

  const isHeader = (el) => {
    const t = (el.innerText || '').trim();
    return t.startsWith('Data de Pagamento') && t.length < 200;
  };

  const isRowCard = (el) => {
    const t = el.innerText || '';
    if (t.startsWith('Data de Pagamento')) return false;
    if (!t.includes('R$') && !t.includes('$')) return false;
    if (!el.querySelector('button')) return false;
    const hasMatchingChild = Array.from(el.querySelectorAll('div')).some(child => {
      const ct = child.innerText || '';
      return (
        !ct.startsWith('Data de Pagamento') &&
        (ct.includes('R$') || ct.includes('$')) &&
        !!child.querySelector('button')
      );
    });
    return !hasMatchingChild;
  };

  const items = [];
  for (const el of allDivs) {
    if (isHeader(el)) items.push({ kind: 'header', el });
    else if (isRowCard(el)) items.push({ kind: 'row', el });
  }

  // Evita contar a mesma linha 2x se ela bater a assinatura em mais de um
  // nível (mantém só o elemento mais externo entre os que se contêm).
  const rows = items.filter(i => i.kind === 'row');
  const keepRow = (item) =>
    !rows.some(other => other.el !== item.el && item.el.contains(other.el));
  const filtered = items.filter(i => i.kind === 'header' || keepRow(i));

  const groups = [];
  let current = null;
  for (const item of filtered) {
    if (item.kind === 'header') {
      const m = (item.el.innerText || '').match(/(\\d{2})\\/(\\d{2})/);
      current = { payment_date_ddmm: m ? m[0] : null, rows: [] };
      groups.push(current);
      continue;
    }
    if (!current) continue;
    const el = item.el;
    const btn = el.querySelector('button');
    const badges = Array.from(el.querySelectorAll('span')).map(s => s.innerText.trim()).filter(Boolean);
    const values = Array.from(el.querySelectorAll('p')).map(p => p.innerText.trim()).filter(Boolean);
    current.rows.push({
      ticker: btn ? btn.innerText.trim() : '',
      type: badges[0] || null,
      asset_class: badges[1] || null,
      display_value: values[0] || null,
      native_value: values[1] || null,
    });
  }
  return groups;
}
"""


class DividendosMeScrapingError(Exception):
    """Erro de extração/layout — mensagem sempre segura para exibir ao usuário."""


def _require_playwright() -> None:
    if not is_playwright_available():
        raise DividendosMeScrapingError(
            "Playwright não está instalado neste ambiente. "
            "Rode a sincronização localmente (python -m scripts.sync_dividendos_me)."
        )


class DividendosMeClient:
    """Orquestra uma sessão Playwright efêmera: login -> navega -> extrai -> fecha.

    Nunca reaproveita sessão entre execuções (sem `storage_state` salvo
    em disco) — cada chamada faz login do zero e fecha o browser ao
    final, mesmo em caso de erro.
    """

    def __init__(self, email: str, password: str, *, headless: bool = True):
        self._email = email
        self._password = password
        self._headless = headless

    def test_login(self) -> bool:
        """Só confirma que o login funciona; fecha tudo sem extrair nada e sem salvar nada."""
        _require_playwright()
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self._headless)
            try:
                page = browser.new_page()
                login(page, self._email, self._password, timeout_ms=DEFAULT_TIMEOUT_MS)
                return True
            finally:
                browser.close()

    def fetch_portfolio(
        self,
    ) -> tuple[list[ExtractedPosition], list[str], list[SectionDiagnostics]]:
        """Faz login e extrai as posições de todas as seções conhecidas.

        Devolve `(posições, seções_que_falharam, diagnóstico_por_seção)`
        — uma seção falhar nunca interrompe as demais. `diagnóstico` traz
        contagens (linhas brutas/válidas/rejeitadas) e motivos de
        rejeição já sanitizados, nunca HTML bruto ou dado sensível.
        """
        _require_playwright()
        from playwright.sync_api import sync_playwright

        positions: list[ExtractedPosition] = []
        failed_sections: list[str] = []
        diagnostics: list[SectionDiagnostics] = []
        synced_at = datetime.now(UTC)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self._headless)
            try:
                page = browser.new_page()
                login(page, self._email, self._password, timeout_ms=DEFAULT_TIMEOUT_MS)

                for spec in _SECTIONS:
                    try:
                        outcome = self._goto_section(page, spec)
                        if spec.kind == "table":
                            raw_rows, retried = self._extract_table_section(page)
                            section_positions = [
                                self._to_extracted_position(row, spec.key, synced_at)
                                for row in raw_rows
                            ]
                        else:
                            raw_cards, retried = self._extract_card_section(page, spec)
                            section_positions = [
                                self._card_to_extracted_position(lines, spec.key, synced_at)
                                for lines in raw_cards
                            ]
                    except (
                        Exception
                    ):  # noqa: BLE001 - layout/timeout não pode derrubar as demais seções
                        logger.warning(
                            "Falha ao extrair a seção %s do Dividendos.me (detalhe suprimido).",
                            spec.key,
                        )
                        failed_sections.append(spec.key)
                        continue

                    diagnostics.append(
                        self._build_diagnostics(
                            spec,
                            section_positions,
                            navigation_detail=self._navigation_detail(outcome, retried),
                        )
                    )
                    positions.extend(section_positions)
            finally:
                browser.close()

        return positions, failed_sections, diagnostics

    @staticmethod
    def _navigation_detail(outcome: _NavigationOutcome, retried: bool) -> str:
        suffix = "; releitura após espera extra foi necessária" if retried else ""
        return outcome.describe() + suffix

    def fetch_income_events(
        self,
    ) -> tuple[list[NormalizedIncomeEvent], list[str], list[SectionDiagnostics]]:
        """Faz login (sessão própria, separada de `fetch_portfolio()`) e
        extrai o CALENDÁRIO FUTURO de proventos (aba "Próximos
        Dividendos") da "Central de Proventos".

        Correção Sprint 23.3: este método só cobre calendário futuro —
        o histórico mensal agregado (aba "Análise") tem seu próprio
        método, `fetch_income_monthly_summaries()`, e vai para uma
        tabela própria (`income_monthly_summaries`), nunca mais
        misturado com `income_events` aqui.

        Isolado de `fetch_portfolio()` de propósito: uma falha aqui nunca
        pode impedir a sincronização da carteira (Prioridade explícita do
        usuário). Devolve `(eventos, seções_que_falharam, diagnóstico)`
        com `"income_calendar"` como única chave de seção possível.
        """
        _require_playwright()
        from playwright.sync_api import sync_playwright

        events: list[NormalizedIncomeEvent] = []
        failed_sections: list[str] = []
        diagnostics: list[SectionDiagnostics] = []
        current_year = datetime.now(UTC).year

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self._headless)
            try:
                page = browser.new_page()
                login(page, self._email, self._password, timeout_ms=DEFAULT_TIMEOUT_MS)
                self._goto_income_hub(page)

                try:
                    upcoming_events, raw_rows_count = self._extract_upcoming_dividends(
                        page, current_year
                    )
                    events.extend(upcoming_events)
                    rejected = max(raw_rows_count - len(upcoming_events), 0)
                    reasons = ["ticker vazio ou valor não positivo"] if rejected else []
                    diagnostics.append(
                        SectionDiagnostics(
                            section="income_calendar",
                            selector_used="cards (div, agrupados por dia de pagamento)",
                            raw_rows_detected=raw_rows_count,
                            valid_rows=len(upcoming_events),
                            rejected_rows=rejected,
                            rejection_reasons=reasons,
                        )
                    )
                except Exception:  # noqa: BLE001 - proventos nunca derruba a carteira
                    logger.warning(
                        "Falha ao extrair o calendário de próximos dividendos (detalhe suprimido)."
                    )
                    failed_sections.append("income_calendar")
            finally:
                browser.close()

        return events, failed_sections, diagnostics

    def fetch_income_monthly_summaries(
        self,
        *,
        debug: bool = False,
        debug_dir: str | None = None,
    ) -> tuple[list[NormalizedMonthlySummary], list[str], list[SectionDiagnostics]]:
        """Faz login (sessão própria) e extrai o HISTÓRICO MENSAL agregado
        (aba "Central de Proventos" -> "Análise", tabela ano x mês, uma
        por carteira BR/Dólar). Sprint 23.3: separado de
        `fetch_income_events()` (calendário futuro) — nunca mistura os
        dois na mesma tabela/dedup.

        `debug=True` (ajuste pós-Sprint 25, Parte 3): além do diagnóstico
        padrão, salva localmente um snapshot de HTML sanitizado (sem
        `<script>`/`<style>`, truncado) e um screenshot da página no
        estado final da extração — nunca enviados a lugar nenhum, só para
        o usuário inspecionar manualmente por que `raw_rows_detected`
        ficou em 0. `debug_dir` (default `DEFAULT_DEBUG_DIR`) é sempre um
        caminho local.

        Devolve `(resumos, seções_que_falharam, diagnóstico)` com
        `"income_monthly"` como única chave de seção possível.
        """
        _require_playwright()
        from playwright.sync_api import sync_playwright

        summaries: list[NormalizedMonthlySummary] = []
        failed_sections: list[str] = []
        diagnostics: list[SectionDiagnostics] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self._headless)
            try:
                page = browser.new_page()
                login(page, self._email, self._password, timeout_ms=DEFAULT_TIMEOUT_MS)
                self._goto_income_hub(page)

                try:
                    monthly_summaries, wallets_found, tabs_clicked = (
                        self._extract_monthly_summary_all_wallets(page)
                    )
                    summaries.extend(monthly_summaries)
                    diag_extra = self._diagnose_income_page(page, debug=debug, debug_dir=debug_dir)
                    # "Raw" aqui é quantas linhas-ano foram encontradas (uma
                    # tabela sem nenhuma linha indicaria falha de seletor);
                    # meses com R$ 0,00 não são "rejeitados", só não geram
                    # resumo (não houve provento naquele mês).
                    diagnostics.append(
                        SectionDiagnostics(
                            section="income_monthly",
                            selector_used="table (thead/tbody), aba Análise por carteira",
                            raw_rows_detected=wallets_found,
                            valid_rows=len(monthly_summaries),
                            rejected_rows=0,
                            rejection_reasons=[],
                            navigation_detail=(
                                "carteiras clicadas com sucesso: "
                                + (", ".join(tabs_clicked) if tabs_clicked else "nenhuma")
                            ),
                            **diag_extra,
                        )
                    )
                except Exception:  # noqa: BLE001 - proventos nunca derruba a carteira
                    logger.warning(
                        "Falha ao extrair o histórico mensal de proventos (detalhe suprimido)."
                    )
                    failed_sections.append("income_monthly")
                    # Mesmo com falha, tenta coletar o diagnóstico reforçado
                    # no estado em que a página ficou — é exatamente o
                    # cenário que mais precisa de diagnóstico (raw_rows=0).
                    try:
                        diag_extra = self._diagnose_income_page(
                            page, debug=debug, debug_dir=debug_dir
                        )
                        diagnostics.append(
                            SectionDiagnostics(
                                section="income_monthly",
                                selector_used="table (thead/tbody), aba Análise por carteira",
                                raw_rows_detected=0,
                                valid_rows=0,
                                rejected_rows=0,
                                rejection_reasons=[],
                                navigation_detail="extração levantou exceção antes de concluir",
                                **diag_extra,
                            )
                        )
                    except (
                        Exception
                    ):  # noqa: BLE001 - diagnóstico nunca pode mascarar o erro original
                        pass
            finally:
                browser.close()

        return summaries, failed_sections, diagnostics

    def _diagnose_income_page(
        self, page, *, debug: bool = False, debug_dir: str | None = None
    ) -> dict:
        """Coleta sinais honestos sobre o estado atual da página — nunca
        inventa uma estrutura de DOM que não foi confirmada ao vivo, só
        reporta presença/ausência de rótulos conhecidos e contagens
        genéricas (`table`/`canvas`/`svg`). Nunca levanta exceção: um
        diagnóstico que falha não pode mascarar o erro/resultado original."""
        result: dict = {
            "final_url": None,
            "tabs_found": [],
            "wallet_selectors_found": [],
            "table_elements_found": 0,
            "canvas_or_svg_detected": False,
            "debug_snapshot_path": None,
            "debug_screenshot_path": None,
        }
        try:
            result["final_url"] = page.url
        except Exception:  # noqa: BLE001
            pass

        for label in _INCOME_KNOWN_TABS:
            try:
                if page.get_by_text(label, exact=True).count() > 0:
                    result["tabs_found"].append(label)
            except Exception:  # noqa: BLE001
                pass

        for label in _INCOME_WALLET_LABELS:
            try:
                if page.get_by_text(label, exact=True).count() > 0:
                    result["wallet_selectors_found"].append(label)
            except Exception:  # noqa: BLE001
                pass

        try:
            counts = page.evaluate(_DIAGNOSE_PAGE_JS) or {}
            result["table_elements_found"] = counts.get("table_count", 0)
            result["canvas_or_svg_detected"] = bool(
                counts.get("canvas_count", 0) or counts.get("svg_count", 0)
            )
        except Exception:  # noqa: BLE001
            pass

        if debug:
            target_dir = Path(debug_dir or DEFAULT_DEBUG_DIR)
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

                html = page.content()
                sanitized_html = _SCRIPT_OR_STYLE_RE.sub("", html)[:_DEBUG_HTML_MAX_CHARS]
                html_path = target_dir / f"income_monthly_{stamp}.html"
                html_path.write_text(sanitized_html, encoding="utf-8")
                result["debug_snapshot_path"] = str(html_path)
            except Exception:  # noqa: BLE001 - debug nunca pode derrubar a extração
                pass

            try:
                screenshot_path = target_dir / f"income_monthly_{stamp}.png"
                page.screenshot(path=str(screenshot_path))
                result["debug_screenshot_path"] = str(screenshot_path)
            except Exception:  # noqa: BLE001
                pass

        return result

    def _goto_income_hub(self, page) -> None:
        """Navega até "Central de Proventos" via clique real (client-side),
        nunca `page.goto()` — mesmo motivo do `_goto_section`."""
        page.click(f'a[href="{INCOME_HUB_HREF}"]', timeout=15_000)
        try:
            page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:  # noqa: BLE001 - polling em background pode nunca "ociar"
            pass
        page.wait_for_timeout(1_500)

    def _click_real(self, page, text: str) -> None:
        """Clique de verdade (via CDP, evento confiável) num elemento pelo
        texto exato — confirmado ao vivo que só isso troca de aba dentro do
        hub de proventos (um `element.click()` em JavaScript puro não
        troca de aba, mesmo bem localizado no DOM)."""
        page.get_by_text(text, exact=True).first.click(timeout=10_000)
        page.wait_for_timeout(2_000)

    def _extract_monthly_summary_all_wallets(
        self, page
    ) -> tuple[list[NormalizedMonthlySummary], int, list[str]]:
        """Clica na aba "Análise" e, para cada carteira conhecida, tenta
        ler a tabela ano x mês. Correção (ajuste pós-Sprint 25, Parte 3):
        antes só havia UMA leitura por carteira, sem espera nem nova
        tentativa — mesma classe de bug de timing já corrigida em
        `_extract_table_section` (Sprint 23.3) para a carteira principal,
        mas nunca aplicada aqui. Agora espera a tabela aparecer e tenta de
        novo (uma vez, com espera extra) se a primeira leitura vier vazia,
        antes de considerar a carteira sem dado."""
        self._click_real(page, _INCOME_TAB_ANALISE)

        summaries: list[NormalizedMonthlySummary] = []
        year_rows_found = 0
        wallets_clicked: list[str] = []
        for wallet_label in _INCOME_WALLET_LABELS:
            try:
                self._click_real(page, wallet_label)
            except Exception:  # noqa: BLE001 - carteira pode não existir p/ este usuário
                continue
            wallets_clicked.append(wallet_label)

            raw_rows = self._extract_monthly_table_with_retry(page)
            year_rows_found += len(raw_rows)
            summaries.extend(parse_monthly_summary(raw_rows, wallet=wallet_label))
        return summaries, year_rows_found, wallets_clicked

    def _extract_monthly_table_with_retry(self, page) -> list[dict]:
        try:
            if page.query_selector("table") is not None:
                page.wait_for_selector("table", timeout=DEFAULT_TIMEOUT_MS)
        except Exception:  # noqa: BLE001 - segue para a leitura mesmo se a espera falhar
            pass
        raw = page.evaluate(_EXTRACT_MONTHLY_TABLE_JS) or []
        if raw:
            return raw

        # Primeira leitura vazia sem erro — mesma hipótese de timing já
        # tratada para a carteira principal (Sprint 23.3): dá mais tempo e
        # tenta de novo antes de considerar a carteira sem dado.
        page.wait_for_timeout(_RETRY_WAIT_MS)
        return page.evaluate(_EXTRACT_MONTHLY_TABLE_JS) or []

    def _extract_upcoming_dividends(
        self, page, current_year: int
    ) -> tuple[list[NormalizedIncomeEvent], int]:
        # "Próximos Dividendos" é a aba padrão do hub — voltar a ela
        # explicitamente em vez de assumir estado, já que a extração do
        # agregado mensal (se rodou antes) troca de aba.
        self._click_real(page, _INCOME_TAB_UPCOMING)
        raw_groups = page.evaluate(_EXTRACT_UPCOMING_DIVIDENDS_JS) or []
        raw_rows_count = sum(len(g.get("rows", [])) for g in raw_groups)
        events = parse_upcoming_dividends(raw_groups, start_year=current_year)
        return events, raw_rows_count

    def _goto_section(self, page, spec: _SectionSpec) -> _NavigationOutcome:
        """Navega até a seção via clique real (client-side), nunca via
        `page.goto()` — ver docstring do módulo para o motivo. Devolve um
        `_NavigationOutcome` (Sprint 23.3) para diagnóstico — nunca dado
        sensível, só sinais de navegação (acordeão clicado, URL final)."""
        accordion_clicked = False
        if spec.accordion_label:
            try:
                page.get_by_text(spec.accordion_label, exact=True).first.click(timeout=5_000)
                page.wait_for_timeout(400)
                accordion_clicked = True
            except Exception:  # noqa: BLE001 - acordeão pode já estar expandido
                pass

        page.click(f'a[href="{spec.href}"]', timeout=15_000)
        try:
            page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:  # noqa: BLE001 - polling em background pode nunca "ociar"
            pass
        page.wait_for_timeout(1_200)

        final_url = None
        try:
            final_url = page.url
        except Exception:  # noqa: BLE001 - nunca deixar a instrumentação derrubar a extração
            pass

        return _NavigationOutcome(
            accordion_label=spec.accordion_label,
            accordion_clicked=accordion_clicked,
            final_url=final_url,
        )

    def _extract_table_section(self, page) -> tuple[list[dict], bool]:
        if page.query_selector("table") is not None:
            page.wait_for_selector("table", timeout=DEFAULT_TIMEOUT_MS)
        raw = page.evaluate(_EXTRACT_TABLE_JS) or []
        if raw:
            return raw, False

        # Sprint 23.3: primeira leitura veio vazia sem nenhum erro — dá
        # mais tempo para o conteúdo renderizar e tenta de novo antes de
        # desistir da seção (elimina a hipótese mais simples de timing
        # antes de precisar investigar navegação/seleção adicional).
        page.wait_for_timeout(_RETRY_WAIT_MS)
        raw = page.evaluate(_EXTRACT_TABLE_JS) or []
        return raw, True

    def _extract_card_section(self, page, spec: _SectionSpec) -> tuple[list[list[str]], bool]:
        js = (
            _EXTRACT_CRYPTO_CARDS_JS
            if spec.key == "criptomoedas"
            else _EXTRACT_FIXED_INCOME_CARDS_JS
        )
        raw = page.evaluate(js) or []
        if raw:
            return raw, False

        page.wait_for_timeout(_RETRY_WAIT_MS)
        raw = page.evaluate(js) or []
        return raw, True

    def _build_diagnostics(
        self,
        spec: _SectionSpec,
        positions: list[ExtractedPosition],
        *,
        navigation_detail: str | None = None,
    ) -> SectionDiagnostics:
        rejected = [p for p in positions if p.review_required]
        reasons = sorted({p.review_reason for p in rejected if p.review_reason})[:10]
        return SectionDiagnostics(
            section=spec.key,
            selector_used=(
                "table (thead/tbody)"
                if spec.kind == "table"
                else "cards (div, por assinatura de texto)"
            ),
            raw_rows_detected=len(positions),
            valid_rows=len(positions) - len(rejected),
            rejected_rows=len(rejected),
            rejection_reasons=reasons,
            navigation_detail=navigation_detail,
        )

    def _to_extracted_position(
        self, row: dict, section: str, synced_at: datetime
    ) -> ExtractedPosition:
        raw_ticker = row.get("ATIVO") or ""
        subheader = row.get("__subheader")
        normalized = normalize_position(raw_ticker, section=section, subheader=subheader)
        origin = origin_for_section(section)

        def field(label: str):
            return row.get(label)

        return ExtractedPosition(
            raw_ticker=raw_ticker,
            name=None,  # tabela não expõe nome do ativo, só ticker (ver docs)
            ticker=normalized.ticker,
            asset_class=normalized.asset_class,
            country=normalized.country,
            currency=normalized.currency,
            is_manual=normalized.is_manual,
            review_required=normalized.review_required,
            review_reason=normalized.review_reason,
            quantity=parse_number(field("QNT")) or Decimal("0"),
            average_price=parse_number(field("P.M.")),
            current_price=parse_number(field("ATUAL")),
            current_value=parse_number(field("TOTAL")),
            return_pct=parse_percentage(field("RENT")),
            daily_change_pct=parse_percentage(field("VAR")),
            dividend_yield_pct=parse_percentage(field("DIV")),
            v_vp=parse_number(field("V/VP")),
            origin=origin,
            section=section,
            synced_at=synced_at,
        )

    def _card_to_extracted_position(
        self, lines: list[str], section: str, synced_at: datetime
    ) -> ExtractedPosition:
        fields = parse_card_lines(lines)
        raw_ticker = fields.get("__name", "")
        normalized = normalize_position(raw_ticker, section=section, name=raw_ticker)
        origin = origin_for_section(section)

        # Cards não expõem quantidade para Renda Fixa (só "Valor atual") —
        # 1 representa "uma posição", nunca inventamos uma quantidade real.
        quantity = parse_number(fields.get("quantity"))
        if quantity is None:
            quantity = Decimal("1")

        return ExtractedPosition(
            raw_ticker=raw_ticker,
            name=raw_ticker or None,
            ticker=normalized.ticker,
            asset_class=normalized.asset_class,
            country=normalized.country,
            currency=normalized.currency,
            is_manual=normalized.is_manual,
            review_required=normalized.review_required,
            review_reason=normalized.review_reason,
            quantity=quantity,
            average_price=parse_number(fields.get("average_price")),
            current_price=parse_number(fields.get("current_price")),
            current_value=parse_number(fields.get("current_value")),
            return_pct=parse_percentage(fields.get("return_pct")),
            origin=origin,
            section=section,
            synced_at=synced_at,
        )
