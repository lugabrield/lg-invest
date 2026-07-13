import { cn } from "@/lib/utils";
import type { TopPositionMock } from "@/lib/mock/dashboard";

/** AssetTable — top posições da carteira. Recebe dado já pronto (peso,
 * retorno, classe) — nenhum cálculo acontece aqui. */
export function AssetTable({ positions }: { positions: TopPositionMock[] }) {
  return (
    <div className="rounded-card border border-border bg-surface shadow-card">
      <div className="border-b border-border-soft px-5 py-4 text-sm font-medium text-text-primary">
        Top posições
      </div>
      <div className="scrollbar-thin overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-soft text-left text-xs text-text-faint">
              <th className="px-5 py-2.5 font-medium">Ativo</th>
              <th className="px-5 py-2.5 font-medium">Classe</th>
              <th className="px-5 py-2.5 text-right font-medium">Peso</th>
              <th className="px-5 py-2.5 text-right font-medium">Retorno</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((position) => (
              <tr key={position.ticker} className="border-b border-border-soft/60 last:border-0">
                <td className="px-5 py-3">
                  <div className="font-medium text-text-primary">{position.ticker}</div>
                  <div className="text-xs text-text-faint">{position.name}</div>
                </td>
                <td className="px-5 py-3 text-text-muted">{position.classLabel}</td>
                <td className="px-5 py-3 text-right font-medium text-text-primary">
                  {position.weight.toFixed(1)}%
                </td>
                <td
                  className={cn(
                    "px-5 py-3 text-right font-medium",
                    position.returnPct >= 0 ? "text-positive" : "text-critical",
                  )}
                >
                  {position.returnPct >= 0 ? "+" : ""}
                  {position.returnPct.toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
