"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { ThesisView } from "@/lib/api";
import { ApiError, createThesisReview } from "@/lib/api";
import { REVIEW_CLASSIFICATION_LABELS_PT, REVIEW_CLASSIFICATIONS } from "@/lib/adapt-journal";
import { EmptyState } from "@/components/states";
import { cn } from "@/lib/utils";

interface JournalReviewPanelProps {
  theses: ThesisView[];
}

/** JournalReviewPanel — aba "Revisões" do Journal (v1.1, Fase 9).
 * Espelha `_render_reviews()`: escolhe uma tese existente, registra uma
 * revisão imutável e o status da tese muda conforme a classificação
 * (regra 100% em `ThesisService.review_thesis`, nada recalculado aqui). */
export function JournalReviewPanel({ theses }: JournalReviewPanelProps) {
  const router = useRouter();
  const [thesisId, setThesisId] = useState<number | null>(theses[0]?.id ?? null);
  const [reviewDate, setReviewDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [classification, setClassification] =
    useState<(typeof REVIEW_CLASSIFICATIONS)[number]>("confirmed");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  if (theses.length === 0) {
    return (
      <EmptyState
        title="Nenhuma tese para revisar"
        message='Crie uma tese na aba "Teses" antes de registrar uma revisão.'
      />
    );
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (thesisId === null) return;
    setIsSubmitting(true);
    setError(null);
    setSuccess(false);
    try {
      await createThesisReview(thesisId, {
        review_date: reviewDate,
        classification,
        notes: notes.trim() || null,
      });
      setNotes("");
      setSuccess(true);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível registrar a revisão agora.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <h2 className="mb-3 text-sm font-medium text-text-primary">Revisar uma tese</h2>
      <form
        onSubmit={handleSubmit}
        className="space-y-3 rounded-card border border-border bg-surface p-5 shadow-card"
      >
        <div>
          <label className="mb-1 block text-xs text-text-muted">Tese</label>
          <select
            value={thesisId ?? ""}
            onChange={(e) => setThesisId(Number(e.target.value))}
            className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
          >
            {theses.map((thesis) => (
              <option key={thesis.id} value={thesis.id}>
                #{thesis.id} · {thesis.ticker} · {thesis.status}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs text-text-muted">Data da revisão</label>
            <input
              type="date"
              value={reviewDate}
              onChange={(e) => setReviewDate(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-muted">Classificação</label>
            <select
              value={classification}
              onChange={(e) => setClassification(e.target.value as typeof classification)}
              className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
            >
              {REVIEW_CLASSIFICATIONS.map((c) => (
                <option key={c} value={c}>
                  {REVIEW_CLASSIFICATION_LABELS_PT[c]}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs text-text-muted">Notas da revisão (opcional)</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
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
        {success && (
          <div className="flex items-start gap-2 rounded-lg border border-positive/25 bg-positive/[0.06] p-3 text-sm text-text-muted">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-positive" strokeWidth={1.75} />
            Revisão registrada. Status da tese atualizado.
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
          {isSubmitting ? "Registrando..." : "Registrar revisão"}
        </button>
      </form>
    </div>
  );
}
