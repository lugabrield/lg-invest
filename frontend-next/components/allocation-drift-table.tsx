import { cn } from "@/lib/utils";
import type { TargetAllocationResult } from "@/lib/api";
import { formatPct } from "@/lib/format";

const STATUS_LABEL: Record<string, string> = {
  abaixo: "Abaixo da meta",
  dentro: "Dentro da tolerância",
  acima: "Acima da meta",
};

const STATUS_COLOR: Record<string, string> = {
  abaixo: "text-attention",
  dentro: "text-positive",
  acima: "text-critical",
};

// Alocação-alvo por classe — Fase 5. Espelha a tabela de
// `pages_impl/inteligencia.py` (Atual/Meta/Desvio/Status), sem meta
// configurada mostra o motivo em vez de uma tabela vazia.
export function AllocationDriftTable({ drift }: { drift: TargetAllocationResult }) {
  if (!drift.has_target) {
    return (
      <p className="text-sm text-text-muted">
        {drift.reason ?? "Nenhuma meta de alocação configurada ainda — configure em Configurações."}
      </p>
    );
  }

  return (
    <div>
      <div className="scrollbar-thin overflow-x-auto rounded-card border border-border bg-surface shadow-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-soft text-left text-xs text-text-faint">
              <th className="px-5 py-2.5 font-medium">Classe</th>
              <th className="px-5 py-2.5 text-right font-medium">Atual</th>
              <th className="px-5 py-2.5 text-right font-medium">Meta</th>
              <th className="px-5 py-2.5 text-right font-medium">Desvio</th>
              <th className="px-5 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {drift.classes.map((c) => (
              <tr key={c.asset_class} className="border-b border-border-soft/60 last:border-0">
                <td className="px-5 py-3 font-medium text-text-primary">{c.asset_class}</td>
                <td className="px-5 py-3 text-right text-text-primary">{formatPct(Number(c.current_pct))}</td>
                <td className="px-5 py-3 text-right text-text-muted">{formatPct(Number(c.target_pct))}</td>
                <td className="px-5 py-3 text-right text-text-muted">
                  {Number(c.drift_pct) >= 0 ? "+" : ""}
                  {formatPct(Number(c.drift_pct))}
                </td>
                <td className={cn("px-5 py-3 font-medium", STATUS_COLOR[c.status] ?? "text-text-muted")}>
                  {STATUS_LABEL[c.status] ?? c.status}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {drift.most_underweight_class && (
        <p className="mt-2 text-xs text-text-faint">
          Classe mais subalocada: <span className="font-medium text-text-muted">{drift.most_underweight_class}</span> —
          candidata natural ao próximo aporte.
        </p>
      )}
    </div>
  );
}
