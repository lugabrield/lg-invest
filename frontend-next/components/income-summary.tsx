import type { IncomeAnalysisResultView } from "@/lib/api";
import { formatBRL, formatPct } from "@/lib/format";
import { MetricCard } from "@/components/metric-card";

// Renda de Proventos — Fase 5. Espelha a seção final de
// `pages_impl/inteligencia.py`: tendência agregada (Análise mensal) e
// renda por ativo (calendário), nunca somadas entre si (Fase 7 do
// Income Engine).
export function IncomeSummary({ income }: { income: IncomeAnalysisResultView }) {
  const { trend, breakdown } = income;
  const growth = trend.growth_pct !== null ? Number(trend.growth_pct) : null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetricCard label="Renda últimos 12 meses" value={formatBRL(Number(trend.ttm_total))} status="positive" icon="wallet" />
        <MetricCard
          label="Crescimento vs. período anterior"
          value={growth !== null ? `${growth >= 0 ? "+" : ""}${formatPct(growth)}` : "—"}
          status={growth === null ? "neutral" : growth >= 0 ? "positive" : "critical"}
          icon="trending-up"
        />
        <MetricCard
          label="Projeção próximos 12 meses"
          value={formatBRL(Number(trend.projected_next_12_months))}
          status="neutral"
          icon="pie-chart"
        />
      </div>

      {breakdown.rows.length > 0 ? (
        <div>
          <p className="mb-2 text-sm font-medium text-text-primary">
            Yield on cost por ativo (renda / custo de aquisição, não sobre o preço de mercado atual)
          </p>
          <div className="scrollbar-thin overflow-x-auto rounded-card border border-border bg-surface shadow-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-soft text-left text-xs text-text-faint">
                  <th className="px-5 py-2.5 font-medium">Ticker</th>
                  <th className="px-5 py-2.5 text-right font-medium">Renda (12m)</th>
                  <th className="px-5 py-2.5 text-right font-medium">Custo de aquisição</th>
                  <th className="px-5 py-2.5 text-right font-medium">Yield on cost</th>
                </tr>
              </thead>
              <tbody>
                {breakdown.rows.map((r) => (
                  <tr key={r.ticker} className="border-b border-border-soft/60 last:border-0">
                    <td className="px-5 py-3 font-medium text-text-primary">{r.ticker}</td>
                    <td className="px-5 py-3 text-right text-text-primary">{formatBRL(Number(r.ttm_income))}</td>
                    <td className="px-5 py-3 text-right text-text-muted">
                      {r.cost_basis !== null ? formatBRL(Number(r.cost_basis)) : "—"}
                    </td>
                    <td className="px-5 py-3 text-right text-text-muted">
                      {r.yield_on_cost !== null ? formatPct(Number(r.yield_on_cost)) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {breakdown.portfolio_yield_on_cost !== null && (
            <p className="mt-2 text-xs text-text-faint">
              Yield on cost da carteira: {formatPct(Number(breakdown.portfolio_yield_on_cost))}
            </p>
          )}
        </div>
      ) : (
        <p className="text-sm text-text-muted">Nenhum evento de renda por ativo registrado ainda para esta carteira.</p>
      )}

      {income.warnings.map((w, idx) => (
        <p key={idx} className="text-xs text-attention">
          ⚠️ {w}
        </p>
      ))}
    </div>
  );
}
