"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { AllocationSliceMock } from "@/lib/mock/dashboard";

interface DonutChartCardProps {
  title: string;
  description?: string;
  data: AllocationSliceMock[];
}

/** DonutChartCard — composição por classe/moeda/BR-vs-exterior. Sempre
 * consome dados já prontos (nunca calcula porcentagem aqui). */
export function DonutChartCard({ title, description, data }: DonutChartCardProps) {
  return (
    <div className="rounded-card border border-border bg-surface p-5 shadow-card">
      <div className="mb-1 text-sm font-medium text-text-primary">{title}</div>
      {description && <div className="mb-3 text-xs text-text-muted">{description}</div>}
      <div className="flex items-center gap-4">
        <div className="h-40 w-40 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="label"
                innerRadius={48}
                outerRadius={70}
                paddingAngle={2}
                stroke="none"
              >
                {data.map((slice) => (
                  <Cell key={slice.label} fill={slice.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "#0B1020",
                  border: "1px solid #1E2740",
                  borderRadius: 8,
                  fontSize: 12,
                  color: "#F5F7FB",
                }}
                formatter={(value: number, name: string) => [`${value}%`, name]}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex-1 space-y-2">
          {data.map((slice) => (
            <div key={slice.label} className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-2 text-text-muted">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: slice.color }} />
                {slice.label}
              </span>
              <span className="font-medium text-text-primary">{slice.value}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
