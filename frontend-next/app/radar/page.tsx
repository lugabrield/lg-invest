import { RadarOpportunitySections } from "@/components/radar-opportunity-sections";
import { WatchlistForm } from "@/components/watchlist-form";
import { WatchlistSummary } from "@/components/watchlist-summary";
import { WatchlistTable } from "@/components/watchlist-table";
import { EmptyState, ErrorState } from "@/components/states";
import { TopBar } from "@/components/topbar";
import { ApiError, fetchRadarEvaluation, fetchWatchlist } from "@/lib/api";

// Tela Radar — Fase 7 do plano de migração (docs/V1_1_MIGRATION_PLAN.md).
// Reaproveita `GET /api/watchlist` + `GET /api/radar` (WatchlistService +
// RadarService, inalterados). Nenhum cálculo de score/classificação
// acontece aqui — só apresentação do que a API já devolve. Esta tela
// NUNCA cria uma posição nem altera o patrimônio calculado pelo
// Portfolio Engine: cadastra candidatos e mostra como eles se comparam
// à carteira atual.
export default async function RadarPage() {
  let entries;
  let evaluation;
  try {
    [entries, evaluation] = await Promise.all([fetchWatchlist(), fetchRadarEvaluation()]);
  } catch (error) {
    const message =
      error instanceof ApiError
        ? error.message
        : "Não foi possível carregar o Radar agora. Tente novamente.";
    return (
      <div className="space-y-8 pb-12">
        <TopBar greeting="Radar" lastUpdated="—" showActions={false} />
        <ErrorState message={message} />
      </div>
    );
  }

  const radarByTicker = new Map(evaluation.candidates.map((c) => [c.ticker, c]));

  return (
    <div className="space-y-8 pb-12">
      <TopBar greeting="Radar" lastUpdated="agora" showActions={false} />
      <p className="-mt-6 text-sm text-text-muted">
        Acompanhe ativos que você ainda não tem, sem alterar sua carteira.
      </p>

      <section>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Resumo da Watchlist</h2>
        <WatchlistSummary entries={entries} radarByTicker={radarByTicker} />
      </section>

      <section>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Cadastrar novo candidato</h2>
        <WatchlistForm />
      </section>

      <section>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Ativos na Watchlist</h2>
        {entries.length === 0 ? (
          <EmptyState
            title="Você ainda não acompanha ativos novos"
            message="Use o formulário &quot;Cadastrar novo candidato&quot; acima para começar."
          />
        ) : (
          <WatchlistTable entries={entries} radarByTicker={radarByTicker} />
        )}
      </section>

      <section>
        <h2 className="mb-1 text-sm font-medium text-text-primary">Radar de oportunidades</h2>
        <p className="mb-4 text-xs text-text-faint">
          Compara candidatos da Watchlist e posições atuais com base na estratégia configurada.
        </p>
        {evaluation.candidates.length === 0 ? (
          <EmptyState
            title="Nada para comparar ainda"
            message="Cadastre candidatos na Watchlist ou registre posições na carteira."
          />
        ) : (
          <RadarOpportunitySections candidates={evaluation.candidates} />
        )}
      </section>
    </div>
  );
}
