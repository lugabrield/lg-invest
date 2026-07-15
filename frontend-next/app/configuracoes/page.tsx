import { ConfiguracoesTabs } from "@/components/configuracoes-tabs";
import { ErrorState } from "@/components/states";
import { TopBar } from "@/components/topbar";
import {
  ApiError,
  fetchAllocationOverview,
  fetchAllocationPresets,
  fetchFxStatus,
  fetchInvestmentPolicy,
  fetchSimpleAllocation,
  fetchSimulationAssumptions,
  fetchSystemInfo,
  fetchTargetAllocationRules,
} from "@/lib/api";

// Tela Configurações — Fase 10 do plano de migração
// (docs/V1_1_MIGRATION_PLAN.md). Espelha `pages_impl/configuracoes.py`:
// 6 abas (Visão geral, Alocação simples, Regras detalhadas, Política de
// investimento, Simulação, Sistema) sobre os serviços já existentes —
// nenhum cálculo novo, tudo lido pronto da API.
export default async function ConfiguracoesPage() {
  let system, fx, simpleAllocation, presets, rules, policy, overview, assumptions;
  try {
    [system, fx, simpleAllocation, presets, rules, policy, overview, assumptions] =
      await Promise.all([
        fetchSystemInfo(),
        fetchFxStatus(),
        fetchSimpleAllocation(),
        fetchAllocationPresets(),
        fetchTargetAllocationRules(),
        fetchInvestmentPolicy(),
        fetchAllocationOverview(),
        fetchSimulationAssumptions(),
      ]);
  } catch (error) {
    const message =
      error instanceof ApiError
        ? error.message
        : "Não foi possível carregar as Configurações agora. Tente novamente.";
    return (
      <div className="space-y-8 pb-12">
        <TopBar greeting="Configurações" lastUpdated="—" showActions={false} />
        <ErrorState message={message} />
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      <TopBar greeting="Configurações" lastUpdated="agora" showActions={false} />
      <p className="-mt-6 text-sm text-text-muted">
        Alocação-alvo, política de investimento, premissas de simulação e ajustes de sistema —
        organizados em 3 camadas com precedência explícita.
      </p>

      <ConfiguracoesTabs
        system={system}
        fx={fx}
        simpleAllocation={simpleAllocation}
        presets={presets}
        rules={rules}
        policy={policy}
        overview={overview}
        assumptions={assumptions}
      />
    </div>
  );
}
