// Cliente HTTP para a API FastAPI (v1.1, Fase 2 — ver docs/API_CONTRACT.md).
// Nenhum cálculo acontece aqui: os tipos abaixo espelham 1:1 os schemas
// Pydantic (`backend/app/schemas/*`) devolvidos por `GET /api/dashboard`.
// Valores monetários/percentuais chegam como string (Decimal serializado),
// nunca float — a conversão para número só acontece na apresentação
// (`lib/adapt-dashboard.ts`), nunca recalculando nada.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ConvertedPosition {
  ticker: string;
  asset_class: string;
  currency: string;
  quantity: string;
  average_price: string;
  current_price: string;
  position_value: string;
  position_value_brl: string;
  weight: string; // fração 0..1
  return_pct: string | null; // fração
  is_price_estimated: boolean;
  group_label: string;
  price_source: string;
  price_updated_at: string | null;
}

export interface CurrencyExposure {
  currency: string;
  value_brl: string;
  weight: string; // fração 0..1
}

export interface DashboardView {
  exchange_rate: string;
  total_brl: string;
  total_usd: string;
  total_converted_brl: string;
  total_cost_brl: string;
  total_return_pct: string | null;
  is_multi_currency: boolean;
  currency_exposure: CurrencyExposure[];
  positions: ConvertedPosition[];
  largest_position_ticker: string | null;
  concentration_hhi: string;
  effective_number_of_assets: string | null;
  estimated_price_tickers: string[];
  manual_price_tickers: string[];
  unpriced_tickers: string[];
}

export interface DiagnosticInsight {
  code: string;
  severity: "positive" | "info" | "attention" | "alert";
  title: string;
  message: string;
}

export interface PortfolioDiagnostics {
  insights: DiagnosticInsight[];
}

export interface HealthFactorView {
  name: string;
  available: boolean;
  raw_value: string | null;
  score: string | null;
  weight_used: string;
  reason: string;
}

export interface PortfolioHealthResultView {
  model_version: string;
  overall_score: string;
  overall_classification: string;
  factors: HealthFactorView[];
  reasons: string[];
  warnings: string[];
}

export interface RiskFactorView {
  name: string;
  available: boolean;
  raw_value: string | null;
  score: string | null;
  classification: string | null;
  weight_used: string;
  reason: string;
}

export interface PortfolioRiskResultView {
  model_version: string;
  overall_score: string;
  overall_classification: string;
  factors: RiskFactorView[];
  declared_risk_tolerance: string | null;
  tolerance_alert: string | null;
  reasons: string[];
  warnings: string[];
}

export interface LastRefreshStatus {
  prices_at: string | null;
  fundamentals_at: string | null;
  watchlist_at: string | null;
  valuation_at: string | null;
  trap_detection_at: string | null;
}

// Os tipos completos de `intelligence` e `data_quality` ainda não são
// consumidos pelo Dashboard — ficam como `unknown` até a Fase 4/6 os usar,
// para não travar o build por causa de um shape parcial.
export interface DashboardBundle {
  view: DashboardView;
  diagnostics: PortfolioDiagnostics;
  intelligence: unknown;
  data_quality: unknown;
  health: PortfolioHealthResultView;
  risk: PortfolioRiskResultView;
  data_refresh_status: LastRefreshStatus;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function fetchDashboard(portfolioId = 1): Promise<DashboardBundle> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/dashboard?portfolio_id=${portfolioId}`, {
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Não foi possível conectar à API em ${API_URL}. Ela está rodando? (uvicorn backend.app.api.app:app --reload --port 8000)`,
    );
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // resposta sem corpo JSON — usa o statusText mesmo
    }
    throw new ApiError(detail, response.status);
  }

  return response.json();
}

// --- Aporte (v1.1, Fase 3) — espelha 1:1 backend/app/schemas/recommendation_result.py,
// backend/app/schemas/allocation_projection.py e backend/app/schemas/aporte_bundle.py.
// Mesma regra do Dashboard: Decimal sempre como string, conversão para
// número só na apresentação (`lib/adapt-aporte.ts`).

export interface ScoreFactor {
  label: string;
  weight: string | null;
  value: string;
  contribution: string;
}

