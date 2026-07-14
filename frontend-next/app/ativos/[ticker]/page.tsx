import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { AssetActionsPanel } from "@/components/asset-actions-panel";
import { AssetScorePanel } from "@/components/asset-score-panel";
import { DataCoveragePanel } from "@/components/data-coverage-panel";
import { FundamentalAnalysisPanel } from "@/components/fundamental-analysis-panel";
import { FundamentalsPanel } from "@/components/fundamentals-panel";
import { ErrorState } from "@/components/states";
import { TopBar } from "@/components/topbar";
import { ApiError, fetchAtivoDetail } from "@/lib/api";

// Tela Ativos (detalhe) — Fase 6 do plano de migração (docs/V1_1_MIGRATION_PLAN.md).
// Reaproveita `GET /api/ativos/{ticker}` (LG Score, Conviction Score v2,
// data quality, fundamentos, valuation v1/v2, análise de renda
// imobiliária, adequação à política, trap detection, cobertura de
// dados) — composição pura de cada bloco, nenhum cálculo novo.
export default async function AtivoDetailPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  const decodedTicker = decodeURIComponent(ticker);

  let bundle;
  try {
    bundle = await fetchAtivoDetail(decodedTicker);
  } catch (error) {
    const notFound = error instanceof ApiError && error.status === 404;
    const message = notFound
      ? `Ativo "${decodedTicker}" não encontrado.`
      : error instanceof ApiError
        ? error.message
        : "Não foi possível carregar o ativo agora. Tente novamente.";
    return (
      <div className="space-y-8 pb-12">
        <TopBar greeting={decodedTicker} lastUpdated="—" showActions={false} />
        <ErrorState message={message} />
        <Link href="/ativos" className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline">
          <ArrowLeft className="h-4 w-4" strokeWidth={1.75} />
          Voltar para Ativos
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      <div>
        <Link
          href="/ativos"
          className="mb-3 inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text-primary hover:underline"
        >
          <ArrowLeft className="h-4 w-4" strokeWidth={1.75} />
          Ativos
        </Link>
        <TopBar greeting={`${bundle.ticker} — ${bundle.name}`} lastUpdated="agora" showActions={false} />
        <p className="mt-1 text-xs text-text-faint">
          {bundle.asset_class} · {bundle.currency} · {bundle.is_manual ? "ativo manual" : "preço automático"}
        </p>
      </div>

      <section>
        <h2 className="mb-1 text-sm font-medium text-text-primary">Scores</h2>
        <p className="mb-4 text-xs text-text-faint">
          LG Score é usado pelo Decision Engine. Conviction Score v2 é paralelo, não substitui o LG Score.
        </p>
        <AssetScorePanel lgScore={bundle.lg_score} conviction={bundle.conviction} />
      </section>

      <section>
        <h2 className="mb-1 text-sm font-medium text-text-primary">Fundamentos</h2>
        <FundamentalsPanel
          fundamentals={bundle.fundamentals}
          analysis={bundle.fundamentals_analysis}
          legacyValuation={bundle.legacy_valuation}
        />
      </section>

      <section>
        <h2 className="mb-1 text-sm font-medium text-text-primary">Análise Fundamentalista</h2>
        <FundamentalAnalysisPanel
          valuationV2={bundle.valuation_v2}
          incomeRealEstate={bundle.income_real_estate}
          adequacy={bundle.adequacy}
          trapDetection={bundle.trap_detection}
        />
      </section>

      <section>
        <h2 className="mb-1 text-sm font-medium text-text-primary">Cobertura de Dados</h2>
        <DataCoveragePanel coverage={bundle.coverage} />
      </section>

      <section>
        <h2 className="mb-1 text-sm font-medium text-text-primary">Gerenciar ativo</h2>
        <AssetActionsPanel ticker={bundle.ticker} isManual={bundle.is_manual} />
      </section>
    </div>
  );
}
