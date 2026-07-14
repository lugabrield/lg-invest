import { AporteForm } from "@/components/aporte-form";
import { ErrorState } from "@/components/states";
import { TopBar } from "@/components/topbar";
import { ApiError, fetchAssets } from "@/lib/api";

// Tela Aporte — Fase 3 do plano de migração (docs/V1_1_MIGRATION_PLAN.md):
// busca o universo de ativos no servidor (só para popular o seletor de
// "bloqueados"), e delega a simulação em si a um client component
// (`AporteForm`), já que o fluxo é disparado por um clique do usuário
// ("Gerar recomendação"), não por um GET no carregamento da página.
export default async function AportePage() {
  let assets;
  try {
    assets = await fetchAssets();
  } catch (error) {
    const message =
      error instanceof ApiError
        ? error.message
        : "Não foi possível carregar os ativos agora. Tente novamente.";
    return (
      <div className="space-y-8 pb-12">
        <TopBar greeting="Aporte" lastUpdated="—" showActions={false} />
        <ErrorState message={message} />
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      <TopBar greeting="Aporte" lastUpdated="agora" showActions={false} />
      <AporteForm assets={assets} />
    </div>
  );
}
