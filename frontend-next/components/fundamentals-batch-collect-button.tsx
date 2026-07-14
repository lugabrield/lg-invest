"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { ApiError, collectAllFundamentals } from "@/lib/api";

// Coleta de fundamentos em lote (todos os ativos automáticos) — Fase 6.
// Espelha o botão "Coletar todos" da seção "Fundamentos" em
// `pages_impl/ativos.py`. Nenhuma regra de coleta aqui — só dispara
// `FundamentalsService.collect_all()` via API e resume o resultado.
export function FundamentalsBatchCollectButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "positive" | "critical"; text: string } | null>(null);

  async function handleClick() {
    setBusy(true);
    setMessage(null);
    try {
      const { result } = await collectAllFundamentals();
      const collected = result.results.filter((r) => r.collected).length;
      const skipped = result.results.length - collected;
      setMessage({
        kind: "positive",
        text: `${collected} ativo(s) com fundamentos coletados, ${skipped} não coletado(s) (manual ou sem dado disponível).`,
      });
      router.refresh();
    } catch (err) {
      setMessage({
        kind: "critical",
        text: err instanceof ApiError ? err.message : "Não foi possível coletar fundamentos agora.",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        onClick={() => void handleClick()}
        disabled={busy}
        className={cn(
          "inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover",
          busy && "opacity-60",
        )}
      >
        <RefreshCw className="h-4 w-4" strokeWidth={1.75} />
        {busy ? "Coletando..." : "Coletar fundamentos de todos os ativos"}
      </button>
      {message && (
        <div
          className={cn(
            "mt-3 flex items-start gap-2 rounded-lg border p-3 text-sm text-text-muted",
            message.kind === "positive" ? "border-positive/25 bg-positive/[0.06]" : "border-critical/25 bg-critical/[0.06]",
          )}
        >
          {message.kind === "positive" ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-positive" strokeWidth={1.75} />
          ) : (
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-critical" strokeWidth={1.75} />
          )}
          {message.text}
        </div>
      )}
    </div>
  );
}
