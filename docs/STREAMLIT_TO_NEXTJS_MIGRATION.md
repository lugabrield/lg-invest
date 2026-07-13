# Mapa de Migração — Streamlit → Next.js

> Tela por tela: o que existe hoje, quais services/engines ela consome,
> qual endpoint novo a alimenta, e para qual fase do
> `docs/V1_1_MIGRATION_PLAN.md` isso está planejado. Base para não
> esquecer nenhum dado real ao recriar a tela em React.

## 1. Dashboard (`pages_impl/dashboard.py`)

**Consome:** `dashboard_view_service.build_dashboard_view`,
`portfolio_diagnostics_service.get_portfolio_diagnostics`,
`intelligence_dashboard_service.build_intelligence_dashboard`,
`data_quality_service.DataQualityService`,
`portfolio_health_service.PortfolioHealthService`,
`portfolio_risk_service.PortfolioRiskService`,
`data_refresh_service.DataRefreshService`,
`data_refresh_status_service`, `fx_settings_service`. Hoje agrupado em
`frontend/streamlit_app/cache.py::cached_dashboard_bundle` (6 services
numa leitura só, com `st.cache_data` — Streamlit-only, precisa de um
equivalente no backend, ver Fase 2).

**Mostra:** hero (patrimônio, variação, exposição internacional, Health
Score, risco, próximo aporte sugerido), "Decisão do mês" (melhor
oportunidade pelo Conviction Score), Saúde da Carteira (5 pilares),
Risco da Carteira, Oportunidades & Riscos, Alocação (classe/moeda/BR
vs. exterior), Central de Dados (última atualização + botões de
refresh).

**Endpoint alvo:** `GET /api/dashboard` (Fase 2) — um único payload
agregando tudo acima (mesma composição do `cached_dashboard_bundle`,
só sem depender de `st.cache_data`).

**Ações que escrevem:** `POST /api/data-refresh/{prices|fundamentals|watchlist|all}`.

## 2. Carteira (`pages_impl/carteira.py`)

**Consome:** `dashboard_view_service.build_dashboard_view`,
`fx_settings_service`, `portfolio_import_service.PortfolioImportService`
(upload de CSV/Excel).

**Mostra:** hero (patrimônio convertido, Brasil/BRL, exterior, maior
posição), tabela de posições agrupada, filtros.

**Endpoint alvo:** `GET /api/portfolio/positions` +
`GET /api/portfolio/summary` (Fase 4). Upload de carteira via
`POST /api/portfolio/import` (multipart, mesmo formato CSV/Excel já
aceito).

## 3. Aporte v3 (`pages_impl/aporte.py`)

**Consome:** `decision_service.DecisionService.recommend_v3`,
`allocation_projection_service.build_allocation_projection`,
`dashboard_view_service.build_dashboard_view`, `fx_settings_service`.

**Mostra:** input de valor, toggle de watchlist, cards por ativo
recomendado (valor, %, motivo, LG Score, Conviction Score, confiança,
tag já-tenho/novo-candidato), breakdown por fator, ativos ignorados,
dimensões com corte pós-alocação, saldo não alocado, projeção "como a
carteira ficaria depois".

**Endpoint alvo:** `POST /api/recommendations/aporte` (Fase 3) — ver
`docs/API_CONTRACT.md` para o payload completo (é o endpoint mais rico
de todos, corresponde 1:1 ao `RecommendationResult`).

## 4. Ativos (`pages_impl/ativos.py`)

**Consome (a tela mais rica do app):**
`conviction_score_service.ConvictionScoreService`,
`data_coverage_service.DataCoverageService`,
`data_quality_service.DataQualityService`,
`fundamentals_analysis_service.FundamentalsAnalysisService`,
`fundamentals_import_service.FundamentalsImportService` (import manual
de CSV), `income_real_estate_service.IncomeRealEstateService`,
`lg_score_service.LGScoreService`,
`portfolio_adequacy_service.PortfolioAdequacyService`,
`trap_detection_service.TrapDetectionService`,
`valuation_service.ValuationService` (v1, legado),
`valuation_v2_service.ValuationServiceV2`.

**Mostra:** por ativo — LG Score, Conviction Score v2 (breakdown por
pilar), Valuation Engine 2.0 (DCF/múltiplos/Graham/reverse DCF) para
ações, Análise de Renda Imobiliária para FIIs/REITs, Adequação de
Política para ETF/cripto/Tesouro, Trap Detection flags, Data Coverage
(dado disponível/ausente), preço manual, import manual de fundamentos.

