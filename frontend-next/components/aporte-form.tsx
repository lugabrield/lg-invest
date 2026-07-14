"use client";

import { useState, type FormEvent } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { AlertCard } from "@/components/alert-card";
import { BeforeAfterBarChart } from "@/components/before-after-bar-chart";
import { FormInput } from "@/components/form-controls";
import { MetricCard } from "@/components/metric-card";
import { RecommendationCard } from "@/components/recommendation-card";
import { EmptyState, ErrorState } from "@/components/states";
import { ApiError, simulateAporte } from "@/lib/api";
import type { AporteBundle, AssetSummary, EngineVersion, RecommendationItem } from "@/lib/api";
import {
  adaptCappedDimension,
  adaptIgnoredItem,
  adaptProjectionSummary,
  adaptRecommendationItem,
} from "@/lib/adapt-aporte";
import { formatBRL } from "@/lib/format";
import { cn } from "@/lib/utils";

const ENGINE_OPTIONS: { value: EngineVersion; label: string; help: string }[] = [
  {
    value: "v1",
    label: "v1",
    help: "LG Score + gap de alocação por classe + concentração (padrão, inalterado).",
  },
  {
    value: "v2",
    label: "v2",
    help: "Prioriza o LG Conviction Score quando calculável, com bônus por classe subalocada.",
  },
  {
    value: "v3",
    label: "v3",
    help: "Score multi-fator (fundamentos + alocação-alvo + concentração + internacionalização), respeita os bloqueios da Política de Investimento e da Alocação-alvo — nenhuma versão jamais recomenda venda.",
  },
];

interface AporteFormProps {
  assets: AssetSummary[];
}

/** AporteForm — formulário + resultado da simulação de aporte (v1.1,
 * Fase 3). Espelha `frontend/streamlit_app/pages_impl/aporte.py`: só
 * coleta input e apresenta o que `POST /api/aporte` devolve — nenhuma
 * regra de decisão é recalculada aqui. */
