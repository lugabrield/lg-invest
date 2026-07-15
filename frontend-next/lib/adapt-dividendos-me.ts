import type { StatusKind } from "@/lib/mock/dashboard";
import { formatBRL } from "@/lib/format";

// Vocabulário compartilhado da tela Dividendos.me (v1.1, Fase 11) —
// mesmos rótulos de `frontend/streamlit_app/components/import_preview.py`
// e `income_preview.py`/`monthly_summary_preview.py`. Nenhum cálculo
// financeiro mora aqui, só apresentação do que a API já devolve pronto.

export const SECTION_LABELS_PT: Record<string, string> = {
  brasil: "Brasil (Renda Variável)",
  eua: "EUA (Renda Variável)",
  criptomoedas: "Criptomoedas",
  renda_fixa: "Renda Fixa",
  income_calendar: "Calendário de proventos",
  income_monthly: "Histórico mensal de proventos",
};

export const PREVIEW_STATUS_LABELS_PT: Record<string, string> = {
  success: "Sucesso",
  partial: "Parcial",
  failed: "Falhou",
};

export const PREVIEW_STATUS_KIND: Record<string, StatusKind> = {
  success: "positive",
  partial: "attention",
  failed: "critical",
};

export function sectionLabel(section: string): string {
  return SECTION_LABELS_PT[section] ?? section;
}

export function statusLabel(status: string): string {
  return PREVIEW_STATUS_LABELS_PT[status] ?? status;
}

export function statusKind(status: string): StatusKind {
  return PREVIEW_STATUS_KIND[status] ?? "muted";
}

export function formatDecimalBRL(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return formatBRL(Number(value));
}

export function formatDecimalPct(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${(Number(value) * 100).toFixed(2)}%`.replace(".", ",");
}

export function formatQuantity(value: string): string {
  const num = Number(value);
  if (Number.isInteger(num)) return num.toLocaleString("pt-BR");
  return num.toLocaleString("pt-BR", { maximumFractionDigits: 8 });
}

export function formatDateOnly(value: string | null): string {
  if (!value) return "—";
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) return value;
  return `${day}/${month}/${year}`;
}

export function formatMonthYear(month: number, year: number): string {
  const names = [
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
  ];
  return `${names[month - 1] ?? month}/${year}`;
}
