import type { ConvictionScoreResult, LGScoreResult } from "@/lib/api";
import { CLASSIFICATION_LABELS_PT, CLASSIFICATION_STATUS, CONFIDENCE_LABELS, CONFIDENCE_STATUS, PILLAR_LABELS_PT } from "@/lib/adapt-ativos";
import { StatusBadge } from "@/components/status-badge";

// LG Score + LG Conviction Score v2 de um ativo — Fase 6. Espelha as
// seções "LG Score de um ativo" e "LG Conviction Score v2" de
// `pages_impl/ativos.py`.
export function AssetScorePanel({
  lgScore,
  conviction,
}: {
  lgScore: LGScoreResult | null;
  conviction: ConvictionScoreResult | null;
}) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="rounded-card border border-border bg-surface p-5 shadow-card">
        <div className="mb-3 text-sm font-medium text-text-primary">LG Score</div>
        {lgScore === null ? (
          <p className="text-sm text-text-muted">LG Score indisponível para este ativo (sem histórico de preço).</p>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <div className="text-xs text-text-faint">Score</div>
                <div className="text-lg font-semibold text-text-primary">{Number(lgScore.lg_score).toFixed(1)}</div>
              </div>
              <div>
                <div className="text-xs text-text-faint">Classificação</div>
                <div className="text-sm font-medium text-text-primary">{lgScore.classification}</div>
              </div>
              <div>
                <div className="text-xs text-text-faint">Confiança</div>
                <div className="text-sm font-medium text-text-primary">{lgScore.confidence_label}</div>
              </div>
            </div>
            <p className="mt-3 text-xs text-text-muted">
              Qualidade {Number(lgScore.quality).toFixed(0)} · Valuation {Number(lgScore.valuation).toFixed(0)} · Crescimento{" "}
              {Number(lgScore.growth).toFixed(0)} · Risco {Number(lgScore.risk).toFixed(0)} · Alocação{" "}
              {Number(lgScore.allocation).toFixed(0)}
            </p>
            {lgScore.explanation.length > 0 && (
              <details className="mt-3 text-xs text-text-muted">
                <summary className="cursor-pointer text-text-primary">Por que essa nota? (explicação por fator)</summary>
                <div className="mt-2 space-y-2">
                  {lgScore.explanation.map((pillar) => (
                    <div key={pillar.name}>
                      <div className="font-medium text-text-primary">{PILLAR_LABELS_PT[pillar.name] ?? pillar.name}</div>
                      {pillar.reasons.map((reason, idx) => (
                        <div key={idx}>· {reason}</div>
                      ))}
                    </div>
                  ))}
                </div>
              </details>
            )}
          </>
        )}
      </div>

      <div className="rounded-card border border-border bg-surface p-5 shadow-card">
        <div className="mb-3 text-sm font-medium text-text-primary">LG Conviction Score v2</div>
        {conviction === null ? (
          <p className="text-sm text-text-muted">Conviction Score indisponível para este ativo (sem histórico de preço).</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge
                label={CLASSIFICATION_LABELS_PT[conviction.classification] ?? conviction.classification}
                status={CLASSIFICATION_STATUS[conviction.classification] ?? "muted"}
              />
              <StatusBadge
                label={CONFIDENCE_LABELS[conviction.confidence_label] ?? conviction.confidence_label}
                status={CONFIDENCE_STATUS[conviction.confidence_label] ?? "muted"}
              />
              <span className="text-sm font-semibold text-text-primary">
                Score: {Number(conviction.conviction_score).toFixed(1)} / 100
              </span>
            </div>
            {conviction.recommendation_hint && (
              <p className="mt-2 text-xs text-text-muted">{conviction.recommendation_hint}</p>
            )}
            <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-5">
              {[
                ["quality", conviction.quality],
                ["valuation", conviction.valuation],
                ["growth", conviction.growth],
                ["risk", conviction.risk],
                ["capital_reinvestment", conviction.capital_reinvestment],
              ].map(([key, value]) => (
                <div key={key as string} className="rounded-lg border border-border-soft bg-surface-hover p-2 text-center">
                  <div className="text-[10px] text-text-faint">{PILLAR_LABELS_PT[key as string]}</div>
                  <div className="text-sm font-semibold text-text-primary">
                    {value !== null ? Number(value).toFixed(1) : "—"}
                  </div>
                </div>
              ))}
            </div>
            {conviction.explanation.length > 0 && (
              <details className="mt-3 text-xs text-text-muted">
                <summary className="cursor-pointer text-text-primary">Motivos por pilar</summary>
                <div className="mt-2 space-y-2">
                  {conviction.explanation.map((pillar) => (
                    <div key={pillar.name}>
                      <div className="font-medium text-text-primary">{PILLAR_LABELS_PT[pillar.name] ?? pillar.name}</div>
                      {pillar.reasons.map((reason, idx) => (
                        <div key={idx}>· {reason}</div>
                      ))}
                    </div>
                  ))}
                </div>
              </details>
            )}
          </>
        )}
      </div>
    </div>
  );
}