export interface RecommendationItem {
  ticker: string;
  amount: string;
  weight: string; // fração do aporte
  buy_score: string;
  lg_score: string;
  conviction_score: string | null;
  item_confidence: string | null;
  reasons: string[];
  score_breakdown: ScoreFactor[];
  is_new_from_watchlist: boolean;
  watchlist_reason: string | null;
}

export interface CappedDimensionResult {
  dimension_type: string;
  dimension_key: string;
  label: string;
  weight_before: string;
  weight_after: string;
  max_weight: string;
  source: string;
}

export interface IgnoredItem {
  ticker: string;
  reason: string;
  block_source: string | null;
}

export interface DecisionAudit {
  contribution_amount: string;
  eligible_tickers: string[];
  blocked_tickers: string[];
  model_version: string;
  weights: Record<string, number>;
}

export interface RecommendationResult {
  contribution_amount: string;
  allocated_amount: string;
  items: RecommendationItem[];
  ignored: IgnoredItem[];
  alerts: string[];
  confidence: string;
  confidence_label: string;
  explanation: string;
  audit: DecisionAudit;
  capped_dimensions: CappedDimensionResult[];
}

export interface WeightComparison {
  label: string;
  weight_before: string;
  weight_after: string;
}

export interface AllocationProjection {
  contribution_amount: string;
  total_before_brl: string;
  total_after_brl: string;
  by_group: WeightComparison[];
  by_currency: WeightComparison[];
  concentration_hhi_before: string;
  concentration_hhi_after: string;
  international_weight_before: string;
  international_weight_after: string;
}

export interface AporteBundle {
  result: RecommendationResult;
  projection: AllocationProjection | null;
}

export interface AssetSummary {
  ticker: string;
  name: string;
  asset_class: string;
}

export type EngineVersion = "v1" | "v2" | "v3";

export interface AporteRequestPayload {
  amount: string;
  blocked?: string[];
  engine_version?: EngineVersion;
  persist?: boolean;
  allow_watchlist_candidates?: boolean;
}

export async function fetchAssets(): Promise<AssetSummary[]> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/assets`, { cache: "no-store" });
  } catch {
    throw new ApiError(
      `Não foi possível conectar à API em ${API_URL}. Ela está rodando? (uvicorn backend.app.api.app:app --reload --port 8000)`,
    );
  }
  if (!response.ok) {
    throw new ApiError(response.statusText, response.status);
  }
  return response.json();
}

export async function simulateAporte(
  payload: AporteRequestPayload,
  portfolioId = 1,
): Promise<AporteBundle> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/aporte?portfolio_id=${portfolioId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Não foi possível conectar à API em ${API_URL}. Ela está rodando? (uvicorn backend.app.api.app:app --reload --port 8000)`,
    );
  }

  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // resposta sem corpo JSON — usa o statusText mesmo
    }
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), response.status);
  }

  return response.json();
}

// --- Carteira (v1.1, Fase 4) — a leitura (posições, pesos, grupos) não
// tem endpoint próprio: já vem de `fetchDashboard()` (`view.positions`).
// Só a importação de arquivo é nova aqui, espelhando
// backend/app/schemas/portfolio_import.py.

export interface ImportErrorView {
  line: number;
  field: string | null;
  message: string;
}

export interface ImportResultView {
  total_rows: number;
  imported: number;
  updated: number;
  skipped: number;
  errors: ImportErrorView[];
}

