import type { RadarClassificationResult, WatchlistAssetView } from "@/lib/api";
import { CLASSIFICATION_LABELS_PT, formatConfidencePct, formatDateTime, formatScore } from "@/lib/adapt-radar";
import { StatusPill } from "@/components/watchlist-summary";
import { WatchlistRowActions } from "@/components/watchlist-row-actions";

// Ativos na Watchlist — Fase 7. Espelha a tabela + ações de
// `pages_impl/radar.py`, mas sem o seletor único do Streamlit: cada
// linha já traz suas próprias ações (coletar, mudar status, remover).
export function WatchlistTable({
  entries,
  radarByTicker,
}: {
  entries: WatchlistAssetView[];
  radarByTicker: Map<string, RadarClassificationResult>;
}) {
  return (
    <div className="rounded-card border border-border bg-surface shadow-card">
      <div className="scrollbar-thin overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-soft text-left text-xs text-text-faint">
              <th className="px-4 py-2.5 font-medium">Ticker</th>
              <th className="px-4 py-2.5 font-medium">Nome</th>
              <th className="px-4 py-2.5 font-medium">Classe</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 text-right font-medium">Prioridade</th>
              <th className="px-4 py-2.5 font-medium">Já na carteira?</th>
              <th className="px-4 py-2.5 text-right font-medium">Score</th>
              <th className="px-4 py-2.5 text-right font-medium">Confiança</th>
              <th className="px-4 py-2.5 font-medium">Classificação do Radar</th>
              <th className="px-4 py-2.5 font-medium">Última coleta</th>
              <th className="px-4 py-2.5 font-medium">Ações</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const radar = radarByTicker.get(entry.ticker);
              return (
                <tr key={entry.id} className="border-b border-border-soft/60 align-top last:border-0">
                  <td className="px-4 py-3 font-medium text-text-primary">{entry.ticker}</td>
                  <td className="px-4 py-3 text-text-muted">{entry.name}</td>
                  <td className="px-4 py-3 text-text-muted">
                    {entry.asset_class} · {entry.country}/{entry.currency}
                  </td>
                  <td className="px-4 py-3">
                    <StatusPill status={entry.status} />
                  </td>
                  <td className="px-4 py-3 text-right text-text-primary">{entry.priority}</td>
                  <td className="px-4 py-3 text-text-muted">{entry.already_in_portfolio ? "Sim" : "Não"}</td>
                  <td className="px-4 py-3 text-right text-text-primary">
                    {formatScore(radar?.effective_score ?? null)}
                  </td>
                  <td className="px-4 py-3 text-right text-text-muted">
                    {formatConfidencePct(radar?.confidence ?? null)}
                  </td>
                  <td className="px-4 py-3 text-text-muted">
                    {radar ? CLASSIFICATION_LABELS_PT[radar.classification] ?? radar.classification : "—"}
                  </td>
                  <td className="px-4 py-3 text-text-faint">{formatDateTime(entry.last_collected_at)}</td>
                  <td className="px-4 py-3">
                    <WatchlistRowActions entry={entry} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
