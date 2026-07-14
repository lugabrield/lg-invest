import { JournalTabs } from "@/components/journal-tabs";
import { EmptyState, ErrorState } from "@/components/states";
import { TopBar } from "@/components/topbar";
import { ApiError, fetchAssets, fetchJournalEntries, fetchTheses } from "@/lib/api";

// Tela Journal — Fase 9 do plano de migração (docs/V1_1_MIGRATION_PLAN.md).
// Espelha `pages_impl/journal.py`: 3 abas (Diário, Teses, Revisões) sobre
// `JournalService`/`ThesisService`, inalterados. Sem ativos cadastrados,
// não há o que registrar — mesmo empty state do Streamlit.
export default async function JournalPage() {
  let assets, entries, theses;
  try {
    [assets, entries, theses] = await Promise.all([
      fetchAssets(),
      fetchJournalEntries(),
      fetchTheses(),
    ]);
  } catch (error) {
    const message =
      error instanceof ApiError
        ? error.message
        : "Não foi possível carregar o Journal agora. Tente novamente.";
    return (
      <div className="space-y-8 pb-12">
        <TopBar greeting="Journal" lastUpdated="—" showActions={false} />
        <ErrorState message={message} />
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      <TopBar greeting="Journal" lastUpdated="agora" showActions={false} />
      <p className="-mt-6 text-sm text-text-muted">
        Memória é vantagem de longo prazo: registre o porquê de cada decisão.
      </p>

      {assets.length === 0 ? (
        <EmptyState
          title="Nenhum ativo cadastrado"
          message="Cadastre ativos antes de registrar teses e entradas de diário."
        />
      ) : (
        <JournalTabs assets={assets} entries={entries} theses={theses} />
      )}
    </div>
  );
}
