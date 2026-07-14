// Adaptador puro da Inteligência (v1.1, Fase 5): buckets por
// classificação, rankings por pilar e rótulos — mesma leitura de
// `frontend/streamlit_app/pages_impl/inteligencia.py`. Nenhum cálculo
// novo, só reorganização do que `GET /api/intelligence` já devolve.

import type { AssetIntelligence, IntelligenceDashboardView } from "@/lib/api";

// Mesmo vocabulário de `frontend/streamlit_app/styles/theme.py::CLASSIFICATION_LABELS_PT`.
export const CLASSIFICATION_LABELS_PT: Record<string, string> = {
  strong_buy: "Aportar",
  buy: "Candidato",
  hold: "Manter",
  watch: "Monitorar",
  avoid: "Evitar",
  insufficient_data: "Dados insuficientes",
};

export const CLASSIFICATION_ICONS: Record<string, string> = {
  strong_buy: "🟢",
  buy: "🔵",
  hold: "⚪",
  watch: "🟡",
  avoid: "🔴",
  insufficient_data: "⬜",
};

// Mesmo mapeamento de cor por status usado no design system (positive/
// neutral/attention/critical/muted) — usado pelos componentes.
export const CLASSIFICATION_STATUS: Record<string, "positive" | "neutral" | "attention" | "critical" | "muted"> = {
  strong_buy: "positive",
  buy: "positive",
  hold: "neutral",
  watch: "attention",
  avoid: "critical",
  insufficient_data: "muted",
};

const BUCKET_ORDER = ["strong_buy", "buy", "hold", "watch", "avoid", "insufficient_data"];

export const PILLAR_LABELS_PT: Record<string, string> = {
  quality: "Qualidade",
  valuation: "Valuation",
  growth: "Crescimento",
  risk: "Risco",
  capital_reinvestment: "Reinvestimento de capital",
};

export interface AssetBucket {
  key: string;
  label: string;
  icon: string;
  assets: AssetIntelligence[];
}

export function bucketAssets(assets: AssetIntelligence[]): AssetBucket[] {
  const buckets: Record<string, AssetIntelligence[]> = Object.fromEntries(BUCKET_ORDER.map((k) => [k, []]));
  for (const a of assets) {
    const key = !a.has_conviction_score
      ? "insufficient_data"
      : a.classification && BUCKET_ORDER.includes(a.classification)
        ? a.classification
        : "insufficient_data";
    buckets[key].push(a);
  }
  for (const key of BUCKET_ORDER) {
    if (key !== "insufficient_data") {
      buckets[key].sort((x, y) => Number(y.conviction_score ?? 0) - Number(x.conviction_score ?? 0));
    }
  }
  return BUCKET_ORDER.map((key) => ({
    key,
    label: CLASSIFICATION_LABELS_PT[key] ?? key,
    icon: CLASSIFICATION_ICONS[key] ?? "⬜",
    assets: buckets[key],
  })).filter((b) => b.assets.length > 0);
}

// Classes onde cada pilar é uma medida real do engine (não o proxy de
// preço v1 genérico) — mesmo filtro de `_RANKING_APPLICABLE_CLASSES` no
// Streamlit (Sprint 22). Risco não tem filtro (plausível para qualquer classe).
const RANKING_APPLICABLE_CLASSES: Record<string, string[]> = {
  valuation: ["stock", "fii", "reit"],
  quality: ["stock", "reit"],
  growth: ["stock", "reit"],
};

export function rankBy(
  assets: AssetIntelligence[],
  field: "valuation" | "quality" | "growth" | "risk",
  { reverse, topN = 5 }: { reverse: boolean; topN?: number },
): AssetIntelligence[] {
  const applicable = RANKING_APPLICABLE_CLASSES[field];
  const scored = assets.filter(
    (a) =>
      a[field] !== null &&
      a.has_conviction_score &&
      a.classification !== "insufficient_data" &&
      (!applicable || applicable.includes(a.asset_class)),
  );
  scored.sort((x, y) => {
    const vx = Number(x[field]);
    const vy = Number(y[field]);
    return reverse ? vy - vx : vx - vy;
  });
  return scored.slice(0, topN);
}

export interface IntelligenceSummary {
  averageScore: string;
  coveragePct: string;
  mostConvictedLabel: string;
  leastConvictedLabel: string;
  hasLowCoverage: boolean;
}

export function adaptIntelligenceSummary(view: IntelligenceDashboardView): IntelligenceSummary {
  return {
    averageScore: view.average_conviction_score !== null ? Number(view.average_conviction_score).toFixed(1) : "—",
    coveragePct: `${(Number(view.coverage_pct) * 100).toFixed(0)}%`,
    mostConvictedLabel: view.most_convicted
      ? `${view.most_convicted.ticker} (${Number(view.most_convicted.conviction_score).toFixed(1)})`
      : "—",
    leastConvictedLabel: view.least_convicted
      ? `${view.least_convicted.ticker} (${Number(view.least_convicted.conviction_score).toFixed(1)})`
      : "—",
    hasLowCoverage: Number(view.coverage_pct) < 1,
  };
}