export async function importPortfolio(file: File, portfolioId = 1): Promise<ImportResultView> {
  const formData = new FormData();
  formData.append("file", file);

  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/portfolio/import?portfolio_id=${portfolioId}`, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new ApiError(
      `Não foi possível conectar à API em ${API_URL}. Ela está rodando? (uvicorn backend.app.api.app:app --reload --port 8000)`,
    );
  }

  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // resposta sem corpo JSON — usa o statusText mesmo
    }
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), response.status);
  }

  return response.json();
}

// --- Inteligência (v1.1, Fase 5) — espelha 1:1
// backend/app/schemas/intelligence_dashboard.py, ids_methodology.py,
// target_allocation.py e income_analysis.py (via
// backend/app/schemas/intelligence_bundle.py). Nenhum cálculo novo:
// buckets/rankings/rótulos ficam em lib/adapt-intelligence.ts.

export interface ConvictionPillarResult {
  name: string;
  score: string; // 0..100
  confidence: string; // fração 0..1
  reasons: string[];
}

export interface AssetIntelligence {
  ticker: string;
  asset_class: string;
  current_weight: string; // fração 0..1
  has_conviction_score: boolean;
  conviction_score: string | null;
  classification: string | null;
  confidence: string | null;
  confidence_label: string | null;
  quality: string | null;
  valuation: string | null;
  growth: string | null;
  risk: string | null;
  capital_reinvestment: string | null;
  recommendation_hint: string;
  explanation: ConvictionPillarResult[];
  unavailable_reason: string | null;
}

export interface AllocationClassDrift {
  asset_class: string;
  current_pct: string; // fração 0..1
  target_pct: string; // fração 0..1
  drift_pct: string;
  status: string; // "abaixo" | "dentro" | "acima"
}

export interface TargetAllocationResult {
  has_target: boolean;
  classes: AllocationClassDrift[];
  most_underweight_class: string | null;
  reason: string | null;
}

export interface IntelligenceDashboardView {
  assets: AssetIntelligence[];
  average_conviction_score: string | null;
  coverage_pct: string; // fração 0..1
  classification_counts: Record<string, number>;
  most_convicted: AssetIntelligence | null;
  least_convicted: AssetIntelligence | null;
  allocation_drift: TargetAllocationResult;
}

export interface MonthlyPointView {
  year: number;
  month: number;
  amount_total: string;
}

export interface PortfolioIncomeTrendView {
  ttm_total: string;
  prior_ttm_total: string;
  growth_pct: string | null; // fração
  monthly_series: MonthlyPointView[];
  projected_next_12_months: string;
  months_with_data_ttm: number;
  months_with_data_prior_ttm: number;
  reason: string;
}

export interface TickerIncomeRowView {
  ticker: string;
  ttm_income: string;
  cost_basis: string | null;
  yield_on_cost: string | null; // fração
}

export interface TickerIncomeBreakdownView {
  rows: TickerIncomeRowView[];
  concentration_hhi: string | null;
  portfolio_yield_on_cost: string | null; // fração
  excluded_tickers_without_position: string[];
  reason: string;
}

export interface IncomeAnalysisResultView {
  model_version: string;
  trend: PortfolioIncomeTrendView;
  breakdown: TickerIncomeBreakdownView;
  reasons: string[];
  warnings: string[];
}

export interface IntelligenceBundle {
  view: IntelligenceDashboardView;
  income: IncomeAnalysisResultView;
}

export async function fetchIntelligence(portfolioId = 1): Promise<IntelligenceBundle> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/intelligence?portfolio_id=${portfolioId}`, {
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Não foi possível conectar à API em ${API_URL}. Ela está rodando? (uvicorn backend.app.api.app:app --reload --port 8000)`,
    );
  }

  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // resposta sem corpo JSON — usa o statusText mesmo
    }
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), response.status);
  }

  return response.json();
}

// --- Ativos (v1.1, Fase 6) — espelha 1:1 backend/app/schemas/asset_row.py,
// asset_detail.py, asset_actions.py e os schemas de cada engine (LG
// Score, Conviction Score v2, Data Quality, Fundamentos, Valuation v1/v2,
// Análise de Renda Imobiliária, Adequação à Política, Trap Detection,
// Cobertura de Dados). Nenhum cálculo novo — tudo já vem pronto da API.

export interface AssetRowView {
  ticker: string;
  name: string;
  asset_class: string;
  country: string;
  currency: string;
  sector: string | null;
  price: string | null;
  price_status: "automatic" | "manual" | "missing";
  is_manual: boolean;
  updated_at: string | null;
}

export interface PillarResult {
  name: string;
  score: string; // 0..100
  confidence: string; // fração 0..1
  reasons: string[];
}

export interface LGScoreResult {
  ticker: string;
  lg_score: string;
  quality: string;
  valuation: string;
  growth: string;
  risk: string;
  allocation: string;
  confidence: string;
  confidence_label: string;
  classification: string;
  model_version: string;
  explanation: PillarResult[];
}

export interface ConvictionScoreResult {
  ticker: string;
  conviction_score: string; // 0..100
  quality: string;
  valuation: string;
  growth: string;
  risk: string;
  capital_reinvestment: string;
  confidence: string; // 0..1
  confidence_label: string;
  classification: string;
  recommendation_hint: string;
  model_version: string;
  explanation: ConvictionPillarResult[];
}

export interface AssetDataQuality {
  ticker: string;
  asset_class: string;
  price_status: string;
  fundamentals_status: string;
  fundamentals_fields_available: number;
  fundamentals_fields_total: number;
  valuation_status: string;
  score_confidence: string;
  issues: string[];
}

export interface FundamentalSnapshotResult {
  ticker: string;
  period_end: string;
  source: string;
  collected_at: string;
  roe: string | null;
  roa: string | null;
  net_margin: string | null;
  ebitda_margin: string | null;
  revenue: string | null;
  net_income: string | null;
  ebitda: string | null;
  ebit: string | null;
  free_cash_flow: string | null;
  net_debt: string | null;
  debt_to_ebitda: string | null;
  pe_ratio: string | null;
  pb_ratio: string | null;
  ev_ebitda: string | null;
  dividend_yield: string | null;
  payout_ratio: string | null;
  eps: string | null;
  revenue_per_share: string | null;
  beta: string | null;
  market_cap: string | null;
  enterprise_value: string | null;
  forward_pe: string | null;
  operating_margin: string | null;
  total_debt: string | null;
  total_cash: string | null;
  operating_cash_flow: string | null;
  gross_profit: string | null;
  shares_outstanding: string | null;
  total_equity: string | null;
  roic: string | null;
  interest_coverage: string | null;
}

export interface FundamentalsAnalysisResult {
  ticker: string;
  periods_used: number;
  revenue_cagr: string | null;
  revenue_cagr_reason: string | null;
  net_income_cagr: string | null;
  net_income_cagr_reason: string | null;
  ebitda_cagr: string | null;
  ebitda_cagr_reason: string | null;
  fcf_cagr: string | null;
  fcf_cagr_reason: string | null;
  margin_trend: string;
  margin_trend_reason: string | null;
  confidence: string;
  reason: string | null;
}

export interface MetricVerdict {
  field: string;
  label: string;
  value: string | null;
  verdict: string;
  reason: string | null;
}

export interface ValuationResult {
  ticker: string;
  asset_class: string;
  classification: string;
  metrics: MetricVerdict[];
  confidence: string;
  reason: string | null;
}

export interface FairValueRange {
  low: string | null;
  base: string | null;
  high: string | null;
}

export interface ValuationScenario {
  label: string;
  fair_value: string | null;
  assumptions: string;
  reason: string | null;
}

export interface ValuationV2Result {
  ticker: string;
  asset_class: string;
  current_price: string | null;
  valuation_status: string;
  fair_value_range: FairValueRange;
  scenarios: ValuationScenario[];
  margin_of_safety: string | null;
  required_margin_of_safety: string | null;
  graham_sanity_check: string | null;
  graham_reason: string | null;
  implied_expectation: string | null;
  implied_growth_rate: string | null;
  confidence: string;
  warnings: string[];
  methodology: string[];
  reason: string | null;
}

export interface IncomeRealEstateAnalysisResult {
  ticker: string;
  asset_class: string;
  status: string;
  pvp: string | null;
  dividend_yield: string | null;
  dy_own_history_average: string | null;
  dy_stability: string;
  dy_stability_reason: string | null;
  confidence: string;
  warnings: string[];
  methodology: string[];
  reason: string | null;
}

export interface PortfolioAdequacyResult {
  ticker: string;
  asset_class: string;
  valuation_applicable: boolean;
  valuation_note: string;
  adequacy_status: string;
  evaluated_dimension: string | null;
  current_weight: string | null;
  target_weight: string | null;
  min_weight: string | null;
  max_weight: string | null;
  gap_to_target: string | null;
  rebalance_required: boolean;
  extreme_overweight: boolean;
  alert_message: string | null;
  class_current_weight: string | null;
  class_target_weight: string | null;
  warnings: string[];
}

export interface TrapFlag {
  trap_type: string;
  label: string;
  severity: string;
  affected_metric: string;
  explanation: string;
  impact_on_score: string;
  recommended_interpretation: string;
  confidence_penalty: string;
}

export interface TrapDetectionResult {
  ticker: string;
  asset_class: string;
  flags: TrapFlag[];
  confidence_penalty: string;
  reason: string | null;
}

export interface FieldAvailability {
  field: string;
  label: string;
  available: boolean;
  value: string | null;
  source: string | null;
  updated_at: string | null;
  warning: string | null;
}

export interface CoveragePurposeScore {
  score: string | null;
  classification: string;
  missing_labels: string[];
  reason: string | null;
}

export interface DataCoverageResult {
  ticker: string;
  asset_class: string;
  period_end: string | null;
  fields: FieldAvailability[];
  quality: CoveragePurposeScore;
  valuation: CoveragePurposeScore;
  trap_detection: CoveragePurposeScore;
  income: CoveragePurposeScore;
  decision_engine: CoveragePurposeScore;
  summary: string;
}

export interface AssetDetailBundle {
  ticker: string;
  name: string;
  asset_class: string;
  currency: string;
  is_manual: boolean;
  lg_score: LGScoreResult | null;
  conviction: ConvictionScoreResult | null;
  data_quality: AssetDataQuality | null;
  fundamentals: FundamentalSnapshotResult | null;
  fundamentals_analysis: FundamentalsAnalysisResult | null;
  legacy_valuation: ValuationResult | null;
  valuation_v2: ValuationV2Result | null;
  income_real_estate: IncomeRealEstateAnalysisResult | null;
  adequacy: PortfolioAdequacyResult | null;
  trap_detection: TrapDetectionResult | null;
  coverage: DataCoverageResult | null;
}

export async function fetchAtivos(): Promise<AssetRowView[]> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/ativos`, { cache: "no-store" });
  } catch {
    throw new ApiError(
      `Não foi possível conectar à API em ${API_URL}. Ela está rodando? (uvicorn backend.app.api.app:app --reload --port 8000)`,
    );
  }
  if (!response.ok) {
    throw new ApiError(response.statusText, response.status);
  }
  return response.json();
}

