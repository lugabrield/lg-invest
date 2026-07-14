// Adaptador puro da Carteira (v1.1, Fase 4): a leitura reaproveita
// integralmente `DashboardBundle.view` (mesmos dados do Dashboard) — só
// reorganiza para o layout da tela Carteira (cards de resumo BR/exterior,
// tabela completa, agrupamento por classe). Nenhum cálculo financeiro
// novo, mesma regra das demais telas já migradas.

import type { ConvertedPosition, DashboardView } from "@/lib/api";
import { formatBRL, formatPct } from "@/lib/format";

// Mesma ordem de `backend/app/services/dashboard_view_service.py::GROUP_ORDER`.
export const GROUP_ORDER = ["Ações BR", "FIIs", "Ações EUA", "ETFs", "REITs", "Cripto", "Renda Fixa"];

const PRICE_SOURCE_LABELS: Record<string, string> = {
  yahoo: "Automático",
  manual: "Manual",
  estimated: "Estimado",
};

export interface CarteiraSummary {
  totalConverted: string;
  brazilTotal: string;
  brazilCount: number;
  internationalTotal: string;
  internationalCount: number;
  largestLabel: string;
  largestIsConcentrated: boolean;
}

export function adaptCarteiraSummary(view: DashboardView): CarteiraSummary {
  const brazilPositions = view.positions.filter((p) => p.currency === "BRL");
  const internationalPositions = view.positions.filter((p) => p.currency !== "BRL");
  const brazilTotal = brazilPositions.reduce((sum, p) => sum + Number(p.position_value_brl), 0);
  const totalConverted = Number(view.total_converted_brl);
  const internationalTotal = totalConverted - brazilTotal;
  const largest = view.positions.find((p) => p.ticker === view.largest_position_ticker);

  return {
    totalConverted: formatBRL(totalConverted),
    brazilTotal: formatBRL(brazilTotal),
    brazilCount: brazilPositions.length,
    internationalTotal: formatBRL(internationalTotal),
    internationalCount: internationalPositions.length,
    largestLabel: largest ? `${largest.ticker} (${formatPct(Number(largest.weight))})` : "—",
    largestIsConcentrated: largest ? Number(largest.weight) >= 0.2 : false,
  };
}

export interface PositionRowView {
  ticker: string;
  isLargest: boolean;
  group: string;
  currency: string;
  quantity: string;
  averagePrice: string;
  currentPrice: string;
  priceSourceLabel: string;
  isNegative: boolean;
  valueOriginal: string;
  valueBRL: string;
  weightPct: string;
  returnPct: string | null;
}

export function adaptPositionRow(position: ConvertedPosition, largestTicker: string | null): PositionRowView {
  const returnPct = position.return_pct !== null ? Number(position.return_pct) : null;
  return {
    ticker: position.ticker,
    isLargest: position.ticker === largestTicker,
    group: position.group_label,
    currency: position.currency,
    quantity: Number(position.quantity).toLocaleString("pt-BR", { maximumFractionDigits: 4 }),
    averagePrice: Number(position.average_price).toLocaleString("pt-BR", { minimumFractionDigits: 2 }),
    currentPrice: Number(position.current_price).toLocaleString("pt-BR", { minimumFractionDigits: 2 }),
    priceSourceLabel: PRICE_SOURCE_LABELS[position.price_source] ?? position.price_source,
    isNegative: returnPct !== null && returnPct < 0,
    valueOriginal: Number(position.position_value).toLocaleString("pt-BR", { minimumFractionDigits: 2 }),
    valueBRL: formatBRL(Number(position.position_value_brl)),
    weightPct: formatPct(Number(position.weight)),
    returnPct: returnPct !== null ? `${returnPct >= 0 ? "+" : ""}${formatPct(returnPct)}` : null,
  };
}

export interface GroupedPositions {
  group: string;
  totalLabel: string;
  negativeCount: number;
  positions: ConvertedPosition[];
}

export function adaptGroupedPositions(view: DashboardView): GroupedPositions[] {
  return GROUP_ORDER.map((group) => {
    const positions = view.positions.filter((p) => p.group_label === group);
    const total = positions.reduce((sum, p) => sum + Number(p.position_value_brl), 0);
    const negativeCount = positions.filter(
      (p) => p.return_pct !== null && Number(p.return_pct) < 0,
    ).length;
    return { group, totalLabel: formatBRL(total), negativeCount, positions };
  }).filter((g) => g.positions.length > 0);
}
