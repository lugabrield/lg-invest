"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Check, Trash2 } from "lucide-react";
import type { AllocationPresetView, SimpleAllocationView } from "@/lib/api";
import {
  ApiError,
  applyAllocationPreset,
  clearSimpleAllocation,
  setSimpleAllocation,
} from "@/lib/api";
import { ASSET_CLASSES } from "@/lib/adapt-configuracoes";
import { cn } from "@/lib/utils";

interface ConfiguracoesSimpleAllocationPanelProps {
  allocation: SimpleAllocationView;
  presets: AllocationPresetView[];
}

function toDraft(allocation: Record<string, string>): Record<string, string> {
  const draft: Record<string, string> = {};
  for (const cls of ASSET_CLASSES) {
    draft[cls] = allocation[cls] ? String(Number(allocation[cls]) * 100) : "0";
  }
  return draft;
}

/** ConfiguracoesSimpleAllocationPanel — aba "Alocação simples" (Camada 1,
 * v1.1, Fase 10). Espelha `_render_simple_allocation_section`: presets
 * prontos (aplicação imediata) + edição manual por classe, com soma
 * validada pela própria API (`ValueError` → 422, "deve somar 100%").
 * Limpar meta usa confirmação de 2 passos, como no Streamlit. */
export function ConfiguracoesSimpleAllocationPanel({
  allocation,
  presets,
}: ConfiguracoesSimpleAllocationPanelProps) {
  const router = useRouter();
  const [draft, setDraft] = useState<Record<string, string>>(() => toDraft(allocation.allocation));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  const sum = ASSET_CLASSES.reduce((total, cls) => total + (Number(draft[cls]) || 0), 0);

  async function handleApplyPreset(presetKey: string) {
    if (presetKey === "personalizado") return;
    setIsSubmitting(true);
    setError(null);
    try {
      const updated = await applyAllocationPreset(presetKey);
      setDraft(toDraft(updated.allocation));
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível aplicar o preset agora.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const payload: Record<string, string> = {};
      for (const cls of ASSET_CLASSES) {
        payload[cls] = String((Number(draft[cls]) || 0) / 100);
      }
      const updated = await setSimpleAllocation(payload);
      setDraft(toDraft(updated.allocation));
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar a alocação agora.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleClear() {
    if (!confirmClear) {
      setConfirmClear(true);
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await clearSimpleAllocation();
      setDraft(toDraft({}));
      setConfirmClear(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível limpar a meta agora.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Presets prontos</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {presets.map((preset) => (
            <button
              key={preset.key}
              type="button"
              disabled={isSubmitting || preset.allocation === null}
              onClick={() => handleApplyPreset(preset.key)}
              className={cn(
                "rounded-card border border-border bg-surface p-4 text-left shadow-card transition-colors hover:bg-surface-hover disabled:opacity-50",
              )}
            >
              <div className="text-sm font-medium text-text-primary">{preset.label}</div>
              <p className="mt-1 text-xs text-text-muted">{preset.description}</p>
            </button>
          ))}
        </div>
      </div>

      <div>
        <h2 className="mb-1 text-sm font-medium text-text-primary">Meta manual por classe</h2>
        <p className="mb-3 text-xs text-text-muted">
          {allocation.has_target ? "Meta configurada." : "Nenhuma meta configurada ainda."} Os
          valores devem somar 100%.
        </p>
        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-card border border-border bg-surface p-5 shadow-card"
        >
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {ASSET_CLASSES.map((cls) => (
              <div key={cls}>
                <label className="mb-1 block text-xs text-text-muted">{cls}</label>
                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="100"
                    value={draft[cls]}
                    onChange={(e) => setDraft((prev) => ({ ...prev, [cls]: e.target.value }))}
                    className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
                  />
                  <span className="text-xs text-text-faint">%</span>
                </div>
              </div>
            ))}
          </div>

          <p className={cn("text-sm", Math.abs(sum - 100) < 0.01 ? "text-positive" : "text-attention")}>
            Soma atual: {sum.toFixed(1)}%{Math.abs(sum - 100) >= 0.01 && " — precisa somar 100%"}
          </p>

          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-critical/25 bg-critical/[0.06] p-3 text-sm text-text-muted">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-critical" strokeWidth={1.75} />
              {error}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={isSubmitting}
              className={cn(
                "inline-flex items-center gap-2 rounded-lg bg-gradient-primary px-3.5 py-2 text-sm font-medium text-white shadow-glow transition-opacity hover:opacity-90",
                isSubmitting && "opacity-60",
              )}
            >
              <Check className="h-4 w-4" strokeWidth={1.75} />
              Salvar alocação
            </button>

            <button
              type="button"
              onClick={handleClear}
              disabled={isSubmitting || !allocation.has_target}
              className={cn(
                "inline-flex items-center gap-2 rounded-lg border px-3.5 py-2 text-sm font-medium transition-colors disabled:opacity-40",
                confirmClear
                  ? "border-critical/40 bg-critical/[0.06] text-critical"
                  : "border-border bg-surface-hover text-text-primary hover:opacity-90",
              )}
            >
              <Trash2 className="h-4 w-4" strokeWidth={1.75} />
              {confirmClear ? "Confirmar limpeza da meta" : "Limpar meta"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