export async function fetchAtivoDetail(ticker: string, portfolioId = 1): Promise<AssetDetailBundle> {
  let response: Response;
  try {
    response = await fetch(
      `${API_URL}/api/ativos/${encodeURIComponent(ticker)}?portfolio_id=${portfolioId}`,
      { cache: "no-store" },
    );
  } catch {
    throw new ApiError(
      `Não foi possível conectar à API em ${API_URL}. Ela está rodando? (uvicorn backend.app.api.app:app --reload --port 8000)`,
    );
  }
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // resposta sem corpo JSON — usa o statusText mesmo
    }
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), response.status);
  }
  return response.json();
}

export interface ManualFlagResponse {
  ticker: string;
  is_manual: boolean;
}

export async function setManualFlag(ticker: string, isManual: boolean): Promise<ManualFlagResponse> {
  const response = await fetch(`${API_URL}/api/ativos/${encodeURIComponent(ticker)}/manual-flag`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_manual: isManual }),
  });
  if (!response.ok) {
    throw new ApiError(response.statusText, response.status);
  }
  return response.json();
}

export interface ManualPriceResponse {
  ticker: string;
  price: string;
  source: string;
}

export async function setManualPrice(ticker: string, price: string): Promise<ManualPriceResponse> {
  const response = await fetch(`${API_URL}/api/ativos/${encodeURIComponent(ticker)}/manual-price`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ price }),
  });
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // resposta sem corpo JSON — usa o statusText mesmo
    }
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), response.status);
  }
  return response.json();
}

