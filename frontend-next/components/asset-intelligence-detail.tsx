"use client";

import { useState } from "react";
import type { AssetIntelligence } from "@/lib/api";
import { CLASSIFICATION_LABELS_PT, CLASSIFICATION_STATUS, PILLAR_LABELS_PT } from "@/lib/adapt-intelligence";
import { StatusBadge } from "@/components/status-badge";

// "Por que esse ativo?" — Fase 5. Espelha `_why_this_asset()` de
// `pages_impl/inteligencia.py`: seletor de ativo + pilares do Conviction
// Score, motivos por pilar, pilar mais forte/mais fraco e pilares com
// confiança baixa. Nenhum cálculo aqui, só apresentação do que a API
// já devolve em `explanation`.
export function AssetIntelligenceDetail({ assets }: { assets: AssetIntelligence[] }) {
  const [selected, setSelected] = useState(assets[0]?.ticker ?? "");
  const asset = assets.find((a) => a.ticker === selected);

  return (
    <div>
      <select
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
        className="mb-4 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/20"
      >
        {assets.map((a) => (
          <option key={a.ticker} value={a.ticker}>
            {a.ticker}
          </option>
        ))}
      </select>

      {asset && (
        <div className="rounded-card border border-border bg-surface p-5 shadow-card">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-text-primary">{asset.ticker}</span>
            <span className="text-xs text-text-faint">({asset.asset_class})</span>
            <StatusBadge
              label={CLASSIFICATION_LABELS_PT[asset.classification ?? "insufficient_data"] ?? "Dados insuficientes"}
              status={CLASSIFICATION_STATUS[asset.classification ?? "insufficient_data"] ?? "muted"}
            />
            {asset.confidence_label && <StatusBadge label={asset.confidence_label} status="neutral" />}
          </div>

          {!asset.has_conviction_score ? (
            <p className="mt-3 text-sm text-text-muted">
              {asset.unavailable_reason ?? "Conviction Score indisponível para este ativo."}
            </p>
          ) : (
            <>
              <p className="mt-3 text-sm text-text-primary">
                <span className="font-medium">Conviction Score:</span> {Number(asset.conviction_score).toFixed(1)} / 100
              </p>
              {asset.recommendation_hint && (
                <p className="mt-2 rounded-lg border border-info/25 bg-info/[0.06] p-3 text-sm text-text-muted">
                  {asset.recommendation_hint}
                </p>
              )}

              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                {asset.explanation.map((pillar) => (
                  <div key={pillar.name} className="rounded-lg border border-border-soft bg-surface-hover p-3">
                    <div className="text-xs text-text-faint">{PILLAR_LABELS_PT[pillar.name] ?? pillar.name}</div>
                    <div className="mt-1 text-lg font-semibold text-text-primary">{Number(pillar.score).toFixed(1)}</div>
                  </div>
                ))}
              </div>

              <div className="mt-4 space-y-3">
                {asset.explanation.map((pillar) => (
                  <div key={pillar.name}>
                    <div className="text-xs font-medium text-text-primary">
                      {PILLAR_LABELS_PT[pillar.name] ?? pillar.name}
                    </div>
                    {pillar.reasons.map((reason, idx) => (
                      <div key={idx} className="text-xs text-text-faint">
                        · {reason}
                      </div>
                    ))}
                  </div>
                ))}
              </div>

              {asset.explanation.length > 0 && (
                <div className="mt-4 space-y-1.5 border-t border-border-soft pt-3 text-xs text-text-muted">
                  {(() => {
                    const strongest = asset.explanation.reduce((a, b) => (Number(b.score) > Number(a.score) ? b : a));
                    const weakest = asset.explanation.reduce((a, b) => (Number(b.score) < Number(a.score) ? b : a));
                    const lowConfidence = asset.explanation.filter((p) => Number(p.confidence) < 0.4);
                    return (
                      <>
                        <p>
                          Pilar mais forte hoje: {PILLAR_LABELS_PT[strongest.name] ?? strongest.name} (
                          {Number(strongest.score).toFixed(1)}) — perder força aqui é o que mais pioraria a nota.
                        </p>
                        <p>
                          Pilar mais fraco hoje: {PILLAR_LABELS_PT[weakest.name] ?? weakest.name} (
                          {Number(weakest.score).toFixed(1)}) — é o que, se melhorar, mais aumentaria a nota.
                        </p>
                        {lowConfidence.length > 0 && (
                          <p>
                            Pilares com confiança baixa:{" "}
                            {lowConfidence.map((p) => PILLAR_LABELS_PT[p.name] ?? p.name).join(", ")}.
                          </p>
                        )}
                      </>
                    );
                  })()}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
