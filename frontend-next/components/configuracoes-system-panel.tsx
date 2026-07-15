"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, RefreshCcw } from "lucide-react";
import type { BatchUpdateResultView, FxStatusView, SystemInfoView } from "@/lib/api";
import { ApiError, refreshFxRate, refreshPrices, setFxRateManually } from "@/lib/api";
import { FX_SOURCE_LABELS_PT } from "@/lib/adapt-configuracoes";
import { AlertCard } from "@/components/alert-card";
import { cn } from "@/lib/utils";

interface ConfiguracoesSystemPanelProps {
  system: SystemInfoView;
  fx: FxStatusView;
}

/** ConfiguracoesSystemPanel — aba "Sistema" (v1.1, Fase 10). Espelha
 * `_render_system_section()`: ambiente, câmbio USD/BRL (automático ou
 * manual) e atualização de preços via Yahoo Finance. Ambas as
 * atualizações automáticas dependem de rede — erro nunca derruba a
 * tela, só mostra um aviso (mesma regra do Streamlit). */
export function ConfiguracoesSystemPanel({ system, fx }: ConfiguracoesSystemPanelProps) {
  const router = useRouter();
  const [manualRate, setManualRate] = useState(fx.current_rate);
  const [fxLoading, setFxLoading] = useState(false);
  const [fxError, setFxError] = useState<string | null>(null);
  const [priceLoading, setPriceLoading] = useState(false);
  const [priceResult, setPriceResult] = useState<BatchUpdateResultView | null>(null);
  const [priceError, setPriceError] = useState<string | null>(null);

  async function handleRefreshFx() {
    setFxLoading(true);
    setFxError(null);
    try {
      await refreshFxRate();
      router.refresh();
    } catch (err) {
      setFxError(
        err instanceof ApiError
          ? err.message
          : "Não foi possível atualizar o câmbio automaticamente agora — sem internet ou fonte indisponível.",
      );
    } finally {
      setFxLoading(false);
    }
  }

  async function handleSetManualRate() {
    setFxLoading(true);
    setFxError(null);
    try {
      await setFxRateManually(manualRate.replace(",", "."));
      router.refresh();
    } catch (err) {
      setFxError(err instanceof ApiError ? err.message : "Câmbio inválido.");
    } finally {
      setFxLoading(false);
    }
  }

  async function handleRefreshPrices() {
    setPriceLoading(true);
    setPriceError(null);
    setPriceResult(null);
    try {
      const result = await refreshPrices();
      setPriceResult(result);
      router.refresh();
    } catch (err) {
      setPriceError(
        err instanceof ApiError
          ? err.message
          : "Não foi possível atualizar os preços agora — sem internet ou fonte indisponível.",
      );
    } finally {
      setPriceLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-card border border-border bg-surface p-5 shadow-card">
        <div className="mb-3 text-sm font-medium text-text-primary">Ambiente</div>
        <div className="space-y-1 text-sm text-text-muted">
          <p>
            Ambiente: <code className="text-text-primary">{system.environment}</code>
          </p>
          <p>
            Banco de dados: <code className="text-text-primary">{system.database_url_redacted}</code>
          </p>
          <p>
            Carteira ativa: <code className="text-text-primary">{system.portfolio_id}</code>
          </p>
          <p>
            Ativos cadastrados: <strong className="text-text-primary">{system.assets_count}</strong>
          </p>
        </div>
      </div>

      <div className="rounded-card border border-border bg-surface p-5 shadow-card">
        <div className="mb-1 text-sm font-medium text-text-primary">Câmbio USD/BRL</div>
        <p className="mb-3 text-xs text-text-muted">
          Usado apenas para exibição no Dashboard. Não afeta Decision Engine, LG Score nem o
          Portfolio Engine. Fonte automática: BCB PTAX → Yahoo Finance → última cotação salva.
        </p>

        <div className="mb-3 text-sm text-text-muted">
          Câmbio em uso: <strong className="text-text-primary">{Number(fx.current_rate).toFixed(4)}</strong>
          {fx.quote && (
            <>
              {" "}
              · Fonte: <strong className="text-text-primary">{FX_SOURCE_LABELS_PT[fx.quote.source] ?? fx.quote.source}</strong>
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleRefreshFx}
            disabled={fxLoading}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg bg-gradient-primary px-3.5 py-2 text-sm font-medium text-white shadow-glow transition-opacity hover:opacity-90",
              fxLoading && "opacity-60",
            )}
          >
            {fxLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" strokeWidth={1.75} />}
            Atualizar câmbio automático
          </button>

          <input
            value={manualRate}
            onChange={(e) => setManualRate(e.target.value)}
            className="w-32 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
          />
          <button
            type="button"
            onClick={handleSetManualRate}
            disabled={fxLoading}
            className="rounded-lg border border-border bg-surface-hover px-3.5 py-2 text-sm font-medium text-text-primary hover:opacity-90"
          >
            Salvar câmbio manual
          </button>
        </div>

        {fxError && <p className="mt-3 text-sm text-critical">{fxError}</p>}
      </div>

      <div className="rounded-card border border-border bg-surface p-5 shadow-card">
        <div className="mb-1 text-sm font-medium text-text-primary">Atualizar preços de mercado</div>
        <p className="mb-3 text-xs text-text-muted">
          Usa o Yahoo Finance e requer internet. Coleta incremental (não duplica preços). Ativos
          manuais (ex.: Tesouro Direto) são pulados.
        </p>
        <button
          type="button"
          onClick={handleRefreshPrices}
          disabled={priceLoading}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg bg-gradient-primary px-3.5 py-2 text-sm font-medium text-white shadow-glow transition-opacity hover:opacity-90",
            priceLoading && "opacity-60",
          )}
        >
          {priceLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" strokeWidth={1.75} />}
          Atualizar preços agora
        </button>

        {priceError && <p className="mt-3 text-sm text-critical">{priceError}</p>}
        {priceResult && (
          <p className="mt-3 text-sm text-text-muted">
            Preços atualizados. Inseridos: {priceResult.results.reduce((s, r) => s + r.inserted, 0)} · Atualizados:{" "}
            {priceResult.results.reduce((s, r) => s + r.updated, 0)} · Manuais pulados:{" "}
            {priceResult.results.filter((r) => r.skipped_manual).length}
          </p>
        )}
        {priceResult && priceResult.results.some((r) => r.error) && (
          <AlertCard
            title="Falhas na atualização"
            message={priceResult.results
              .filter((r) => r.error)
              .map((r) => r.ticker)
              .join(", ")}
            severity="attention"
          />
        )}
      </div>
    </div>
  );
}
