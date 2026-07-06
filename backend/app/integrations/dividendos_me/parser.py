"""Normalização pura de dados extraídos do Dividendos.me (Sprint 23).

Nenhuma função aqui acessa rede ou banco — só transforma texto bruto
(números em formato BR/US, percentuais, tickers, linhas de card) em
valores tipados. Isso torna o módulo inteiro testável sem Playwright/
mock de HTTP.

Convenção de sinal/escala idêntica ao resto da LG INVEST (Sprint 22):
percentuais viram fração 0..1 (6,52% -> 0.0652), nunca "6.52" solto.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from backend.app.integrations.dividendos_me.schemas import (
    ORIGIN_B3,
    ORIGIN_CRYPTO,
    ORIGIN_INTERNATIONAL,
    NormalizedTicker,
)

_CURRENCY_OR_SIGN_NOISE = re.compile(r"[Rr]\$|US\$|\$|\s|\+")

# Setas de ordenação que o Dividendos.me anexa ao rótulo da coluna
# atualmente ordenada (ex.: "ATIVO\n↑") — precisam ser removidas antes de
# comparar com os rótulos esperados, senão `row.get("ATIVO")` nunca bate
# com a chave real `"ATIVO ↑"` (bug real encontrado em produção, Sprint 23.1).
_SORT_ARROW_PATTERN = re.compile(r"[↑↓▲▼]")

# Classes de ativo por rótulo de subgrupo, para as tabelas de "Ações",
# "Fundos Imobiliários", "ETFs", "BDRs" (Brasil) e "Ações"/"ETFs"/"REITs"
# (EUA) — vistas ao vivo na tela "Tabela de Ativos" do Dividendos.me.
# Comparação por substring (não igualdade exata): o rótulo real observado
# ao vivo para ETFs nos EUA veio como "ETF\nETFs" (um badge + o nome do
# grupo concatenados), não a string exata "ETFs".
_BR_SUBHEADER_ASSET_CLASS = {
    "Fundos Imobiliários": "fii",
    "Ações": "stock",
    "ETFs": "etf",
    # BDR representa uma ação estrangeira negociada na B3 em BRL (ticker
    # com sufixo .SA, ex.: AAPL34.SA) — tratado como stock/BR para fins
    # de carteira, mesma convenção usada pelo Yahoo Finance para BDRs.
    "BDRs": "stock",
}
_US_SUBHEADER_ASSET_CLASS = {
    "Ações": "stock",
    "ETFs": "etf",
    "REITs": "reit",
}

_TESOURO_INDEXER_PATTERNS = (
    ("IPCA+", "IPCA"),
    ("IPCA", "IPCA"),
    ("SELIC", "SELIC"),
    ("PREFIXADO", "PREFIXADO"),
    ("PRÉ-FIXADO", "PREFIXADO"),
    ("PRE-FIXADO", "PREFIXADO"),
)
_YEAR_PATTERN = re.compile(r"(20\d{2})")

# Rótulos de campo conhecidos nos cards de Criptomoedas/Renda Fixa (não são
# tabelas <table> — ver `docs/DIVIDENDOS_ME_INTEGRATION.md`). Comparação
# sempre em minúsculas e sem ":" à direita ("Quantidade:" == "quantidade").
_CARD_FIELD_LABELS = {
    "quantidade": "quantity",
    "preço médio": "average_price",
    "preço atual": "current_price",
    "total": "current_value",
    "valor atual": "current_value",
    "rentabilidade": "return_pct",
}
_CARD_IGNORED_LABELS = {"ver operações", "editar"}

# Rótulos de "label: valor" que devem ser descartados INTEIROS (label +
# valor), nunca viram campo nem entram no nome do ativo. Confirmado ao
# vivo (Sprint 23.2, tela "Criptomoedas → Extrato"): o card de cripto
# começa com "Carteira:" / "Carteira Criptomoeda (Manual)" ANTES do nome
# do ativo ("btc") — sem descartar esse par, o nome do ativo saía
# poluído com o texto da carteira (bug real: "btc" nunca era reconhecido
# como tal, pois `__name` virava "Carteira: Carteira Criptomoeda
# (Manual) btc").
_CARD_LABELED_IGNORED = {"carteira"}


def clean_header_label(raw: str | None) -> str:
    """Normaliza o texto de um `<th>`: remove seta de ordenação e colapsa
    quebras de linha/espaços em um único espaço, depois `strip()`.

    Sem isso, um cabeçalho ordenado (ex.: "ATIVO\\n↑") nunca bate com o
    rótulo esperado ("ATIVO"), e a linha inteira vira ticker vazio — bug
    real reportado em produção nesta sprint.
    """
    if raw is None:
        return ""
    text = _SORT_ARROW_PATTERN.sub("", raw)
    return re.sub(r"\s+", " ", text).strip()


def _match_subheader(subheader: str | None, mapping: dict[str, str]) -> str | None:
    """Casa o subcabeçalho por substring, não por igualdade exata.

    O rótulo real de um subgrupo pode vir concatenado com um badge (ex.:
    "ETF\\nETFs" em vez de "ETFs") — normalizamos espaços e procuramos a
    chave conhecida como substring do texto observado.
    """
    text = re.sub(r"\s+", " ", (subheader or "")).strip()
    for key, value in mapping.items():
        if key in text:
            return value
    return None


def parse_number(raw: str | None) -> Decimal | None:
    """Normaliza um número em formato BR (1.234,56) ou US (1,234.56),
    com ou sem símbolo de moeda (R$/US$/$) e com ou sem sinal (+/-).

    Nunca levanta exceção: texto não interpretável vira `None`, para o
    chamador decidir como tratar dado ausente/corrompido (nunca inventa
    um valor).
    """
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None

    text = _CURRENCY_OR_SIGN_NOISE.sub("", text)
    text = text.replace("%", "")

    is_negative = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
    text = text.strip("()").lstrip("-").strip()
    if not text:
        return None

    has_comma = "," in text
    has_dot = "." in text
    if has_comma and has_dot:
        if text.rfind(",") > text.rfind("."):
            # Formato BR: ponto é separador de milhar, vírgula é decimal.
            text = text.replace(".", "").replace(",", ".")
        else:
            # Formato US: vírgula é separador de milhar, ponto é decimal.
            text = text.replace(",", "")
    elif has_comma and not has_dot:
        # "6,52" -> decimal com vírgula (padrão BR para número sem milhar).
        text = text.replace(",", ".")
    # Só ponto, ou nenhum separador: já está em formato Decimal válido.

    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return -value if is_negative else value


def parse_percentage(raw: str | None) -> Decimal | None:
    """Normaliza um percentual textual (ex.: '6,52%', '-2,40%') para
    fração 0..1, mesma convenção do resto da LG INVEST (Sprint 22)."""
    value = parse_number(raw)
    if value is None:
        return None
    return value / Decimal("100")


def parse_card_lines(lines: list[str]) -> dict[str, str]:
    """Interpreta as linhas de texto de um card (Criptomoedas/Renda Fixa)
    como pares rótulo/valor, mais um "nome" (tudo antes do primeiro
    rótulo reconhecido).

    Função pura — recebe só a lista de linhas já extraída pelo
    `client.py` via `innerText.split("\\n")`, nunca acessa o DOM.

    Ex. cripto (Sprint 23.2, tela "Criptomoedas → Extrato"): ["Carteira:",
    "Carteira Criptomoeda (Manual)", "btc", "Quantidade:", "0,00584925",
    "Preço Médio:", "R$ 76.308,58", ..., "Ver Operações"] vira
    {"__name": "btc", "quantity": "0,00584925", "average_price": "R$ 76.308,58", ...}
    — o par "Carteira:"/"Carteira Criptomoeda (Manual)" é descartado
    inteiro (ver `_CARD_LABELED_IGNORED`), nunca vira parte do nome.

    Ex. renda fixa: ["Tesouro IPCA+ 2050", "XP INVESTIMENTOS CCTVM S/A",
    "Valor atual", "R$ 5.483,53"] vira
    {"__name": "Tesouro IPCA+ 2050 XP INVESTIMENTOS CCTVM S/A", "current_value": "R$ 5.483,53"}
    (o rótulo "Valor atual" não tem ":" — por isso o casamento usa o texto
    sem ":" à direita, não presença de ":').
    """
    fields: dict[str, str] = {}
    name_lines: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()
        key = line.rstrip(":").strip().lower()
        if key in _CARD_IGNORED_LABELS:
            i += 1
            continue
        if key in _CARD_LABELED_IGNORED and i + 1 < n:
            # "label: valor" a descartar por completo (ex.: "Carteira:
            # Carteira Criptomoeda (Manual)") — nunca vira campo nem nome.
            i += 2
            continue
        if key in _CARD_FIELD_LABELS and i + 1 < n:
            fields[_CARD_FIELD_LABELS[key]] = lines[i + 1]
            i += 2
            continue
        if not fields:
            # Ainda não vimos nenhum rótulo conhecido: é nome/metadado do card.
            name_lines.append(line)
        i += 1
    fields["__name"] = " ".join(name_lines).strip()
    return fields


def _normalize_us_ticker_share_class(ticker: str) -> str:
    """Ações de classe dos EUA (ex.: Berkshire "BRK.B") aparecem no
    Dividendos.me com ponto, mas o Yahoo Finance (fonte de preço da LG
    INVEST) usa hífen ("BRK-B"). Sem essa conversão, a sincronização
    trataria a mesma posição existente como um ticker novo."""
    if re.fullmatch(r"[A-Z]{1,5}\.[A-Z]{1,2}", ticker):
        return ticker.replace(".", "-")
    return ticker


def _normalize_br_variable_income(ticker: str, subheader: str | None) -> NormalizedTicker:
    asset_class = _match_subheader(subheader, _BR_SUBHEADER_ASSET_CLASS)
    if asset_class is None:
        return NormalizedTicker(
            ticker=ticker,
            asset_class="unknown",
            country="BR",
            currency="BRL",
            review_required=True,
            review_reason=f"subgrupo da B3 não reconhecido: {subheader!r}",
        )
    normalized = ticker if ticker.endswith(".SA") else f"{ticker}.SA"
    return NormalizedTicker(
        ticker=normalized, asset_class=asset_class, country="BR", currency="BRL"
    )


def _normalize_us_variable_income(ticker: str, subheader: str | None) -> NormalizedTicker:
    asset_class = _match_subheader(subheader, _US_SUBHEADER_ASSET_CLASS)
    if asset_class is None:
        return NormalizedTicker(
            ticker=ticker,
            asset_class="unknown",
            country="US",
            currency="USD",
            review_required=True,
            review_reason=f"subgrupo dos EUA não reconhecido: {subheader!r}",
        )
    normalized = ticker[:-3] if ticker.endswith(".SA") else ticker
    normalized = _normalize_us_ticker_share_class(normalized)
    return NormalizedTicker(
        ticker=normalized, asset_class=asset_class, country="US", currency="USD"
    )


def _normalize_crypto(ticker: str) -> NormalizedTicker:
    """Normaliza um ticker de cripto extraído de "Criptomoedas → Extrato".

    Correção Sprint 24 (revisão da Sprint 23.2): a tela "Criptomoedas →
    Extrato" usa o símbolo visual "R$" na interface, mas os NÚMEROS de
    quantidade/preço médio/preço atual/valor atual que ela mostra são, na
    prática, expressos em USD (conferido contra a conta real: quantidade
    × preço atual bate com o valor atual apenas se preço/valor forem
    tratados como USD, não BRL — um `current_value` em BRL implicaria um
    preço de BTC ~18x menor que o real). O símbolo "R$" da tela NUNCA deve
    ser usado como fonte de verdade para a moeda de um ativo cripto:
    a moeda é inferida pelo próprio ticker (par "-USD" do Yahoo Finance,
    fonte de preço da LG INVEST) — qualquer par "XXX-USD" é USD.
    """
    base = ticker.replace("-USD", "").strip()
    if not base:
        return NormalizedTicker(
            ticker=ticker,
            asset_class="crypto",
            country="US",
            currency="USD",
            review_required=True,
            review_reason="ticker de criptomoeda vazio",
        )
    normalized = f"{base}-USD"
    # BTC é a única criptomoeda confirmada/testada nesta sprint; outras
    # passam pelo mesmo padrão de normalização mas ficam sinalizadas para
    # revisão manual até serem validadas contra a fonte real de preço.
    # Em ambos os casos a moeda é USD — qualquer par "-USD" é USD, nunca
    # BRL, independentemente do símbolo mostrado na tela do Dividendos.me.
    if base == "BTC":
        return NormalizedTicker(
            ticker=normalized, asset_class="crypto", country="US", currency="USD"
        )
    return NormalizedTicker(
        ticker=normalized,
        asset_class="crypto",
        country="US",
        currency="USD",
        review_required=True,
        review_reason=f"criptomoeda {base!r} não validada — confira o ticker antes de usar",
    )


def _normalize_fixed_income(ticker: str, name: str | None) -> NormalizedTicker:
    text = f"{name or ''} {ticker or ''}".upper()
    if "TESOURO" not in text:
        return NormalizedTicker(
            ticker=ticker,
            asset_class="bond",
            country="BR",
            currency="BRL",
            is_manual=True,
            review_required=True,
            review_reason="renda fixa não identificada como Tesouro Direto",
        )

    indexer = next((code for label, code in _TESOURO_INDEXER_PATTERNS if label in text), None)
    year_match = _YEAR_PATTERN.search(text)
    year = year_match.group(1) if year_match else None

    if indexer and year:
        normalized = f"TESOURO-{indexer}-{year}"
        return NormalizedTicker(
            ticker=normalized, asset_class="bond", country="BR", currency="BRL", is_manual=True
        )

    fallback_ticker = ticker or name or "TESOURO-DESCONHECIDO"
    return NormalizedTicker(
        ticker=fallback_ticker,
        asset_class="bond",
        country="BR",
        currency="BRL",
        is_manual=True,
        review_required=True,
        review_reason="não foi possível identificar indexador/ano do Tesouro automaticamente",
    )


def normalize_position(
    raw_ticker: str, *, section: str, subheader: str | None = None, name: str | None = None
) -> NormalizedTicker:
    """Normaliza um ticker bruto extraído de uma seção do Dividendos.me.

    `section` identifica de onde a linha veio (ex.: "brasil", "eua",
    "criptomoedas", "renda_fixa") — normalmente resolvido pelo
    `client.py` a partir da URL/menu da página, não pelo conteúdo da
    linha em si. Qualquer combinação não reconhecida (seção nova,
    subgrupo novo, ticker vazio) vira `review_required=True` em vez de
    classificada silenciosamente errada.
    """
    ticker = (raw_ticker or "").strip().upper()
    section_key = (section or "").strip().lower()

    if not ticker:
        return NormalizedTicker(
            ticker="",
            asset_class="unknown",
            country="",
            currency="",
            review_required=True,
            review_reason="ticker vazio",
        )

    if section_key in ("brasil", "br"):
        return _normalize_br_variable_income(ticker, subheader)
    if section_key in ("eua", "us", "estados unidos", "estados_unidos"):
        return _normalize_us_variable_income(ticker, subheader)
    if section_key in ("criptomoedas", "cripto", "crypto"):
        return _normalize_crypto(ticker)
    if section_key in ("renda fixa", "renda_fixa", "fixed_income", "tesouro"):
        return _normalize_fixed_income(ticker, name)

    return NormalizedTicker(
        ticker=ticker,
        asset_class="unknown",
        country="",
        currency="",
        review_required=True,
        review_reason=f"seção não reconhecida: {section!r}",
    )


def origin_for_section(section: str) -> str:
    """Mapeia a seção de extração para o rótulo de origem salvo em `Position.source`."""
    section_key = (section or "").strip().lower()
    if section_key in ("brasil", "br"):
        return ORIGIN_B3
    if section_key in ("criptomoedas", "cripto", "crypto"):
        return ORIGIN_CRYPTO
    return ORIGIN_INTERNATIONAL
