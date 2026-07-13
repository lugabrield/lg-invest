// Dados mockados do Dashboard (Fase 1 — protótipo visual, sem API real
// ainda). O formato aqui é deliberadamente próximo do payload real
// planejado em docs/API_CONTRACT.md (`GET /api/dashboard`) para que a
// troca por dado real na Fase 2 seja só trocar a fonte, não redesenhar
// os componentes.

export type StatusKind = "positive" | "neutral" | "attention" | "critical" | "muted";

export interface KpiMock {
  label: string;
  value: string;
  delta?: string;
  status: StatusKind;
  icon: string;
}

export interface AllocationSliceMock {
  label: string;
  value: number;
  color: string;
}

export interface TopPositionMock {
  ticker: string;
  name: string;
  weight: number;
  returnPct: number;
  classLabel: string;
}

export interface InsightMock {
  title: string;
  message: string;
  severity: StatusKind;
}

export const kpis: KpiMock[] = [
  { label: "Patrimônio total", value: "R$ 487.320,15", delta: "+2,4% no mês", status: "positive", icon: "wallet" },
  { label: "Rentabilidade total", value: "+18,7%", delta: "desde o início", status: "positive", icon: "trending-up" },
  { label: "Exposição internacional", value: "34,2%", delta: "meta: 40%", status: "neutral", icon: "globe" },
  { label: "Maior posição", value: "WEGE3 · 12,8%", status: "attention", icon: "pie-chart" },
  { label: "LG Health Score", value: "82 / 100", delta: "Boa", status: "positive", icon: "heart-pulse" },
];

export const allocationByClass: AllocationSliceMock[] = [
  { label: "Ações BR", value: 32, color: "#8B5CF6" },
  { label: "FIIs", value: 18, color: "#3B82F6" },
  { label: "Ações EUA", value: 22, color: "#38BDF8" },
  { label: "ETFs", value: 12, color: "#22C55E" },
  { label: "Bitcoin", value: 9, color: "#F59E0B" },
  { label: "Tesouro Direto", value: 7, color: "#5B6478" },
];

export const allocationByCurrency: AllocationSliceMock[] = [
  { label: "BRL", value: 65.8, color: "#8B5CF6" },
  { label: "USD", value: 34.2, color: "#3B82F6" },
];

export const brazilVsInternational: AllocationSliceMock[] = [
  { label: "Brasil", value: 65.8, color: "#8B5CF6" },
  { label: "Exterior", value: 34.2, color: "#38BDF8" },
];

export const topPositions: TopPositionMock[] = [
  { ticker: "WEGE3.SA", name: "WEG S.A.", weight: 12.8, returnPct: 34.2, classLabel: "Ação BR" },
  { ticker: "AAPL", name: "Apple Inc.", weight: 9.4, returnPct: 21.6, classLabel: "Ação EUA" },
  { ticker: "HGLG11.SA", name: "CSHG Logística", weight: 7.9, returnPct: 8.1, classLabel: "FII" },
  { ticker: "BTC-USD", name: "Bitcoin", weight: 7.2, returnPct: 61.3, classLabel: "Cripto" },
  { ticker: "VOO", name: "Vanguard S&P 500", weight: 6.5, returnPct: 17.4, classLabel: "ETF" },
];

export const concentrationScore = 68; // 0-100, quanto maior, mais concentrado

export const insights: InsightMock[] = [
  {
    title: "Pontos fortes",
    message: "Carteira bem diversificada entre Brasil e exterior, com boa exposição a ativos de qualidade (WEGE3, AAPL).",
    severity: "positive",
  },
  {
    title: "Atenções",
    message: "WEGE3 já representa 12,8% da carteira — acima do limite configurado de 12% para ativo individual.",
    severity: "attention",
  },
  {
    title: "Oportunidades",
    message: "Exposição internacional está 5,8 p.p. abaixo da meta (40%) — próximo aporte pode priorizar ativos em USD.",
    severity: "neutral",
  },
  {
    title: "Próximo passo",
    message: "Simular um aporte de R$ 2.000 para ver a recomendação do Decision Engine v3 dado o cenário atual.",
    severity: "muted",
  },
];

export const lastUpdated = "há 12 minutos";
export const userName = "Lucas";