export async function refreshAtivoPrice(ticker: string): Promise<{ result: UpdateResult }> {
  const response = await fetch(`${API_URL}/api/ativos/${encodeURIComponent(ticker)}/refresh-price`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new ApiError(response.statusText, response.status);
  }
  return response.json();
}

export interface UpdateResult {
  ticker: string;
  inserted: number;
  updated: number;
  rejected: number;
  skipped_manual: boolean;
  error: string | null;
}

export interface FundamentalsCollectionResult {
  ticker: string;
  collected: boolean;
  period_end: string | null;
  reason: string | null;
  error: string | null;
}

export async function collectAtivoFundamentals(
  ticker: string,
): Promise<{ result: FundamentalsCollectionResult }> {
  const response = await fetch(
    `${API_URL}/api/ativos/${encodeURIComponent(ticker)}/collect-fundamentals`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw new ApiError(response.statusText, response.status);
  }
  return response.json();
}

export interface BatchFundamentalsResult {
  results: FundamentalsCollectionResult[];
}

export async function collectAllFundamentals(): Promise<{ result: BatchFundamentalsResult }> {
  const response = await fetch(`${API_URL}/api/ativos/collect-fundamentals-batch`, { method: "POST" });
  if (!response.ok) {
    throw new ApiError(response.statusText, response.status);
  }
  return response.json();
}

