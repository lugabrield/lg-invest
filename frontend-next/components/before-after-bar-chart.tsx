"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface BeforeAfterBarChartProps {
  title: string;
  description?: string;
  data: { label: string; before: number; after: number }[];
}

/** BeforeAfterBarChart — peso por classe antes x depois de um aporte
 * simulado (Aporte v3, Fase 3). Mesma leitura do gráfico Plotly em
 * `pages_impl/aporte.py::_before_after_chart`, só trocando a lib —
 * nenhum peso é recalculado aqui, `data` já vem pronto de
 * `lib/adapt-aporte.ts`. */
export function BeforeAfterBarChart({ title, description, data }: BeforeAfterBarChartProps) {
  return (
    <div className="rounded-card border border-border bg-surface p-5 shadow-card">
      <div className="mb-1 text-sm font-medium text-text-primary">{title}</div>
      {description && <div className="mb-3 text-xs text-text-muted">{description}</div>}
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1E2740" horizontal={false} />
            <XAxis type="number" tick={{ fill: "#9AA4C0", fontSize: 11 }} unit="%" />
            <YAxis type="category" dataKey="label" tick={{ fill: "#F5F7FB", fontSize: 12 }} width={90} />
            <Tooltip
              contentStyle={{
                background: "#0B1020",
                border: "1px solid #1E2740",
                borderRadius: 8,
                fontSize: 12,
                color: "#F5F7FB",
              }}
              formatter={(value: number) => `${value}%`}
            />
            <Legend wrapperStyle={{ fontSize: 12, color: "#9AA4C0" }} />
            <Bar dataKey="before" name="Antes" fill="#5B6478" radius={[0, 4, 4, 0]} />
            <Bar dataKey="after" name="Depois" fill="#8B5CF6" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
