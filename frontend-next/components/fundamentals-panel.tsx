import type { FundamentalsAnalysisResult, FundamentalSnapshotResult, ValuationResult } from "@/lib/api";
import { FUNDAMENTAL_HIGHLIGHT_FIELDS } from "@/lib/adapt-ativos";
import { StatusBadge } from "@/components/status-badge";

const FIELD_LABELS: Record<string, string> = {
  roe: "ROE",
  net_margin: "Margem líquida",
  pe_ratio: "P/L",
  pb_ratio: "P/VP",
  dividend_yield: "Dividend yield",
  debt_to_ebitda: "Dívida/EBITDA",
  market_cap: "Valor de mercado",
  forward_pe: "P/L futuro",
  operating_margin: "Margem operacional",
};

const CAGR_LABELS: Record<string, string> = {
  revenue_cagr: "Receita",
  net_income_cagr: "Lucro líquido",
  ebitda_cagr: "EBITDA",
  fcf_cagr: "Fluxo de caixa livre",
};

// Fundamentos (snapshot + CAGR + valuation legado v1) — Fase 6. Espelha
// as seções "Fundamentos" e parte de "Análise Fundamentalista" de
// `pages_impl/ativos.py`.
export function FundamentalsPanel({
  fundamentals,
  analysis,
  legacyValuation,
}: {
  fundamentals: FundamentalSnapshotResult | null;
  analysis: FundamentalsAnalysisResult | null;
  legacyValuation: ValuationResult | null;
}) {
  if (fundamentals === null) {
    return (
      <div className="rounded-card border border-border bg-surface p-5 shadow-card">
        <div className="mb-2 text-sm font-medium text-text-primary">Fundamentos</div>
        <p className="text-sm text-text-muted">
          Nenhum snapshot de fundamentos coletado ainda para este ativo.
        </p>
      </div>
    );
  }

  const cagrPairs: Array<[string, string | null, string | null]> = [
    ["revenue_cagr", analysis?.revenue_cagr ?? null, analysis?.revenue_cagr_reason ?? null],
    ["net_income_cagr", analysis?.net_income_cagr ?? null, analysis?.net_income_cagr_reason ?? null],
    ["ebitda_cagr", analysis?.ebitda_cagr ?? null, analysis?.ebitda_cagr_reason ?? null],
    ["fcf_cagr", analysis?.fcf_cagr ?? null, analysis?.fcf_cagr_reason ?? null],
  ];

  return (
    <div className="rounded-card border border-border bg-surface p-5 shadow-card">
      <div className="mb-1 flex items-baseline justify-between">
        <div className="text-sm font-medium text-text-primary">Fundamentos</div>
        <span className="text-xs text-text-faint">
          Período: {fundamentals.period_end} · Fonte: {fundamentals.source}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {FUNDAMENTAL_HIGHLIGHT_FIELDS.map((field) => (
          <div key={field} className="rounded-lg border border-border-soft bg-surface-hover p-2.5">
            <div className="text-xs text-text-faint">{FIELD_LABELS[field]}</div>
            <div className="text-sm font-semibold text-text-primary">
              {(fundamentals as unknown as Record<string, string | null>)[field] ?? "—"}
            </div>
          </div>
        ))}
      </div>

      {analysis && (
        <div className="mt-4 border-t border-border-soft pt-4">
          <div className="mb-2 text-xs font-medium text-text-primary">
            Crescimento (CAGR, {analysis.periods_used} período(s) usado(s)) — confiança: {analysis.confidence}
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {cagrPairs.map(([key, value, reason]) => (
              <div key={key} className="rounded-lg border border-border-soft bg-surface-hover p-2 text-center">
                <div className="text-[10px] text-text-faint">{CAGR_LABELS[key]}</div>
                <div className="text-sm font-semibold text-text-primary">{value ?? "—"}</div>
                {!value && reason && <div className="mt-0.5 text-[10px] text-text-faint">{reason}</div>}
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-text-muted">
            Tendência de margem: {analysis.margin_trend}
            {analysis.margin_trend_reason ? ` — ${analysis.margin_trend_reason}` : ""}
          </p>
          {analysis.reason && <p className="mt-1 text-xs text-text-faint">{analysis.reason}</p>}
        </div>
      )}

      {legacyValuation && (
        <div className="mt-4 border-t border-border-soft pt-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-xs font-medium text-text-primary">Valuation (v1, múltiplos)</span>
            <StatusBadge label={legacyValuation.classification} status="muted" />
            <span className="text-xs text-text-faint">confiança: {legacyValuation.confidence}</span>
          </div>
          <div className="space-y-1.5">
            {legacyValuation.metrics.map((metric) => (
              <div key={metric.field} className="flex items-center justify-between text-xs">
                <span className="text-text-muted">{metric.label}</span>
                <span className="text-text-primary">
                  {metric.value ?? "—"} <span className="text-text-faint">({metric.verdict})</span>
                </span>
              </div>
            ))}
          </div>
          {legacyValuation.reason && (
            <p className="mt-2 text-xs text-text-faint">{legacyValuation.reason}</p>
          )}
        </div>
      )}
    </div>
  );
}