export interface FundamentalsImportRowOutcomeView {
  line: number;
  ticker: string;
  period_end: string | null;
  status: string;
  fields_applied: string[];
  reported_source: string | null;
  message: string | null;
}

export interface FundamentalsImportRowErrorView {
  line: number;
  field: string | null;
  message: string;
}

export interface FundamentalsImportResultView {
  total_rows: number;
  imported: number;
  conflicts_pending: number;
  outcomes: FundamentalsImportRowOutcomeView[];
  errors: FundamentalsImportRowErrorView[];
  tickers_recomputed: string[];
  valuation_recalculated: number;
  traps_recalculated: number;
  scores_recalculated: number;
}

export async function importFundamentals(
  file: File,
  overwrite: boolean,
  portfolioId = 1,
): Promise<FundamentalsImportResultView> {
  const formData = new FormData();
  formData.append("file", file);

  let response: Response;
  try {
    response = await fetch(
      `${API_URL}/api/ativos/fundamentals-import?portfolio_id=${portfolioId}&overwrite=${overwrite}`,
      { method: "POST", body: formData },
    );
  } catch {
    throw new ApiError(
      `Não foi possível conectar à API em ${API_URL}. Ela está rodando? (uvicorn backend.app.api.app:app --reload --port 8000)`,
    );
  }
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // resposta sem corpo JSON — usa o statusText mesmo
    }
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), response.status);
  }
  return response.json();
}

// --- Radar / Watchlist (v1.1, Fase 7) — espelha 1:1
// backend/app/schemas/watchlist.py, radar.py e radar_actions.py. A
// Watchlist é um cadastro de candidatos — nunca uma posição; nenhuma
// destas funções cria `Position` ou altera patrimônio.

export interface WatchlistAssetView {
  id: number;
  portfolio_id: number;
  ticker: string;
  name: string;
  asset_class: string;
  country: string;
  currency: string;
  sector: string | null;
  status: string;
  priority: number;
  thesis: string | null;
  notes: string | null;
  source: string;
  already_in_portfolio: boolean;
  last_collected_at: string | null;
}

export interface WatchlistAssetCreatePayload {
  ticker: string;
  name: string;
  asset_class: string;
  country: string;
  currency: string;
  sector?: string | null;
  status?: string;
  priority?: number;
  thesis?: string | null;
  notes?: string | null;
  source?: string;
}

export interface WatchlistAssetUpdatePayload {
  name?: string;
  asset_class?: string;
  country?: string;
  currency?: string;
  sector?: string | null;
  status?: string;
  priority?: number;
  thesis?: string | null;
  notes?: string | null;
}

export interface WatchlistDataCollectionResult {
  ticker: string;
  asset_ensured: boolean;
  price_collected: boolean;
  fundamentals_collected: boolean;
  lg_score: string | null;
  conviction_score: string | null;
  confidence: string | null;
  low_confidence: boolean;
  notes: string[];
}

export interface WatchlistCollectAllResult {
  results: WatchlistDataCollectionResult[];
}

export interface RadarClassificationResult {
  ticker: string;
  name: string;
  asset_class: string;
  watchlist_status: string | null;
  is_current_holding: boolean;
  current_weight: string | null;
  classification: string;
  effective_score: string | null;
  score_source: string | null;
  confidence: string | null;
  reasons: string[];
}

export interface RadarEvaluation {
  candidates: RadarClassificationResult[];
}

async function _handleJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // resposta sem corpo JSON — usa o statusText mesmo
    }
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), response.status);
  }
  return response.json();
}

