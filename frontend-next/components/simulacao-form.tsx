"use client";

import { useState, type FormEvent } from "react";
import { Dices, Loader2 } from "lucide-react";
import { AlertCard } from "@/components/alert-card";
import { FormInput } from "@/components/form-controls";
import { MetricCard } from "@/components/metric-card";
import { SimulationPercentileChart } from "@/components/simulation-percentile-chart";
import { ErrorState } from "@/components/states";
import { ApiError, runSimulation } from "@/lib/api";
import type { SimulationResultView } from "@/lib/api";
import { buildMetricCards, orderedPercentiles } from "@/lib/adapt-simulacao";
import { cn } from "@/lib/utils";

/** SimulacaoForm — formulário + resultado do Monte Carlo Simulation
 * Engine (v1.1, Fase 8). Espelha `pages_impl/simulacao.py`: só coleta
 * input (aporte mensal, horizonte, nº de simulações, semente fixa) e
 * apresenta o que `POST /api/simulacao` devolve — nenhum percentil,
 * probabilidade de perda ou cenário é calculado aqui. Sempre uma
 * projeção probabilística, nunca uma previsão real de mercado nem
 * recomendação financeira (disclaimer fixo no topo da tela). */
export function SimulacaoForm() {
  const [monthlyContribution, setMonthlyContribution] = useState("1000");
  const [horizonYears, setHorizonYears] = useState("20");
  const [numSimulations, setNumSimulations] = useState("2000");
  const [reproducible, setReproducible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SimulationResultView | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const contribution = Number(monthlyContribution.replace(",", "."));
    const horizon = Number(horizonYears);
    const numSim = Number(numSimulations);

    if (!(contribution >= 0)) {
      setError("O aporte mensal presumido não pode ser negativo.");
      return;
    }
    if (!(horizon >= 1 && horizon <= 100)) {
      setError("O horizonte deve estar entre 1 e 100 anos.");
      return;
    }
    if (!(numSim >= 100 && numSim <= 20000)) {
      setError("O número de simulações deve estar entre 100 e 20.000.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await runSimulation({
        monthly_contribution: contribution.toFixed(2),
        horizon_years: horizon,
        num_simulations: numSim,
        reproducible,
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível rodar a simulação agora.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8 pb-12">
      <AlertCard
        title="Isto não é uma previsão"
        message="É uma projeção probabilística — não é uma previsão real de mercado nem recomendação financeira. As premissas de retorno/volatilidade por classe são editáveis em Configurações, e o resultado muda conforme essas hipóteses."
        severity="neutral"
      />

      <form
        onSubmit={handleSubmit}
        className="space-y-5 rounded-card border border-border bg-surface p-5 shadow-card"
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <FormInput
            id="sim-monthly-contribution"
            label="Aporte mensal presumido (R$)"
            inputMode="decimal"
            value={monthlyContribution}
            onChange={(event) => setMonthlyContribution(event.target.value)}
          />
          <FormInput
            id="sim-horizon-years"
            label="Horizonte (anos)"
            type="number"
            min={1}
            max={100}
            value={horizonYears}
            onChange={(event) => setHorizonYears(event.target.value)}
          />
          <FormInput
            id="sim-num-simulations"
            label="Nº de simulações"
            type="number"
            min={100}
            max={20000}
            step={100}
            value={numSimulations}
            onChange={(event) => setNumSimulations(event.target.value)}
          />
        </div>

        <label className="flex items-center gap-2 text-sm text-text-muted">
          <input
            type="checkbox"
            checked={reproducible}
            onChange={(event) => setReproducible(event.target.checked)}
            className="h-4 w-4 rounded border-border bg-surface accent-primary"
          />
          Usar semente fixa (resultado reproduzível)
        </label>
        <p className="-mt-3 text-xs text-text-faint">
          Sem isso, cada execução sorteia trajetórias diferentes.
        </p>

        <button
          type="submit"
          disabled={loading}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg bg-gradient-primary px-4 py-2.5 text-sm font-medium text-white shadow-glow transition-opacity hover:opacity-90",
            loading && "opacity-60",
          )}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Dices className="h-4 w-4" strokeWidth={1.75} />}
          {loading ? "Rodando simulação..." : "Rodar simulação"}
        </button>
      </form>

      {error && <ErrorState message={error} />}

      {result && <SimulacaoResult result={result} />}
    </div>
  );
}

function SimulacaoResult({ result }: { result: SimulationResultView }) {
  const cards = buildMetricCards(result);
  const percentiles = orderedPercentiles(result.percentiles);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="mb-3 text-sm font-medium text-text-primary">
          <span className="mr-1.5">🎲</span>
          Resultado da simulação
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {cards.map((card) => (
            <MetricCard key={card.label} label={card.label} value={card.value} status={card.status} />
          ))}
        </div>
        <p className="mt-3 text-xs text-text-faint">
          Probabilidade de perda: fração das simulações que terminaram abaixo do total efetivamente aportado.
        </p>
      </div>

      {result.num_simulations > 0 && (
        <>
          <SimulationPercentileChart percentiles={result.percentiles} />

          <div className="rounded-card border border-border bg-surface shadow-card">
            <div className="scrollbar-thin overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-soft text-left text-xs text-text-faint">
                    <th className="px-5 py-2.5 font-medium">Percentil</th>
                    <th className="px-5 py-2.5 text-right font-medium">Valor projetado</th>
                  </tr>
                </thead>
                <tbody>
                  {percentiles.map((p) => (
                    <tr key={p.key} className="border-b border-border-soft/60 last:border-0">
                      <td className="px-5 py-3 text-text-muted">{p.label}</td>
                      <td className="px-5 py-3 text-right font-medium text-text-primary">
                        {new Intl.NumberFormat("pt-BR", {
                          style: "currency",
                          currency: "BRL",
                          maximumFractionDigits: 2,
                        }).format(Number(p.value))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      <details className="rounded-lg border border-border-soft bg-surface-hover px-4 py-3 text-sm text-text-muted">
        <summary className="cursor-pointer select-none font-medium text-text-primary">
          Premissas e simplificações usadas
        </summary>
        <div className="mt-2 space-y-1">
          {result.reasons.map((reason) => (
            <p key={reason}>· {reason}</p>
          ))}
        </div>
      </details>

      {result.warnings.map((warning) => (
        <AlertCard key={warning} title="Atenção" message={warning} severity="attention" />
      ))}
    </div>
  );
}
