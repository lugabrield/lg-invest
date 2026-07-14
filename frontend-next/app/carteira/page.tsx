import { AlertTriangle } from "lucide-react";
import { GroupedPositions } from "@/components/grouped-positions";
import { MetricCard } from "@/components/metric-card";
import { PortfolioUpload } from "@/components/portfolio-upload";
import { PositionsTable } from "@/components/positions-table";
import { EmptyState, ErrorState } from "@/components/states";
import { TopBar } from "@/components/topbar";
import { ApiError, fetchDashboard } from "@/lib/api";
import { adaptCarteiraSummary, adaptGroupedPositions } from "@/lib/adapt-carteira";

// Tela Carteira — Fase 4 do plano de migração (docs/V1_1_MIGRATION_PLAN.md).
// A leitura reaproveita `GET /api/dashboard` (mesmo `view.positions` do
// Dashboard) — não existe endpoint próprio de leitura. Só a importação
// de arquivo é nova aqui (`PortfolioUpload`, cliente). Nenhum cálculo
// financeiro acontece nesta tela: tudo já vem pronto da API.
export default async function CarteiraPage() {
  let bundle;
  try {
    bundle = await fetchDashboard();
  } catch (error) {
    const message =
      error instanceof ApiError
        ? error.message
        : "Não foi possível carregar a carteira agora. Tente novamente.";
    return (
      <div className="space-y-8 pb-12">
        <TopBar greeting="Carteira" lastUpdated="—" showActions={false} />
        <ErrorState message={message} />
        <PortfolioUpload />
      </div>
    );
  }

  const { view } = bundle;

  if (view.positions.length === 0) {
    return (
      <div className="space-y-8 pb-12">
        <TopBar greeting="Carteira" lastUpdated="agora" showActions={false} />
        <PortfolioUpload />
        <EmptyState
          title="Carteira vazia"
          message="Importe um arquivo .csv ou .xlsx acima para ver suas posições aqui."
        />
      </div>
    );
  }

  const summary = adaptCarteiraSummary(view);
  const groups = adaptGroupedPositions(view);

  return (
    <div className="space-y-8 pb-12">
      <TopBar greeting="Carteira" lastUpdated="agora" showActions={false} />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Patrimônio total convertido" value={summary.totalConverted} status="positive" icon="wallet" />
        <MetricCard
          label="Brasil (BRL)"
          value={summary.brazilTotal}
          delta={`${summary.brazilCount} posição(ões)`}
          status="neutral"
          icon="pie-chart"
        />
        <MetricCard
          label="Exterior"
          value={summary.internationalTotal}
          delta={`${summary.internationalCount} posição(ões)`}
          status="neutral"
          icon="globe"
        />
        <MetricCard
          label="Maior posição"
          value={summary.largestLabel}
          status={summary.largestIsConcentrated ? "attention" : "neutral"}
          icon="trending-up"
        />
      </section>

      {view.estimated_price_tickers.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-attention/25 bg-attention/[0.06] p-3 text-sm text-text-muted">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-attention" strokeWidth={1.75} />
          <span>
            Preço estimado (não automático) para: {view.estimated_price_tickers.join(", ")}. Atualize manualmente na tela
            Ativos se necessário.
          </span>
        </div>
      )}

      <PortfolioUpload />

      <PositionsTable positions={view.positions} largestTicker={view.largest_position_ticker} />

      <section>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Por classe de ativo</h2>
        <GroupedPositions groups={groups} />
      </section>
    </div>
  );
}
