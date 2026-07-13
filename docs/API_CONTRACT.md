# Contrato Inicial da API — LG INVEST v1.1

> Contrato de referência para o FastAPI (`backend/app/api/`, a criar na
> Fase 2). Todos os endpoints são camada fina sobre `services/*`
> existentes — nenhum cálculo novo, nenhuma regra nova. Response models
> derivam diretamente dos schemas Pydantic já existentes em
> `backend/app/schemas/*`; onde o schema já existe, ele é reaproveitado
> como `response_model` quase sem alteração.

## Convenções

- Todas as rotas prefixadas com `/api`.
- `portfolio_id` como query param onde relevante (`?portfolio_id=1`) —
  v1.1 continua single-user/single-portfolio por padrão (`portfolio_id=1`),
  mas o parâmetro já existe para não fechar a porta a multi-portfólio
  depois.
- Erros seguem o formato padrão do FastAPI:
  `{"detail": "mensagem amigável, nunca stack trace"}`, com status HTTP
  apropriado (400 validação, 404 não encontrado, 409 conflito/precisa
  confirmação, 502 falha de fonte externa, 500 erro genérico).
- Valores monetários serializados como string decimal (não float) para
  não perder precisão — mesma convenção que os schemas Pydantic já
  usam com `Decimal`.
- Nenhum endpoint devolve HTML, CSS ou qualquer decisão de
  apresentação — cores/labels de status vêm como chave semântica
  (`"status": "attention"`) e o frontend decide a cor a partir do
  design system, nunca a API.

## Portfolio / Dashboard

### `GET /api/portfolio/summary?portfolio_id=1`
→ `PortfolioSummary` (via `portfolio_service.PortfolioService.get_summary`).

### `GET /api/portfolio/positions?portfolio_id=1`
→ lista de `ConvertedPosition` (via `dashboard_view_service.build_dashboard_view`,
campo `positions`).

### `POST /api/portfolio/import`
Multipart form com o arquivo CSV/Excel (mesmo formato de
`scripts/import_portfolio.py` / `PortfolioImportService`).
Body adicional: `portfolio_id`, `create_portfolio: bool`.
→ relatório de linhas importadas/erros por linha (mesmo formato hoje
exibido na tela Carteira).

### `GET /api/dashboard?portfolio_id=1`
Agrega (mesma composição de `cache.py::cached_dashboard_bundle`):
```jsonc
{
  "view": { /* DashboardView */ },
  "diagnostics": { /* PortfolioDiagnostics */ },
  "intelligence": { /* IntelligenceDashboardView (resumo) */ },
  "data_quality": { /* DataQualityService.evaluate_portfolio */ },
  "health": { /* PortfolioHealthService.evaluate */ },
  "risk": { /* PortfolioRiskService.evaluate */ },
  "data_refresh_status": { /* data_refresh_status_service */ }
}
```

## Inteligência / Ativos

### `GET /api/intelligence?portfolio_id=1`
→ `IntelligenceDashboardView` + `IncomeAnalysisResult` (mesma composição
de `cached_intelligence_bundle`).

### `GET /api/assets?portfolio_id=1`
→ lista resumida de ativos (ticker, nome, classe, LG Score, Conviction
Score, status de dado) — para a listagem/tabela.

### `GET /api/assets/{ticker}`
Agrega, por ativo: `ConvictionScoreService`, `DataCoverageService`,
`LGScoreService`, `PortfolioAdequacyService`, `TrapDetectionService`,
`ValuationServiceV2` (ações) **ou** `IncomeRealEstateService` (FII/REIT)
**ou** adequação de política (ETF/cripto/Tesouro) — o service correto é
escolhido pela mesma lógica de classe de ativo que `ativos.py` já usa
hoje (`if valuation_v2 is not None: ... elif income_re is not None: ...`).

### `GET /api/assets/{ticker}/fundamentals`
→ `FundamentalSnapshotResult` (via `fundamentals_analysis_service` /
`fundamentals_service`).

### `POST /api/assets/{ticker}/fundamentals/import`
Multipart CSV — mesma validação de `fundamentals_import_service.FundamentalsImportService`.

## Radar / Watchlist

### `GET /api/radar?portfolio_id=1`
→ funil por estágio (via `radar_service.RadarService`).

### `POST /api/radar/watchlist`
Body: `WatchlistAssetCreate`.
→ `WatchlistAssetView` criado.

### `PATCH /api/radar/watchlist/{ticker}`
Body: `WatchlistAssetUpdate` (ex.: mudar `status`).
→ `WatchlistAssetView` atualizado.

## Recomendação (Aporte v3)

