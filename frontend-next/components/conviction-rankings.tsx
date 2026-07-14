import type { AssetIntelligence } from "@/lib/api";
import { CLASSIFICATION_STATUS } from "@/lib/adapt-intelligence";
import { StatusBadge } from "@/components/status-badge";

// Uma coluna de ranking (mais baratos / maior qualidade / maior
// crescimento / mais caros / maior risco) — Fase 5. Espelha
// `_render_asset_line()` de `pages_impl/inteligencia.py`.
interface RankingColumnProps {
  title: string;
  caption?: string;
  assets: AssetIntelligence[];
  valueLabel: string;
  value: (a: AssetIntelligence) => string | null;
}

export function RankingColumn({ title, caption, assets, valueLabel, value }: RankingColumnProps) {
  return (
    <div>
      <div className="mb-2 text-sm font-medium text-text-primary">{title}</div>
      {assets.length === 0 ? (
        <p className="text-xs text-text-faint">Nenhum ativo elegível para este ranking.</p>
      ) : (
        <ul className="space-y-1.5">
          {assets.map((a) => {
            const v = value(a);
            return (
              <li key={a.ticker} className="flex items-center gap-2 text-sm">
                <StatusBadge
                  label={a.classification ?? "insufficient_data"}
                  status={CLASSIFICATION_STATUS[a.classification ?? "insufficient_data"] ?? "muted"}
                  className="shrink-0"
                />
                <span className="font-medium text-text-primary">{a.ticker}</span>
                <span className="text-text-faint">({a.asset_class})</span>
                <span className="ml-auto text-text-muted">
                  {valueLabel}: {v !== null ? Number(v).toFixed(1) : "—"}
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {caption && <p className="mt-2 text-xs text-text-faint">{caption}</p>}
    </div>
  );
}
