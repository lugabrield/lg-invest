import { AlertCard } from "@/components/alert-card";
import { AssetTable } from "@/components/asset-table";
import { DonutChartCard } from "@/components/donut-chart-card";
import { MetricCard } from "@/components/metric-card";
import { PortfolioGauge, ProgressBar } from "@/components/progress-bar";
import { TopBar } from "@/components/topbar";
import {
  allocationByClass,
  allocationByCurrency,
  brazilVsInternational,
  concentrationScore,
  insights,
  kpis,
  lastUpdated,
  topPositions,
  userName,
} from "@/lib/mock/dashboard";

// Dashboard premium — Fase 1 do plano de migração (docs/V1_1_MIGRATION_PLAN.md):
// só visual, com dados mockados (lib/mock/dashboard.ts). Nenhum cálculo
// acontece aqui — quando a Fase 2 ligar em `GET /api/dashboard`, esses
// mesmos componentes passam a receber dado real, sem redesenho.
export default function DashboardPage() {
  return (
    <div className="space-y-8 pb-12">
      <TopBar greeting={`Bem-vindo de volta, ${userName}`} lastUpdated={lastUpdated} />

      {/* Cards principais */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {kpis.map((kpi) => (
          <MetricCard key={kpi.label} {...kpi} />
        ))}
      </section>

      {/* Gráficos de composição */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <DonutChartCard title="Alocação por classe" description="Composição atual da carteira" data={allocationByClass} />
        <DonutChartCard title="Alocação por moeda" description="BRL vs. USD" data={allocationByCurrency} />
        <DonutChartCard title="Brasil vs. exterior" description="Meta de exposição internacional: 40%" data={brazilVsInternational} />
      </section>

      {/* Top posições + Health Score */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <AssetTable positions={topPositions} />
        </div>
        <div className="space-y-4">
          <PortfolioGauge value={82} label="LG Health Score" />
          <div className="rounded-card border border-border bg-surface p-5 shadow-card">
            <ProgressBar value={concentrationScore} status="attention" label="Concentração da carteira" />
            <p className="mt-3 text-xs text-text-muted">
              Quanto maior, mais concentrada em poucos ativos — hoje puxada por WEGE3.SA (12,8% da carteira).
            </p>
          </div>
        </div>
      </section>

      {/* Diagnóstico da carteira */}
      <section>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Diagnóstico da carteira</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {insights.map((insight) => (
            <AlertCard key={insight.title} title={insight.title} message={insight.message} severity={insight.severity} />
          ))}
        </div>
      </section>
    </div>
  );
}
