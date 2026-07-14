"use client";

import { useState } from "react";
import { Trophy } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ConvertedPosition } from "@/lib/api";
import { adaptPositionRow } from "@/lib/adapt-carteira";

// Tabela de posições da Carteira — Fase 4. Espelha `_SIMPLE_COLUMNS` vs.
// colunas detalhadas de `frontend/streamlit_app/components/tables.py`;
// o toggle simples/detalhado é só apresentação (nenhum recálculo).
interface PositionsTableProps {
  positions: ConvertedPosition[];
  largestTicker: string | null;
}

export function PositionsTable({ positions, largestTicker }: PositionsTableProps) {
  const [detailed, setDetailed] = useState(false);
  const rows = positions.map((p) => adaptPositionRow(p, largestTicker));

  return (
    <div className="rounded-card border border-border bg-surface shadow-card">
      <div className="flex items-center justify-between border-b border-border-soft px-5 py-4">
        <span className="text-sm font-medium text-text-primary">Todas as posições</span>
        <button
          onClick={() => setDetailed((v) => !v)}
          className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-medium text-text-primary transition-colors hover:bg-surface-hover"
        >
          {detailed ? "Ver simplificado" : "Ver detalhado"}
        </button>
      </div>
      <div className="scrollbar-thin overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-soft text-left text-xs text-text-faint">
              <th className="px-5 py-2.5 font-medium">Ticker</th>
              <th className="px-5 py-2.5 font-medium">Grupo</th>
              {detailed && <th className="px-5 py-2.5 font-medium">Moeda</th>}
              <th className="px-5 py-2.5 text-right font-medium">Quantidade</th>
              {detailed && <th className="px-5 py-2.5 text-right font-medium">Preço médio</th>}
              <th className="px-5 py-2.5 text-right font-medium">Preço atual</th>
              {detailed && <th className="px-5 py-2.5 font-medium">Origem do preço</th>}
              <th className="px-5 py-2.5 text-right font-medium">Valor (R$ convertido)</th>
              <th className="px-5 py-2.5 text-right font-medium">Peso %</th>
              <th className="px-5 py-2.5 text-right font-medium">Rentab. %</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.ticker} className="border-b border-border-soft/60 last:border-0">
                <td className="px-5 py-3">
                  <div className="flex items-center gap-1.5 font-medium text-text-primary">
                    {row.isLargest && <Trophy className="h-3.5 w-3.5 text-attention" strokeWidth={1.75} />}
                    {row.ticker}
                  </div>
                </td>
                <td className="px-5 py-3 text-text-muted">{row.group}</td>
                {detailed && <td className="px-5 py-3 text-text-muted">{row.currency}</td>}
                <td className="px-5 py-3 text-right text-text-primary">{row.quantity}</td>
                {detailed && <td className="px-5 py-3 text-right text-text-muted">{row.averagePrice}</td>}
                <td className="px-5 py-3 text-right text-text-primary">{row.currentPrice}</td>
                {detailed && <td className="px-5 py-3 text-text-muted">{row.priceSourceLabel}</td>}
                <td className="px-5 py-3 text-right font-medium text-text-primary">{row.valueBRL}</td>
                <td className="px-5 py-3 text-right text-text-primary">{row.weightPct}</td>
                <td
                  className={cn(
                    "px-5 py-3 text-right font-medium",
                    row.returnPct === null
                      ? "text-text-faint"
                      : row.isNegative
                        ? "text-critical"
                        : "text-positive",
                  )}
                >
                  {row.returnPct ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
