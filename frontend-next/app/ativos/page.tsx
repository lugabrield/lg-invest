import { AssetListTable } from "@/components/asset-list-table";
import { FundamentalsBatchCollectButton } from "@/components/fundamentals-batch-collect-button";
import { FundamentalsImportPanel } from "@/components/fundamentals-import-panel";
import { EmptyState, ErrorState } from "@/components/states";
import { TopBar } from "@/components/topbar";
import { ApiError, fetchAtivos } from "@/lib/api";

// Tela Ativos (lista) — Fase 6 do plano de migração (docs/V1_1_MIGRATION_PLAN.md).
// Reaproveita `GET /api/ativos`. Nenhum cálculo acontece aqui — cada linha
// já vem com preço/status resolvidos pela API.
export default async function AtivosPage() {
  let rows;
  try {
    rows = await fetchAtivos();
  } catch (error) {
    const message =
      error instanceof ApiError
        ? error.message
        : "Não foi possível carregar os ativos agora. Tente novamente.";
    return (
      <div className="space-y-8 pb-12">
        <TopBar greeting="Ativos" lastUpdated="—" showActions={false} />
        <ErrorState message={message} />
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      <TopBar greeting="Ativos" lastUpdated="agora" showActions={false} />

      {rows.length === 0 ? (
        <EmptyState
          title="Nenhum ativo cadastrado"
          message="Importe posições na tela Carteira para ver os ativos aqui."
        />
      ) : (
        <section>
          <h2 className="mb-1 text-sm font-medium text-text-primary">Ativos cadastrados</h2>
          <p className="mb-4 text-xs text-text-faint">
            Clique em um ticker para ver LG Score, Conviction Score, fundamentos e análise fundamentalista completa.
          </p>
          <AssetListTable rows={rows} />
        </section>
      )}

      <section>
        <h2 className="mb-1 text-sm font-medium text-text-primary">Dados de fundamentos</h2>
        <p className="mb-4 text-xs text-text-faint">
          Coleta automática via Yahoo Finance ou importação manual por CSV/Excel.
        </p>
        <div className="space-y-4">
          <FundamentalsBatchCollectButton />
          <FundamentalsImportPanel />
        </div>
      </section>
    </div>
  );
}
