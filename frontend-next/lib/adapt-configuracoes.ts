import type { StatusKind } from "@/lib/mock/dashboard";

// Rótulos/cores da tela Configurações (v1.1, Fase 10) — mesmo
// vocabulário de `pages_impl/configuracoes.py`. Nenhuma regra de
// precedência/conflito é recalculada aqui, só formatação.

export const ASSET_CLASSES = ["stock", "fii", "etf", "reit", "crypto", "bond", "cash"] as const;

export const TARGET_ALLOCATION_DIMENSIONS = ["class", "currency", "country", "asset"] as const;

export const DIMENSION_TYPE_LABELS_PT: Record<string, string> = {
  class: "Classe",
  currency: "Moeda",
  country: "País",
  asset: "Ativo",
};

export const EFFECTIVE_LIMIT_SOURCE_LABELS_PT: Record<string, string> = {
  regra_detalhada: "Regra detalhada",
  politica_geral: "Política geral",
};

export const CONFLICT_KIND_LABELS_PT: Record<string, string> = {
  simple_vs_detailed: "Alocação simples x regra detalhada",
  sum_not_100: "Soma não fecha 100%",
  min_greater_than_target: "Mínimo maior que o alvo",
};

export const RISK_TOLERANCES = ["baixo", "moderado", "moderado-alto", "alto"] as const;

export const FX_SOURCE_LABELS_PT: Record<string, string> = {
  bcb: "BCB (PTAX)",
  yahoo: "Yahoo Finance",
  manual: "Manual",
};

// Cadastro rápido (mesmo atalho de `_QUICK_RULE_PRESETS` do Streamlit) —
// só preenche o formulário de regra detalhada, nunca salva sozinho.
export const QUICK_RULE_PRESETS: { label: string; dimensionType: string; dimensionKey: string }[] = [
  { label: "USD", dimensionType: "currency", dimensionKey: "USD" },
  { label: "BRL", dimensionType: "currency", dimensionKey: "BRL" },
  { label: "FIIs", dimensionType: "class", dimensionKey: "fii" },
  { label: "ETFs", dimensionType: "class", dimensionKey: "etf" },
  { label: "BTC", dimensionType: "asset", dimensionKey: "BTC-USD" },
  { label: "Tesouro", dimensionType: "class", dimensionKey: "bond" },
  { label: "VOO", dimensionType: "asset", dimensionKey: "VOO" },
  { label: "QQQ", dimensionType: "asset", dimensionKey: "QQQ" },
];

export function formatPct(value: string | number, decimals = 1): string {
  const n = typeof value === "string" ? Number(value) : value;
  return `${(n * 100).toFixed(decimals)}%`.replace(".", ",");
}

export function formatPctOrDash(value: string | null, decimals = 1): string {
  return value === null ? "—" : formatPct(value, decimals);
}

export function conflictSeverity(): StatusKind {
  return "attention";
}
