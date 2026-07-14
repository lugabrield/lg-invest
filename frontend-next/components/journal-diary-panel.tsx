"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Plus } from "lucide-react";
import type { AssetSummary, JournalEntryView } from "@/lib/api";
import { ApiError, createJournalEntry } from "@/lib/api";
import { JOURNAL_ACTIONS, JOURNAL_ACTION_LABELS_PT, formatDate } from "@/lib/adapt-journal";
import { EmptyState } from "@/components/states";
import { cn } from "@/lib/utils";

interface JournalDiaryPanelProps {
  assets: AssetSummary[];
  entries: JournalEntryView[];
}

/** JournalDiaryPanel — aba "Diário" do Journal (v1.1, Fase 9). Espelha
 * `_render_diary()` de `pages_impl/journal.py`: formulário de nova
 * entrada + histórico. Nenhuma regra de negócio aqui — `POST
 * /api/journal` já valida `action` e resolve o `ticker`. */
export function JournalDiaryPanel({ assets, entries }: JournalDiaryPanelProps) {
  const router = useRouter();
  const [ticker, setTicker] = useState(assets[0]?.ticker ?? "");
  const [action, setAction] = useState<(typeof JOURNAL_ACTIONS)[number]>("buy");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [thesis, setThesis] = useState("");
  const [expected, setExpected] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!thesis.trim()) {
      setError("A nota não pode ficar vazia.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await createJournalEntry({
        ticker,
        action,
        date,
        thesis: thesis.trim(),
        expected_outcome: expected.trim() || null,
      });
      setThesis("");
      setExpected("");
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível registrar a entrada agora.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Nova entrada de diário</h2>
        <form
          onSubmit={handleSubmit}
          className="space-y-3 rounded-card border border-border bg-surface p-5 shadow-card"
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
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
              <label className="mb-1 block text-xs text-text-muted">Ação</label>
              <select
                value={action}
                onChange={(e) => setAction(e.target.value as typeof action)}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              >
                {JOURNAL_ACTIONS.map((a) => (
                  <option key={a} value={a}>
                    {JOURNAL_ACTION_LABELS_PT[a]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Data</label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs text-text-muted">Nota / tese</label>
            <textarea
              value={thesis}
              onChange={(e) => setThesis(e.target.value)}
              rows={2}
              className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-text-muted">Resultado esperado (opcional)</label>
            <textarea
              value={expected}
              onChange={(e) => setExpected(e.target.value)}
              rows={2}
              className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
            />
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
            {isSubmitting ? "Salvando..." : "Salvar entrada"}
          </button>
        </form>
      </div>

      <div>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Histórico do diário</h2>
        {entries.length === 0 ? (
          <EmptyState
            title="Nenhuma entrada ainda"
            message="Use o formulário acima para registrar sua primeira entrada de diário."
          />
        ) : (
          <div className="rounded-card border border-border bg-surface shadow-card">
            <div className="scrollbar-thin overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-soft text-left text-xs text-text-faint">
                    <th className="px-4 py-2.5 font-medium">Data</th>
                    <th className="px-4 py-2.5 font-medium">Ativo</th>
                    <th className="px-4 py-2.5 font-medium">Ação</th>
                    <th className="px-4 py-2.5 font-medium">Nota</th>
                    <th className="px-4 py-2.5 font-medium">Esperado</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr key={entry.id} className="border-b border-border-soft/60 align-top last:border-0">
                      <td className="px-4 py-3 text-text-faint">{formatDate(entry.date)}</td>
                      <td className="px-4 py-3 font-medium text-text-primary">{entry.ticker}</td>
                      <td className="px-4 py-3 text-text-muted">
                        {JOURNAL_ACTION_LABELS_PT[entry.action] ?? entry.action}
                      </td>
                      <td className="px-4 py-3 text-text-muted">{entry.thesis}</td>
                      <td className="px-4 py-3 text-text-faint">{entry.expected_outcome ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
