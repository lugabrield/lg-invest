"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, RotateCcw, Save } from "lucide-react";
import type { SimulationAssumptionsView } from "@/lib/api";
import { ApiError, resetSimulationAssumption, setSimulationAssumption } from "@/lib/api";
import { formatPct } from "@/lib/adapt-configuracoes";
import { cn } from "@/lib/utils";

interface ConfiguracoesSimulationAssumptionsPanelProps {
  assumptions: SimulationAssumptionsView;
}

/** ConfiguracoesSimulationAssumptionsPanel — aba "Simulação" (v1.1,
 * Fase 10). Espelha `_render_simulation_assumptions_section`: tabela
 * das premissas de retorno/volatilidade em uso por classe (com a
 * origem — default do sistema ou ajustado pelo usuário), formulário
 * de edição por classe e botão de reset individual (2 passos, como no
 * Streamlit). Estas premissas alimentam SOMENTE o Simulation Engine —
 * nunca o Decision Engine ou o LG Score. */
export function ConfiguracoesSimulationAssumptionsPanel({
  assumptions,
}: ConfiguracoesSimulationAssumptionsPanelProps) {
  const router = useRouter();
  const [selectedClass, setSelectedClass] = useState(assumptions.assumptions[0]?.asset_class ?? "");
  const [expectedReturn, setExpectedReturn] = useState(
    assumptions.assumptions[0] ? String(Number(assumptions.assumptions[0].expected_return) * 100) : "0",
  );
  const [volatility, setVolatility] = useState(
    assumptions.assumptions[0] ? String(Number(assumptions.assumptions[0].volatility) * 100) : "0",
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState<string | null>(null);

  function handleSelectClass(assetClass: string) {
    setSelectedClass(assetClass);
    const found = assumptions.assumptions.find((a) => a.asset_class === assetClass);
    if (found) {
      setExpectedReturn(String(Number(found.expected_return) * 100));
      setVolatility(String(Number(found.volatility) * 100));
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await setSimulationAssumption({
        asset_class: selectedClass,
        expected_return: String((Number(expectedReturn) || 0) / 100),
        volatility: String((Number(volatility) || 0) / 100),
      });
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar a premissa agora.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleReset(assetClass: string) {
    if (confirmReset !== assetClass) {
      setConfirmReset(assetClass);
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await resetSimulationAssumption(assetClass);
      setConfirmReset(null);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível resetar a premissa agora.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-card border border-border bg-surface-hover p-4 text-sm text-text-muted">
        {assumptions.disclaimer}
      </div>

      <div className="rounded-card border border-border bg-surface shadow-card">
        <div className="scrollbar-thin overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-soft text-left text-xs text-text-faint">
                <th className="px-4 py-2.5 font-medium">Classe</th>
                <th className="px-4 py-2.5 font-medium">Retorno esperado</th>
                <th className="px-4 py-2.5 font-medium">Volatilidade</th>
                <th className="px-4 py-2.5 font-medium">Origem</th>
                <th className="px-4 py-2.5 font-medium" />
              </tr>
            </thead>
            <tbody>
              {assumptions.assumptions.map((assumption) => (
                <tr key={assumption.asset_class} className="border-b border-border-soft/60 last:border-0">
                  <td className="px-4 py-3 font-medium text-text-primary">{assumption.asset_class}</td>
                  <td className="px-4 py-3 text-text-muted">{formatPct(assumption.expected_return)}</td>
                  <td className="px-4 py-3 text-text-muted">{formatPct(assumption.volatility)}</td>
                  <td className="px-4 py-3 text-text-faint">{assumption.source}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => handleReset(assumption.asset_class)}
                      disabled={isSubmitting}
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-40",
                        confirmReset === assumption.asset_class
                          ? "border-attention/40 bg-attention/[0.06] text-attention"
                          : "border-border text-text-muted hover:bg-surface-hover",
                      )}
                    >
                      <RotateCcw className="h-3.5 w-3.5" strokeWidth={1.75} />
                      {confirmReset === assumption.asset_class ? "Confirmar reset" : "Resetar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Ajustar premissa de uma classe</h2>
        <form
          onSubmit={handleSubmit}
          className="space-y-3 rounded-card border border-border bg-surface p-5 shadow-card"
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs text-text-muted">Classe</label>
              <select
                value={selectedClass}
                onChange={(e) => handleSelectClass(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              >
                {assumptions.assumptions.map((a) => (
                  <option key={a.asset_class} value={a.asset_class}>
                    {a.asset_class}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Retorno esperado (% a.a.)</label>
              <input
                type="number"
                step="0.1"
                value={expectedReturn}
                onChange={(e) => setExpectedReturn(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Volatilidade (% a.a.)</label>
              <input
                type="number"
                step="0.1"
                value={volatility}
                onChange={(e) => setVolatility(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              />
            </div>
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-critical/25 bg-critical/[0.06] p-3 text-sm text-text-muted">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-critical" strokeWidth={1.75} />
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg bg-gradient-primary px-3.5 py-2 text-sm font-medium text-white shadow-glow transition-opacity hover:opacity-90",
              isSubmitting && "opacity-60",
            )}
          >
            <Save className="h-4 w-4" strokeWidth={1.75} />
            Salvar premissa
          </button>
        </form>
      </div>
    </div>
  );
}
