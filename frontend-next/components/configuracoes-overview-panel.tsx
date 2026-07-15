"use client";

import type { AllocationOverviewView } from "@/lib/api";
import {
  CONFLICT_KIND_LABELS_PT,
  DIMENSION_TYPE_LABELS_PT,
  EFFECTIVE_LIMIT_SOURCE_LABELS_PT,
  conflictSeverity,
  formatPct,
} from "@/lib/adapt-configuracoes";
import { AlertCard } from "@/components/alert-card";
import { EmptyState } from "@/components/states";

interface ConfiguracoesOverviewPanelProps {
  overview: AllocationOverviewView;
}

/** ConfiguracoesOverviewPanel — aba "Visão geral" (v1.1, Fase 10).
 * Espelha `_render_allocation_overview_intro` + `_render_effective_limits_and_conflicts`:
 * explica a precedência (regra detalhada > política geral > nenhum
 * limite) e mostra o limite EFETIVO de cada dimensão + conflitos
 * detectados entre as 3 camadas. Cálculo já vem pronto de
 * `GET /api/configuracoes/visao-geral` — nada é recalculado aqui. */
export function ConfiguracoesOverviewPanel({ overview }: ConfiguracoesOverviewPanelProps) {
  return (
    <div className="space-y-6">
      <AlertCard
        title="Como funcionam as 3 camadas"
        message="Alocação simples (Camada 1) define metas por classe. Regras detalhadas (Camada 2) refinam por moeda, país ou ativo específico. Política de investimento (Camada 3) define limites gerais. Quando uma regra detalhada e a política geral definem limites para a mesma dimensão, a regra detalhada tem precedência — a política geral só vale onde não há regra específica."
        severity="neutral"
      />

      <div>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Limites efetivos</h2>
        {overview.effective_limits.length === 0 ? (
          <EmptyState
            title="Nenhum limite configurado"
            message="Configure a alocação simples, regras detalhadas ou a política de investimento para ver os limites efetivos aqui."
          />
        ) : (
          <div className="rounded-card border border-border bg-surface shadow-card">
            <div className="scrollbar-thin overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-soft text-left text-xs text-text-faint">
                    <th className="px-4 py-2.5 font-medium">Dimensão</th>
                    <th className="px-4 py-2.5 font-medium">Chave</th>
                    <th className="px-4 py-2.5 font-medium">Limite máximo</th>
                    <th className="px-4 py-2.5 font-medium">Origem</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.effective_limits.map((limit) => (
                    <tr
                      key={`${limit.dimension_type}-${limit.dimension_key}`}
                      className="border-b border-border-soft/60 last:border-0"
                    >
                      <td className="px-4 py-3 text-text-muted">
                        {DIMENSION_TYPE_LABELS_PT[limit.dimension_type] ?? limit.dimension_type}
                      </td>
                      <td className="px-4 py-3 font-medium text-text-primary">{limit.dimension_key}</td>
                      <td className="px-4 py-3 text-text-primary">{formatPct(limit.max_weight)}</td>
                      <td className="px-4 py-3 text-text-faint">
                        {EFFECTIVE_LIMIT_SOURCE_LABELS_PT[limit.source] ?? limit.source}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <div>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Conflitos detectados</h2>
        {overview.conflicts.length === 0 ? (
          <AlertCard
            title="Nenhum conflito"
            message="As 3 camadas estão consistentes entre si."
            severity="positive"
          />
        ) : (
          <div className="space-y-3">
            {overview.conflicts.map((conflict, idx) => (
              <AlertCard
                key={`${conflict.kind}-${idx}`}
                title={CONFLICT_KIND_LABELS_PT[conflict.kind] ?? conflict.kind}
                message={conflict.message}
                severity={conflictSeverity()}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
