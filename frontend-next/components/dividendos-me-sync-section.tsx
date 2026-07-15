"use client";

import { useState } from "react";
import { AlertTriangle, RefreshCcw } from "lucide-react";
import type { DividendosMeCredentialsPayload, DryRunResponse } from "@/lib/api";
import { ApiError, dryRunDividendosMe, syncReplaceDividendosMe, syncUpdateDividendosMe } from "@/lib/api";
import { DividendosMePreview } from "@/components/dividendos-me-preview";
import { cn } from "@/lib/utils";

interface DividendosMeSyncSectionProps {
  credentials: DividendosMeCredentialsPayload;
  portfolioId: number;
  disabled: boolean;
}

type Mode = "replace" | "update";

const CONFIRM_WORD: Record<Mode, string> = { replace: "SUBSTITUIR", update: "ATUALIZAR" };

/** DividendosMeSyncSection — passos "2. Buscar carteira" a "4. Confirmar
 * substituição" do Streamlit (`_render_fetch_portfolio` +
 * `_render_preview_and_confirmation`). `replace` exige a frase exata
 * "SUBSTITUIR" (validada de novo no backend — a API nunca relaxa esse
 * bloqueio); `update` só precisa do checkbox de confirmação. O botão de
 * confirmar fica desabilitado sempre que `blocking_reasons_*` (já
 * calculado pelo backend) não estiver vazio. */