export function AporteForm({ assets }: AporteFormProps) {
  const [amount, setAmount] = useState("1000");
  const [blocked, setBlocked] = useState<Set<string>>(new Set());
  const [engineVersion, setEngineVersion] = useState<EngineVersion>("v3");
  const [persist, setPersist] = useState(true);
  const [allowWatchlist, setAllowWatchlist] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bundle, setBundle] = useState<AporteBundle | null>(null);

  function toggleBlocked(ticker: string) {
    setBlocked((prev) => {
      const next = new Set(prev);
      if (next.has(ticker)) next.delete(ticker);
      else next.add(ticker);
      return next;
    });
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const parsedAmount = Number(amount.replace(",", "."));
    if (!parsedAmount || parsedAmount <= 0) {
      setError("O valor do aporte deve ser positivo.");
      setBundle(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await simulateAporte({
        amount: parsedAmount.toFixed(2),
        blocked: Array.from(blocked),
        engine_version: engineVersion,
        persist,
        allow_watchlist_candidates: engineVersion === "v3" ? allowWatchlist : false,
      });
      setBundle(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível gerar a recomendação agora.");
      setBundle(null);
    } finally {
      setLoading(false);
    }
  }

  if (assets.length === 0) {
    return (
      <EmptyState
        title="Nenhum ativo cadastrado ainda"
        message="Cadastre ativos e importe sua carteira na tela Carteira antes de simular um aporte — sem ativos, não há nada para recomendar."
      />
    );
  }

  const activeEngine = ENGINE_OPTIONS.find((option) => option.value === engineVersion)!;

  return (
    <div className="space-y-8 pb-12">
      <form
        onSubmit={handleSubmit}
        className="space-y-5 rounded-card border border-border bg-surface p-5 shadow-card"
      >
        <FormInput
          id="aporte-amount"
          label="Valor do aporte (R$)"
          inputMode="decimal"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />

        {assets.length > 0 && (
          <div>
            <div className="mb-1.5 text-xs font-medium text-text-muted">Ativos bloqueados (opcional)</div>
            <div className="flex flex-wrap gap-1.5">
              {assets.map((asset) => {
                const isBlocked = blocked.has(asset.ticker);
                return (
                  <button
                    key={asset.ticker}
                    type="button"
                    onClick={() => toggleBlocked(asset.ticker)}
                    className={cn(
                      "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                      isBlocked
                        ? "border-critical/40 bg-critical/10 text-critical"
                        : "border-border bg-surface-hover text-text-muted hover:text-text-primary",
                    )}
                  >
                    {asset.ticker}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div>
          <div className="mb-1.5 text-xs font-medium text-text-muted">Motor de recomendação</div>
          <div className="flex gap-1.5">
            {ENGINE_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setEngineVersion(option.value)}
                className={cn(
                  "rounded-lg border px-3.5 py-1.5 text-sm font-medium transition-colors",
                  engineVersion === option.value
                    ? "border-primary/40 bg-primary/10 text-text-primary"
                    : "border-border bg-surface-hover text-text-muted hover:text-text-primary",
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-xs text-text-faint">{activeEngine.help}</p>
        </div>

        <div className="flex flex-wrap items-center gap-5">
          <label className="flex items-center gap-2 text-sm text-text-muted">
            <input
              type="checkbox"
              checked={persist}
              onChange={(event) => setPersist(event.target.checked)}
              className="h-4 w-4 rounded border-border bg-surface accent-primary"
            />
            Salvar recomendação (auditoria)
          </label>

          {engineVersion === "v3" && (
            <label className="flex items-center gap-2 text-sm text-text-muted">
              <input
                type="checkbox"
                checked={allowWatchlist}
                onChange={(event) => setAllowWatchlist(event.target.checked)}
                className="h-4 w-4 rounded border-border bg-surface accent-primary"
              />
              Permitir ativos novos da watchlist
            </label>
          )}
        </div>

        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-gradient-primary px-4 py-2.5 text-sm font-medium text-white shadow-glow transition-opacity hover:opacity-90 disabled:opacity-60"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" strokeWidth={1.75} />}
          Gerar recomendação
        </button>
      </form>

      {error && <ErrorState message={error} />}

      {bundle && <AporteResult bundle={bundle} requestedAmount={amount} />}
    </div>
  );
}

function AporteResult({ bundle, requestedAmount }: { bundle: AporteBundle; requestedAmount: string }) {
  const { result, projection } = bundle;
  const heldItems = result.items.filter((item) => !item.is_new_from_watchlist);
  const newItems = result.items.filter((item) => item.is_new_from_watchlist);
  const requested = Number(requestedAmount.replace(",", "."));
  const allocated = Number(result.allocated_amount);
  const projectionSummary = projection ? adaptProjectionSummary(projection) : null;

  return (
    <div className="space-y-8">
      <div className="rounded-card border border-border bg-surface p-5 shadow-card">
        <div className="mb-1 text-sm font-medium text-text-primary">Resultado da recomendação</div>
        <p className="text-sm text-text-muted">{result.explanation}</p>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <MetricCard label="Alocado" value={formatBRL(allocated)} status="positive" />
          <MetricCard label="Confiança" value={result.confidence_label} status="neutral" />
        </div>
        {allocated < requested && (
          <p className="mt-3 text-xs text-text-faint">
            O Decision Engine ainda tem alcance limitado no MVP: nem todo o valor informado necessariamente é
            distribuído — veja &quot;Ativos evitados&quot; abaixo.
          </p>
        )}
      </div>

      {result.items.length > 0 && (
        <>
          {newItems.length > 0 ? (
            <>
              <ResultSection title="Recomendações principais" icon="📌">
                {heldItems.length > 0 ? (
                  heldItems.map((item) => <RecommendationItemCard key={item.ticker} item={item} />)
                ) : (
                  <p className="text-sm text-text-muted">
                    Nenhum ativo já existente na carteira entrou nesta recomendação.
                  </p>
                )}
              </ResultSection>

              <ResultSection title="Novos candidatos (Watchlist)" icon="🆕">
                <p className="mb-3 text-sm text-text-muted">
                  Estes ativos ainda não são posição na sua carteira. A recomendação aqui é só para você{" "}
                  <strong className="text-text-primary">considerar iniciar uma posição pequena</strong> — nada é
                  comprado ou registrado automaticamente.
                </p>
                {newItems.map((item) => (
                  <RecommendationItemCard key={item.ticker} item={item} />
                ))}
              </ResultSection>
            </>
          ) : (
            <ResultSection title="Recomendações principais" icon="📥">
              {result.items.map((item) => (
                <RecommendationItemCard key={item.ticker} item={item} />
              ))}
            </ResultSection>
          )}
        </>
      )}

      {result.alerts.map((alert) => (
        <AlertCard key={alert} title="Atenção" message={alert} severity="attention" />
      ))}

      {result.capped_dimensions.length > 0 && (
        <ResultSection title="Limites pós-aporte atingidos" icon="🚧">
          <p className="mb-3 text-sm text-text-muted">
            Estas dimensões ultrapassariam o limite máximo configurado se o aporte fosse distribuído sem ajuste. O
            valor foi cortado para respeitar o limite — o restante não foi forçado em outro lugar só para chegar em
            100% do aporte; ficou como saldo não alocado.
          </p>
          <CappedDimensionsTable capped={result.capped_dimensions} />
        </ResultSection>
      )}

      {result.ignored.length > 0 && (
        <ResultSection title="Ativos evitados" icon="🚫">
          <IgnoredTable ignored={result.ignored} />
        </ResultSection>
      )}

      {projectionSummary && projection && (
        <ResultSection title="Como a carteira ficaria depois" icon="🔄">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <MetricCard label="Patrimônio antes" value={projectionSummary.totalBefore} status="neutral" />
            <MetricCard label="Patrimônio depois" value={projectionSummary.totalAfter} status="positive" />
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <MetricCard
              label="Concentração (HHI)"
              value={projectionSummary.hhiAfter}
              delta={`${projectionSummary.hhiDelta >= 0 ? "+" : ""}${projectionSummary.hhiDelta.toFixed(3)}`}
              status={projectionSummary.hhiDelta <= 0 ? "positive" : "attention"}
            />
            <MetricCard
              label="Exposição internacional"
              value={projectionSummary.internationalAfter}
              delta={`${projectionSummary.internationalDeltaPp >= 0 ? "+" : ""}${projectionSummary.internationalDeltaPp.toFixed(2)} p.p.`}
              status="neutral"
            />
          </div>
          <div className="mt-4">
            <BeforeAfterBarChart title="Peso por classe: antes x depois" data={projectionSummary.byGroup} />
          </div>
        </ResultSection>
      )}
    </div>
  );
}

function ResultSection({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="mb-3 text-sm font-medium text-text-primary">
        <span className="mr-1.5">{icon}</span>
        {title}
      </h2>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function RecommendationItemCard({ item }: { item: RecommendationItem }) {
  const view = adaptRecommendationItem(item);
  return (
    <div>
      <RecommendationCard
        ticker={view.ticker}
        amount={view.amount}
        weightLabel={view.weightLabel}
        reason={view.reason}
        tag={view.tag}
        scoreBadges={view.scoreBadges}
      />
      {view.watchlistReason && <p className="mt-1.5 text-xs text-text-faint">🆕 {view.watchlistReason}</p>}
      {(view.extraReasons.length > 0 || view.scoreBreakdown.length > 0) && (
        <details className="mt-1.5 rounded-lg border border-border-soft bg-surface-hover px-3 py-2 text-xs text-text-muted">
          <summary className="cursor-pointer select-none font-medium text-text-primary">
            Ver detalhes técnicos — {view.ticker}
          </summary>
          <div className="mt-2 space-y-1">
            {view.extraReasons.map((reason) => (
              <p key={reason}>· {reason}</p>
            ))}
            {view.scoreBreakdown.map((factor) => (
              <div key={factor.label} className="flex items-center justify-between">
                <span>{factor.label}</span>
                <span className={cn("font-medium", factor.contribution >= 0 ? "text-positive" : "text-text-muted")}>
                  {factor.contribution >= 0 ? "+" : ""}
                  {factor.contribution.toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function CappedDimensionsTable({ capped }: { capped: AporteBundle["result"]["capped_dimensions"] }) {
  return (
    <div className="rounded-card border border-border bg-surface shadow-card">
      <div className="scrollbar-thin overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-soft text-left text-xs text-text-faint">
              <th className="px-5 py-2.5 font-medium">Dimensão</th>
              <th className="px-5 py-2.5 font-medium">Item</th>
              <th className="px-5 py-2.5 text-right font-medium">Atual</th>
              <th className="px-5 py-2.5 text-right font-medium">Depois</th>
              <th className="px-5 py-2.5 text-right font-medium">Limite</th>
              <th className="px-5 py-2.5 font-medium">Origem</th>
              <th className="px-5 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {capped.map((cd) => {
              const view = adaptCappedDimension(cd);
              return (
                <tr key={`${cd.dimension_type}-${cd.dimension_key}`} className="border-b border-border-soft/60 last:border-0">
                  <td className="px-5 py-3 text-text-muted">{view.dimensionLabel}</td>
                  <td className="px-5 py-3 font-medium text-text-primary">{view.item}</td>
                  <td className="px-5 py-3 text-right text-text-muted">{view.before}</td>
                  <td className="px-5 py-3 text-right text-text-muted">{view.after}</td>
                  <td className="px-5 py-3 text-right text-text-muted">{view.maxWeight}</td>
                  <td className="px-5 py-3 text-text-muted">{view.sourceLabel}</td>
                  <td
                    className={cn(
                      "px-5 py-3 font-medium",
                      view.status === "Limite atingido" ? "text-critical" : "text-positive",
                    )}
                  >
                    {view.status}
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

function IgnoredTable({ ignored }: { ignored: AporteBundle["result"]["ignored"] }) {
  return (
    <div className="rounded-card border border-border bg-surface shadow-card">
      <div className="scrollbar-thin overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-soft text-left text-xs text-text-faint">
              <th className="px-5 py-2.5 font-medium">Ticker</th>
              <th className="px-5 py-2.5 font-medium">Origem do bloqueio</th>
              <th className="px-5 py-2.5 font-medium">Motivo</th>
            </tr>
          </thead>
          <tbody>
            {ignored.map((item) => {
              const view = adaptIgnoredItem(item);
              return (
                <tr key={view.ticker} className="border-b border-border-soft/60 last:border-0">
                  <td className="px-5 py-3 font-medium text-text-primary">{view.ticker}</td>
                  <td className="px-5 py-3 text-text-muted">{view.blockSourceLabel}</td>
                  <td className="px-5 py-3 text-text-muted">{view.reason}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
