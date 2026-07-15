// Tipos de apresentação compartilhados do Dashboard (v1.1). Nasceu na
// Fase 1 como protótipo visual com dados mockados; desde a Fase 2 os
// dados reais vêm de `GET /api/dashboard` via `lib/adapt-dashboard.ts`
// — este arquivo ficou só com as interfaces/tipos (`StatusKind`,
// `KpiMock`, `AllocationSliceMock`, `TopPositionMock`, `InsightMock`),
// reusadas por `adapt-dashboard.ts` e pelos componentes de
// apresentação (AlertCard, DonutChartCard, AssetTable, MetricCard,
// ProgressBar, RecommendationCard, StatusBadge, DataCoveragePanel).
// Nenhum dado mockado é importado ou renderizado em nenhuma tela —
// confirmado na auditoria de RC da v1.1.

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
