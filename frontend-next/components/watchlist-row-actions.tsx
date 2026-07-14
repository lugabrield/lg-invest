"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, CheckCircle2, RefreshCw, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  ApiError,
  collectWatchlistAssetData,
  removeWatchlistAsset,
  setWatchlistStatus,
  type WatchlistAssetView,
} from "@/lib/api";
import { STATUS_LABELS_PT, WATCHLIST_STATUSES } from "@/lib/adapt-radar";

// Ações por candidato da Watchlist — Fase 7. Espelha "Coletar dados",
// "Remover" e "Alterar status" de `pages_impl/radar.py`. Qualquer
// transição de status (watching/candidate/blocked/discarded/bought, em
// qualquer direção) usa o mesmo `WatchlistService.set_status` — nunca
// recria o registro. Nenhuma ação aqui cria posição ou muda patrimônio.
export function WatchlistRowActions({ entry }: { entry: WatchlistAssetView }) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "positive" | "critical"; text: string } | null>(null);
  const [newStatus, setNewStatus] = useState(entry.status);

  async function run(action: string, fn: () => Promise<void>) {
    setBusy(action);
    setMessage(null);
    try {
      await fn();
      router.refresh();
    } catch (err) {
      setMessage({
        kind: "critical",
        text: err instanceof ApiError ? err.message : "Não foi possível completar a ação agora.",
      });
    } finally {
      setBusy(null);
    }
  }

  async function handleCollect() {
    await run("collect", async () => {
      const result = await collectWatchlistAssetData(entry.id);
      const parts = [`${result.ticker}`];
      if (result.lg_score !== null) parts.push(`LG Score: ${Number(result.lg_score).toFixed(1)}`);
      if (result.conviction_score !== null)
        parts.push(`Conviction Score: ${Number(result.conviction_score).toFixed(1)}`);
      if (result.confidence !== null) parts.push(`confiança: ${(Number(result.confidence) * 100).toFixed(0)}%`);
      setMessage({
        kind: result.low_confidence ? "critical" : "positive",
        text:
          parts.join(" - ") +
          (result.low_confidence ? " — confiança baixa, não deve ser motivo primário de aporte." : ""),
      });
    });
  }

  async function handleRemove() {
    await run("remove", async () => {
      await removeWatchlistAsset(entry.id);
      setMessage({ kind: "positive", text: `${entry.ticker} removido da Watchlist.` });
    });
  }

  async function handleUpdateStatus() {
    await run("status", async () => {
      await setWatchlistStatus(entry.id, newStatus);
      setMessage({ kind: "positive", text: `Status de ${entry.ticker} atualizado para ${STATUS_LABELS_PT[newStatus]}.` });
    });
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => void handleCollect()}
          disabled={busy !== null}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 py-1 text-xs font-medium text-text-primary transition-colors hover:bg-surface-hover",
            busy === "collect" && "opacity-60",
          )}
        >
          <RefreshCw className="h-3.5 w-3.5" strokeWidth={1.75} />
          Coletar dados
        </button>

        <select
          value={newStatus}
          onChange={(e) => setNewStatus(e.target.value)}
          className="rounded-lg border border-border bg-surface px-2 py-1 text-xs text-text-primary outline-none focus:border-primary"
        >
          {WATCHLIST_STATUSES.map((status) => (
            <option key={status} value={status}>
              {STATUS_LABELS_PT[status]}
            </option>
          ))}
        </select>
        <button
          onClick={() => void handleUpdateStatus()}
          disabled={busy !== null || newStatus === entry.status}
          className={cn(
            "rounded-lg border border-border bg-surface px-2.5 py-1 text-xs font-medium text-text-primary transition-colors hover:bg-surface-hover",
            (busy === "status" || newStatus === entry.status) && "opacity-60",
          )}
        >
          Atualizar status
        </button>

        <button
          onClick={() => void handleRemove()}
          disabled={busy !== null}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-lg border border-critical/25 bg-critical/[0.04] px-2.5 py-1 text-xs font-medium text-critical transition-colors hover:bg-critical/[0.08]",
            busy === "remove" && "opacity-60",
          )}
        >
          <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
          Remover
        </button>
      </div>

      {message && (
        <div
          className={cn(
            "flex items-start gap-1.5 rounded-lg border p-2 text-xs text-text-muted",
            message.kind === "positive" ? "border-positive/25 bg-positive/[0.06]" : "border-critical/25 bg-critical/[0.06]",
          )}
        >
          {message.kind === "positive" ? (
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-positive" strokeWidth={1.75} />
          ) : (
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-critical" strokeWidth={1.75} />
          )}
          {message.text}
        </div>
      )}
    </div>
  );
}
