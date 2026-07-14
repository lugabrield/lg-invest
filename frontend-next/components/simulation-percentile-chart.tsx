"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatBRL } from "@/lib/format";

interface SimulationPercentileChartProps {
  percentiles: Record<string, string>;
}

/** SimulationPercentileChart — distribuição do patrimônio projetado ao
 * final do horizonte, mesma leitura de
 * `chart_simulation_percentiles` (Plotly): faixa p10–p90 (clara) com
 * p25–p75 destacado (cheio) e a mediana (p50) marcada — só trocando a
 * lib, nenhum percentil é recalculado aqui. Implementado como barra
 * horizontal empilhada (o primeiro segmento é um "offset" invisível
 * até p10) porque o Recharts não tem um equivalente direto ao `base`
 * do Plotly. */
export function SimulationPercentileChart({ percentiles }: SimulationPercentileChartProps) {
  const p10 = Number(percentiles.p10 ?? 0);
  const p25 = Number(percentiles.p25 ?? 0);
  const p50 = Number(percentiles.p50 ?? 0);
  const p75 = Number(percentiles.p75 ?? 0);
  const p90 = Number(percentiles.p90 ?? 0);

  const data = [
    {
      name: "Patrimônio projetado",
      offset: p10,
      faixaBaixa: p25 - p10,
      faixaCentral: p75 - p25,
      faixaAlta: p90 - p75,
    },
  ];

  return (
    <div className="rounded-card border border-border bg-surface p-5 shadow-card">
      <div className="mb-1 text-sm font-medium text-text-primary">
        Distribuição do patrimônio projetado ao final do horizonte
      </div>
      <div className="mb-3 text-xs text-text-muted">
        Faixa p10–p90 (clara), com p25–p75 destacado (cheio) e a mediana (p50) marcada.
      </div>
      <div className="h-32 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ left: 8, right: 24, top: 8, bottom: 8 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#1E2740" horizontal={false} />
            <XAxis
              type="number"
              domain={["dataMin", "dataMax"]}
              tick={{ fill: "#9AA4C0", fontSize: 11 }}
              tickFormatter={(value: number) => formatBRL(value)}
            />
            <YAxis type="category" dataKey="name" tick={{ fill: "#F5F7FB", fontSize: 12 }} width={0} hide />
            <Tooltip
              contentStyle={{
                background: "#0B1020",
                border: "1px solid #1E2740",
                borderRadius: 8,
                fontSize: 12,
                color: "#F5F7FB",
              }}
              formatter={(value: number, key: string) => {
                if (key === "offset") return [formatBRL(p10), "p10"];
                if (key === "faixaBaixa") return [formatBRL(p25), "p25"];
                if (key === "faixaCentral") return [formatBRL(p75), "p75"];
                if (key === "faixaAlta") return [formatBRL(p90), "p90"];
                return [formatBRL(value), key];
              }}
            />
            <Bar dataKey="offset" stackId="a" fill="transparent" isAnimationActive={false} />
            <Bar dataKey="faixaBaixa" stackId="a" fill="#5B6478" name="p10–p25" radius={[4, 0, 0, 4]} />
            <Bar dataKey="faixaCentral" stackId="a" fill="#8B5CF6" name="p25–p75" />
            <Bar dataKey="faixaAlta" stackId="a" fill="#5B6478" name="p75–p90" radius={[0, 4, 4, 0]} />
            <ReferenceLine
              x={p50}
              stroke="#22C55E"
              strokeWidth={2}
              label={{ value: "Mediana (p50)", position: "insideTopRight", fill: "#22C55E", fontSize: 11 }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
