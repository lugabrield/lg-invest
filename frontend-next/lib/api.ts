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
