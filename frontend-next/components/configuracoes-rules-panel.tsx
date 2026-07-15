"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Plus, Trash2 } from "lucide-react";
import type { TargetAllocationRuleView } from "@/lib/api";
import { ApiError, deleteTargetAllocationRule, upsertTargetAllocationRule } from "@/lib/api";
import {
  DIMENSION_TYPE_LABELS_PT,
  QUICK_RULE_PRESETS,
  TARGET_ALLOCATION_DIMENSIONS,
  formatPctOrDash,
} from "@/lib/adapt-configuracoes";
import { EmptyState } from "@/components/states";
import { cn } from "@/lib/utils";

interface ConfiguracoesRulesPanelProps {
  rules: TargetAllocationRuleView[];
}

const EMPTY_FORM = {
  dimension_type: "class" as string,
  dimension_key: "",
  min_weight: "",
  target_weight: "",
  max_weight: "",
  priority: "0",
};

/** ConfiguracoesRulesPanel — aba "Regras detalhadas" (Camada 2, v1.1,
 * Fase 10). Espelha `_render_target_allocation_rules_section`: tabela
 * agrupada por dimensão, atalhos de preset rápido (`QUICK_RULE_PRESETS`)
 * e formulário de adicionar/editar. Remoção usa confirmação de 2
 * passos, como no Streamlit. Validação (min <= target <= max) é feita
 * inteiramente pela API — aqui só se repassa o `ValueError` como 422. */
export function ConfiguracoesRulesPanel({ rules }: ConfiguracoesRulesPanelProps) {
  const router = useRouter();
  const [form, setForm] = useState(EMPTY_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  function applyQuickPreset(dimensionType: string, dimensionKey: string) {
    setForm((prev) => ({ ...prev, dimension_type: dimensionType, dimension_key: dimensionKey }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.dimension_key.trim()) {
      setError("Informe a chave da dimensão (ex.: USD, fii, BTC-USD).");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await upsertTargetAllocationRule({
        dimension_type: form.dimension_type,
        dimension_key: form.dimension_key.trim(),
        min_weight: form.min_weight ? String(Number(form.min_weight) / 100) : null,
        target_weight: form.target_weight ? String(Number(form.target_weight) / 100) : null,
        max_weight: form.max_weight ? String(Number(form.max_weight) / 100) : null,
        priority: Number(form.priority) || 0,
      });
      setForm(EMPTY_FORM);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar a regra agora.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete(dimensionType: string, dimensionKey: string) {
    const id = `${dimensionType}:${dimensionKey}`;
    if (confirmDelete !== id) {
      setConfirmDelete(id);
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await deleteTargetAllocationRule(dimensionType, dimensionKey);
      setConfirmDelete(null);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível remover a regra agora.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const grouped = TARGET_ALLOCATION_DIMENSIONS.map((dim) => ({
    dimension: dim,
    rules: rules.filter((r) => r.dimension_type === dim),
  })).filter((group) => group.rules.length > 0);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Regras cadastradas</h2>
        {rules.length === 0 ? (
          <EmptyState
            title="Nenhuma regra detalhada"
            message="Adicione regras por moeda, país ou ativo específico usando o formulário abaixo."
          />
        ) : (
          <div className="space-y-4">
            {grouped.map((group) => (
              <div key={group.dimension} className="rounded-card border border-border bg-surface shadow-card">
                <div className="border-b border-border-soft px-4 py-2.5 text-xs font-medium text-text-faint">
                  {DIMENSION_TYPE_LABELS_PT[group.dimension] ?? group.dimension}
                </div>
                <div className="scrollbar-thin overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border-soft text-left text-xs text-text-faint">
                        <th className="px-4 py-2 font-medium">Chave</th>
                        <th className="px-4 py-2 font-medium">Mín.</th>
                        <th className="px-4 py-2 font-medium">Alvo</th>
                        <th className="px-4 py-2 font-medium">Máx.</th>
                        <th className="px-4 py-2 font-medium">Prioridade</th>
                        <th className="px-4 py-2 font-medium" />
                      </tr>
                    </thead>
                    <tbody>
                      {group.rules.map((rule) => {
                        const id = `${rule.dimension_type}:${rule.dimension_key}`;
                        return (
                          <tr key={id} className="border-b border-border-soft/60 last:border-0">
                            <td className="px-4 py-2.5 font-medium text-text-primary">{rule.dimension_key}</td>
                            <td className="px-4 py-2.5 text-text-muted">{formatPctOrDash(rule.min_weight)}</td>
                            <td className="px-4 py-2.5 text-text-muted">{formatPctOrDash(rule.target_weight)}</td>
                            <td className="px-4 py-2.5 text-text-muted">{formatPctOrDash(rule.max_weight)}</td>
                            <td className="px-4 py-2.5 text-text-faint">{rule.priority}</td>
                            <td className="px-4 py-2.5 text-right">
                              <button
                                type="button"
                                onClick={() => handleDelete(rule.dimension_type, rule.dimension_key)}
                                disabled={isSubmitting}
                                className={cn(
                                  "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-40",
                                  confirmDelete === id
                                    ? "border-critical/40 bg-critical/[0.06] text-critical"
                                    : "border-border text-text-muted hover:bg-surface-hover",
                                )}
                              >
                                <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
                                {confirmDelete === id ? "Confirmar" : "Remover"}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Adicionar / editar regra</h2>

        <div className="mb-3 flex flex-wrap gap-2">
          {QUICK_RULE_PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => applyQuickPreset(preset.dimensionType, preset.dimensionKey)}
              className="rounded-full border border-border bg-surface px-3 py-1 text-xs text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary"
            >
              {preset.label}
            </button>
          ))}
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-3 rounded-card border border-border bg-surface p-5 shadow-card"
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs text-text-muted">Dimensão</label>
              <select
                value={form.dimension_type}
                onChange={(e) => setForm((prev) => ({ ...prev, dimension_type: e.target.value }))}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              >
                {TARGET_ALLOCATION_DIMENSIONS.map((dim) => (
                  <option key={dim} value={dim}>
                    {DIMENSION_TYPE_LABELS_PT[dim] ?? dim}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Chave (ex.: USD, fii, BTC-USD)</label>
              <input
                value={form.dimension_key}
                onChange={(e) => setForm((prev) => ({ ...prev, dimension_key: e.target.value }))}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Prioridade de aporte</label>
              <input
                type="number"
                value={form.priority}
                onChange={(e) => setForm((prev) => ({ ...prev, priority: e.target.value }))}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Mínimo (%)</label>
              <input
                type="number"
                step="0.1"
                value={form.min_weight}
                onChange={(e) => setForm((prev) => ({ ...prev, min_weight: e.target.value }))}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Alvo (%)</label>
              <input
                type="number"
                step="0.1"
                value={form.target_weight}
                onChange={(e) => setForm((prev) => ({ ...prev, target_weight: e.target.value }))}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Máximo (%)</label>
              <input
                type="number"
                step="0.1"
                value={form.max_weight}
                onChange={(e) => setForm((prev) => ({ ...prev, max_weight: e.target.value }))}
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
            <Plus className="h-4 w-4" strokeWidth={1.75} />
            Salvar regra
          </button>
        </form>
      </div>
    </div>
  );
}
