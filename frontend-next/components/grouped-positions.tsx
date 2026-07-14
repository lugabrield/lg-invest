"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { GroupedPositions as GroupedPositionsData } from "@/lib/adapt-carteira";
import { formatPct } from "@/lib/format";

// Agrupamento por classe — Fase 4. Espelha `render_grouped_positions()`
// de `frontend/streamlit_app/components/tables.py`: um "expander" por
// grupo, cabeçalho com total e contagem de posições negativas.
export function GroupedPositions({ groups }: { groups: GroupedPositionsData[] }) {
  const [openGroup, setOpenGroup] = useState<string | null>(groups[0]?.group ?? null);

  return (
    <div className="space-y-2">
      {groups.map((group) => {
        const isOpen = openGroup === group.group;
        return (
          <div key={group.group} className="rounded-card border border-border bg-surface shadow-card">
            <button
              onClick={() => setOpenGroup(isOpen ? null : group.group)}
              className="flex w-full items-center justify-between px-5 py-3.5 text-left"
            >
              <span className="text-sm font-medium text-text-primary">
                {group.group} · {group.totalLabel}
                {group.negativeCount > 0 && (
                  <span className="ml-2 text-xs font-normal text-critical">
                    {group.negativeCount} em queda
                  </span>
                )}
              </span>
              <ChevronDown
                className={cn("h-4 w-4 text-text-faint transition-transform", isOpen && "rotate-180")}
                strokeWidth={1.75}
              />
            </button>
            {isOpen && (
              <div className="border-t border-border-soft px-5 py-3">
                <ul className="divide-y divide-border-soft/60">
                  {group.positions.map((position) => (
                    <li key={position.ticker} className="flex items-center justify-between py-2 text-sm">
                      <span className="text-text-primary">{position.ticker}</span>
                      <span className="text-text-muted">{formatPct(Number(position.weight))}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
