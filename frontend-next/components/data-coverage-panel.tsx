import type { CoveragePurposeScore, DataCoverageResult } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import type { StatusKind } from "@/lib/mock/dashboard";

const PURPOSE_LABELS: Record<string, string> = {
  quality: "Qualidade",
  valuation: "Valuation",
  trap_detection: "Detecção de armadilhas",
  income: "Análise de renda",
  decision_engine: "Decision Engine",
};

const COVERAGE_STATUS: Record<string, StatusKind> = {
  completo: "positive",
  parcial: "attention",
  insuficiente: "critical",
  nao_aplicavel: "muted",
};

function PurposeScoreCard({ label, purpose }: { label: string; purpose: CoveragePurposeScore }) {
  return (
    <div className="rounded-lg border border-border-soft bg-surface-hover p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-primary">{label}</span>
        <StatusBadge
          label={purpose.classification}
          status={COVERAGE_STATUS[purpose.classification] ?? "muted"}
        />
      </div>
      <div className="mt-1 text-sm font-semibold text-text-primary">{purpose.score ?? "—"}</div>
      {purpose.missing_labels.length > 0 && (
        <p className="mt-1 text-[11px] text-text-faint">Faltando: {purpose.missing_labels.join(", ")}</p>
      )}
      {purpose.reason && <p className="mt-1 text-[11px] text-text-faint">{purpose.reason}</p>}
    </div>
  );
}

// Cobertura de Dados — Fase 6. Espelha a subseção de cobertura dentro de
// "Análise Fundamentalista" em `pages_impl/ativos.py`: score por
// finalidade (qualidade/valuation/traps/renda/decisão) + campos
// disponíveis/ausentes expansíveis.
export function DataCoveragePanel({ coverage }: { coverage: DataCoverageResult | null }) {
  if (coverage === null) {
    return null;
  }

  const available = coverage.fields.filter((f) => f.available);
  const missing = coverage.fields.filter((f) => !f.available);

  return (
    <div className="rounded-card border border-border bg-surface p-5 shadow-card">
      <div className="mb-1 text-sm font-medium text-text-primary">Cobertura de Dados</div>
      <p className="mb-3 text-xs text-text-muted">{coverage.summary}</p>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        <PurposeScoreCard label={PURPOSE_LABELS.quality} purpose={coverage.quality} />
        <PurposeScoreCard label={PURPOSE_LABELS.valuation} purpose={coverage.valuation} />
        <PurposeScoreCard label={PURPOSE_LABELS.trap_detection} purpose={coverage.trap_detection} />
        <PurposeScoreCard label={PURPOSE_LABELS.income} purpose={coverage.income} />
        <PurposeScoreCard label={PURPOSE_LABELS.decision_engine} purpose={coverage.decision_engine} />
      </div>

      <details className="mt-4 text-xs">
        <summary className="cursor-pointer text-text-primary">
          Campos disponíveis ({available.length})
        </summary>
        <div className="mt-2 grid grid-cols-2 gap-1.5 sm:grid-cols-3">
          {available.map((field) => (
            <div key={field.field} className="text-text-muted">
              {field.label}: <span className="text-text-primary">{field.value ?? "—"}</span>
              {field.source && <span className="text-text-faint"> ({field.source})</span>}
            </div>
          ))}
        </div>
      </details>

      <details className="mt-2 text-xs">
        <summary className="cursor-pointer text-text-primary">Campos ausentes ({missing.length})</summary>
        <div className="mt-2 space-y-1">
          {missing.map((field) => (
            <div key={field.field} className="text-text-muted">
              {field.label}
              {field.warning && <span className="text-attention"> — {field.warning}</span>}
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
