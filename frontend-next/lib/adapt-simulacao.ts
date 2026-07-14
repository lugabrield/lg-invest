import type { SimulationResultView } from "@/lib/api";
import { formatBRL, formatPct } from "@/lib/format";
import type { StatusKind } from "@/lib/mock/dashboard";

// Formatação/interpretação da Simulação (v1.1, Fase 8) — espelha
// `pages_impl/simulacao.py`: nenhum percentil, probabilidade de perda
// ou métrica é recalculado aqui, só formatado (BRL/%) e classificado em
// um `StatusKind` visual, igual ao `loss_status` do Streamlit.

const PERCENTILE_ORDER = ["p10", "p25", "p50", "p75", "p90"] as const;

const PERCENTILE_LABELS_PT: Record<string, string> = {
  p10: "Pessimista (p10)",
  p25: "Conservador (p25)",
  p50: "Mediana (p50)",
  p75: "Otimista (p75)",
  p90: "Muito otimista (p90)",
};

export function orderedPercentiles(
  percentiles: Record<string, string>,
): { key: string; label: string; value: string }[] {
  return PERCENTILE_ORDER.filter((key) => key in percentiles).map((key) => ({
    key,
    label: PERCENTILE_LABELS_PT[key] ?? key,
    value: percentiles[key],
  }));
}

/** Mesmos limiares de `pages_impl/simulacao.py::loss_status`: >=30%
 * crítico, >=10% atenção, senão positivo. */
export function lossStatus(probabilityOfLoss: number): StatusKind {
  if (probabilityOfLoss >= 0.3) return "critical";
  if (probabilityOfLoss >= 0.1) return "attention";
  return "positive";
}

export interface SimulationMetricCardView {
  label: string;
  value: string;
  status: StatusKind;
}

export function buildMetricCards(result: SimulationResultView): SimulationMetricCardView[] {
  const probLoss = Number(result.probability_of_loss);
  return [
    { label: "Valor inicial", value: formatBRL(Number(result.initial_value)), status: "neutral" },
    {
      label: "Total aportado (horizonte)",
      value: formatBRL(Number(result.total_contributed)),
      status: "neutral",
    },
    {
      label: "Mediana projetada",
      value: formatBRL(Number(result.median_final_value)),
      status: "positive",
    },
    { label: "Probabilidade de perda", value: formatPct(probLoss), status: lossStatus(probLoss) },
  ];
}

/** Dado achatado para o gráfico de faixa p10–p90 (uma única "barra"
 * horizontal), mesma leitura de `chart_simulation_percentiles` —
 * nenhum percentil é recalculado aqui, só reorganizado para o Recharts. */
export function buildPercentileRangeDatum(percentiles: Record<string, string>): {
  name: string;
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  bandLow: number;
  bandMid: number;
  bandHigh: number;
} {
  const p10 = Number(percentiles.p10 ?? 0);
  const p25 = Number(percentiles.p25 ?? 0);
  const p50 = Number(percentiles.p50 ?? 0);
  const p75 = Number(percentiles.p75 ?? 0);
  const p90 = Number(percentiles.p90 ?? 0);
  return {
    name: "Patrimônio projetado",
    p10,
    p25,
    p50,
    p75,
    p90,
    bandLow: p10,
    bandMid: p25 - p10,
    bandHigh: p75 - p25,
  };
}
