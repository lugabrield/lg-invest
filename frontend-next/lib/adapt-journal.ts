import type { StatusKind } from "@/lib/mock/dashboard";

// Rótulos/cores do Investment Journal (v1.1, Fase 9) — mesmo vocabulário
// de `pages_impl/journal.py` (JOURNAL_ACTIONS, THESIS_STATUSES,
// REVIEW_CLASSIFICATIONS). Nenhuma regra de negócio aqui, só apresentação.

export const JOURNAL_ACTIONS = ["buy", "sell", "hold", "thesis_review"] as const;

export const JOURNAL_ACTION_LABELS_PT: Record<string, string> = {
  buy: "Compra",
  sell: "Venda",
  hold: "Manutenção",
  thesis_review: "Revisão de tese",
};

export const THESIS_STATUSES = ["open", "confirmed", "partially_confirmed", "invalidated"] as const;

export const THESIS_STATUS_LABELS_PT: Record<string, string> = {
  open: "Em observação",
  confirmed: "Confirmada",
  partially_confirmed: "Parcialmente confirmada",
  invalidated: "Invalidada",
};

export const THESIS_STATUS_KIND: Record<string, StatusKind> = {
  open: "neutral",
  confirmed: "positive",
  partially_confirmed: "attention",
  invalidated: "critical",
};

export const REVIEW_CLASSIFICATIONS = [
  "confirmed",
  "partially_confirmed",
  "in_observation",
  "invalidated",
] as const;

export const REVIEW_CLASSIFICATION_LABELS_PT: Record<string, string> = {
  confirmed: "Confirmada",
  partially_confirmed: "Parcialmente confirmada",
  in_observation: "Em observação",
  invalidated: "Invalidada",
};

export function formatDate(value: string): string {
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) return value;
  return `${day}/${month}/${year}`;
}
