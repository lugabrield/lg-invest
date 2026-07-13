"""Data Coverage Engine — orquestração pura (Sprint 28).

Recebe o snapshot mais recente de fundamentos, o histórico completo, a
análise de CAGR (`FundamentalsAnalysisResult`, já calculada pelo
Fundamentals Engine) e sinais de preço de um ativo, e devolve um
`DataCoverageResult`: disponibilidade campo a campo, mais um score de
completude (0-100) por finalidade (Quality/Valuation/Trap Detection/
Análise de Renda/Decision Engine), com os rótulos exatos do que falta.

Nunca decide um veredito de compra/venda, nunca inventa um valor
ausente — só relata disponibilidade e agrega. Os grupos de campos por
finalidade espelham deliberadamente o que `QualityEngine`,
`ValuationEngineV2`, `TrapDetectionEngine` e `IncomeRealEstateEngine`
realmente usam (`engines/data_coverage/thresholds.py`), para que este
relatório nunca divirja do comportamento real dessas engines.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.engines.data_coverage.thresholds import (
    CLASSIFICATION_NOT_APPLICABLE,
    FIELD_CURRENT_PRICE,
    FIELD_DIVIDEND_HISTORY,
    FIELD_GROWTH_HISTORY,
    FIELD_PRICE_HISTORY,
    INCOME_APPLICABLE_CLASSES,
    INCOME_FIELDS,
    INCOME_HISTORY_LABEL,
    MIN_PERIODS_FOR_CONFIDENT_HISTORY,
    MIN_PERIODS_FOR_OWN_HISTORY,
    MIN_PERIODS_FOR_PRICE_HISTORY,
    QUALITY_APPLICABLE_CLASSES,
    QUALITY_FIELDS,
    REPORT_SNAPSHOT_FIELDS,
    REPORT_SYNTHETIC_FIELDS,
    STALE_DATA_SCORE_FACTOR,
    STALE_DATA_THRESHOLD_DAYS,
    TRAP_DETECTION_APPLICABLE_CLASSES,
    TRAP_DETECTION_HISTORY_LABEL,
    TRAP_DETECTION_INCOME_FIELDS,
    TRAP_DETECTION_STOCK_FIELDS,
    VALUATION_APPLICABLE_CLASSES,
    VALUATION_GROWTH_LABEL,
    VALUATION_SNAPSHOT_FIELDS,
    classify_score,
)
from backend.app.schemas.data_coverage import (
    CoveragePurposeScore,
    DataCoverageResult,
    FieldAvailability,
)
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.fundamentals_analysis import FundamentalsAnalysisResult

_GROWTH_CAGR_FIELDS = ("fcf_cagr", "net_income_cagr", "revenue_cagr", "ebitda_cagr")


def _snapshot_field_score(
    snapshot: FundamentalSnapshotResult | None, fields: tuple[tuple[str, str], ...]
) -> tuple[Decimal, list[str]]:
    """Fração (0-100) de `fields` presentes no snapshot + rótulos ausentes."""
    if not fields:
        return Decimal(100), []
    missing = [
        label
        for field, label in fields
        if snapshot is None or getattr(snapshot, field, None) is None
    ]
    present = len(fields) - len(missing)
    score = Decimal(present) / Decimal(len(fields)) * 100
    return score, missing


def _growth_history_available(analysis: FundamentalsAnalysisResult | None) -> bool:
    if analysis is None:
        return False
    return any(getattr(analysis, field, None) is not None for field in _GROWTH_CAGR_FIELDS)


def _dividend_history_available(history: list[FundamentalSnapshotResult]) -> bool:
    periods = sum(1 for s in history if s.dividend_yield is not None)
    return periods >= MIN_PERIODS_FOR_OWN_HISTORY


class DataCoverageEngine:
    """Relata disponibilidade de dados fundamentais e completude por finalidade."""

    def evaluate(
        self,
        ticker: str,
        asset_class: str,
        latest_snapshot: FundamentalSnapshotResult | None,
        history: list[FundamentalSnapshotResult],
        fundamentals_analysis: FundamentalsAnalysisResult | None,
        has_current_price: bool,
        price_history_periods: int,
        today: date | None = None,
    ) -> DataCoverageResult:
        fields = self._build_fields(
            latest_snapshot,
            history,
            fundamentals_analysis,
            has_current_price,
            price_history_periods,
        )

        stale_days = self._staleness_days(latest_snapshot, today)

        quality = self._quality_purpose(asset_class, latest_snapshot)
        valuation = self._valuation_purpose(asset_class, latest_snapshot, fundamentals_analysis)
        trap_detection = self._trap_detection_purpose(asset_class, latest_snapshot, history)
        income = self._income_purpose(asset_class, latest_snapshot, history)
        decision_engine = self._decision_engine_purpose(
            quality, valuation, trap_detection, income, stale_days
        )

        summary = self._build_summary(quality, valuation, trap_detection, income)
        if stale_days is not None and stale_days > STALE_DATA_THRESHOLD_DAYS:
            summary += (
                f" Dados fundamentais desatualizados (coletados há {stale_days} dias) — "
                "confiança do Decision Engine reduzida."
            )

        return DataCoverageResult(
            ticker=ticker,
            asset_class=asset_class,
            period_end=latest_snapshot.period_end if latest_snapshot else None,
            fields=fields,
            quality=quality,
            valuation=valuation,
            trap_detection=trap_detection,
            income=income,
            decision_engine=decision_engine,
            summary=summary,
        )

    # -- campo a campo (Parte 1) ---------------------------------------

    def _build_fields(
        self,
        latest_snapshot: FundamentalSnapshotResult | None,
        history: list[FundamentalSnapshotResult],
        fundamentals_analysis: FundamentalsAnalysisResult | None,
        has_current_price: bool,
        price_history_periods: int,
    ) -> list[FieldAvailability]:
        fields: list[FieldAvailability] = []

        synthetic_values = {
            FIELD_CURRENT_PRICE: has_current_price,
            FIELD_PRICE_HISTORY: price_history_periods >= MIN_PERIODS_FOR_PRICE_HISTORY,
            FIELD_DIVIDEND_HISTORY: _dividend_history_available(history),
            FIELD_GROWTH_HISTORY: _growth_history_available(fundamentals_analysis),
        }
        for field, label in REPORT_SYNTHETIC_FIELDS:
            fields.append(
                FieldAvailability(field=field, label=label, available=synthetic_values[field])
            )

        for field, label in REPORT_SNAPSHOT_FIELDS:
            value = getattr(latest_snapshot, field, None) if latest_snapshot else None
            fields.append(
                FieldAvailability(
                    field=field,
                    label=label,
                    available=value is not None,
                    value=value,
                    source=(
                        latest_snapshot.source if latest_snapshot and value is not None else None
                    ),
                    updated_at=(
                        latest_snapshot.collected_at
                        if latest_snapshot and value is not None
                        else None
                    ),
                )
            )
        return fields

    # -- finalidades (Parte 2) -------------------------------------------

    def _quality_purpose(
        self, asset_class: str, latest_snapshot: FundamentalSnapshotResult | None
    ) -> CoveragePurposeScore:
        if asset_class not in QUALITY_APPLICABLE_CLASSES:
            return CoveragePurposeScore(
                classification=CLASSIFICATION_NOT_APPLICABLE,
                reason=f"classe '{asset_class}' fora do escopo do Quality Engine",
            )
        score, missing = _snapshot_field_score(latest_snapshot, QUALITY_FIELDS)
        return CoveragePurposeScore(
            score=score,
            classification=classify_score(score),
            missing_labels=missing,
            reason=(f"faltam: {', '.join(missing)}" if missing else None),
        )

    def _valuation_purpose(
        self,
        asset_class: str,
        latest_snapshot: FundamentalSnapshotResult | None,
        fundamentals_analysis: FundamentalsAnalysisResult | None,
    ) -> CoveragePurposeScore:
        if asset_class not in VALUATION_APPLICABLE_CLASSES:
            return CoveragePurposeScore(
                classification=CLASSIFICATION_NOT_APPLICABLE,
                reason=(
                    f"classe '{asset_class}' fora do escopo do Valuation Engine 2.0 "
                    "(cobre apenas ações)"
                ),
            )
        score, missing = _snapshot_field_score(latest_snapshot, VALUATION_SNAPSHOT_FIELDS)
        growth_available = _growth_history_available(fundamentals_analysis)
        total_slots = len(VALUATION_SNAPSHOT_FIELDS) + 1
        present_slots = (len(VALUATION_SNAPSHOT_FIELDS) - len(missing)) + (
            1 if growth_available else 0
        )
        combined_score = Decimal(present_slots) / Decimal(total_slots) * 100
        missing_labels = list(missing)
        if not growth_available:
            missing_labels.append(VALUATION_GROWTH_LABEL)
        return CoveragePurposeScore(
            score=combined_score,
            classification=classify_score(combined_score),
            missing_labels=missing_labels,
            reason=(f"faltam: {', '.join(missing_labels)}" if missing_labels else None),
        )

    def _trap_detection_purpose(
        self,
        asset_class: str,
        latest_snapshot: FundamentalSnapshotResult | None,
        history: list[FundamentalSnapshotResult],
    ) -> CoveragePurposeScore:
        if asset_class not in TRAP_DETECTION_APPLICABLE_CLASSES:
            return CoveragePurposeScore(
                classification=CLASSIFICATION_NOT_APPLICABLE,
                reason=(
                    f"classe '{asset_class}' fora do escopo do Trap Detection Engine "
                    "(cobre ações, FIIs e REITs)"
                ),
            )
        field_group = (
            TRAP_DETECTION_STOCK_FIELDS if asset_class == "stock" else TRAP_DETECTION_INCOME_FIELDS
        )
        score, missing = _snapshot_field_score(latest_snapshot, field_group)
        periods_used = len(history)
        history_ok = periods_used >= MIN_PERIODS_FOR_CONFIDENT_HISTORY
        total_slots = len(field_group) + 1
        present_slots = (len(field_group) - len(missing)) + (1 if history_ok else 0)
        combined_score = Decimal(present_slots) / Decimal(total_slots) * 100
        missing_labels = list(missing)
        if not history_ok:
            missing_labels.append(TRAP_DETECTION_HISTORY_LABEL)
        return CoveragePurposeScore(
            score=combined_score,
            classification=classify_score(combined_score),
            missing_labels=missing_labels,
            reason=(f"faltam: {', '.join(missing_labels)}" if missing_labels else None),
        )

    def _income_purpose(
        self,
        asset_class: str,
        latest_snapshot: FundamentalSnapshotResult | None,
        history: list[FundamentalSnapshotResult],
    ) -> CoveragePurposeScore:
        if asset_class not in INCOME_APPLICABLE_CLASSES:
            return CoveragePurposeScore(
                classification=CLASSIFICATION_NOT_APPLICABLE,
                reason=(
                    f"classe '{asset_class}' fora do escopo da Análise de Renda Imobiliária "
                    "(cobre apenas FIIs e REITs)"
                ),
            )
        score, missing = _snapshot_field_score(latest_snapshot, INCOME_FIELDS)
        history_ok = _dividend_history_available(history)
        total_slots = len(INCOME_FIELDS) + 1
        present_slots = (len(INCOME_FIELDS) - len(missing)) + (1 if history_ok else 0)
        combined_score = Decimal(present_slots) / Decimal(total_slots) * 100
        missing_labels = list(missing)
        if not history_ok:
            missing_labels.append(INCOME_HISTORY_LABEL)
        return CoveragePurposeScore(
            score=combined_score,
            classification=classify_score(combined_score),
            missing_labels=missing_labels,
            reason=(f"faltam: {', '.join(missing_labels)}" if missing_labels else None),
        )

    def _staleness_days(
        self, latest_snapshot: FundamentalSnapshotResult | None, today: date | None
    ) -> int | None:
        """Dias desde a última coleta de fundamentos, ou `None` quando não
        há snapshot/`collected_at` (nada a avaliar — nunca inventa uma
        idade para um dado inexistente)."""
        if latest_snapshot is None or latest_snapshot.collected_at is None:
            return None
        reference = today or date.today()
        return (reference - latest_snapshot.collected_at.date()).days

    def _decision_engine_purpose(
        self,
        quality: CoveragePurposeScore,
        valuation: CoveragePurposeScore,
        trap_detection: CoveragePurposeScore,
        income: CoveragePurposeScore,
        stale_days: int | None = None,
    ) -> CoveragePurposeScore:
        """Decision Engine v3 consome Trap Detection sempre e Valuation
        (ações) ou Análise de Renda (FII/REIT) quando aplicável — o score
        agregado é a média simples dos scores aplicáveis, nunca uma nota
        inventada para uma finalidade fora de escopo.

        Sprint 28, Parte 8 ("stale data reduces confidence"): quando o
        snapshot mais recente foi coletado há mais de
        `STALE_DATA_THRESHOLD_DAYS`, o score agregado é reduzido por
        `STALE_DATA_SCORE_FACTOR` e o motivo explica exatamente por quê —
        nunca um "confiança baixa" sem explicação."""
        applicable = [p for p in (valuation, trap_detection, income) if p.score is not None]
        if not applicable:
            return CoveragePurposeScore(
                classification=CLASSIFICATION_NOT_APPLICABLE,
                reason="nenhuma finalidade fundamentalista aplicável a esta classe de ativo",
            )
        combined_score = sum((p.score for p in applicable), Decimal("0")) / Decimal(len(applicable))
        missing_labels = sorted({label for p in applicable for label in p.missing_labels})
        reason = f"faltam: {', '.join(missing_labels)}" if missing_labels else None

        is_stale = stale_days is not None and stale_days > STALE_DATA_THRESHOLD_DAYS
        if is_stale:
            combined_score = combined_score * STALE_DATA_SCORE_FACTOR
            stale_note = f"dados desatualizados há {stale_days} dias (confiança reduzida)"
            reason = f"{reason}; {stale_note}" if reason else stale_note

        return CoveragePurposeScore(
            score=combined_score,
            classification=classify_score(combined_score),
            missing_labels=missing_labels,
            reason=reason,
        )

    def _build_summary(
        self,
        quality: CoveragePurposeScore,
        valuation: CoveragePurposeScore,
        trap_detection: CoveragePurposeScore,
        income: CoveragePurposeScore,
    ) -> str:
        parts: list[str] = []
        for name, purpose in (
            ("Quality", quality),
            ("Valuation", valuation),
            ("Trap Detection", trap_detection),
            ("Análise de Renda", income),
        ):
            if purpose.classification == CLASSIFICATION_NOT_APPLICABLE:
                continue
            piece = f"{name}: {purpose.classification} ({purpose.score:.0f}%)"
            if purpose.missing_labels:
                piece += f" — faltam: {', '.join(purpose.missing_labels)}"
            parts.append(piece)
        if not parts:
            return "Nenhuma análise fundamentalista aplicável a esta classe de ativo."
        return ". ".join(parts) + "."
