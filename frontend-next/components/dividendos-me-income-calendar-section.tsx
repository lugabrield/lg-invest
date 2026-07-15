"use client";

import { useState } from "react";
import { Download, RefreshCcw } from "lucide-react";
import type { DividendosMeCredentialsPayload, IncomeSyncPreviewView } from "@/lib/api";
import { ApiError, fetchIncomeCalendarPreview, importIncomeCalendar } from "@/lib/api";
import { formatDateOnly, formatDecimalBRL, sectionLabel } from "@/lib/adapt-dividendos-me";
import { AlertCard } from "@/components/alert-card";
import { cn } from "@/lib/utils";

interface DividendosMeIncomeCalendarSectionProps {
  credentials: DividendosMeCredentialsPayload;
  portfolioId: number;
  disabled: boolean;
}

/** DividendosMeIncomeCalendarSection — "5B. Proventos — Calendário
 * futuro" do Streamlit. Extrai o calendário de próximos dividendos
 * anunciados por ativo (aba "Próximos Dividendos"). Não há, hoje, um
 * evento por ativo já pago com data exata — limitação da fonte, não
 * desta tela. Gravado em `income_events`, separado do histórico mensal.
 * Uma falha aqui nunca bloqueia a carteira nem o histórico mensal. */
export function DividendosMeIncomeCalendarSection({
  credentials,
  portfolioId,
  disabled,
}: DividendosMeIncomeCalendarSectionProps) {
  const [fetching, setFetching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [preview, setPreview] = useState<IncomeSyncPreviewView | null>(null);

  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<{ created: number; skipped: number } | null>(null);

  async function handleFetch() {
    setFetching(true);
    setFetchError(null);
    setImportResult(null);
    try {
      const response = await fetchIncomeCalendarPreview({ ...credentials, portfolio_id: portfolioId });
      setPreview(response);
    } catch (err) {
      setFetchError(
        err instanceof ApiError ? err.message : "Falha inesperada ao buscar o calendário futuro de proventos.",
      );
    } finally {
      setFetching(false);
    }
  }

  async function handleImport() {
    setImporting(true);
    setImportError(null);
    try {
      const response = await importIncomeCalendar({ ...credentials, portfolio_id: portfolioId });
      setImportResult({ created: response.events_created, skipped: response.events_skipped_duplicate });
    } catch (err) {
      setImportError(
        err instanceof ApiError ? err.message : "Falha inesperada ao importar o calendário futuro de proventos.",
      );
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="rounded-card border border-border bg-surface p-5 shadow-card">
      <h2 className="mb-1 text-sm font-medium text-text-primary">5B. Proventos — Calendário futuro</h2>
      <p className="mb-3 text-xs text-text-muted">
        Extrai o calendário de próximos dividendos anunciados por ativo, da tela &quot;Próximos
        Dividendos&quot;. Gravado em income_events, separado do histórico mensal acima.
      </p>

      <button
        type="button"
        onClick={handleFetch}
        disabled={disabled || fetching}
        className={cn(
          "inline-flex items-center gap-2 rounded-lg border border-border bg-surface-hover px-3.5 py-2 text-sm font-medium text-text-primary transition-opacity hover:opacity-90 disabled:opacity-50",
        )}
      >
        <RefreshCcw className="h-4 w-4" strokeWidth={1.75} />
        {fetching ? "Buscando..." : "Buscar calendário futuro"}
      </button>
      {fetchError && <p className="mt-3 text-sm text-critical">{fetchError}</p>}

      {preview && (
        <div className="mt-4 space-y-4">
          {preview.sections_failed.length > 0 && (
            <AlertCard
              title="Calendário futuro não extraído completamente"
              message={`Seções com falha: ${preview.sections_failed.map(sectionLabel).join(", ")}`}
              severity="attention"
            />
          )}
          <p className="text-sm text-text-muted">{preview.events_valid} evento(s) futuro(s) encontrado(s).</p>

          {preview.sample.length > 0 && (
            <div className="scrollbar-thin overflow-x-auto rounded-card border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-soft text-left text-xs text-text-faint">
                    <th className="px-3 py-2 font-medium">Ticker</th>
                    <th className="px-3 py-2 font-medium">Tipo</th>
                    <th className="px-3 py-2 font-medium">Data pagamento</th>
                    <th className="px-3 py-2 font-medium">Valor</th>
                    <th className="px-3 py-2 font-medium">Moeda</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.sample.map((e, idx) => (
                    <tr key={`${e.ticker}-${e.payment_date}-${idx}`} className="border-b border-border-soft/60 last:border-0">
                      <td className="px-3 py-2 text-text-primary">{e.ticker || "—"}</td>
                      <td className="px-3 py-2 text-text-muted">{e.event_type}</td>
                      <td className="px-3 py-2 text-text-muted">{formatDateOnly(e.payment_date)}</td>
                      <td className="px-3 py-2 text-text-muted">{formatDecimalBRL(e.amount_total)}</td>
                      <td className="px-3 py-2 text-text-faint">{e.currency}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div>
            <p className="mb-2 text-xs text-text-muted">
              Importar só adiciona eventos futuros novos (nunca duplica, nunca remove histórico já
              salvo) — não precisa de palavra de confirmação.
            </p>
            <button
              type="button"
              onClick={handleImport}
              disabled={importing}
              className={cn(
                "inline-flex items-center gap-2 rounded-lg bg-gradient-primary px-3.5 py-2 text-sm font-medium text-white shadow-glow transition-opacity hover:opacity-90 disabled:opacity-50",
              )}
            >
              <Download className="h-4 w-4" strokeWidth={1.75} />
              {importing ? "Importando..." : "Importar calendário encontrado"}
            </button>
            {importError && <p className="mt-2 text-sm text-critical">{importError}</p>}
            {importResult && (
              <p className="mt-2 text-sm text-positive">
                Importação concluída. Novos: {importResult.created} · Já existentes (ignorados):{" "}
                {importResult.skipped}.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
