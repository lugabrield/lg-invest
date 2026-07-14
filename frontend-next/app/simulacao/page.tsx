import { SimulacaoForm } from "@/components/simulacao-form";
import { TopBar } from "@/components/topbar";

// Tela Simulação — Fase 8 do plano de migração (docs/V1_1_MIGRATION_PLAN.md).
// Espelha `frontend/streamlit_app/pages_impl/simulacao.py`: nenhum GET
// dispara a simulação no carregamento da página (o Monte Carlo é caro
// e não é cacheável entre requests), então toda a tela é delegada a um
// client component (`SimulacaoForm`) que só chama `POST /api/simulacao`
// quando o usuário clica em "Rodar simulação" — igual ao gate do botão
// no Streamlit.
export default function SimulacaoPage() {
  return (
    <div className="space-y-8 pb-12">
      <TopBar greeting="Simulação" lastUpdated="—" showActions={false} />
      <SimulacaoForm />
    </div>
  );
}
