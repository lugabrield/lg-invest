"""Schemas da Importação Manual de Fundamentos (Sprint 28, Fase 5).

Modela o resultado, linha a linha, de um arquivo CSV/Excel de
fundamentos importado manualmente — fallback para quando Yahoo Finance
não cobre um ativo (ver `docs/DATA_COVERAGE_REPORT.md` e
`docs/MANUAL_FUNDAMENTALS_IMPORT.md`).

Regras (Volume 18 §8 + regras específicas do Sprint 28, Parte 5):

- Nunca cria `Asset` novo — o ticker precisa já estar cadastrado.
- Nunca sobrescreve um snapshot existente sem confirmação explícita do
  usuário (`confirm_overwrite=True` na segunda chamada).
- Todo valor persistido recebe `source="manual_import"`, mesmo que a
  coluna `source` do arquivo informe outra origem (ex.: "Status
  Invest", "CVM") — essa origem informada só aparece na mensagem da
  linha, não é um campo do banco (limitação documentada).
- Erros de linha nunca abortam o arquivo inteiro — cada linha é
  independente, igual à importação de posições (Sprint 3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# Colunas aceitas no arquivo, na ordem da especificação do Sprint 28.
# `ticker`/`period_end`/`source` são obrigatórias; as demais são todas
# opcionais (ausência de uma coluna/valor é normal — o import aplica só
# o que veio preenchido).
FUNDAMENTALS_IMPORT_REQUIRED_COLUMNS = ("ticker", "period_end")
FUNDAMENTALS_IMPORT_OPTIONAL_COLUMNS = (
    "source",
    "revenue",
    "net_income",
    "ebitda",
    "ebit",
    "free_cash_flow",
    "net_debt",
    "total_debt",
    "total_cash",
    "total_equity",
    "roe",
    "roic",
    "net_margin",
    "operating_margin",
    "pe_ratio",
    "pb_ratio",
    "ev_ebitda",
    "dividend_yield",
    "payout_ratio",
    "market_cap",
)
# Subconjunto de colunas opcionais que mapeia 1:1 para colunas de
# `FundamentalSnapshot` (todas exceto `source`, que vira metadado da
# linha, nunca uma coluna do banco).
FUNDAMENTALS_IMPORT_NUMERIC_FIELDS = tuple(
    c for c in FUNDAMENTALS_IMPORT_OPTIONAL_COLUMNS if c != "source"
)

MANUAL_IMPORT_SOURCE = "manual_import"

ROW_STATUSES = ("imported", "updated", "conflict_pending_confirmation", "error")


@dataclass
class FundamentalsImportRowOutcome:
    """Resultado de UMA linha do arquivo importado."""

    line: int
    ticker: str
    period_end: date | None
    status: str  # ver ROW_STATUSES
    fields_applied: list[str] = field(default_factory=list)
    reported_source: str | None = None  # coluna "source" do arquivo, informativa
    message: str | None = None

    def as_dict(self) -> dict:
        return {
            "line": self.line,
            "ticker": self.ticker,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "status": self.status,
            "fields_applied": self.fields_applied,
            "reported_source": self.reported_source,
            "message": self.message,
        }


@dataclass
class FundamentalsImportRowError:
    """Erro de validação/leitura de UMA linha — não aplicado ao banco."""

    line: int
    field: str | None
    message: str

    def as_dict(self) -> dict:
        return {"line": self.line, "field": self.field, "message": self.message}


@dataclass
class FundamentalsImportResult:
    """Resumo estruturado de uma importação manual de fundamentos."""

    total_rows: int = 0
    outcomes: list[FundamentalsImportRowOutcome] = field(default_factory=list)
    errors: list[FundamentalsImportRowError] = field(default_factory=list)
    tickers_recomputed: list[str] = field(default_factory=list)
    valuation_recalculated: int = 0
    traps_recalculated: int = 0
    scores_recalculated: int = 0

    @property
    def imported(self) -> int:
        return sum(1 for o in self.outcomes if o.status in ("imported", "updated"))

    @property
    def conflicts_pending(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "conflict_pending_confirmation")

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_pending_conflicts(self) -> bool:
        return self.conflicts_pending > 0

    def as_dict(self) -> dict:
        return {
            "total_rows": self.total_rows,
            "imported": self.imported,
            "conflicts_pending": self.conflicts_pending,
            "outcomes": [o.as_dict() for o in self.outcomes],
            "errors": [e.as_dict() for e in self.errors],
            "tickers_recomputed": self.tickers_recomputed,
            "valuation_recalculated": self.valuation_recalculated,
            "traps_recalculated": self.traps_recalculated,
            "scores_recalculated": self.scores_recalculated,
        }
