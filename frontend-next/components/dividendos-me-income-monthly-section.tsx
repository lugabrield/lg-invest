"use client";

import { useState } from "react";
import { Download, RefreshCcw } from "lucide-react";
import type { DividendosMeCredentialsPayload, IncomeMonthlySyncPreviewView } from "@/lib/api";
import { ApiError, fetchIncomeMonthlyPreview, importIncomeMonthly } from "@/lib/api";
import { formatDecimalBRL, formatMonthYear, sectionLabel } from "@/lib/adapt-dividendos-me";
import { AlertCard } from "@/components/alert-card";
import { cn } from "@/lib/utils";

interface DividendosMeIncomeMonthlySectionProps {
  credentials: DividendosMeCredentialsPayload;
  portfolioId: number;
  disabled: boolean;
}

/** DividendosMeIncomeMonthlySection — "5A. Proventos — Histórico
 * mensal" do Streamlit. Extrai o agregado mensal já recebido (Central
 * de Proventos → Análise), por carteira/mês — nunca um evento por
 * ativo/data (a fonte só entrega o agregado). Uma falha aqui nunca
 * bloqueia a sincronização da carteira. Importar é sempre aditivo (dedup
 * por carteira/ano/mês/moeda) — não exige palavra de confirmação. */
export function DividendosMeIncomeMonthlySection({
  credentials,
  portfolioId,
  disabled,
}: DividendosMeIncomeMonthlySectionProps) {
  const [fetching, setFetching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [preview, setPreview] = useState<IncomeMonthlySyncPreviewView | null>(null);

  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<{ created: number; skipped: number } | null>(null);

  async function handleFetch() {
    setFetching(true);
    setFetchError(null);
    setImportResult(null);
    try {
      const response = await fetchIncomeMonthlyPreview({ ...credentials, portfolio_id: portfolioId });
      setPreview(response);
    } catch (err) {
      setFetchError(
        err instanceof ApiError ? err.message : "Falha inesperada ao buscar o histórico mensal de proventos.",
      );
    } finally {
      setFetching(false);
    }
  }

  async function handleImport() {
    setImporting(true);
    setImportError(null);
    try {
      const response = await importIncomeMonthly({ ...credentials, portfolio_id: portfolioId });
      setImportResult({ created: response.summaries_created, skipped: response.summaries_skipped_duplicate });
    } catch (err) {
      setImportError(
        err instanceof ApiError ? err.message : "Falha inesperada ao importar o histórico mensal de proventos.",
      );
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="rounded-card border border-border bg-surface p-5 shadow-card">
      <h2 className="mb-1 text-sm font-medium text-text-primary">5A. Proventos — Histórico mensal</h2>
      <p className="mb-3 text-xs text-text-muted">
        Extrai o agregado mensal já recebido de Central de Proventos → Renda Variável → Brasil →
        Análise, por carteira. Gravado em uma tabela própria, separado do calendário futuro abaixo.
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
        {fetching ? "Buscando..." : "Buscar histórico mensal"}
      </button>
      {fetchError && <p className="mt-3 text-sm text-critical">{fetchError}</p>}

      {preview && (
        <div className="mt-4 space-y-4">
          {preview.sections_failed.length > 0 && (
            <AlertCard
              title="Histórico mensal não extraído completamente"
              message={`Seções com falha: ${preview.sections_failed.map(sectionLabel).join(", ")}`}
              severity="attention"
            />
          )}
          <p className="text-sm text-text-muted">
            {preview.summaries_valid} mês(es) de histórico encontrado(s) · Carteiras:{" "}
            {preview.wallets_found.join(", ") || "—"}
          </p>

          {preview.sample.length > 0 && (
            <div className="scrollbar-thin overflow-x-auto rounded-card border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-soft text-left text-xs text-text-faint">
                    <th className="px-3 py-2 font-medium">Carteira</th>
                    <th className="px-3 py-2 font-medium">Mês</th>
                    <th className="px-3 py-2 font-medium">Total</th>
                    <th className="px-3 py-2 font-medium">Moeda</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.sample.map((s, idx) => (
                    <tr key={`${s.wallet_name}-${s.year}-${s.month}-${idx}`} className="border-b border-border-soft/60 last:border-0">
                      <td className="px-3 py-2 text-text-primary">{s.wallet_name}</td>
                      <td className="px-3 py-2 text-text-muted">{formatMonthYear(s.month, s.year)}</td>
                      <td className="px-3 py-2 text-text-muted">{formatDecimalBRL(s.amount_total)}</td>
                      <td className="px-3 py-2 text-text-faint">{s.currency}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div>
            <p className="mb-2 text-xs text-text-muted">
              Importar só adiciona meses novos por carteira/moeda (nunca duplica, nunca remove
              histórico já salvo) — não precisa de palavra de confirmação.
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
              {importing ? "Importando..." : "Importar histórico mensal encontrado"}
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
