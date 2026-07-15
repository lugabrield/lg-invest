"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Check } from "lucide-react";
import type { InvestmentPolicyView } from "@/lib/api";
import { ApiError, updateInvestmentPolicy } from "@/lib/api";
import { RISK_TOLERANCES } from "@/lib/adapt-configuracoes";
import { cn } from "@/lib/utils";

interface ConfiguracoesPolicyPanelProps {
  policy: InvestmentPolicyView;
}

const PCT_FIELDS: { key: keyof InvestmentPolicyView; label: string }[] = [
  { key: "max_asset_weight", label: "Peso máximo por ativo (%)" },
  { key: "max_crypto_weight", label: "Peso máximo em cripto (%)" },
  { key: "target_international_min", label: "Exposição internacional mín. (%)" },
  { key: "target_international_max", label: "Exposição internacional máx. (%)" },
  { key: "target_fii_max", label: "Peso máximo em FIIs (%)" },
  { key: "target_brazil_equity", label: "Alvo — ações Brasil (%)" },
  { key: "target_us_equity", label: "Alvo — ações EUA (%)" },
  { key: "target_etf", label: "Alvo — ETFs (%)" },
  { key: "target_reit", label: "Alvo — REITs (%)" },
  { key: "target_fixed_income", label: "Alvo — renda fixa (%)" },
  { key: "rebalance_threshold", label: "Limiar de rebalanceamento (%)" },
];

function toDraft(policy: InvestmentPolicyView): Record<string, string> {
  const draft: Record<string, string> = {
    investor_profile: policy.investor_profile,
    horizon_years: String(policy.horizon_years),
    base_currency: policy.base_currency,
    risk_tolerance: policy.risk_tolerance,
    monthly_contribution_default: policy.monthly_contribution_default,
    notes: policy.notes ?? "",
  };
  for (const field of PCT_FIELDS) {
    draft[field.key] = String(Number(policy[field.key]) * 100);
  }
  return draft;
}

/** ConfiguracoesPolicyPanel — aba "Política de investimento" (Camada 3,
 * v1.1, Fase 10). Espelha `_render_investment_policy_section`: perfil,
 * horizonte, moeda-base, tolerância a risco e ~11 limites/alvos
 * percentuais. `PATCH /api/configuracoes/politica` — nenhuma regra de
 * negócio é validada aqui, tudo fica a cargo de `InvestmentPolicyService`. */
export function ConfiguracoesPolicyPanel({ policy }: ConfiguracoesPolicyPanelProps) {
  const router = useRouter();
  const [draft, setDraft] = useState<Record<string, string>>(() => toDraft(policy));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  function setField(key: string, value: string) {
    setDraft((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setSaved(false);
    try {
      const payload: Record<string, unknown> = {
        investor_profile: draft.investor_profile,
        horizon_years: Number(draft.horizon_years),
        base_currency: draft.base_currency,
        risk_tolerance: draft.risk_tolerance,
        monthly_contribution_default: draft.monthly_contribution_default,
        notes: draft.notes || null,
      };
      for (const field of PCT_FIELDS) {
        payload[field.key] = String((Number(draft[field.key]) || 0) / 100);
      }
      const updated = await updateInvestmentPolicy(payload);
      setDraft(toDraft(updated));
      setSaved(true);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar a política agora.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-5 rounded-card border border-border bg-surface p-5 shadow-card"
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label className="mb-1 block text-xs text-text-muted">Perfil do investidor</label>
          <input
            value={draft.investor_profile}
            onChange={(e) => setField("investor_profile", e.target.value)}
            className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-muted">Horizonte (anos)</label>
          <input
            type="number"
            value={draft.horizon_years}
            onChange={(e) => setField("horizon_years", e.target.value)}
            className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-muted">Moeda-base</label>
          <input
            value={draft.base_currency}
            onChange={(e) => setField("base_currency", e.target.value)}
            className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-muted">Tolerância a risco</label>
          <select
            value={draft.risk_tolerance}
            onChange={(e) => setField("risk_tolerance", e.target.value)}
            className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
          >
            {RISK_TOLERANCES.map((tolerance) => (
              <option key={tolerance} value={tolerance}>
                {tolerance}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {PCT_FIELDS.map((field) => (
          <div key={field.key}>
            <label className="mb-1 block text-xs text-text-muted">{field.label}</label>
            <input
              type="number"
              step="0.1"
              value={draft[field.key]}
              onChange={(e) => setField(field.key, e.target.value)}
              className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
            />
          </div>
        ))}
        <div>
          <label className="mb-1 block text-xs text-text-muted">Aporte mensal padrão (R$)</label>
          <input
            type="number"
            step="1"
            value={draft.monthly_contribution_default}
            onChange={(e) => setField("monthly_contribution_default", e.target.value)}
            className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
          />
        </div>
      </div>

      <div>
        <label className="mb-1 block text-xs text-text-muted">Notas (opcional)</label>
        <textarea
          value={draft.notes}
          onChange={(e) => setField("notes", e.target.value)}
          rows={3}
          className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
        />
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-critical/25 bg-critical/[0.06] p-3 text-sm text-text-muted">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-critical" strokeWidth={1.75} />
          {error}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={isSubmitting}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg bg-gradient-primary px-3.5 py-2 text-sm font-medium text-white shadow-glow transition-opacity hover:opacity-90",
            isSubmitting && "opacity-60",
          )}
        >
          <Check className="h-4 w-4" strokeWidth={1.75} />
          {isSubmitting ? "Salvando..." : "Salvar política"}
        </button>
        {saved && <span className="text-sm text-positive">Política salva.</span>}
      </div>
    </form>
  );
}
