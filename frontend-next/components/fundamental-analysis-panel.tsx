import type {
  IncomeRealEstateAnalysisResult,
  PortfolioAdequacyResult,
  TrapDetectionResult,
  ValuationV2Result,
} from "@/lib/api";
import {
  ADEQUACY_STATUS_KIND,
  ADEQUACY_STATUS_LABELS,
  INCOME_RE_STATUS_KIND,
  INCOME_RE_STATUS_LABELS,
  TRAP_SEVERITY_KIND,
  VALUATION_STATUS_KIND,
  VALUATION_STATUS_LABELS,
} from "@/lib/adapt-ativos";
import { StatusBadge } from "@/components/status-badge";

// Análise Fundamentalista — bloco condicional por classe (ações usam
// Valuation Engine 2.0, FII/REIT usam Análise de Renda Imobiliária,
// ETF/cripto/Tesouro usam Adequação à Política) + Trap Detection.
// Fase 6, espelha a seção "Análise Fundamentalista" de `pages_impl/ativos.py`.
export function FundamentalAnalysisPanel({
  valuationV2,
  incomeRealEstate,
  adequacy,
  trapDetection,
}: {
  valuationV2: ValuationV2Result | null;
  incomeRealEstate: IncomeRealEstateAnalysisResult | null;
  adequacy: PortfolioAdequacyResult | null;
  trapDetection: TrapDetectionResult | null;
}) {
  const hasAnyBlock = valuationV2 || incomeRealEstate || adequacy;

  return (
    <div className="rounded-card border border-border bg-surface p-5 shadow-card">
      <div className="mb-3 text-sm font-medium text-text-primary">Análise Fundamentalista</div>

      {!hasAnyBlock && (
        <p className="text-sm text-text-muted">
          Nenhuma análise específica disponível para este ativo (dados insuficientes).
        </p>
      )}

      {valuationV2 && (
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              label={VALUATION_STATUS_LABELS[valuationV2.valuation_status] ?? valuationV2.valuation_status}
              status={VALUATION_STATUS_KIND[valuationV2.valuation_status] ?? "muted"}
            />
            <span className="text-xs text-text-faint">confiança: {valuationV2.confidence}</span>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg border border-border-soft bg-surface-hover p-2">
              <div className="text-[10px] text-text-faint">Faixa baixa</div>
              <div className="text-sm font-semibold text-text-primary">
                {valuationV2.fair_value_range.low ?? "—"}
              </div>
            </div>
            <div className="rounded-lg border border-border-soft bg-surface-hover p-2">
              <div className="text-[10px] text-text-faint">Faixa base</div>
              <div className="text-sm font-semibold text-text-primary">
                {valuationV2.fair_value_range.base ?? "—"}
              </div>
            </div>
            <div className="rounded-lg border border-border-soft bg-surface-hover p-2">
              <div className="text-[10px] text-text-faint">Faixa alta</div>
              <div className="text-sm font-semibold text-text-primary">
                {valuationV2.fair_value_range.high ?? "—"}
              </div>
            </div>
          </div>
          {valuationV2.scenarios.length > 0 && (
            <div className="mt-3 space-y-1.5">
              {valuationV2.scenarios.map((scenario) => (
                <div key={scenario.label} className="text-xs">
                  <span className="font-medium text-text-primary">{scenario.label}: </span>
                  <span className="text-text-muted">{scenario.fair_value ?? "—"} — {scenario.assumptions}</span>
                  {scenario.reason && <span className="text-text-faint"> ({scenario.reason})</span>}
                </div>
              ))}
            </div>
          )}
          <p className="mt-2 text-xs text-text-muted">
            Preço atual: {valuationV2.current_price ?? "—"} · Margem de segurança:{" "}
            {valuationV2.margin_of_safety ?? "—"} (mínima exigida: {valuationV2.required_margin_of_safety ?? "—"})
          </p>
          {valuationV2.graham_sanity_check && (
            <p className="mt-1 text-xs text-text-faint">
              Graham: {valuationV2.graham_sanity_check}
              {valuationV2.graham_reason ? ` — ${valuationV2.graham_reason}` : ""}
            </p>
          )}
          {valuationV2.implied_expectation && (
            <p className="mt-1 text-xs text-text-faint">
              Expectativa implícita no preço: {valuationV2.implied_expectation}
              {valuationV2.implied_growth_rate ? ` (crescimento: ${valuationV2.implied_growth_rate})` : ""}
            </p>
          )}
          {valuationV2.warnings.length > 0 && (
            <ul className="mt-2 list-inside list-disc text-xs text-attention">
              {valuationV2.warnings.map((warning, idx) => (
                <li key={idx}>{warning}</li>
              ))}
            </ul>
          )}
          {valuationV2.reason && <p className="mt-1 text-xs text-text-faint">{valuationV2.reason}</p>}
        </div>
      )}

      {incomeRealEstate && (
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              label={INCOME_RE_STATUS_LABELS[incomeRealEstate.status] ?? incomeRealEstate.status}
              status={INCOME_RE_STATUS_KIND[incomeRealEstate.status] ?? "muted"}
            />
            <span className="text-xs text-text-faint">confiança: {incomeRealEstate.confidence}</span>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg border border-border-soft bg-surface-hover p-2">
              <div className="text-[10px] text-text-faint">P/VP</div>
              <div className="text-sm font-semibold text-text-primary">{incomeRealEstate.pvp ?? "—"}</div>
            </div>
            <div className="rounded-lg border border-border-soft bg-surface-hover p-2">
              <div className="text-[10px] text-text-faint">Dividend yield</div>
              <div className="text-sm font-semibold text-text-primary">
                {incomeRealEstate.dividend_yield ?? "—"}
              </div>
            </div>
            <div className="rounded-lg border border-border-soft bg-surface-hover p-2">
              <div className="text-[10px] text-text-faint">DY médio histórico</div>
              <div className="text-sm font-semibold text-text-primary">
                {incomeRealEstate.dy_own_history_average ?? "—"}
              </div>
            </div>
          </div>
          <p className="mt-2 text-xs text-text-muted">
            Estabilidade do DY: {incomeRealEstate.dy_stability}
            {incomeRealEstate.dy_stability_reason ? ` — ${incomeRealEstate.dy_stability_reason}` : ""}
          </p>
          {incomeRealEstate.warnings.length > 0 && (
            <ul className="mt-2 list-inside list-disc text-xs text-attention">
              {incomeRealEstate.warnings.map((warning, idx) => (
                <li key={idx}>{warning}</li>
              ))}
            </ul>
          )}
          {incomeRealEstate.reason && <p className="mt-1 text-xs text-text-faint">{incomeRealEstate.reason}</p>}
        </div>
      )}

      {adequacy && (
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              label={ADEQUACY_STATUS_LABELS[adequacy.adequacy_status] ?? adequacy.adequacy_status}
              status={ADEQUACY_STATUS_KIND[adequacy.adequacy_status] ?? "muted"}
            />
            {adequacy.extreme_overweight && <StatusBadge label="Sobrepeso extremo" status="critical" />}
          </div>
          <p className="mt-2 text-xs text-text-muted">{adequacy.valuation_note}</p>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className="rounded-lg border border-border-soft bg-surface-hover p-2 text-center">
              <div className="text-[10px] text-text-faint">Peso atual</div>
              <div className="text-sm font-semibold text-text-primary">{adequacy.current_weight ?? "—"}</div>
            </div>
            <div className="rounded-lg border border-border-soft bg-surface-hover p-2 text-center">
              <div className="text-[10px] text-text-faint">Peso alvo</div>
              <div className="text-sm font-semibold text-text-primary">{adequacy.target_weight ?? "—"}</div>
            </div>
            <div className="rounded-lg border border-border-soft bg-surface-hover p-2 text-center">
              <div className="text-[10px] text-text-faint">Faixa (min–max)</div>
              <div className="text-sm font-semibold text-text-primary">
                {adequacy.min_weight ?? "—"} – {adequacy.max_weight ?? "—"}
              </div>
            </div>
            <div className="rounded-lg border border-border-soft bg-surface-hover p-2 text-center">
              <div className="text-[10px] text-text-faint">Distância do alvo</div>
              <div className="text-sm font-semibold text-text-primary">{adequacy.gap_to_target ?? "—"}</div>
            </div>
          </div>
          {adequacy.alert_message && <p className="mt-2 text-xs text-attention">{adequacy.alert_message}</p>}
          {adequacy.warnings.length > 0 && (
            <ul className="mt-2 list-inside list-disc text-xs text-attention">
              {adequacy.warnings.map((warning, idx) => (
                <li key={idx}>{warning}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {trapDetection && trapDetection.flags.length > 0 && (
        <div className="mt-4 border-t border-border-soft pt-4">
          <div className="mb-2 text-xs font-medium text-text-primary">
            Armadilhas detectadas (penalidade de confiança: {trapDetection.confidence_penalty})
          </div>
          <div className="space-y-2">
            {trapDetection.flags.map((flag) => (
              <div key={flag.trap_type} className="rounded-lg border border-border-soft bg-surface-hover p-2.5">
                <div className="flex items-center gap-2">
                  <StatusBadge label={flag.label} status={TRAP_SEVERITY_KIND[flag.severity] ?? "attention"} />
                  <span className="text-xs text-text-faint">métrica afetada: {flag.affected_metric}</span>
                </div>
                <p className="mt-1 text-xs text-text-muted">{flag.explanation}</p>
                <p className="mt-1 text-xs text-text-faint">
                  Impacto: {flag.impact_on_score} · Interpretação recomendada: {flag.recommended_interpretation}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
      {trapDetection?.reason && <p className="mt-2 text-xs text-text-faint">{trapDetection.reason}</p>}
    </div>
  );
}
