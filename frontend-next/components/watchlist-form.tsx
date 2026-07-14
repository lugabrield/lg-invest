"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { addWatchlistAsset, ApiError } from "@/lib/api";
import { STATUS_LABELS_PT, WATCHLIST_STATUSES } from "@/lib/adapt-radar";

// Mesmo enum de `backend/app/infrastructure/database/models/asset.py::ASSET_CLASSES`.
const ASSET_CLASSES = ["stock", "fii", "etf", "reit", "crypto", "bond", "cash"] as const;

const initialForm = {
  ticker: "",
  name: "",
  assetClass: "stock" as (typeof ASSET_CLASSES)[number],
  country: "BR",
  currency: "BRL",
  status: "watching" as (typeof WATCHLIST_STATUSES)[number],
  priority: 0,
  sector: "",
  thesis: "",
  notes: "",
};

// Cadastrar novo candidato — Fase 7. Espelha "Cadastrar novo candidato"
// de `pages_impl/radar.py`. Nenhuma regra de duplicata/validação aqui —
// tudo já vem pronto (ou rejeitado com 422) de `WatchlistService.add_watchlist_asset`.
export function WatchlistForm() {
  const router = useRouter();
  const [form, setForm] = useState(initialForm);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.ticker.trim() || !form.name.trim()) {
      setError("Ticker e nome são obrigatórios.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await addWatchlistAsset({
        ticker: form.ticker,
        name: form.name,
        asset_class: form.assetClass,
        country: form.country,
        currency: form.currency,
        status: form.status,
        priority: form.priority,
        sector: form.sector.trim() || null,
        thesis: form.thesis.trim() || null,
        notes: form.notes.trim() || null,
      });
      setForm(initialForm);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível adicionar o candidato agora.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-card border border-border bg-surface p-5 shadow-card">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs text-text-muted">Ticker</label>
          <input
            value={form.ticker}
            onChange={(e) => setForm({ ...form, ticker: e.target.value })}
            className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-muted">Nome</label>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
          />
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <label className="mb-1 block text-xs text-text-muted">Classe</label>
          <select
            value={form.assetClass}
            onChange={(e) => setForm({ ...form, assetClass: e.target.value as typeof form.assetClass })}
            className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
          >
            {ASSET_CLASSES.map((cls) => (
              <option key={cls} value={cls}>
                {cls}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-muted">País (2 letras)</label>
          <input
            value={form.country}
            onChange={(e) => setForm({ ...form, country: e.target.value })}
            maxLength={2}
            className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-muted">Moeda (3 letras)</label>
          <input
            value={form.currency}
            onChange={(e) => setForm({ ...form, currency: e.target.value })}
            maxLength={3}
            className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
          />
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs text-text-muted">Status inicial</label>
          <select
            value={form.status}
            onChange={(e) => setForm({ ...form, status: e.target.value as typeof form.status })}
            className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
          >
            {WATCHLIST_STATUSES.map((status) => (
              <option key={status} value={status}>
                {STATUS_LABELS_PT[status]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-muted">Prioridade (0-10)</label>
          <input
            type="number"
            min={0}
            max={10}
            value={form.priority}
            onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
            className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
          />
        </div>
      </div>

      <div className="mt-3">
        <label className="mb-1 block text-xs text-text-muted">Setor (opcional)</label>
        <input
          value={form.sector}
          onChange={(e) => setForm({ ...form, sector: e.target.value })}
          className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
        />
      </div>

      <div className="mt-3">
        <label className="mb-1 block text-xs text-text-muted">Tese (opcional)</label>
        <textarea
          value={form.thesis}
          onChange={(e) => setForm({ ...form, thesis: e.target.value })}
          rows={2}
          className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
        />
      </div>

      <div className="mt-3">
        <label className="mb-1 block text-xs text-text-muted">Notas (opcional)</label>
        <textarea
          value={form.notes}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
          rows={2}
          className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
        />
      </div>

      {error && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-critical/25 bg-critical/[0.06] p-3 text-sm text-text-muted">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-critical" strokeWidth={1.75} />
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        className={cn(
          "mt-4 inline-flex items-center gap-2 rounded-lg bg-gradient-primary px-3.5 py-2 text-sm font-medium text-white shadow-glow transition-opacity hover:opacity-90",
          isSubmitting && "opacity-60",
        )}
      >
        <Plus className="h-4 w-4" strokeWidth={1.75} />
        {isSubmitting ? "Adicionando..." : "Adicionar à Watchlist"}
      </button>
    </form>
  );
}
