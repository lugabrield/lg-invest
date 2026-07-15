"use client";

import { useState } from "react";
import type {
  AllocationOverviewView,
  AllocationPresetView,
  FxStatusView,
  InvestmentPolicyView,
  SimpleAllocationView,
  SimulationAssumptionsView,
  SystemInfoView,
  TargetAllocationRuleView,
} from "@/lib/api";
import { ConfiguracoesOverviewPanel } from "@/components/configuracoes-overview-panel";
import { ConfiguracoesSimpleAllocationPanel } from "@/components/configuracoes-simple-allocation-panel";
import { ConfiguracoesRulesPanel } from "@/components/configuracoes-rules-panel";
import { ConfiguracoesPolicyPanel } from "@/components/configuracoes-policy-panel";
import { ConfiguracoesSimulationAssumptionsPanel } from "@/components/configuracoes-simulation-assumptions-panel";
import { ConfiguracoesSystemPanel } from "@/components/configuracoes-system-panel";
import { cn } from "@/lib/utils";

interface ConfiguracoesTabsProps {
  system: SystemInfoView;
  fx: FxStatusView;
  simpleAllocation: SimpleAllocationView;
  presets: AllocationPresetView[];
  rules: TargetAllocationRuleView[];
  policy: InvestmentPolicyView;
  overview: AllocationOverviewView;
  assumptions: SimulationAssumptionsView;
}

const TABS = [
  { key: "visao-geral", label: "Visão geral" },
  { key: "alocacao-simples", label: "Alocação simples" },
  { key: "regras", label: "Regras detalhadas" },
  { key: "politica", label: "Política de investimento" },
  { key: "simulacao", label: "Simulação" },
  { key: "sistema", label: "Sistema" },
] as const;

/** ConfiguracoesTabs — mesmas 6 abas de `pages_impl/configuracoes.py`
 * (🎯 Visão geral, 📐 Alocação simples, 🧩 Regras detalhadas, 🧭 Política
 * de investimento, 🎲 Simulação, ⚙️ Sistema). Dados vêm do servidor
 * (`app/configuracoes/page.tsx`) e cada painel dispara
 * `router.refresh()` após uma mutação. */
export function ConfiguracoesTabs({
  system,
  fx,
  simpleAllocation,
  presets,
  rules,
  policy,
  overview,
  assumptions,
}: ConfiguracoesTabsProps) {
  const [active, setActive] = useState<(typeof TABS)[number]["key"]>("visao-geral");

  return (
    <div>
      <div className="mb-6 flex flex-wrap gap-1.5 border-b border-border-soft">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActive(tab.key)}
            className={cn(
              "border-b-2 px-3.5 py-2 text-sm font-medium transition-colors",
              active === tab.key
                ? "border-primary text-text-primary"
                : "border-transparent text-text-muted hover:text-text-primary",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {active === "visao-geral" && <ConfiguracoesOverviewPanel overview={overview} />}
      {active === "alocacao-simples" && (
        <ConfiguracoesSimpleAllocationPanel allocation={simpleAllocation} presets={presets} />
      )}
      {active === "regras" && <ConfiguracoesRulesPanel rules={rules} />}
      {active === "politica" && <ConfiguracoesPolicyPanel policy={policy} />}
      {active === "simulacao" && (
        <ConfiguracoesSimulationAssumptionsPanel assumptions={assumptions} />
      )}
      {active === "sistema" && <ConfiguracoesSystemPanel system={system} fx={fx} />}
    </div>
  );
}
