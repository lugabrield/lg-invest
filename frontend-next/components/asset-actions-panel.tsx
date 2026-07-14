"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  ApiError,
  collectAtivoFundamentals,
  refreshAtivoPrice,
  setManualFlag,
  setManualPrice,
} from "@/lib/api";

// Ações de um ativo (flag manual, preço manual, refresh de preço/
// fundamentos) — Fase 6. Espelha "Marcar ativo como manual", "Cadastrar
// preço atual manual", "Atualizar preço automático" e "Fundamentos" (parte
// de coleta) de `pages_impl/ativos.py`. Nenhuma regra de negócio aqui — só
// dispara as mutações da API e mostra o resultado devolvido por ela.
export function AssetActionsPanel({ ticker, isManual }: { ticker: string; isManual: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "positive" | "critical"; text: string } | null>(null);
  const [manualPriceInput, setManualPriceInput] = useState("");

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

  async function handleToggleManual() {
    await run("manual-flag", async () => {
      const response = await setManualFlag(ticker, !isManual);
      setMessage({
        kind: "positive",
        text: response.is_manual ? "Ativo marcado como manual." : "Ativo voltou a ser automático.",
      });
    });
  }

  async function handleSetManualPrice() {
    if (!manualPriceInput.trim()) return;
    await run("manual-price", async () => {
      const response = await setManualPrice(ticker, manualPriceInput.trim());
      setMessage({ kind: "positive", text: `Preço manual salvo: ${response.price}.` });
      setManualPriceInput("");
    });
  }

  async function handleRefreshPrice() {
    await run("refresh-price", async () => {
      const response = await refreshAtivoPrice(ticker);
      const { result } = response;
      if (result.skipped_manual) {
        setMessage({ kind: "positive", text: "Ativo é manual — preço automático não foi buscado." });
      } else if (result.error) {
        setMessage({ kind: "critical", text: result.error });
      } else {
        setMessage({
          kind: "positive",
          text: `Preço atualizado (${result.inserted} inserido(s), ${result.updated} atualizado(s)).`,
        });
      }
    });
  }

  async function handleCollectFundamentals() {
    await run("collect-fundamentals", async () => {
      const response = await collectAtivoFundamentals(ticker);
      const { result } = response;
      if (result.collected) {
        setMessage({ kind: "positive", text: `Fundamentos coletados (período ${result.period_end}).` });
      } else {
        setMessage({ kind: "critical", text: result.reason ?? result.error ?? "Coleta não realizada." });
      }
    });
  }

  return (
    <div className="rounded-card border border-border bg-surface p-5 shadow-card">
      <div className="mb-3 text-sm font-medium text-text-primary">Ações</div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => void handleToggleManual()}
          disabled={busy !== null}
          className={cn(
            "rounded-lg border border-border bg-surface px-3.5 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover",
            busy === "manual-flag" && "opacity-60",
          )}
        >
          {isManual ? "Desmarcar como manual" : "Marcar como manual"}
        </button>

        <button
          onClick={() => void handleRefreshPrice()}
          disabled={busy !== null}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover",
            busy === "refresh-price" && "opacity-60",
          )}
        >
          <RefreshCw className="h-4 w-4" strokeWidth={1.75} />
          Atualizar preço automático
        </button>

        <button
          onClick={() => void handleCollectFundamentals()}
          disabled={busy !== null}
          className={cn(
            "rounded-lg border border-border bg-surface px-3.5 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover",
            busy === "collect-fundamentals" && "opacity-60",
          )}
        >
          Coletar fundamentos (Yahoo)
        </button>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <label className="text-sm text-text-muted" htmlFor={`manual-price-${ticker}`}>
          Preço manual:
        </label>
        <input
          id={`manual-price-${ticker}`}
          type="text"
          inputMode="decimal"
          placeholder="Ex.: 42.50"
          value={manualPriceInput}
          onChange={(e) => setManualPriceInput(e.target.value)}
          className="w-32 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
        />
        <button
          onClick={() => void handleSetManualPrice()}
          disabled={busy !== null || !manualPriceInput.trim()}
          className={cn(
            "rounded-lg border border-border bg-surface px-3.5 py-1.5 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover",
            (busy === "manual-price" || !manualPriceInput.trim()) && "opacity-60",
          )}
        >
          Salvar preço
        </button>
      </div>

      {message && (
        <div
          className={cn(
            "mt-4 flex items-start gap-2 rounded-lg border p-3 text-sm text-text-muted",
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
