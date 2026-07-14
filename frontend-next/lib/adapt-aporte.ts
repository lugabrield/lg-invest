// Adaptador puro do Aporte (v1.1, Fase 3): transforma `AporteBundle` (API)
// nos formatos que os componentes de apresentação esperam — mesma regra do
// `adapt-dashboard.ts`, nenhum cálculo financeiro novo, só formatação e
// rótulos. Os mapas de rótulo abaixo espelham exatamente o vocabulário de
// `frontend/streamlit_app/pages_impl/aporte.py` (`_BLOCK_SOURCE_LABELS`,
// `DIMENSION_TYPE_LABELS`) para a tela nova não inventar um texto novo.

import type { StatusKind } from "@/lib/mock/dashboard";
import type {
  AllocationProjection,
  CappedDimensionResult,
  IgnoredItem,
  RecommendationItem,
} from "@/lib/api";
import { formatBRL, formatPct } from "@/lib/format";

export const BLOCK_SOURCE_LABELS: Record<string, string> = {
  bloqueio_manual: "Bloqueio manual",
  sobreconcentracao: "Sobreconcentração",
  regra_detalhada: "Regra detalhada (alocação-alvo)",
  politica_geral: "Política geral de investimento",
};

export const DIMENSION_TYPE_LABELS: Record<string, string> = {
  class: "Classe",
  currency: "Moeda",
  country: "País",
  asset: "Ativo",
  international: "Exposição internacional",
};

export interface ScoreBadgeView {
  label: string;
  status: StatusKind;
}

export interface RecommendationCardView {
  ticker: string;
  amount: string;
  weightLabel: string;
  reason: string;
  tag: "already_have" | "new_candidate";
  scoreBadges: ScoreBadgeView[];
  watchlistReason: string | null;
  extraReasons: string[];
  scoreBreakdown: { label: string; contribution: number }[];
}

export function adaptRecommendationItem(item: RecommendationItem): RecommendationCardView {
  const scoreBadges: ScoreBadgeView[] = [
    { label: `LG Score ${Number(item.lg_score).toFixed(0)}`, status: "neutral" },
  ];
  if (item.conviction_score !== null) {
    scoreBadges.push({ label: `Conviction ${Number(item.conviction_score).toFixed(0)}`, status: "neutral" });
  }
  if (item.item_confidence !== null) {
    const confPct = Number(item.item_confidence) * 100;
    const status: StatusKind = confPct >= 80 ? "positive" : confPct >= 50 ? "attention" : "critical";
    scoreBadges.push({ label: `Confiança do dado ${confPct.toFixed(0)}%`, status });
  }

  return {
    ticker: item.ticker,
    amount: formatBRL(Number(item.amount)),
    weightLabel: formatPct(Number(item.weight)),
    reason: item.reasons[0] ?? "Sem motivo detalhado disponível.",
    tag: item.is_new_from_watchlist ? "new_candidate" : "already_have",
    scoreBadges,
    watchlistReason: item.watchlist_reason,
    extraReasons: item.reasons.slice(1),
    scoreBreakdown: item.score_breakdown.map((factor) => ({
      label: factor.label,
      contribution: Number(factor.contribution),
    })),
  };
}

export interface IgnoredItemView {
  ticker: string;
  blockSourceLabel: string;
  reason: string;
}

export function adaptIgnoredItem(item: IgnoredItem): IgnoredItemView {
  return {
    ticker: item.ticker,
    blockSourceLabel: item.block_source ? (BLOCK_SOURCE_LABELS[item.block_source] ?? item.block_source) : "—",
    reason: item.reason,
  };
}

export interface CappedDimensionView {
  dimensionLabel: string;
  item: string;
  before: string;
  after: string;
  maxWeight: string;
  sourceLabel: string;
  status: "Limite atingido" | "Dentro do limite";
}

export function adaptCappedDimension(cd: CappedDimensionResult): CappedDimensionView {
  const weightAfter = Number(cd.weight_after);
  const maxWeight = Number(cd.max_weight);
  return {
    dimensionLabel: DIMENSION_TYPE_LABELS[cd.dimension_type] ?? cd.dimension_type,
    item: cd.dimension_key,
    before: formatPct(Number(cd.weight_before)),
    after: formatPct(weightAfter),
    maxWeight: formatPct(maxWeight),
    sourceLabel: BLOCK_SOURCE_LABELS[cd.source] ?? cd.source,
    status: weightAfter >= maxWeight ? "Limite atingido" : "Dentro do limite",
  };
}

export interface ProjectionSummaryView {
  totalBefore: string;
  totalAfter: string;
  hhiAfter: string;
  hhiDelta: number;
  internationalAfter: string;
  internationalDeltaPp: number;
  byGroup: { label: string; before: number; after: number }[];
}

export function adaptProjectionSummary(projection: AllocationProjection): ProjectionSummaryView {
  const hhiBefore = Number(projection.concentration_hhi_before);
  const hhiAfter = Number(projection.concentration_hhi_after);
  const intlBefore = Number(projection.international_weight_before);
  const intlAfter = Number(projection.international_weight_after);

  return {
    totalBefore: formatBRL(Number(projection.total_before_brl)),
    totalAfter: formatBRL(Number(projection.total_after_brl)),
    hhiAfter: hhiAfter.toFixed(3),
    hhiDelta: hhiAfter - hhiBefore,
    internationalAfter: formatPct(intlAfter),
    internationalDeltaPp: (intlAfter - intlBefore) * 100,
    byGroup: projection.by_group.map((comparison) => ({
      label: comparison.label,
      before: Number((Number(comparison.weight_before) * 100).toFixed(1)),
      after: Number((Number(comparison.weight_after) * 100).toFixed(1)),
    })),
  };
}
