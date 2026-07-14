// Adaptador puro: transforma o `DashboardBundle` da API (v1.1, Fase 2) nos
// mesmos formatos que os componentes já esperavam na Fase 1 (dados
// mockados) — nenhum cálculo financeiro novo acontece aqui, só formatação
// e reorganização de campos que a API já devolve prontos. Ver
// `lib/mock/dashboard.ts` para os tipos de apresentação (KpiMock etc.).

import type {
  AllocationSliceMock,
  InsightMock,
  KpiMock,
  StatusKind,
  TopPositionMock,
} from "@/lib/mock/dashboard";
import type { DashboardBundle, DiagnosticInsight } from "@/lib/api";

const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 2,
});

const pctFormatter = (fraction: number) => `${(fraction * 100).toFixed(1)}%`.replace(".", ",");

const GROUP_COLORS: Record<string, string> = {
  "Ações BR": "#8B5CF6",
  FIIs: "#3B82F6",
  "Ações EUA": "#38BDF8",
  ETFs: "#22C55E",
  REITs: "#22C55E",
  Cripto: "#F59E0B",
  "Renda Fixa": "#5B6478",
};
const FALLBACK_COLORS = ["#8B5CF6", "#3B82F6", "#38BDF8", "#22C55E", "#F59E0B", "#5B6478", "#EF4444"];

function severityToStatus(severity: DiagnosticInsight["severity"]): StatusKind {
  switch (severity) {
    case "positive":
      return "positive";
    case "attention":
      return "attention";
    case "alert":
      return "critical";
    case "info":
    default:
      return "neutral";
  }
}

export function adaptKpis(bundle: DashboardBundle): KpiMock[] {
  const { view, health } = bundle;
  const totalConverted = Number(view.total_converted_brl);
  const totalReturn = view.total_return_pct !== null ? Number(view.total_return_pct) : null;
  const largest = view.positions.find((p) => p.ticker === view.largest_position_ticker);
  const healthScore = Number(health.overall_score);
  const internationalWeight = view.currency_exposure
    .filter((c) => c.currency !== "BRL")
    .reduce((sum, c) => sum + Number(c.weight), 0);

  return [
    {
      label: "Patrimônio total",
      value: currencyFormatter.format(totalConverted),
      status: "positive",
      icon: "wallet",
    },
    {
      label: "Rentabilidade total",
      value: totalReturn !== null ? `${totalReturn >= 0 ? "+" : ""}${pctFormatter(totalReturn)}` : "—",
      delta: "desde o início",
      status: totalReturn === null ? "neutral" : totalReturn >= 0 ? "positive" : "critical",
      icon: "trending-up",
    },
    {
      label: "Exposição internacional",
      value: pctFormatter(internationalWeight),
      status: "neutral",
      icon: "globe",
    },
    {
      label: "Maior posição",
      value: largest ? `${largest.ticker} · ${pctFormatter(Number(largest.weight))}` : "—",
      status: "attention",
      icon: "pie-chart",
    },
    {
      label: "LG Health Score",
      value: `${healthScore.toFixed(0)} / 100`,
      delta: health.overall_classification,
      status: healthScore >= 70 ? "positive" : healthScore >= 40 ? "attention" : "critical",
      icon: "heart-pulse",
    },
  ];
}

export function adaptAllocationByClass(bundle: DashboardBundle): AllocationSliceMock[] {
  const totals = new Map<string, number>();
  for (const position of bundle.view.positions) {
    totals.set(position.group_label, (totals.get(position.group_label) ?? 0) + Number(position.weight));
  }
  return Array.from(totals.entries()).map(([label, weight], index) => ({
    label,
    value: Number((weight * 100).toFixed(1)),
    color: GROUP_COLORS[label] ?? FALLBACK_COLORS[index % FALLBACK_COLORS.length],
  }));
}

export function adaptAllocationByCurrency(bundle: DashboardBundle): AllocationSliceMock[] {
  const colors: Record<string, string> = { BRL: "#8B5CF6", USD: "#3B82F6" };
  return bundle.view.currency_exposure.map((exposure, index) => ({
    label: exposure.currency,
    value: Number((Number(exposure.weight) * 100).toFixed(1)),
    color: colors[exposure.currency] ?? FALLBACK_COLORS[index % FALLBACK_COLORS.length],
  }));
}

// Brasil vs. exterior usa a mesma exposição por moeda como proxy (BRL =
// Brasil, demais = exterior) — é a mesma leitura que a tela Streamlit já
// faz hoje, não um cálculo novo.
export function adaptBrazilVsInternational(bundle: DashboardBundle): AllocationSliceMock[] {
  let brasil = 0;
  let exterior = 0;
  for (const exposure of bundle.view.currency_exposure) {
    if (exposure.currency === "BRL") brasil += Number(exposure.weight);
    else exterior += Number(exposure.weight);
  }
  return [
    { label: "Brasil", value: Number((brasil * 100).toFixed(1)), color: "#8B5CF6" },
    { label: "Exterior", value: Number((exterior * 100).toFixed(1)), color: "#38BDF8" },
  ];
}

export function adaptTopPositions(bundle: DashboardBundle, limit = 5): TopPositionMock[] {
  return [...bundle.view.positions]
    .sort((a, b) => Number(b.weight) - Number(a.weight))
    .slice(0, limit)
    .map((position) => ({
      ticker: position.ticker,
      name: position.ticker,
      weight: Number((Number(position.weight) * 100).toFixed(1)),
      returnPct: position.return_pct !== null ? Number((Number(position.return_pct) * 100).toFixed(1)) : 0,
      classLabel: position.group_label,
    }));
}

export function adaptInsights(bundle: DashboardBundle): InsightMock[] {
  return bundle.diagnostics.insights.map((insight) => ({
    title: insight.title,
    message: insight.message,
    severity: severityToStatus(insight.severity),
  }));
}

export function adaptConcentrationScore(bundle: DashboardBundle): number {
  // HHI vem em 0..1 — escala para 0..100 só para o gauge visual (mesma
  // ideia de qualquer índice normalizado), sem reinterpretar o número.
  return Math.round(Number(bundle.view.concentration_hhi) * 100);
}

export function adaptHealthScore(bundle: DashboardBundle): number {
  return Math.round(Number(bundle.health.overall_score));
}
