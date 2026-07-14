// Adaptador puro da tela Radar (v1.1, Fase 7): rótulos/ícones/cores de
// status, mesmo vocabulário de `pages_impl/radar.py` (Sprint 30, Parte 7
// — Radar como funil). Nenhum cálculo — só mapeamento de string para
// rótulo/cor de apresentação.

import type { StatusKind } from "@/lib/mock/dashboard";

// Mesma ordem de exibição de `WATCHLIST_STATUSES` no backend — o funil:
// monitorando -> candidato -> comprado (ou bloqueado/descartado).
export const WATCHLIST_STATUSES = ["watching", "candidate", "blocked", "discarded", "bought"] as const;

export const STATUS_LABELS_PT: Record<string, string> = {
  watching: "Monitorando",
  candidate: "Candidato",
  blocked: "Bloqueado",
  discarded: "Descartado",
  bought: "Comprado",
};

export const STATUS_ICON: Record<string, string> = {
  watching: "👁️",
  candidate: "⭐",
  blocked: "🚫",
  discarded: "🗑️",
  bought: "✅",
};

export const STATUS_KIND: Record<string, StatusKind> = {
  watching: "neutral",
  candidate: "attention",
  blocked: "critical",
  discarded: "muted",
  bought: "positive",
};

export const CLASSIFICATION_LABELS_PT: Record<string, string> = {
  current_holding_candidate: "Já tenho — bom para novo aporte",
  new_candidate: "Novo candidato",
  monitor: "Monitorar",
  avoid: "Evitar (candidato novo)",
  blocked: "Bloqueado",
  insufficient_data: "Dado insuficiente",
};

// Mesma ordem de exibição do Radar de oportunidades no Streamlit.
export const CLASSIFICATION_ORDER = [
  "current_holding_candidate",
  "new_candidate",
  "monitor",
  "avoid",
  "blocked",
  "insufficient_data",
] as const;

export const CLASSIFICATION_KIND: Record<string, StatusKind> = {
  current_holding_candidate: "positive",
  new_candidate: "attention",
  monitor: "neutral",
  avoid: "critical",
  blocked: "critical",
  insufficient_data: "muted",
};

export function formatScore(value: string | null): string {
  return value !== null ? Number(value).toFixed(1) : "—";
}

export function formatConfidencePct(value: string | null): string {
  return value !== null ? `${(Number(value) * 100).toFixed(0)}%` : "—";
}

export function formatDateTime(value: string | null): string {
  if (value === null) return "—";
  return new Date(value).toLocaleString("pt-BR");
}
