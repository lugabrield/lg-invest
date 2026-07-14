import type { RadarClassificationResult } from "@/lib/api";
import { CLASSIFICATION_KIND, CLASSIFICATION_LABELS_PT, CLASSIFICATION_ORDER, formatConfidencePct, formatScore } from "@/lib/adapt-radar";
import { StatusBadge } from "@/components/status-badge";

// Radar de oportunidades — Fase 7. Espelha "Radar de oportunidades" de
// `pages_impl/radar.py`: uma seção por classificação (Já tenho / Novo
// candidato / Monitorar / Evitar / Bloqueado / Dado insuficiente), com
// tabela + motivos por ativo. Nenhum cálculo aqui — `classification`,
// `effective_score`, `confidence` e `reasons` já vêm prontos da API.
export function RadarOpportunitySections({ candidates }: { candidates: RadarClassificationResult[] }) {
  const byClassification = new Map<string, RadarClassificationResult[]>();
  for (const candidate of candidates) {
    const list = byClassification.get(candidate.classification) ?? [];
    list.push(candidate);
    byClassification.set(candidate.classification, list);
  }

  return (
    <div className="space-y-6">
      {CLASSIFICATION_ORDER.map((classification) => {
        const subset = byClassification.get(classification);
        if (!subset || subset.length === 0) return null;

        return (
          <div key={classification} className="rounded-card border border-border bg-surface p-5 shadow-card">
            <div className="mb-3 flex items-center gap-2">
              <StatusBadge
                label={CLASSIFICATION_LABELS_PT[classification]}
                status={CLASSIFICATION_KIND[classification] ?? "muted"}
              />
              <span className="text-xs text-text-faint">{subset.length} ativo(s)</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-soft text-left text-xs text-text-faint">
                    <th className="py-2 pr-4 font-medium">Ticker</th>
                    <th className="py-2 pr-4 font-medium">Nome</th>
                    <th className="py-2 pr-4 font-medium">Classe</th>
                    <th className="py-2 pr-4 font-medium">Já tenho?</th>
                    <th className="py-2 pr-4 text-right font-medium">Score</th>
                    <th className="py-2 pr-4 text-right font-medium">Confiança</th>
                  </tr>
                </thead>
                <tbody>
                  {subset.map((c) => (
                    <tr key={c.ticker} className="border-b border-border-soft/60 last:border-0">
                      <td className="py-2 pr-4 font-medium text-text-primary">{c.ticker}</td>
                      <td className="py-2 pr-4 text-text-muted">{c.name}</td>
                      <td className="py-2 pr-4 text-text-muted">{c.asset_class}</td>
                      <td className="py-2 pr-4 text-text-muted">{c.is_current_holding ? "Sim" : "Não"}</td>
                      <td className="py-2 pr-4 text-right text-text-primary">{formatScore(c.effective_score)}</td>
                      <td className="py-2 pr-4 text-right text-text-muted">{formatConfidencePct(c.confidence)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <details className="mt-3 text-xs">
              <summary className="cursor-pointer text-text-primary">
                Explicação — {CLASSIFICATION_LABELS_PT[classification]}
              </summary>
              <div className="mt-2 space-y-2">
                {subset.map((c) => (
                  <div key={c.ticker}>
                    <span className="font-medium text-text-primary">{c.ticker}</span>
                    {c.reasons.length > 0 ? (
                      <ul className="ml-4 list-disc text-text-muted">
                        {c.reasons.map((reason, idx) => (
                          <li key={idx}>{reason}</li>
                        ))}
                      </ul>
                    ) : (
                      <span className="ml-2 text-text-faint">sem motivos registrados.</span>
                    )}
                  </div>
                ))}
              </div>
            </details>
          </div>
        );
      })}
    </div>
  );
}
