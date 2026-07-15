import { AlertTriangle } from "lucide-react";
import type { SyncPreviewView } from "@/lib/api";
import { formatDecimalBRL, formatDecimalPct, formatQuantity, sectionLabel, statusKind, statusLabel } from "@/lib/adapt-dividendos-me";
import { AlertCard } from "@/components/alert-card";
import { StatusBadge } from "@/components/status-badge";

interface DividendosMePreviewProps {
  preview: SyncPreviewView;
  blockingReasons: string[];
  strongAlertSections: string[];
}

/** DividendosMePreview — mesma leitura de `render_full_preview` do
 * Streamlit (`import_preview.py`): KPIs, aviso de seções que falharam
 * (com destaque extra para as "fortes"), diagnóstico, diff contra a LG
 * INVEST hoje e a tabela de posições encontradas. Puramente
 * apresentação — o cálculo (diff, status, motivos de bloqueio) já vem
 * pronto de `POST /api/dividendos-me/dry-run`. */
export function DividendosMePreview({
  preview,
  blockingReasons,
  strongAlertSections,
}: DividendosMePreviewProps) {
  const patrimonioLabel =
    preview.total_patrimonio_status === "consolidated"
      ? "Patrimônio encontrado"
      : "Patrimônio encontrado (PARCIAL)";

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <div className="rounded-card border border-border bg-surface p-4 shadow-card">
          <div className="text-xs text-text-faint">Status da extração</div>
          <div className="mt-1">
            <StatusBadge label={statusLabel(preview.status)} status={statusKind(preview.status)} />
          </div>
        </div>
        <div className="rounded-card border border-border bg-surface p-4 shadow-card">
          <div className="text-xs text-text-faint">{patrimonioLabel}</div>
          <div className="mt-1 text-lg font-semibold text-text-primary">
            {formatDecimalBRL(preview.total_patrimonio)}
          </div>
        </div>
        <div className="rounded-card border border-border bg-surface p-4 shadow-card">
          <div className="text-xs text-text-faint">Ativos válidos</div>
          <div className="mt-1 text-lg font-semibold text-text-primary">{preview.total_assets}</div>
        </div>
        <div className="rounded-card border border-border bg-surface p-4 shadow-card">
          <div className="text-xs text-text-faint">Para revisão manual</div>
          <div className="mt-1 text-lg font-semibold text-text-primary">
            {preview.review_required_tickers.length}
          </div>
        </div>
        <div className="rounded-card border border-border bg-surface p-4 shadow-card">
          <div className="text-xs text-text-faint">Seções com falha</div>
          <div className="mt-1 text-lg font-semibold text-text-primary">
            {preview.sections_failed.length}
          </div>
        </div>
      </div>

      {preview.sections_expected.length > 0 && (
        <p className="text-xs text-text-muted">
          Seções esperadas (com base na carteira atual):{" "}
          {preview.sections_expected.map(sectionLabel).join(", ")}
        </p>
      )}

      {preview.total_patrimonio_status === "partial" && (
        <AlertCard
          title="Patrimônio parcial"
          message="O patrimônio acima é PARCIAL, não consolidado: uma ou mais seções esperadas não vieram nesta extração. Não trate este valor como o patrimônio total real até que todas as seções esperadas sejam extraídas com sucesso."
          severity="attention"
        />
      )}

      {preview.status === "failed" && (
        <AlertCard
          title="Extração falhou"
          message="Não há ativos válidos suficientes para confiar neste preview. Não confirme nenhuma substituição/atualização com este resultado — rode novamente ou investigue antes."
          severity="critical"
        />
      )}

      {preview.sections_failed.length > 0 && (
        <AlertCard
          title={
            strongAlertSections.length > 0
              ? `Atenção especial: ${strongAlertSections.map(sectionLabel).join(", ")}`
              : "Seções não extraídas"
          }
          message={`Não foi possível extrair: ${preview.sections_failed
            .map(sectionLabel)
            .join(", ")}. Os ativos dessas seções não aparecem neste preview e, se a substituição for confirmada agora, as posições correspondentes que já existem na LG INVEST serão removidas sem substituto.`}
          severity={strongAlertSections.length > 0 ? "critical" : "attention"}
        />
      )}

      {preview.review_required_tickers.length > 0 && (
        <AlertCard
          title="Ativos para revisão manual"
          message={`Não puderam ser classificados automaticamente e por isso não serão criados/atualizados em nenhum modo: ${preview.review_required_tickers.join(", ")}`}
          severity="attention"
        />
      )}

      {blockingReasons.length > 0 && (
        <div className="rounded-card border border-critical/25 bg-critical/[0.06] p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-critical">
            <AlertTriangle className="h-4 w-4" strokeWidth={1.75} />
            Substituição/atualização bloqueada
          </div>
          <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-text-muted">
            {blockingReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <h3 className="mb-3 text-sm font-medium text-text-primary">
          Diferença em relação à LG INVEST hoje
        </h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-card border border-border bg-surface p-4 shadow-card">
            <div className="text-xs text-text-faint">Mantidos</div>
            <div className="mt-1 text-lg font-semibold text-text-primary">{preview.diff.kept.length}</div>
          </div>
          <div className="rounded-card border border-border bg-surface p-4 shadow-card">
            <div className="text-xs text-text-faint">Serão atualizados</div>
            <div className="mt-1 text-lg font-semibold text-text-primary">{preview.diff.updated.length}</div>
          </div>
          <div className="rounded-card border border-border bg-surface p-4 shadow-card">
            <div className="text-xs text-text-faint">Novos ativos</div>
            <div className="mt-1 text-lg font-semibold text-text-primary">{preview.diff.created.length}</div>
          </div>
          <div className="rounded-card border border-border bg-surface p-4 shadow-card">
            <div className="text-xs text-text-faint">Serão removidos (replace)</div>
            <div className="mt-1 text-lg font-semibold text-text-primary">
              {preview.diff.missing_in_source.length}
            </div>
          </div>
        </div>
        {preview.diff.missing_in_source.length > 0 && (
          <p className="mt-3 text-sm text-text-muted">
            <strong className="text-text-primary">
              Existem na LG INVEST mas não vieram do Dividendos.me — serão removidos apenas no modo
              replace:
            </strong>{" "}
            {preview.diff.missing_in_source.join(", ")}
          </p>
        )}
      </div>

      <div>
        <h3 className="mb-3 text-sm font-medium text-text-primary">Posições encontradas no Dividendos.me</h3>
        {preview.positions.length === 0 ? (
          <p className="text-sm text-text-muted">Nenhuma posição encontrada no Dividendos.me.</p>
        ) : (
          <div className="rounded-card border border-border bg-surface shadow-card">
            <div className="scrollbar-thin overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-soft text-left text-xs text-text-faint">
                    <th className="px-4 py-2.5 font-medium" />
                    <th className="px-4 py-2.5 font-medium">Ticker</th>
                    <th className="px-4 py-2.5 font-medium">Classe</th>
                    <th className="px-4 py-2.5 font-medium">Moeda</th>
                    <th className="px-4 py-2.5 font-medium">Quantidade</th>
                    <th className="px-4 py-2.5 font-medium">Preço médio</th>
                    <th className="px-4 py-2.5 font-medium">Valor atual</th>
                    <th className="px-4 py-2.5 font-medium">Rentab.</th>
                    <th className="px-4 py-2.5 font-medium">Origem</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.positions.map((p, idx) => (
                    <tr key={`${p.ticker || p.raw_ticker}-${idx}`} className="border-b border-border-soft/60 last:border-0">
                      <td className="px-4 py-2.5">
                        {p.review_required && <AlertTriangle className="h-3.5 w-3.5 text-attention" strokeWidth={1.75} />}
                      </td>
                      <td className="px-4 py-2.5 font-medium text-text-primary">{p.ticker || "—"}</td>
                      <td className="px-4 py-2.5 text-text-muted">{p.asset_class}</td>
                      <td className="px-4 py-2.5 text-text-muted">{p.currency}</td>
                      <td className="px-4 py-2.5 text-text-muted">{formatQuantity(p.quantity)}</td>
                      <td className="px-4 py-2.5 text-text-muted">{formatDecimalBRL(p.average_price)}</td>
                      <td className="px-4 py-2.5 text-text-muted">{formatDecimalBRL(p.current_value)}</td>
                      <td className="px-4 py-2.5 text-text-muted">{formatDecimalPct(p.return_pct)}</td>
                      <td className="px-4 py-2.5 text-text-faint">{p.origin}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {preview.diagnostics.length > 0 && (
        <details className="rounded-card border border-border bg-surface p-4 shadow-card">
          <summary className="cursor-pointer text-sm font-medium text-text-primary">
            Diagnóstico da extração (por seção)
          </summary>
          <div className="scrollbar-thin mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-soft text-left text-xs text-text-faint">
                  <th className="px-3 py-2 font-medium">Seção</th>
                  <th className="px-3 py-2 font-medium">Linhas brutas</th>
                  <th className="px-3 py-2 font-medium">Válidas</th>
                  <th className="px-3 py-2 font-medium">Rejeitadas</th>
                  <th className="px-3 py-2 font-medium">Motivo(s)</th>
                </tr>
              </thead>
              <tbody>
                {preview.diagnostics.map((d) => (
                  <tr key={d.section} className="border-b border-border-soft/60 last:border-0">
                    <td className="px-3 py-2 text-text-primary">{sectionLabel(d.section)}</td>
                    <td className="px-3 py-2 text-text-muted">{d.raw_rows_detected}</td>
                    <td className="px-3 py-2 text-text-muted">{d.valid_rows}</td>
                    <td className="px-3 py-2 text-text-muted">{d.rejected_rows}</td>
                    <td className="px-3 py-2 text-text-faint">{d.rejection_reasons.join("; ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  );
}
