"""Serviço de sincronização com o Dividendos.me (Sprint 23 / 23.1 / 23.2 / 23.3).

Fronteira banco<->integração externa: usa `DividendosMeClient` (Playwright)
para extrair a carteira, `parser.py` para normalizar, calcula o diff
contra a carteira atual da LG INVEST e, nos modos `replace`/`update`,
grava no banco dentro de uma transação. Nenhuma regra de cálculo
financeiro vive aqui — só orquestração e persistência.

Modos (Sprint 23, aprovados pelo usuário):
- `dry-run`: sempre disponível, nunca grava nada.
- `replace`: substitui 100% das posições do `portfolio_id` alvo pelas
  posições consolidadas de todas as seções do Dividendos.me (Brasil +
  internacional, mesma carteira LG INVEST) — exige `confirm=True`.
- `update`: cria/atualiza posições sem remover as que não vieram da
  fonte externa — implementado para uso futuro, também exige
  `confirm=True` (evita gravação acidental em uso programático).

Sprint 23.1 (correção pós-produção — extração real veio agregada/quebrada):
`replace`/`update` agora passam por checagens mínimas de segurança antes
de gravar qualquer coisa (`_extraction_broken_reasons`/`_removal_risk_reasons`).
Se qualquer uma disparar, a sincronização é bloqueada com
`ExtractionInvalidError` e a mensagem exata "Extração inválida ou
incompleta. Substituição bloqueada para evitar perda de carteira." —
usada tanto pelo CLI quanto pela UI, pois ambos chamam este módulo.
Não existe nenhum parâmetro de force/bypass para essas checagens.

Sprint 23.3 (correção pós-produção — dry-run reportou "success" com
EUA/Criptomoedas/Renda Fixa vazios, sem nenhuma seção marcada como
falha): introduz o conceito de "seções esperadas", derivado da própria
carteira ATUAL da LG INVEST (não uma lista fixa de tickers) — se a
carteira já tem um ativo `crypto`, a seção "criptomoedas" passa a ser
esperada nesta extração; se não vier nada dela (nem erro, nem posição),
ela é tratada como uma seção que falhou, o preview nunca pode ser
"success", e `replace` é bloqueado com uma mensagem própria
("Extração incompleta: uma ou mais seções da carteira não foram
carregadas..."), distinta da mensagem geral usada pelas demais checagens
de segurança já existentes. Sem bypass, mesma filosofia do restante do módulo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.database.models.external_sync_run import ExternalSyncRun
from backend.app.infrastructure.database.models.position import Position
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.external_sync_run_repository import (
    ExternalSyncRunRepository,
)
from backend.app.infrastructure.repositories.portfolio_repository import PortfolioRepository
from backend.app.infrastructure.repositories.position_repository import PositionRepository
from backend.app.integrations.dividendos_me.client import DividendosMeClient
from backend.app.integrations.dividendos_me.schemas import (
    MIN_VALID_ASSETS_FOR_SUCCESS,
    ExtractedPosition,
    SyncDiff,
    SyncPreview,
    SyncRunResult,
)

logger = get_logger("lg_invest.integrations.dividendos_me.service")

PROVIDER = "dividendos_me"

# Mensagem EXATA exigida pelo usuário — nunca reformular/traduzir, o CLI e
# a UI devem exibir literalmente este texto quando o bloqueio disparar por
# qualquer um dos motivos "clássicos" (Sprint 23.1: ticker vazio, >50% da
# carteira desaparecendo, ticker sempre-protegido ausente).
EXTRACTION_INVALID_MESSAGE = (
    "Extração inválida ou incompleta. Substituição bloqueada para evitar perda de carteira."
)

# Mensagem EXATA para o motivo específico de "seção esperada veio vazia"
# (Sprint 23.3, a pedido do usuário) — usada em vez de EXTRACTION_INVALID_MESSAGE
# quando esse é (ao menos um) dos motivos do bloqueio, para deixar claro que
# o problema é de COBERTURA de seção, não de um ticker isolado quebrado.
EXTRACTION_INCOMPLETE_SECTIONS_MESSAGE = (
    "Extração incompleta: uma ou mais seções da carteira não foram carregadas. "
    "Substituição bloqueada para evitar perda de ativos."
)

# Seções cuja falha esconde ativos financeiramente relevantes mesmo que
# Brasil/EUA tenham extraído perfeitamente — merece alerta forte na UI/CLI,
# não só um item de lista discreto (Prioridade 1 do usuário). Mantido como
# piso mínimo sempre-forte; Sprint 23.3 generaliza para qualquer seção
# "esperada" (ver `strong_alert_sections`), então EUA também vira alerta
# forte sempre que a carteira atual tiver ativos internacionais.
STRONG_ALERT_SECTIONS = frozenset({"criptomoedas", "renda_fixa"})

# Acima desta fração da carteira atual marcada como "não veio da fonte"
# (seria removida no modo replace), a sincronização é bloqueada — ver
# `_removal_risk_reasons`.
_MISSING_IN_SOURCE_BLOCK_RATIO = Decimal("0.5")

# Tickers que NUNCA podem ser removidos silenciosamente no modo replace,
# independentemente da fração da carteira afetada (Sprint 23.2, a pedido
# do usuário): se BTC-USD já existe na LG INVEST e a seção Criptomoedas
# não trouxer BTC-USD desta vez (ex.: card não encontrado, layout mudou),
# bloqueia — mesmo que seja só 1 de 50 ativos (a regra geral de >50% não
# cobriria esse caso). Nunca existe bypass para esta checagem. Sprint
# 23.3 generaliza essa proteção para QUALQUER ticker cuja seção esperada
# venha vazia (ver `_section_gap_reasons`) — este conjunto continua como
# uma segunda camada de defesa específica para BTC-USD, útil mesmo quando
# a seção "criptomoedas" não está totalmente vazia (ex.: trouxe outra
# cripto, mas não o BTC).
_ALWAYS_PROTECTED_TICKERS = frozenset({"BTC-USD"})


# Mapeia (asset_class, country) -> seção esperada do Dividendos.me (Sprint
# 23.3). Deriva de `parser.py`: Brasil normaliza stock/fii/etf com país
# "BR"; EUA normaliza stock/etf/reit com país "US"; cripto sempre vira
# asset_class "crypto"; Tesouro sempre vira asset_class "bond". Qualquer
# combinação fora daqui não gera seção esperada (nunca bloqueia por uma
# classe/país que o sistema não sabe mapear).
def _expected_section_for_asset(asset_class: str, country: str) -> str | None:
    if asset_class == "crypto":
        return "criptomoedas"
    if asset_class == "bond":
        return "renda_fixa"
    if country == "US":
        return "eua"
    if country == "BR":
        return "brasil"
    return None


class SyncConfirmationRequiredError(Exception):
    """Levantada quando `replace`/`update` é chamado sem confirmação explícita."""


class PortfolioNotFoundError(Exception):
    """A carteira alvo (`portfolio_id`) não existe."""


class ExtractionInvalidError(Exception):
    """Levantada quando a extração falha nas checagens mínimas de segurança
    (Sprint 23.1/23.3) — bloqueia `replace`/`update` para nunca perder
    posições reais da carteira por causa de uma extração quebrada ou
    incompleta (ex.: ticker vazio, quase toda a carteira atual
    "desaparecendo", uma seção esperada vindo vazia).

    Deliberadamente não existe nenhum parâmetro de força/bypass para esta
    checagem, nem aqui, nem no CLI, nem na UI. Se a extração estiver
    correta e o bloqueio for um falso positivo, o ajuste é na regra ou na
    extração — nunca contornar a proteção.
    """


@dataclass
class _CurrentPosition:
    position: Position
    ticker: str
    asset_class: str = ""
    country: str = ""


def _consolidate_positions(extracted: list[ExtractedPosition]) -> list[ExtractedPosition]:
    """Junta linhas com o mesmo ticker final vindas de seções diferentes
    (ex.: o mesmo ETF aparecendo em mais de uma seção) numa única posição
    consolidada — a LG INVEST mantém uma única visão por carteira, nunca
    duas posições para o mesmo ativo (aprovado pelo usuário)."""
    by_ticker: dict[str, list[ExtractedPosition]] = {}
    for p in extracted:
        by_ticker.setdefault(p.ticker, []).append(p)

    consolidated: list[ExtractedPosition] = []
    for rows in by_ticker.values():
        if len(rows) == 1:
            consolidated.append(rows[0])
            continue

        total_quantity = sum((r.quantity for r in rows), Decimal("0"))
        currencies = {r.currency for r in rows}
        review_required = any(r.review_required for r in rows) or len(currencies) > 1
        reason = rows[0].review_reason
        if len(currencies) > 1:
            reason = f"mesmo ticker em moedas diferentes ao consolidar seções: {currencies}"

        if all(r.average_price is not None for r in rows) and total_quantity > 0:
            weighted_cost = sum((r.average_price * r.quantity for r in rows), Decimal("0"))
            average_price = weighted_cost / total_quantity
        else:
            average_price = rows[0].average_price

        consolidated.append(
            rows[0].model_copy(
                update={
                    "quantity": total_quantity,
                    "average_price": average_price,
                    "current_value": sum(
                        (r.current_value for r in rows if r.current_value is not None), Decimal("0")
                    )
                    or None,
                    "origin": "+".join(sorted({r.origin for r in rows})),
                    "review_required": review_required,
                    "review_reason": reason,
                }
            )
        )
    return consolidated


def _apply_btc_fallback(
    extracted: list[ExtractedPosition], current: dict[str, _CurrentPosition]
) -> list[ExtractedPosition]:
    """Rede de segurança (Sprint 23.2). A correção do seletor de card em
    `client.py` já resolve o BTC corretamente na prática, mas esta função
    cobre qualquer regressão futura: se a seção "criptomoedas" trouxer
    EXATAMENTE uma posição sem ticker (`review_required`, `ticker == ""`)
    e a carteira atual já tiver `BTC-USD`, assume que é o mesmo Bitcoin e
    remapeia. Nunca dispara com mais de uma cripto sem ticker (ambíguo
    demais para adivinhar) nem se `BTC-USD` não existir na carteira atual
    (nunca inventa uma posição nova)."""
    unmatched_crypto = [
        p for p in extracted if p.section == "criptomoedas" and p.review_required and p.ticker == ""
    ]
    if len(unmatched_crypto) != 1 or "BTC-USD" not in current:
        return extracted

    target = unmatched_crypto[0]
    remapped = target.model_copy(
        update={
            "ticker": "BTC-USD",
            "asset_class": "crypto",
            "review_required": False,
            "review_reason": None,
        }
    )
    return [remapped if p is target else p for p in extracted]


def _valid_positions(positions: list[ExtractedPosition]) -> list[ExtractedPosition]:
    """Só ativos com ticker reconhecido (não vazio) e sem necessidade de
    revisão manual contam como "válidos" para `assets_found`/`total_assets`
    e para o cálculo de status — ver Sprint 23.1 (bug de extração agregada
    que reportava "sucesso" com um único ativo agregado e ticker vazio)."""
    return [p for p in positions if not p.review_required and p.ticker]


def _compute_preview_status(valid_count: int, sections_failed: list[str]) -> str:
    """Prioridade 3 do usuário: nunca "success" com patrimônio encontrado
    mas ativos válidos insuficientes. `valid_count` já é só ativos com
    ticker reconhecido e `review_required=False` (ver `_valid_positions`).
    `sections_failed` aqui já é o conjunto EFETIVO (Sprint 23.3): inclui
    tanto seções que erraram de verdade quanto seções esperadas que
    vieram vazias sem erro — qualquer uma delas impede "success"."""
    if valid_count == 0:
        return "failed"
    if valid_count < MIN_VALID_ASSETS_FOR_SUCCESS:
        return "partial"
    if sections_failed:
        return "partial"
    return "success"


def _expected_sections_from_current(current: dict[str, _CurrentPosition]) -> list[str]:
    """Sprint 23.3 — deriva as seções que ESTA carteira, hoje, espera ver
    numa extração completa: uma por classe/país de ativo já presente
    (ex.: há um ativo `crypto` -> "criptomoedas" é esperada). Isso é mais
    robusto que uma lista fixa de tickers protegidos: cobre qualquer
    ativo novo na mesma classe, sem precisar de manutenção manual."""
    sections: set[str] = set()
    for cp in current.values():
        section = _expected_section_for_asset(cp.asset_class, cp.country)
        if section:
            sections.add(section)
    return sorted(sections)


def _sections_with_data(extracted: list[ExtractedPosition]) -> set[str]:
    """Seções que de fato produziram ao menos uma posição nesta extração
    (usa `ExtractedPosition.section`, sempre preenchido pelo `client.py`
    real — mais confiável que só olhar `SectionDiagnostics`, que pode não
    ter sido populado em todo caminho de teste/mock)."""
    return {p.section for p in extracted if p.section}


def _extraction_broken_reasons(preview: SyncPreview) -> list[str]:
    """Prioridade 1 (bloqueio obrigatório) — condições que tornam a
    extração inteira não confiável, bloqueando tanto `replace` quanto
    `update` (nenhuma escrita no banco é segura com a extração nesse estado)."""
    reasons: list[str] = []
    if len(preview.positions) <= 1 and any(p.ticker == "" for p in preview.positions):
        reasons.append("apenas uma posição foi extraída e veio com ticker vazio")
    if any(ticker == "" for ticker in preview.review_required_tickers):
        reasons.append("há posição(ões) marcada(s) para revisão manual com ticker vazio")
    return reasons


def _current_count_from_diff(diff: SyncDiff) -> int:
    """Reconstrói o tamanho da carteira atual a partir do diff (kept +
    updated + missing_in_source = todos os tickers que já existiam antes
    da sincronização) — evita precisar consultar o banco de novo só para
    esta checagem, então UI/CLI conseguem calcular o mesmo resultado do
    serviço só com o `SyncPreview` em mãos."""
    return len(diff.kept) + len(diff.updated) + len(diff.missing_in_source)


def _removal_risk_reasons(preview: SyncPreview) -> list[str]:
    """Prioridade 1 (bloqueio obrigatório) — risco de apagar a maior parte
    da carteira atual. Só se aplica a `replace` (único modo que remove
    posições); com carteira atual vazia não há nada a perder, então não
    bloqueia (senão a primeira sincronização de uma carteira nova jamais
    passaria)."""
    reasons: list[str] = []
    current_count = _current_count_from_diff(preview.diff)
    if current_count:
        missing_ratio = Decimal(len(preview.diff.missing_in_source)) / Decimal(current_count)
        if missing_ratio > _MISSING_IN_SOURCE_BLOCK_RATIO:
            reasons.append(
                f"{len(preview.diff.missing_in_source)} de {current_count} ativos da carteira "
                "atual não vieram da extração (mais de 50% seriam removidos no modo replace)"
            )

    protected_missing = sorted(set(preview.diff.missing_in_source) & _ALWAYS_PROTECTED_TICKERS)
    if protected_missing:
        reasons.append(
            f"{', '.join(protected_missing)} já existe na carteira atual e não veio "
            "desta vez na extração — bloqueado independentemente do percentual "
            "afetado (ativo protegido)"
        )
    return reasons


def _section_gap_reasons(preview: SyncPreview) -> list[str]:
    """Prioridade 1 (bloqueio obrigatório, Sprint 23.3) — qualquer seção
    que a carteira atual espera ver (`sections_expected`) e que não veio
    nesta execução (`sections_failed`, já no formato efetivo calculado em
    `build_preview`) bloqueia `replace` incondicionalmente, mesmo que o
    percentual afetado seja pequeno e mesmo que nenhum ticker
    especificamente "sempre protegido" esteja envolvido. Só se aplica a
    `replace` (única operação que remove posições)."""
    missing = sorted(set(preview.sections_expected) & set(preview.sections_failed))
    if not missing:
        return []
    labels = ", ".join(missing)
    return [
        f"a(s) seção(ões) esperada(s) {labels} não retornou(aram) nenhum ativo nesta "
        "extração, mas a carteira atual possui ativos dessa(s) classe(s) — bloqueado "
        "para evitar remoção silenciosa"
    ]


def has_section_gap(preview: SyncPreview) -> bool:
    """Helper público (usado pela UI/CLI) para saber se o bloqueio, se
    houver, é por seção esperada vazia — e portanto qual das duas
    mensagens fixas (`EXTRACTION_INVALID_MESSAGE` ou
    `EXTRACTION_INCOMPLETE_SECTIONS_MESSAGE`) exibir. Não decide sozinho
    se o replace está bloqueado — use `extraction_blocking_reasons` para
    isso."""
    return bool(_section_gap_reasons(preview))


def extraction_blocking_reasons(preview: SyncPreview, *, mode: str = "replace") -> list[str]:
    """Ponto único (reusado por `_apply_sync`, CLI e UI) que decide se uma
    extração é segura o bastante para `replace`/`update` rodarem. Lista
    vazia = passou em tudo. Calculado só a partir do `SyncPreview`, então
    a UI pode desabilitar o botão de confirmação sem chamar o banco de
    novo."""
    reasons = _extraction_broken_reasons(preview)
    if mode == "replace":
        reasons = reasons + _removal_risk_reasons(preview) + _section_gap_reasons(preview)
    return reasons


def strong_alert_sections(preview: SyncPreview) -> list[str]:
    """Seções falhas que merecem alerta forte (não só um item de lista) na
    UI/CLI. Sprint 23.3: generaliza para qualquer seção que a carteira
    atual espera (`sections_expected`) — não só Criptomoedas/Renda Fixa
    fixas — já que perder EUA também esconde ativos que não aparecem em
    nenhum outro lugar do preview quando a carteira atual tem posições
    internacionais."""
    strong = set(STRONG_ALERT_SECTIONS) | set(preview.sections_expected)
    return sorted(s for s in preview.sections_failed if s in strong)


class DividendosMeSyncService:
    def __init__(self, db: Session):
        self.db = db
        self.portfolios = PortfolioRepository(db)
        self.assets = AssetRepository(db)
        self.positions = PositionRepository(db)
        self.sync_runs = ExternalSyncRunRepository(db)

    def _current_positions_by_ticker(self, portfolio_id: int) -> dict[str, _CurrentPosition]:
        current: dict[str, _CurrentPosition] = {}
        for position in self.positions.list_by_portfolio(portfolio_id):
            asset = self.assets.get_by_id(position.asset_id)
            if asset is None:
                continue
            current[asset.ticker] = _CurrentPosition(
                position=position,
                ticker=asset.ticker,
                asset_class=asset.asset_class,
                country=asset.country,
            )
        return current

    def _compute_diff(
        self, current: dict[str, _CurrentPosition], extracted: list[ExtractedPosition]
    ) -> SyncDiff:
        extracted_by_ticker = {p.ticker: p for p in extracted if not p.review_required}
        extracted_tickers = set(extracted_by_ticker)
        current_tickers = set(current)

        created = sorted(extracted_tickers - current_tickers)
        missing_in_source = sorted(current_tickers - extracted_tickers)

        kept: list[str] = []
        updated: list[str] = []
        for ticker in sorted(extracted_tickers & current_tickers):
            existing = current[ticker].position
            new_position = extracted_by_ticker[ticker]
            same_quantity = existing.quantity == new_position.quantity
            same_price = (
                new_position.average_price is None
                or existing.average_price == new_position.average_price
            )
            if same_quantity and same_price:
                kept.append(ticker)
            else:
                updated.append(ticker)

        return SyncDiff(
            kept=kept, updated=updated, created=created, missing_in_source=missing_in_source
        )

    def build_preview(self, portfolio_id: int, client: DividendosMeClient) -> SyncPreview:
        """Busca a carteira no Dividendos.me e monta o preview — nunca grava nada."""
        portfolio = self.portfolios.get_by_id(portfolio_id)
        if portfolio is None:
            raise PortfolioNotFoundError(f"Carteira {portfolio_id} não existe na LG INVEST.")

        extracted_raw, failed_sections, diagnostics = client.fetch_portfolio()
        current = self._current_positions_by_ticker(portfolio_id)
        extracted_raw = _apply_btc_fallback(extracted_raw, current)
        extracted = _consolidate_positions(extracted_raw)

        diff = self._compute_diff(current, extracted)

        # Sprint 23.3: uma seção esperada (derivada da carteira ATUAL) que
        # não navegou com erro mas também não produziu nenhuma posição é
        # tratada como se tivesse falhado — sem isso, uma seção "vazia
        # silenciosa" (ex.: EUA/Criptomoedas/Renda Fixa) deixava o preview
        # reportar "success" mesmo perdendo ativos inteiros de vista.
        sections_expected = _expected_sections_from_current(current)
        sections_with_data = _sections_with_data(extracted)
        sections_missing = [
            s for s in sections_expected if s not in failed_sections and s not in sections_with_data
        ]
        failed_sections_effective = sorted(set(failed_sections) | set(sections_missing))

        total_patrimonio = sum(
            (p.current_value for p in extracted if p.current_value is not None), Decimal("0")
        )
        total_patrimonio_status = "partial" if failed_sections_effective else "consolidated"
        review_required_tickers = sorted({p.ticker for p in extracted if p.review_required})

        valid_count = len(_valid_positions(extracted))
        status = _compute_preview_status(valid_count, failed_sections_effective)

        return SyncPreview(
            portfolio_id=portfolio_id,
            total_patrimonio=total_patrimonio,
            total_patrimonio_status=total_patrimonio_status,
            total_assets=valid_count,
            positions=extracted,
            diff=diff,
            status=status,
            sections_expected=sections_expected,
            sections_failed=failed_sections_effective,
            review_required_tickers=review_required_tickers,
            diagnostics=diagnostics,
            generated_at=datetime.now(UTC),
        )

    def dry_run(self, portfolio_id: int, client: DividendosMeClient) -> SyncRunResult:
        started_at = datetime.now(UTC)
        preview = self.build_preview(portfolio_id, client)
        return SyncRunResult(
            provider=PROVIDER,
            mode="dry-run",
            status=preview.status,
            portfolio_id=portfolio_id,
            assets_found=preview.total_assets,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            preview=preview,
        )

    def _resolve_asset(self, position: ExtractedPosition) -> Asset | None:
        """Cria o ativo no cadastro mestre se ainda não existir. Devolve
        `None` (e não escreve nada) para posições marcadas `review_required`
        — nunca cadastra um ativo com classe/país não confirmados."""
        if position.review_required:
            return None

        asset = self.assets.get_by_ticker(position.ticker)
        if asset is None:
            asset = self.assets.create(
                Asset(
                    ticker=position.ticker,
                    name=position.name or position.ticker,
                    asset_class=position.asset_class,
                    country=position.country or "BR",
                    currency=position.currency or "BRL",
                    is_manual=position.is_manual,
                )
            )
        elif position.is_manual and not asset.is_manual:
            # Só promove is_manual False->True (ex.: Tesouro identificado
            # agora); nunca reverte um ativo que o usuário marcou manual
            # de propósito para automático.
            asset.is_manual = True
            self.db.commit()
        return asset

    def _apply_sync(
        self,
        portfolio_id: int,
        client: DividendosMeClient,
        *,
        mode: str,
        confirm: bool,
    ) -> SyncRunResult:
        if not confirm:
            raise SyncConfirmationRequiredError(
                f"Modo '{mode}' exige confirmação explícita (confirm=True)."
            )

        started_at = datetime.now(UTC)
        preview = self.build_preview(portfolio_id, client)
        current = self._current_positions_by_ticker(portfolio_id)

        # Prioridade 1/5 do usuário: nunca grava nada (e muito menos remove
        # a carteira atual) antes de validar que a extração é minimamente
        # confiável. Checagem roda ANTES de qualquer delete/insert.
        blocking_reasons = extraction_blocking_reasons(preview, mode=mode)
        if blocking_reasons:
            logger.warning(
                "Sincronização (%s) bloqueada por checagens de segurança: %s",
                mode,
                "; ".join(blocking_reasons),
            )
            # Sprint 23.3: mensagem específica quando o motivo (ao menos em
            # parte) é seção esperada vazia — mais informativa que a
            # mensagem genérica de extração inválida/incompleta.
            section_gap = _section_gap_reasons(preview) if mode == "replace" else []
            message = (
                EXTRACTION_INCOMPLETE_SECTIONS_MESSAGE
                if section_gap
                else EXTRACTION_INVALID_MESSAGE
            )
            raise ExtractionInvalidError(message)

        # Snapshot do estado anterior — auditoria, nunca inclui senha/token.
        snapshot_before = {
            ticker: {
                "quantity": str(cp.position.quantity),
                "average_price": str(cp.position.average_price),
                "currency": cp.position.currency,
            }
            for ticker, cp in current.items()
        }

        positions_created = 0
        positions_updated = 0
        positions_removed = 0
        errors: list[str] = []

        writable_positions = [p for p in preview.positions if not p.review_required]
        for p in preview.positions:
            if p.review_required:
                errors.append(f"{p.ticker}: {p.review_reason or 'revisão manual necessária'}")
        for section in preview.sections_failed:
            errors.append(f"seção não extraída: {section}")

        # Tickers que vieram da extração e serão escritos — usados para
        # decidir o que "falta na fonte" no modo replace. Correção de bug
        # real (Sprint 23.2): a versão anterior apagava TODAS as posições
        # atuais incondicionalmente em `replace`, mesmo as que continuavam
        # presentes na extração (recriando-as do zero, perdendo `id`/
        # `opened_at`). O correto é remover só o que não veio da fonte —
        # exatamente `preview.diff.missing_in_source` — e atualizar em
        # lugar o que já existia e continua presente.
        extracted_tickers = {p.ticker for p in writable_positions}

        try:
            if mode == "replace":
                for ticker, cp in current.items():
                    if ticker not in extracted_tickers:
                        self.db.delete(cp.position)
                        positions_removed += 1
                self.db.flush()

            for p in writable_positions:
                asset = self._resolve_asset(p)
                if asset is None:
                    continue
                existing = current.get(p.ticker)
                if existing is not None:
                    existing.position.quantity = p.quantity
                    if p.average_price is not None:
                        existing.position.average_price = p.average_price
                    existing.position.currency = p.currency or existing.position.currency
                    existing.position.source = p.origin
                    positions_updated += 1
                else:
                    self.db.add(
                        Position(
                            portfolio_id=portfolio_id,
                            asset_id=asset.id,
                            quantity=p.quantity,
                            average_price=p.average_price or Decimal("0"),
                            currency=p.currency or "BRL",
                            opened_at=date.today(),
                            source=p.origin,
                        )
                    )
                    positions_created += 1

            self.db.commit()
            status = "success"
        except Exception as exc:  # noqa: BLE001 - qualquer falha vira rollback + status failed
            self.db.rollback()
            status = "failed"
            errors.append(
                "falha ao gravar no banco — todas as alterações foram desfeitas (rollback)"
            )
            logger.error("Falha ao aplicar sincronização Dividendos.me: %s", type(exc).__name__)

        finished_at = datetime.now(UTC)
        run = self.sync_runs.create(
            ExternalSyncRun(
                provider=PROVIDER,
                portfolio_id=portfolio_id,
                mode=mode,
                status=status,
                started_at=started_at,
                finished_at=finished_at,
                assets_found=preview.total_assets,
                positions_created=positions_created,
                positions_updated=positions_updated,
                positions_removed=positions_removed,
                errors_count=len(errors),
                summary_json=json.dumps(
                    {
                        "snapshot_before": snapshot_before,
                        "diff": preview.diff.model_dump(),
                        "sections_expected": preview.sections_expected,
                        "sections_failed": preview.sections_failed,
                        "review_required_tickers": preview.review_required_tickers,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        return SyncRunResult(
            run_id=run.id,
            provider=PROVIDER,
            mode=mode,
            status=status,
            portfolio_id=portfolio_id,
            assets_found=preview.total_assets,
            positions_created=positions_created,
            positions_updated=positions_updated,
            positions_removed=positions_removed,
            errors=errors,
            started_at=started_at,
            finished_at=finished_at,
            preview=preview,
        )

    def replace(
        self, portfolio_id: int, client: DividendosMeClient, *, confirm: bool
    ) -> SyncRunResult:
        """Substitui 100% das posições do `portfolio_id` pelas posições
        consolidadas do Dividendos.me. Exige `confirm=True` — a UI/CLI
        devem sempre mostrar o preview e a confirmação digitada antes.
        Levanta `ExtractionInvalidError` (mensagem fixa, sem bypass) se a
        extração não passar nas checagens mínimas de segurança."""
        return self._apply_sync(portfolio_id, client, mode="replace", confirm=confirm)

    def update(
        self, portfolio_id: int, client: DividendosMeClient, *, confirm: bool
    ) -> SyncRunResult:
        """Cria/atualiza posições sem remover as que não vierem do
        Dividendos.me. Implementado para uso futuro (Sprint 23 só expõe
        `replace` como modo principal na UI/CLI). Também sujeito às
        checagens de extração quebrada (mas não à de remoção, que só se
        aplica a `replace`)."""
        return self._apply_sync(portfolio_id, client, mode="update", confirm=confirm)