export function DividendosMeSyncSection({
  credentials,
  portfolioId,
  disabled,
}: DividendosMeSyncSectionProps) {
  const [fetching, setFetching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [dryRun, setDryRun] = useState<DryRunResponse | null>(null);

  const [mode, setMode] = useState<Mode>("replace");
  const [confirmText, setConfirmText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    status: string;
    created: number;
    updated: number;
    removed: number;
    errors: string[];
  } | null>(null);

  async function handleFetchPortfolio() {
    setFetching(true);
    setFetchError(null);
    setResult(null);
    try {
      const response = await dryRunDividendosMe({ ...credentials, portfolio_id: portfolioId });
      setDryRun(response);
    } catch (err) {
      setFetchError(
        err instanceof ApiError ? err.message : "Falha inesperada ao buscar a carteira. Tente novamente em alguns instantes.",
      );
    } finally {
      setFetching(false);
    }
  }

  const blockingReasons = dryRun
    ? mode === "replace"
      ? dryRun.blocking_reasons_replace
      : dryRun.blocking_reasons_update
    : [];
  const confirmed = confirmText.trim() === CONFIRM_WORD[mode];

  async function handleConfirm() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const response =
        mode === "replace"
          ? await syncReplaceDividendosMe({
              ...credentials,
              portfolio_id: portfolioId,
              confirmation_phrase: confirmText.trim(),
            })
          : await syncUpdateDividendosMe({
              ...credentials,
              portfolio_id: portfolioId,
              confirm: true,
            });

      setResult({
        status: response.status,
        created: response.positions_created,
        updated: response.positions_updated,
        removed: response.positions_removed,
        errors: response.errors,
      });
      setDryRun(null);
      setConfirmText("");
    } catch (err) {
      setSubmitError(
        err instanceof ApiError ? err.message : "Falha inesperada ao aplicar a sincronização. Nenhuma alteração foi salva.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-card border border-border bg-surface p-5 shadow-card">
        <h2 className="mb-1 text-sm font-medium text-text-primary">2. Buscar carteira</h2>
        <p className="mb-3 text-xs text-text-muted">
          Faz login, lê todas as seções (Brasil + internacional) e monta um preview. Não altera
          nada na LG INVEST ainda.
        </p>
        <button
          type="button"
          onClick={handleFetchPortfolio}
          disabled={disabled || fetching}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg bg-gradient-primary px-3.5 py-2 text-sm font-medium text-white shadow-glow transition-opacity hover:opacity-90 disabled:opacity-50",
          )}
        >
          <RefreshCcw className="h-4 w-4" strokeWidth={1.75} />
          {fetching ? "Buscando..." : "Buscar carteira"}
        </button>
        {fetchError && <p className="mt-3 text-sm text-critical">{fetchError}</p>}
      </div>

      {result && (
        <div
          className={cn(
            "rounded-card border p-4 text-sm",
            result.status === "success"
              ? "border-positive/25 bg-positive/[0.06] text-text-primary"
              : "border-critical/25 bg-critical/[0.06] text-text-primary",
          )}
        >
          {result.status === "success" ? (
            <>
              Sincronização concluída. Criadas: {result.created} · Atualizadas: {result.updated} ·
              Removidas: {result.removed}.
              <p className="mt-2 text-text-muted">
                Sugestão: vá em Configurações e clique em &quot;Atualizar preços agora&quot; para
                trazer cotações/fundamentos dos ativos novos.
              </p>
            </>
          ) : (
            <>A sincronização falhou e nenhuma alteração foi gravada (rollback automático).</>
          )}
          {result.errors.length > 0 && (
            <ul className="mt-2 list-inside list-disc text-text-muted">
              {result.errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {dryRun && (
        <>
          <div className="border-t border-border-soft pt-6">
            <h2 className="mb-3 text-sm font-medium text-text-primary">3. Preview da carteira do Dividendos.me</h2>
            <DividendosMePreview
              preview={dryRun.preview}
              blockingReasons={blockingReasons}
              strongAlertSections={dryRun.strong_alert_sections}
            />
          </div>

          <div className="border-t border-border-soft pt-6">
            <h2 className="mb-1 text-sm font-medium text-text-primary">4. Confirmar substituição da carteira</h2>
            <p className="mb-3 text-xs text-text-muted">
              &quot;Substituir&quot; troca 100% das posições desta carteira pelas do Dividendos.me
              (o que faltar aqui é removido). &quot;Atualizar&quot; só cria/atualiza, sem remover
              nada.
            </p>

            <div className="mb-3 flex gap-2">
              {(["replace", "update"] as Mode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => {
                    setMode(m);
                    setConfirmText("");
                  }}
                  className={cn(
                    "rounded-lg border px-3.5 py-1.5 text-sm font-medium transition-colors",
                    mode === m
                      ? "border-primary bg-primary/10 text-text-primary"
                      : "border-border text-text-muted hover:bg-surface-hover",
                  )}
                >
                  {m === "replace" ? "Substituir 100% (recomendado)" : "Atualizar sem remover"}
                </button>
              ))}
            </div>

            {mode === "replace" && dryRun.preview.diff.missing_in_source.length > 0 && (
              <div className="mb-3 flex items-start gap-2 rounded-lg border border-critical/25 bg-critical/[0.06] p-3 text-sm text-text-muted">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-critical" strokeWidth={1.75} />
                Atenção: {dryRun.preview.diff.missing_in_source.length} posição(ões) hoje na LG
                INVEST não vieram do Dividendos.me nesta busca e serão REMOVIDAS ao confirmar:{" "}
                {dryRun.preview.diff.missing_in_source.join(", ")}
              </div>
            )}

            <div className="flex flex-wrap items-center gap-3">
              <input
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder={`Digite "${CONFIRM_WORD[mode]}" para confirmar`}
                className="w-64 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary"
              />
              <button
                type="button"
                onClick={handleConfirm}
                disabled={!confirmed || blockingReasons.length > 0 || submitting}
                className={cn(
                  "inline-flex items-center gap-2 rounded-lg bg-gradient-primary px-3.5 py-2 text-sm font-medium text-white shadow-glow transition-opacity hover:opacity-90 disabled:opacity-50",
                )}
              >
                {mode === "replace" ? "Confirmar substituição da carteira" : "Confirmar atualização"}
              </button>
            </div>
            {submitError && <p className="mt-3 text-sm text-critical">{submitError}</p>}
          </div>
        </>
      )}
    </div>
  );
}
