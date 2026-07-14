import { AllocationDriftTable } from "@/components/allocation-drift-table";
import { AssetIntelligenceDetail } from "@/components/asset-intelligence-detail";
import { ConvictionBuckets } from "@/components/conviction-buckets";
import { RankingColumn } from "@/components/conviction-rankings";
import { IncomeSummary } from "@/components/income-summary";
import { MetricCard } from "@/components/metric-card";
import { EmptyState, ErrorState } from "@/components/states";
import { TopBar } from "@/components/topbar";
import { ApiError, fetchIntelligence } from "@/lib/api";
import { adaptIntelligenceSummary, bucketAssets, rankBy } from "@/lib/adapt-intelligence";

// Tela Inteligência — Fase 5 do plano de migração (docs/V1_1_MIGRATION_PLAN.md).
// Reaproveita `GET /api/intelligence` (Conviction Score v2 + alocação-alvo
// + renda de proventos, mesma composição de `cached_intelligence_bundle`
// no Streamlit). Nenhum cálculo financeiro acontece aqui.
export default async function InteligenciaPage() {
  let bundle;
  try {
    bundle = await fetchIntelligence();
  } catch (error) {
    const message =
      error instanceof ApiError
        ? error.message
        : "Não foi possível carregar a inteligência agora. Tente novamente.";
    return (
      <div className="space-y-8 pb-12">
        <TopBar greeting="Inteligência" lastUpdated="—" showActions={false} />
        <ErrorState message={message} />
      </div>
    );
  }

  const { view, income } = bundle;

  if (view.assets.length === 0) {
    return (
      <div className="space-y-8 pb-12">
        <TopBar greeting="Inteligência" lastUpdated="agora" showActions={false} />
        <EmptyState
          title="Carteira vazia"
          message="Importe posições na tela Carteira para ver a análise de convicção por ativo."
        />
      </div>
    );
  }

  const summary = adaptIntelligenceSummary(view);
  const buckets = bucketAssets(view.assets);

  return (
    <div className="space-y-8 pb-12">
      <TopBar greeting="Inteligência" lastUpdated="agora" showActions={false} />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Conviction Score médio" value={summary.averageScore} status="neutral" icon="heart-pulse" />
        <MetricCard label="Cobertura do score" value={summary.coveragePct} status="neutral" icon="pie-chart" />
        <MetricCard label="Maior convicção" value={summary.mostConvictedLabel} status="positive" icon="trending-up" />
        <MetricCard label="Menor convicção" value={summary.leastConvictedLabel} status="attention" icon="trending-up" />
      </section>
      {summary.hasLowCoverage && (
        <p className="text-xs text-text-faint">
          Ativos sem histórico de preço suficiente ficam de fora da cobertura acima — veja o motivo em &quot;Dados
          insuficientes&quot; abaixo, nunca é um score inventado.
        </p>
      )}

      <section>
        <h2 className="mb-1 text-sm font-medium text-text-primary">Classificação da carteira</h2>
        <p className="mb-3 text-xs text-text-faint">Mesma classificação usada pelo Decision Engine na tela Aporte.</p>
        <ConvictionBuckets buckets={buckets} />
      </section>

      <section>
        <h2 className="mb-1 text-sm font-medium text-text-primary">Rankings por dimensão</h2>
        <p className="mb-4 text-xs text-text-faint">
          Cripto, ETF e renda fixa não entram nos rankings de valuation/qualidade/crescimento — para essas classes
          essas dimensões não são medidas reais. Ativos com dados insuficientes também ficam de fora.
        </p>
        <div className="grid grid-cols-1 gap-6 rounded-card border border-border bg-surface p-5 shadow-card sm:grid-cols-3">
          <RankingColumn
            title="Mais baratos (valuation)"
            caption="Nota alta = 'barato' na classificação de múltiplos. Só ações, FIIs e REITs."
            assets={rankBy(view.assets, "valuation", { reverse: true })}
            valueLabel="valuation"
            value={(a) => a.valuation}
          />
          <RankingColumn
            title="Maior qualidade"
            caption="Só ações e REITs."
            assets={rankBy(view.assets, "quality", { reverse: true })}
            valueLabel="qualidade"
            value={(a) => a.quality}
          />
          <RankingColumn
            title="Maior crescimento"
            caption="Só ações e REITs."
            assets={rankBy(view.assets, "growth", { reverse: true })}
            valueLabel="crescimento"
            value={(a) => a.growth}
          />
        </div>
        <div className="mt-4 grid grid-cols-1 gap-6 rounded-card border border-border bg-surface p-5 shadow-card sm:grid-cols-2">
          <RankingColumn
            title="Mais caros (evitar aporte por valuation)"
            assets={rankBy(view.assets, "valuation", { reverse: false })}
            valueLabel="valuation"
            value={(a) => a.valuation}
          />
          <RankingColumn
            title="Maior risco"
            assets={rankBy(view.assets, "risk", { reverse: false })}
            valueLabel="risco (nota baixa = risco alto)"
            value={(a) => a.risk}
          />
        </div>
      </section>

      <section>
        <h2 className="mb-1 text-sm font-medium text-text-primary">Por que esse ativo?</h2>
        <p className="mb-4 text-xs text-text-faint">Diagnóstico completo por ativo selecionado.</p>
        <AssetIntelligenceDetail assets={view.assets} />
      </section>

      <section>
        <h2 className="mb-1 text-sm font-medium text-text-primary">Alocação-alvo por classe</h2>
        <p className="mb-4 text-xs text-text-faint">Configurada em Configurações. Sem meta, nenhum desvio é mostrado.</p>
        <AllocationDriftTable drift={view.allocation_drift} />
      </section>

      <section>
        <h2 className="mb-1 text-sm font-medium text-text-primary">Renda de Proventos</h2>
        <p className="mb-4 text-xs text-text-faint">
          Tendência agregada e renda por ativo vêm de fontes diferentes e nunca são somadas entre si.
        </p>
        <IncomeSummary income={income} />
      </section>
    </div>
  );
}
