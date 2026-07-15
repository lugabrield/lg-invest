import { DividendosMePanel } from "@/components/dividendos-me-panel";
import { DividendosMeStatusCard } from "@/components/dividendos-me-status-card";
import { ErrorState } from "@/components/states";
import { TopBar } from "@/components/topbar";
import { ApiError, fetchDividendosMeStatus } from "@/lib/api";

// Tela Sincronizar Dividendos.me — Fase 11, última fase do plano de
// migração (docs/V1_1_MIGRATION_PLAN.md). Espelha
// `pages_impl/sincronizar_dividendos_me.py`, com uma mudança de
// arquitetura desenhada em docs/DIVIDENDOS_ME_FRONT_SYNC.md: em vez de
// credenciais em `.env`/`st.secrets`, o usuário digita e-mail/senha
// nesta própria tela a cada sincronização — nunca persistidos em
// nenhum storage do navegador, nunca salvos no backend.
const PORTFOLIO_ID = 1;

export default async function DividendosMePage() {
  let status;
  try {
    status = await fetchDividendosMeStatus(PORTFOLIO_ID);
  } catch (error) {
    const message =
      error instanceof ApiError
        ? error.message
        : "Não foi possível carregar o status da integração agora. Tente novamente.";
    return (
      <div className="space-y-8 pb-12">
        <TopBar greeting="Sincronizar Dividendos.me" lastUpdated="—" showActions={false} />
        <ErrorState message={message} />
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      <TopBar greeting="Sincronizar Dividendos.me" lastUpdated="agora" showActions={false} />
      <p className="-mt-6 text-sm text-text-muted">
        Dividendos.me é a fonte oficial das suas posições reais. A LG INVEST continua sendo a
        camada de análise (LG Conviction Score, decisões, projeções) — esta tela só traz as
        posições atualizadas para a carteira consolidada (portfolio_id {PORTFOLIO_ID}).
      </p>

      <DividendosMeStatusCard status={status} />

      <DividendosMePanel status={status} portfolioId={PORTFOLIO_ID} />
    </div>
  );
}
