"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, CheckCircle2, Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import { ApiError, importPortfolio, type ImportResultView } from "@/lib/api";

// Upload de carteira (CSV/Excel) — Fase 4. Espelha o fluxo de
// `carteira.py` (`st.file_uploader` + `PortfolioImportService`): só troca
// o transporte (multipart HTTP em vez de widget Streamlit). Nenhuma
// regra de importação vive aqui — o resultado já vem pronto da API.
export function PortfolioUpload() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<ImportResultView | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setIsUploading(true);
    setError(null);
    setResult(null);
    try {
      const response = await importPortfolio(file);
      setResult(response);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível importar o arquivo agora.");
    } finally {
      setIsUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="rounded-card border border-border bg-surface p-5 shadow-card">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-sm font-medium text-text-primary">Importar posições</span>
          <p className="mt-1 text-xs text-text-muted">Arquivo .csv, .xlsx ou .xls com ticker, quantidade e preço médio.</p>
        </div>
        <button
          onClick={() => inputRef.current?.click()}
          disabled={isUploading}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover",
            isUploading && "opacity-60",
          )}
        >
          <Upload className="h-4 w-4" strokeWidth={1.75} />
          {isUploading ? "Importando..." : "Escolher arquivo"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleFile(file);
          }}
        />
      </div>

      {error && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-critical/25 bg-critical/[0.06] p-3 text-sm text-text-muted">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-critical" strokeWidth={1.75} />
          {error}
        </div>
      )}

      {result && (
        <div className="mt-4 space-y-3">
          <div className="flex items-start gap-2 rounded-lg border border-positive/25 bg-positive/[0.06] p-3 text-sm text-text-muted">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-positive" strokeWidth={1.75} />
            <span>
              {result.total_rows} linha(s) processadas — {result.imported} importada(s), {result.updated} atualizada(s),{" "}
              {result.skipped} ignorada(s).
            </span>
          </div>
          {result.errors.length > 0 && (
            <div className="rounded-lg border border-attention/25 bg-attention/[0.06] p-3 text-sm">
              <div className="mb-2 flex items-center gap-2 font-medium text-text-primary">
                <AlertTriangle className="h-4 w-4 text-attention" strokeWidth={1.75} />
                {result.errors.length} erro(s) na importação
              </div>
              <ul className="space-y-1 text-xs text-text-muted">
                {result.errors.map((err: ImportResultView["errors"][number], idx: number) => (
                  <li key={idx}>
                    Linha {err.line}
                    {err.field ? ` (${err.field})` : ""}: {err.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