**Endpoint alvo:** `GET /api/assets` (lista) +
`GET /api/assets/{ticker}` (detalhe agregando os 8 services acima) +
`GET /api/assets/{ticker}/fundamentals` (Fase 4).

## 5. Inteligência (`pages_impl/inteligencia.py`)

**Consome:** `intelligence_dashboard_service.build_intelligence_dashboard`,
`income_analysis_service.IncomeAnalysisService` — hoje agrupados em
`cache.py::cached_intelligence_bundle`.

**Mostra:** resumo executivo, rankings (mais baratos, maior qualidade,
maior crescimento, mais caros, maior risco), "por que este ativo"
detalhado por pilar.

**Endpoint alvo:** `GET /api/intelligence` (Fase 4).

## 6. Radar / Watchlist (`pages_impl/radar.py`)

**Consome:** `radar_service.RadarService`, `watchlist_service.WatchlistService`.

**Mostra:** funil por estágio (watching/candidate/blocked/discarded/bought),
cards de candidato, ação de alterar status.

**Endpoint alvo:** `GET /api/radar` + `POST /api/radar/watchlist`
(adicionar) + `PATCH /api/radar/watchlist/{ticker}` (mudar status)
(Fase 4).

## 7. Simulação (`pages_impl/simulacao.py`)

**Consome:** `simulation_service.SimulationService.run_portfolio_simulation`.

**Mostra:** inputs (aporte mensal, horizonte), resultado (valor
inicial, total aportado, mediana projetada, probabilidade de perda).

**Endpoint alvo:** `POST /api/simulation/monte-carlo` (Fase 5).

## 8. Journal (`pages_impl/journal.py`)

**Consome:** `journal_service.JournalService`, `thesis_service.ThesisService`.

**Mostra:** lista de decisões/teses por ativo, criação de entrada,
revisão de tese.

**Endpoint alvo:** `GET/POST /api/journal`, `GET/POST /api/journal/thesis`
(Fase 5 — endpoints exatos a detalhar quando chegar a fase, não estavam
na lista original do brief).

## 9. Configurações (`pages_impl/configuracoes.py`)

**Consome:** `allocation_overview_service.build_allocation_overview`,
`investment_policy_service.InvestmentPolicyService`,
`target_allocation_rule_service.TargetAllocationRuleService`,
`allocation_presets_service`, `fx_settings_service`,
`simulation_assumptions_service`.

**Mostra:** 3 camadas de alocação-alvo (simples/regras
detalhadas/política), câmbio manual, premissas de simulação, presets.

**Endpoint alvo:** `GET/PATCH /api/settings` (Fase 5) — provavelmente
precisa de sub-rotas (`/settings/allocation`, `/settings/policy`,
`/settings/simulation-assumptions`) dado o tamanho da tela; decidir
granularidade na Fase 5.

## 10. Sincronizar Dividendos.me (`pages_impl/sincronizar_dividendos_me.py`)

**Consome:** `integrations/dividendos_me/{auth,client,secrets,service,income_service}.py`.

**Hoje:** credenciais vêm só de `.env`/`st.secrets` — nunca digitadas
na UI. **Muda na v1.1:** modal com email/senha digitados a cada sessão,
nunca persistidos. Ver `docs/DIVIDENDOS_ME_FRONT_SYNC.md` (fluxo
completo) e `docs/SECURITY_NOTES.md` (regras de segurança).

**Endpoint alvo (Fase 6):** `POST /api/dividendos-me/test-login`,
`POST /api/dividendos-me/dry-run`, `POST /api/dividendos-me/sync-update`,
`POST /api/dividendos-me/sync-replace`.

## Componentes de apoio (não são "telas", mas atravessam várias)

- `components/patterns.py` (page_header, metric_card_row, alert_box,
  recommendation_card, data_quality_box, empty_state) → viram
  componentes shadcn/ui equivalentes no design system do Next.js
  (`docs/WEB_APP_ARCHITECTURE.md`, seção "Componentes").
- `components/badges.py` → `StatusBadge`/`RiskBadge` no Next.js,
  recebendo status já resolvido pela API (nunca calculando cor/label no
  frontend).
- `charts/*.py` (Plotly) → Recharts/ECharts equivalentes, mesmos dados,
  visual novo.

## O que NÃO tem tela dedicada hoje (útil para o design da API)

- Backup (`scripts/backup_database.py`) — vira `POST /api/system/backup`,
  sem tela própria no Streamlit hoje; no Next.js pode virar uma ação em
  Configurações ou uma tela de "Sistema"/"Status" (a decidir).
- Healthcheck/status do sistema — não existe hoje; novo em
  `GET /api/system/status` para a Fase 8 (deploy).
