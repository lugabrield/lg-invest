import { AlertCard } from "@/components/alert-card";
import { AssetTable } from "@/components/asset-table";
import { DonutChartCard } from "@/components/donut-chart-card";
import { MetricCard } from "@/components/metric-card";
import { PortfolioGauge, ProgressBar } from "@/components/progress-bar";
import { EmptyState, ErrorState } from "@/components/states";
import { TopBar } from "@/components/topbar";
import { ApiError, fetchDashboard } from "@/lib/api";
import {
  adaptAllocationByClass,
  adaptAllocationByCurrency,
  adaptBrazilVsInternational,
  adaptConcentrationScore,
  adaptHealthScore,
  adaptInsights,
  adaptKpis,
  adaptTopPositions,
} from "@/lib/adapt-dashboard";

// Dashboard premium — Fase 2 do plano de migração (docs/V1_1_MIGRATION_PLAN.md):
// dado real de `GET /api/dashboard`, com os mesmos componentes visuais
// validados na Fase 1 (só trocamos a fonte — nenhum redesenho). Nenhum
// cálculo financeiro acontece aqui: a API já devolve tudo pronto
// (`lib/api.ts` + `lib/adapt-dashboard.ts` só formatam para o shape que os
// componentes esperam).
export default async function DashboardPage() {
  let bundle;
  try {
    bundle = await fetchDashboard();
  } catch (error) {
    const message =
      error instanceof ApiError
        ? error.message
        : "Não foi possível carregar o dashboard agora. Tente novamente.";
    return (
      <div className="space-y-8 pb-12">
        <TopBar greeting="Bem-vindo de volta" lastUpdated="—" />
        <ErrorState message={message} />
      </div>
    );
  }

  if (bundle.view.positions.length === 0) {
    return (
      <div className="space-y-8 pb-12">
        <TopBar greeting="Bem-vindo de volta" lastUpdated="agora" />
        <EmptyState
          title="Carteira vazia"
          message="Importe posições na tela Carteira para ver o dashboard completo."
        />
      </div>
    );
  }

  const kpis = adaptKpis(bundle);
  const allocationByClass = adaptAllocationByClass(bundle);
  const allocationByCurrency = adaptAllocationByCurrency(bundle);
  const brazilVsInternational = adaptBrazilVsInternational(bundle);
  const topPositions = adaptTopPositions(bundle);
  const insights = adaptInsights(bundle);
  const concentrationScore = adaptConcentrationScore(bundle);
  const healthScore = adaptHealthScore(bundle);
  const largestTicker = bundle.view.largest_position_ticker ?? "—";

  return (
    <div className="space-y-8 pb-12">
      <TopBar greeting="Bem-vindo de volta" lastUpdated="agora" />

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
        <DonutChartCard title="Brasil vs. exterior" description="Exposição por região" data={brazilVsInternational} />
      </section>

      {/* Top posições + Health Score */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <AssetTable positions={topPositions} />
        </div>
        <div className="space-y-4">
          <PortfolioGauge value={healthScore} label="LG Health Score" />
          <div className="rounded-card border border-border bg-surface p-5 shadow-card">
            <ProgressBar value={concentrationScore} status="attention" label="Concentração da carteira" />
            <p className="mt-3 text-xs text-text-muted">
              Quanto maior, mais concentrada em poucos ativos — hoje puxada por {largestTicker}.
            </p>
          </div>
        </div>
      </section>

      {/* Diagnóstico da carteira */}
      {insights.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-medium text-text-primary">Diagnóstico da carteira</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {insights.map((insight) => (
              <AlertCard key={insight.title} title={insight.title} message={insight.message} severity={insight.severity} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