export async function fetchWatchlist(portfolioId = 1): Promise<WatchlistAssetView[]> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/watchlist?portfolio_id=${portfolioId}`, {
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Não foi possível conectar à API em ${API_URL}. Ela está rodando? (uvicorn backend.app.api.app:app --reload --port 8000)`,
    );
  }
  return _handleJsonResponse<WatchlistAssetView[]>(response);
}

export async function addWatchlistAsset(
  payload: WatchlistAssetCreatePayload,
  portfolioId = 1,
): Promise<WatchlistAssetView> {
  const response = await fetch(`${API_URL}/api/watchlist?portfolio_id=${portfolioId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return _handleJsonResponse<WatchlistAssetView>(response);
}

export async function updateWatchlistAsset(
  watchlistAssetId: number,
  payload: WatchlistAssetUpdatePayload,
  portfolioId = 1,
): Promise<WatchlistAssetView> {
  const response = await fetch(
    `${API_URL}/api/watchlist/${watchlistAssetId}?portfolio_id=${portfolioId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return _handleJsonResponse<WatchlistAssetView>(response);
}

export async function setWatchlistStatus(
  watchlistAssetId: number,
  status: string,
  portfolioId = 1,
): Promise<WatchlistAssetView> {
  const response = await fetch(
    `${API_URL}/api/watchlist/${watchlistAssetId}/status?portfolio_id=${portfolioId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    },
  );
  return _handleJsonResponse<WatchlistAssetView>(response);
}

export async function removeWatchlistAsset(
  watchlistAssetId: number,
  portfolioId = 1,
): Promise<void> {
  const response = await fetch(
    `${API_URL}/api/watchlist/${watchlistAssetId}?portfolio_id=${portfolioId}`,
    { method: "DELETE" },
  );
  if (!response.ok && response.status !== 204) {
    throw new ApiError(response.statusText, response.status);
  }
}

export async function collectWatchlistAssetData(
  watchlistAssetId: number,
  portfolioId = 1,
): Promise<WatchlistDataCollectionResult> {
  const response = await fetch(
    `${API_URL}/api/watchlist/${watchlistAssetId}/collect?portfolio_id=${portfolioId}`,
    { method: "POST" },
  );
  return _handleJsonResponse<WatchlistDataCollectionResult>(response);
}

export async function collectAllWatchlistData(
  portfolioId = 1,
): Promise<WatchlistCollectAllResult> {
  const response = await fetch(
    `${API_URL}/api/watchlist/collect-all?portfolio_id=${portfolioId}`,
    { method: "POST" },
  );
  return _handleJsonResponse<WatchlistCollectAllResult>(response);
}

export async function fetchRadarEvaluation(portfolioId = 1): Promise<RadarEvaluation> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/radar?portfolio_id=${portfolioId}`, {
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Não foi possível conectar à API em ${API_URL}. Ela está rodando? (uvicorn backend.app.api.app:app --reload --port 8000)`,
    );
  }
  return _handleJsonResponse<RadarEvaluation>(response);
}

// --- Simulação (v1.1, Fase 8) — espelha 1:1
// backend/app/schemas/simulation.py (`SimulationResultView`). O Monte
// Carlo Simulation Engine é puro e não persiste nada no banco — cada
// chamada aqui é uma nova projeção sob demanda. Isto nunca é uma
// previsão real de mercado, sempre uma projeção probabilística (ver
// docs/SIMULATION_ENGINE.md); nenhum percentil/probabilidade é
// recalculado no frontend.

export interface SimulationResultView {
  model_version: string;
  initial_value: string;
  monthly_contribution: string;
  horizon_years: number;
  num_simulations: number;
  total_contributed: string;
  percentiles: Record<string, string>;
  median_final_value: string;
  probability_of_loss: string; // fração 0..1
  reasons: string[];
  warnings: string[];
}

export interface SimulationRunPayload {
  monthly_contribution: string;
  horizon_years: number;
  num_simulations: number;
  reproducible: boolean;
}

export async function runSimulation(
  payload: SimulationRunPayload,
  portfolioId = 1,
): Promise<SimulationResultView> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/simulacao?portfolio_id=${portfolioId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Não foi possível conectar à API em ${API_URL}. Ela está rodando? (uvicorn backend.app.api.app:app --reload --port 8000)`,
    );
  }
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // resposta sem corpo JSON — usa o statusText mesmo
    }
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), response.status);
  }
  return response.json();
}
