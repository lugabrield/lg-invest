// Formatadores compartilhados de apresentação (v1.1, Fase 3) — extraídos de
// `adapt-dashboard.ts` para não duplicar a mesma conta em `adapt-aporte.ts`.
// Nenhum cálculo financeiro mora aqui, só formatação de número já pronto
// vindo da API (BRL/percentual em pt-BR).

const currencyFormatterBRL = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 2,
});

export function formatBRL(value: number): string {
  return currencyFormatterBRL.format(value);
}

export function formatPct(fraction: number, decimals = 1): string {
  return `${(fraction * 100).toFixed(decimals)}%`.replace(".", ",");
}
