import type { RadarClassificationResult, WatchlistAssetView } from "@/lib/api";
import { STATUS_ICON, STATUS_KIND, STATUS_LABELS_PT, WATCHLIST_STATUSES } from "@/lib/adapt-radar";
import { StatusBadge } from "@/components/status-badge";

// Resumo da Watchlist — Fase 7. Espelha "Resumo da Watchlist" de
// `pages_impl/radar.py`: contagem por estágio do funil (monitorando ->
// candidato -> comprado, ou bloqueado/descartado) + quantos candidatos
// ainda não têm dado suficiente para o Radar classificar.
export function WatchlistSummary({
  entries,
  radarByTicker,
}: {
  entries: WatchlistAssetView[];
  radarByTicker: Map<string, RadarClassificationResult>;
}) {
  const counts = new Map<string, number>();
  for (const entry of entries) {
    counts.set(entry.status, (counts.get(entry.status) ?? 0) + 1);
  }

  const insufficient = entries.filter((e) => {
    const radar = radarByTicker.get(e.ticker);
    return radar === undefined || radar.classification === "insufficient_data";
  }).length;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {WATCHLIST_STATUSES.map((status) => (
        <div key={status} className="rounded-card border border-border bg-surface p-4 shadow-card">
          <div className="flex items-center gap-1.5 text-xs text-text-faint">
            <span>{STATUS_ICON[status]}</span>
            {STATUS_LABELS_PT[status]}
          </div>
          <div className="mt-2 text-xl font-semibold text-text-primary">{counts.get(status) ?? 0}</div>
        </div>
      ))}
      <div className="rounded-card border border-border bg-surface p-4 shadow-card">
        <div className="flex items-center gap-1.5 text-xs text-text-faint">
          <span>❓</span>
          Dados insuficientes
        </div>
        <div className="mt-2 text-xl font-semibold text-text-primary">{insufficient}</div>
      </div>
    </div>
  );
}

export function StatusPill({ status }: { status: string }) {
  return (
    <StatusBadge
      label={`${STATUS_ICON[status] ?? ""} ${STATUS_LABELS_PT[status] ?? status}`.trim()}
      status={STATUS_KIND[status] ?? "muted"}
    />
  );
}
