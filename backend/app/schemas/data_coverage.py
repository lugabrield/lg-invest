"""Schemas do Data Coverage Report (Sprint 28).

Responde, para um ativo: quais dados fundamentais existem, quais
faltam, de onde vieram e quando foram atualizados, e o quanto isso
permite calcular Quality/Valuation/Trap Detection/Análise de Renda/
Decision Engine — nunca um "confiança baixa" genérico sem explicação.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class FieldAvailability(BaseModel):
    """Disponibilidade de UM campo fundamentalista de um ativo."""

    field: str
    label: str
    available: bool
    value: Decimal | str | None = None
    source: str | None = None
    updated_at: datetime | None = None
    warning: str | None = None


class CoveragePurposeScore(BaseModel):
    """Cobertura de dados para UMA finalidade (quality/valuation/...).

    `score` é `None` quando a classe do ativo está fora do escopo dessa
    finalidade (ex.: valuation tradicional para ETF) — nunca um score
    fabricado de "0" para uma coisa que nem deveria existir para essa
    classe. `missing_labels` lista, em português, exatamente o que falta
    — nunca só "dados insuficientes".
    """

    score: Decimal | None = None  # 0-100
    classification: str = "não aplicável"
    missing_labels: list[str] = Field(default_factory=list)
    reason: str | None = None


class DataCoverageResult(BaseModel):
    """Relatório de cobertura de dados de um ativo (Data Coverage Report)."""

    ticker: str
    asset_class: str
    period_end: date | None = None

    fields: list[FieldAvailability] = Field(default_factory=list)

    quality: CoveragePurposeScore = CoveragePurposeScore()
    valuation: CoveragePurposeScore = CoveragePurposeScore()
    trap_detection: CoveragePurposeScore = CoveragePurposeScore()
    income: CoveragePurposeScore = CoveragePurposeScore()
    decision_engine: CoveragePurposeScore = CoveragePurposeScore()

    summary: str = ""

    @property
    def missing_field_labels(self) -> list[str]:
        """Todos os campos ausentes do relatório completo (Parte 1) — não
        só os relevantes para uma finalidade específica."""
        return [f.label for f in self.fields if not f.available]

    def as_dict(self) -> dict:
        return self.model_dump()


def most_missing_fields(results: list[DataCoverageResult], top_n: int = 5) -> list[str]:
    """Os `top_n` rótulos de campo mais ausentes entre vários relatórios —
    usado pelo resumo de execução da Central de Dados ("campos mais
    ausentes: FCF, ROIC, EV/EBITDA..."). Nunca inventa uma contagem: é uma
    contagem real sobre os `DataCoverageResult` recebidos."""
    counts: dict[str, int] = {}
    for result in results:
        for label in result.missing_field_labels:
            counts[label] = counts.get(label, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [label for label, _ in ranked[:top_n]]
