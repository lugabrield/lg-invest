// Adaptador puro da tela Ativos (v1.1, Fase 6): rótulos e cores de
// status, mesmo vocabulário de `frontend/streamlit_app/components/badges.py`.
// Nenhum cálculo — só mapeamento de string para rótulo/cor de apresentação.

import type { StatusKind } from "@/lib/mock/dashboard";

export const PRICE_STATUS_LABELS: Record<string, string> = {
  automatic: "🌐 Automático",
  manual: "✍️ Manual",
  missing: "📛 Sem preço",
};

export const CONFIDENCE_LABELS: Record<string, string> = {
  alta: "Confiança alta",
  média: "Confiança média",
  baixa: "Confiança baixa",
};

export const CONFIDENCE_STATUS: Record<string, StatusKind> = {
  alta: "positive",
  média: "attention",
  baixa: "critical",
};

export const DATA_QUALITY_STATUS: Record<string, StatusKind> = {
  automatico: "positive",
  manual: "neutral",
  estimado: "attention",
  ausente: "critical",
  completo: "positive",
  parcial: "attention",
  proxy: "attention",
  nao_aplicavel: "muted",
};

export const VALUATION_STATUS_LABELS: Record<string, string> = {
  subvalorizado: "Subvalorizado",
  valor_justo: "Valor justo",
  sobrevalorizado: "Sobrevalorizado",
  indeterminado: "Indeterminado",
};

export const VALUATION_STATUS_KIND: Record<string, StatusKind> = {
  subvalorizado: "positive",
  valor_justo: "neutral",
  sobrevalorizado: "critical",
  indeterminado: "muted",
};

export const INCOME_RE_STATUS_LABELS: Record<string, string> = {
  atrativo: "Atrativo",
  neutro: "Neutro",
  pouco_atrativo: "Pouco atrativo",
  indeterminado: "Indeterminado",
};

export const INCOME_RE_STATUS_KIND: Record<string, StatusKind> = {
  atrativo: "positive",
  neutro: "neutral",
  pouco_atrativo: "critical",
  indeterminado: "muted",
};

export const ADEQUACY_STATUS_LABELS: Record<string, string> = {
  underweight: "Abaixo do alvo",
  neutral: "No alvo",
  overweight: "Acima do alvo",
  blocked: "Bloqueado",
  indeterminado: "Indeterminado",
};

export const ADEQUACY_STATUS_KIND: Record<string, StatusKind> = {
  underweight: "positive",
  neutral: "neutral",
  overweight: "attention",
  blocked: "critical",
  indeterminado: "muted",
};

export const TRAP_SEVERITY_KIND: Record<string, StatusKind> = {
  baixa: "neutral",
  média: "attention",
  alta: "critical",
};

export const CLASSIFICATION_LABELS_PT: Record<string, string> = {
  strong_buy: "Aportar",
  buy: "Candidato",
  hold: "Manter",
  watch: "Monitorar",
  avoid: "Evitar",
  insufficient_data: "Dados insuficientes",
};

export const CLASSIFICATION_STATUS: Record<string, StatusKind> = {
  strong_buy: "positive",
  buy: "positive",
  hold: "neutral",
  watch: "attention",
  avoid: "critical",
  insufficient_data: "muted",
};

export const PILLAR_LABELS_PT: Record<string, string> = {
  quality: "Qualidade",
  valuation: "Valuation",
  growth: "Crescimento",
  risk: "Risco",
  capital_reinvestment: "Reinvestimento de capital",
  allocation: "Alocação",
};

// Mesmos 9 campos exibidos nos cards de fundamentos do Streamlit (o
// snapshot completo tem 30+ campos — só os visíveis por padrão entram
// aqui; o resto fica disponível/ausente via `coverage.fields`).
export const FUNDAMENTAL_HIGHLIGHT_FIELDS = [
  "roe",
  "net_margin",
  "pe_ratio",
  "pb_ratio",
  "dividend_yield",
  "debt_to_ebitda",
  "market_cap",
  "forward_pe",
  "operating_margin",
] as const;
