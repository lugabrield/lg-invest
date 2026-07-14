"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Plus } from "lucide-react";
import type { AssetSummary, ThesisView } from "@/lib/api";
import { ApiError, createThesis } from "@/lib/api";
import { THESIS_STATUS_LABELS_PT, THESIS_STATUSES, formatDate } from "@/lib/adapt-journal";
import { StatusBadge } from "@/components/status-badge";
import { EmptyState } from "@/components/states";
import { cn } from "@/lib/utils";
import { THESIS_STATUS_KIND } from "@/lib/adapt-journal";

interface JournalThesisPanelProps {
  assets: AssetSummary[];
  theses: ThesisView[];
}

/** JournalThesisPanel — aba "Teses" do Journal (v1.1, Fase 9). Espelha
 * `_render_theses()`: formulário de nova tese + tabela de teses
 * registradas. Toda tese nasce com status "open" — só muda via revisão
 * (aba "Revisões"), nunca editada diretamente aqui. */
export function JournalThesisPanel({ assets, theses }: JournalThesisPanelProps) {
  const router = useRouter();
  const [ticker, setTicker] = useState(assets[0]?.ticker ?? "");
  const [thesisDate, setThesisDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [hypothesis, setHypothesis] = useState("");
  const [drivers, setDrivers] = useState("");
  const [risks, setRisks] = useState("");
  const [horizon, setHorizon] = useState("");
  const [criteria, setCriteria] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!hypothesis.trim()) {
      setError("A hipótese não pode ficar vazia.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await createThesis({
        ticker,
        thesis_date: thesisDate,
        hypothesis: hypothesis.trim(),
        return_drivers: drivers.trim() || null,
        main_risks: risks.trim() || null,
        horizon: horizon.trim() || null,
        review_criteria: criteria.trim() || null,
      });
      setHypothesis("");
      setDrivers("");
      setRisks("");
      setHorizon("");
      setCriteria("");
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível criar a tese agora.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Nova tese de investimento</h2>
        <form
          onSubmit={handleSubmit}
          className="space-y-3 rounded-card border border-border bg-surface p-5 shadow-card"
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-text-muted">Ativo</label>
              <select
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              >
                {assets.map((asset) => (
                  <option key={asset.ticker} value={asset.ticker}>
                    {asset.ticker}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Data da tese</label>
              <input
                type="date"
                value={thesisDate}
                onChange={(e) => setThesisDate(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs text-text-muted">Hipótese principal</label>
            <textarea
              value={hypothesis}
              onChange={(e) => setHypothesis(e.target.value)}
              rows={2}
              className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-text-muted">Drivers de retorno (opcional)</label>
              <textarea
                value={drivers}
                onChange={(e) => setDrivers(e.target.value)}
                rows={2}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Riscos principais (opcional)</label>
              <textarea
                value={risks}
                onChange={(e) => setRisks(e.target.value)}
                rows={2}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-text-muted">Horizonte (opcional)</label>
              <input
                value={horizon}
                onChange={(e) => setHorizon(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Critérios de revisão (opcional)</label>
              <input
                value={criteria}
                onChange={(e) => setCriteria(e.target.value)}
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
            {isSubmitting ? "Criando..." : "Criar tese"}
          </button>
        </form>
      </div>

      <div>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Teses registradas</h2>
        {theses.length === 0 ? (
          <EmptyState
            title="Nenhuma tese ainda"
            message="Use o formulário acima para registrar sua primeira tese de investimento."
          />
        ) : (
          <>
            <div className="rounded-card border border-border bg-surface shadow-card">
              <div className="scrollbar-thin overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border-soft text-left text-xs text-text-faint">
                      <th className="px-4 py-2.5 font-medium">ID</th>
                      <th className="px-4 py-2.5 font-medium">Data</th>
                      <th className="px-4 py-2.5 font-medium">Ativo</th>
                      <th className="px-4 py-2.5 font-medium">Status</th>
                      <th className="px-4 py-2.5 font-medium">Hipótese</th>
                      <th className="px-4 py-2.5 font-medium">Horizonte</th>
                    </tr>
                  </thead>
                  <tbody>
                    {theses.map((thesis) => (
                      <tr key={thesis.id} className="border-b border-border-soft/60 align-top last:border-0">
                        <td className="px-4 py-3 text-text-faint">#{thesis.id}</td>
                        <td className="px-4 py-3 text-text-faint">{formatDate(thesis.thesis_date)}</td>
                        <td className="px-4 py-3 font-medium text-text-primary">{thesis.ticker}</td>
                        <td className="px-4 py-3">
                          <StatusBadge
                            label={THESIS_STATUS_LABELS_PT[thesis.status] ?? thesis.status}
                            status={THESIS_STATUS_KIND[thesis.status] ?? "muted"}
                          />
                        </td>
                        <td className="px-4 py-3 text-text-muted">{thesis.hypothesis}</td>
                        <td className="px-4 py-3 text-text-muted">{thesis.horizon ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <p className="mt-2 text-xs text-text-faint">
              Status possíveis: {THESIS_STATUSES.map((s) => THESIS_STATUS_LABELS_PT[s]).join(", ")}.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