### `POST /api/recommendations/aporte`
Body:
```jsonc
{
  "portfolio_id": 1,
  "amount": "1000.00",
  "blocked_assets": ["TICKER1", "TICKER2"],
  "allow_watchlist_candidates": false,
  "persist": false
}
```
Mapeia 1:1 para `DecisionService.recommend_v3(portfolio_id, amount,
blocked, config, persist, allow_watchlist_candidates)`. `persist`
default `false` na API pública (o Streamlit também não persiste por
padrão na tela — confirmar comportamento exato na Fase 3).

Response → `RecommendationResult` serializado quase direto:
```jsonc
{
  "items": [ /* RecommendationItem: ticker, amount, weight, reasons,
                score_breakdown, badges, tag (already_have/new_candidate) */ ],
  "ignored_items": [ /* IgnoredItem: ticker, block_source, reason */ ],
  "capped_dimensions": [ /* CappedDimensionResult: dimension, weight_before,
                            weight_after, max_weight, source */ ],
  "unallocated_amount": "387350.49",
  "audit": { /* DecisionAudit */ }
}
```

## Simulação

### `POST /api/simulation/monte-carlo`
Body:
```jsonc
{
  "portfolio_id": 1,
  "monthly_contribution": "1000.00",
  "horizon_years": 30,
  "num_simulations": 2000,
  "seed": null
}
```
→ `SimulationResultView` (via `SimulationService.run_portfolio_simulation`).

## Configurações

### `GET /api/settings?portfolio_id=1`
→ agrega alocação-alvo (simples + regras detalhadas), política de
investimento, premissas de simulação, câmbio manual — mesma composição
de `allocation_overview_service.build_allocation_overview` + os demais
services de Configurações.

### `PATCH /api/settings/allocation`
Body: alvo simples por classe ou regra detalhada (schema a definir na
Fase 5 com base em `TargetAllocationRuleService`).

### `PATCH /api/settings/policy`
Body: `InvestmentPolicyUpdate`.

### `PATCH /api/settings/simulation-assumptions`
Body: premissas por classe (`SimulationAssumptionUpdate`).

## Central de Dados

### `POST /api/data-refresh/prices?portfolio_id=1`
### `POST /api/data-refresh/fundamentals?portfolio_id=1`
### `POST /api/data-refresh/watchlist?portfolio_id=1`
### `POST /api/data-refresh/all?portfolio_id=1`
Todos via `DataRefreshService` — mesmo comportamento da tela Dashboard
hoje. **Atenção (ver `docs/WEB_APP_ARCHITECTURE.md`, riscos):** para
carteiras grandes isso pode demorar; considerar resposta assíncrona
(job id + polling) em vez de request/response síncrono se o tempo
passar de alguns segundos — decisão técnica da Fase 4/8, não fechada
ainda.

## Dividendos.me

Ver `docs/DIVIDENDOS_ME_FRONT_SYNC.md` para o fluxo completo e
`docs/SECURITY_NOTES.md` para as regras de segurança — aqui só o
formato dos endpoints.

### `POST /api/dividendos-me/test-login`
Body: `{ "email": "...", "password": "..." }` (nunca logado, nunca
persistido — ver nota de segurança).
→ `{ "success": true }` ou erro 401 com mensagem genérica.

### `POST /api/dividendos-me/dry-run`
Body: `{ "email": "...", "password": "...", "portfolio_id": 1 }`.
→ `SyncPreview` (mesmo schema já usado hoje: ativos encontrados, seções
encontradas, diff novo/atualizado/removido, alertas, status).

### `POST /api/dividendos-me/sync-update`
Body: `{ "email": "...", "password": "...", "portfolio_id": 1, "confirm": true }`.
→ `SyncRunResult`.

### `POST /api/dividendos-me/sync-replace`
Body: `{ "email": "...", "password": "...", "portfolio_id": 1, "confirmation_phrase": "..." }`.
Exige a frase de confirmação exata (mesma trava que já existe no
`service.py::replace` hoje) — a API só relaxa esse bloqueio se o
service permitir, nunca no frontend.
→ `SyncRunResult`.

## Sistema

### `POST /api/system/backup`
Via `scripts/backup_database.py` (reaproveitado como função, não
CLI) — dispara um backup do banco atual.

### `GET /api/system/status`
Healthcheck: versão da API, conectividade com o banco, ambiente
(`ENVIRONMENT`), sem nenhum dado sensível.

## O que fica fora deste contrato inicial

Journal (endpoints de CRUD simples, a detalhar na Fase 5 — não estava
na lista de endpoints do brief original) e a granularidade exata de
`PATCH /api/settings/*` (a tela de Configurações é a mais complexa em
formulários; melhor fechar o contrato quando a Fase 5 começar de fato,
com o schema real na tela).
