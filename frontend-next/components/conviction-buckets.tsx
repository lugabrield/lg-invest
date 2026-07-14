"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AssetBucket } from "@/lib/adapt-intelligence";
import { formatPct } from "@/lib/format";

// Classificação da carteira — Fase 5. Espelha os expanders por bucket
// (Aportar/Candidato/Manter/Monitorar/Evitar/Dados insuficientes) de
// `pages_impl/inteligencia.py`, mesma ordem e mesmo texto por ativo.
export function ConvictionBuckets({ buckets }: { buckets: AssetBucket[] }) {
  const [openKey, setOpenKey] = useState<string | null>(buckets[0]?.key ?? null);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-text-muted">
        {buckets.map((b) => (
          <span key={b.key}>
            {b.icon} {b.label}: {b.assets.length}
          </span>
        ))}
      </div>
      {buckets.map((bucket) => {
        const isOpen = openKey === bucket.key;
        return (
          <div key={bucket.key} className="rounded-card border border-border bg-surface shadow-card">
            <button
              onClick={() => setOpenKey(isOpen ? null : bucket.key)}
              className="flex w-full items-center justify-between px-5 py-3.5 text-left"
            >
              <span className="text-sm font-medium text-text-primary">
                {bucket.icon} {bucket.label} ({bucket.assets.length})
              </span>
              <ChevronDown
                className={cn("h-4 w-4 text-text-faint transition-transform", isOpen && "rotate-180")}
                strokeWidth={1.75}
              />
            </button>
            {isOpen && (
              <div className="border-t border-border-soft px-5 py-3">
                <ul className="divide-y divide-border-soft/60">
                  {bucket.assets.map((a) => (
                    <li key={a.ticker} className="py-2 text-sm">
                      {bucket.key === "insufficient_data" ? (
                        <>
                          <span className="font-medium text-text-primary">{a.ticker}</span>
                          <span className="ml-2 text-text-muted">{a.unavailable_reason}</span>
                        </>
                      ) : (
                        <>
                          <span className="font-medium text-text-primary">{a.ticker}</span>
                          <span className="ml-2 text-text-muted">({a.asset_class})</span>
                          <span className="ml-2 text-text-muted">
                            score {Number(a.conviction_score).toFixed(1)} · peso {formatPct(Number(a.current_weight))}
                          </span>
                          {a.explanation[0]?.reasons[0] && (
                            <div className="mt-0.5 text-xs text-text-faint">· {a.explanation[0].reasons[0]}</div>
                          )}
                        </>
                      )}
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
