# Contrato da API — LG INVEST v1.1

> Contrato de referência para o FastAPI (`backend/app/api/`). Todos os
> endpoints são camada fina sobre `services/*` existentes — nenhum
> cálculo novo, nenhuma regra nova. Response models derivam diretamente
> dos schemas Pydantic já existentes em `backend/app/schemas/*`; onde o
> schema já existe, ele é reaproveitado como `response_model` quase sem
> alteração.
>
> **Status (14/07/2026 — Release Candidate v1.1.0-rc1):** este contrato
> foi escrito na Fase 0 (planejamento) e evoluiu junto com cada fase da
> migração. As seções de Journal e Configurações, que na versão inicial
> deste documento estavam marcadas "a detalhar", agora refletem os
> endpoints finais implementados nas Fases 9 e 10. A seção de
> Dividendos.me foi expandida com os endpoints de proventos e status
> adicionados na Fase 11. Os 10 routers abaixo estão todos registrados
> em `backend/app/api/app.py` e cobertos por testes de contrato em
> `backend/tests/unit/test_api_*.py`.

## Convenções

- Todas as rotas prefixadas com `/api`.
- `portfolio_id` como query param onde relevante (`?portfolio_id=1`) —
  v1.1 continua single-user/single-portfolio por padrão (`portfolio_id=1`),
  mas o parâmetro já existe para não fechar a porta a multi-portfólio
  depois.
- Erros seguem o formato padrão do FastAPI:
  `{"detail": "mensagem amigável, nunca stack trace"}`, com status HTTP
  apropriado (400/422 validação, 404 não encontrado, 401 credenciais
  inválidas, 409 conflito/precisa confirmação, 503 falha de fonte
  externa, 500 erro genérico).
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
default `false` na API pública (mesmo comportamento do Streamlit: a
tela não persiste por padrão).

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

## Journal (Fase 9 — implementado)

Diário de decisões e teses de investimento. Sem escopo por
`portfolio_id` (os modelos `JournalEntry`/`InvestmentThesis` têm só
`asset_id`, não `portfolio_id`) — mesmo comportamento do Streamlit, que
também nunca filtrou por carteira aqui. Cada view acrescenta o
`ticker` do ativo (via `AssetRepository`) ao que `JournalService`/
`ThesisService` já devolvem — nenhum cálculo novo.

### `GET /api/journal`
→ lista de `JournalEntryView` (todas as entradas, mais recentes
primeiro — via `JournalService.list_all`).

### `POST /api/journal`
Body: `JournalEntryCreateByTicker` (`ticker`, `action`, `thesis`, `date`,
`expected_outcome`).
→ `JournalEntryView` criado. 404 se o ticker não existir na carteira.

### `GET /api/theses`
→ lista de `ThesisView` (via `ThesisService.list_theses`).

### `POST /api/theses`
Body: `ThesisCreateByTicker` (`ticker`, `thesis_date`, `hypothesis`,
`entry_price`, `return_drivers`, `main_risks`, `horizon`,
`review_criteria`).
→ `ThesisView` criado. 404 se o ticker não existir.

### `POST /api/theses/{thesis_id}/reviews`
Body: `ThesisReviewCreateRequest` (`review_date`, `classification`,
`notes`).
→ `ThesisReviewView` criado. 404 se a tese não existir.

## Configurações (Fase 10 — implementado)

Todos os endpoints sob o prefixo `/api/configuracoes`, organizados
pelas mesmas 3 camadas de alocação-alvo do Streamlit (simples/regras
detalhadas/política), mais câmbio, sistema e premissas de simulação.
Composição fina sobre `fx_settings_service`/`fx_service`,
`market_data_service`, `target_allocation_settings_service`/
`allocation_presets_service` (Camada 1), `TargetAllocationRuleService`
(Camada 2), `InvestmentPolicyService` (Camada 3),
`allocation_overview_service` (precedência entre as 3 camadas) e
`simulation_assumptions_service`. Nenhuma regra de negócio nova.

### Sistema e câmbio
- `GET /api/configuracoes/sistema` → `SystemInfoView` (ambiente,
  `DATABASE_URL` com credenciais mascaradas, `portfolio_id`, contagem
  de ativos).
- `GET /api/configuracoes/fx` → `FxStatusView` (taxa atual + última
  cotação).
- `POST /api/configuracoes/fx/refresh` → busca uma cotação nova (BCB
  PTAX com fallback Yahoo); 503 se nenhuma fonte responder.
- `PUT /api/configuracoes/fx` → define a taxa manualmente
  (`FxManualUpdateRequest`); 422 se inválida.
- `POST /api/configuracoes/precos/refresh` → `BatchUpdateResult`
  (atualiza preços de todos os ativos ativos via Yahoo Finance); 503 se
  a fonte estiver indisponível.

### Camada 1 — alocação-alvo simples
- `GET /api/configuracoes/alocacao-simples` → `SimpleAllocationView`.
- `PUT /api/configuracoes/alocacao-simples` → define a alocação-alvo
  simples por classe; 422 se não somar 100% ou for inválida.
- `DELETE /api/configuracoes/alocacao-simples` → limpa a alocação-alvo
  simples (204).
- `GET /api/configuracoes/alocacao-presets` → lista de
  `AllocationPresetView` (presets prontos).
- `POST /api/configuracoes/alocacao-presets/{preset_key}/aplicar` →
  aplica um preset como alocação-alvo simples; 404 se o preset não
  existir, 422 se o preset não tiver alocação para aplicar.

### Camada 2 — regras detalhadas
- `GET /api/configuracoes/regras-alocacao?portfolio_id=1` → lista de
  `TargetAllocationRuleView`.
- `PUT /api/configuracoes/regras-alocacao?portfolio_id=1` → cria/atualiza
  uma regra (`TargetAllocationRuleUpsertRequest`: `dimension_type`,
  `dimension_key`, `min_weight`, `target_weight`, `max_weight`,
  `priority`); 422 se inválida.
- `DELETE /api/configuracoes/regras-alocacao/{dimension_type}/{dimension_key}?portfolio_id=1`
  → remove uma regra (204); 404 se não existir.

### Camada 3 — política de investimento
- `GET /api/configuracoes/politica?portfolio_id=1` → `InvestmentPolicyView`
  (cria com valores padrão se ainda não existir).
- `PATCH /api/configuracoes/politica?portfolio_id=1` → atualiza a
  política (`InvestmentPolicyUpdate`).

### Visão geral e premissas de simulação
- `GET /api/configuracoes/visao-geral?portfolio_id=1` → `AllocationOverview`
  (precedência e conflitos entre as 3 camadas).
- `GET /api/configuracoes/premissas-simulacao` → `SimulationAssumptionsView`
  (retorno esperado/volatilidade por classe, com aviso de que são
  premissas configuráveis, não previsão de mercado).
- `PUT /api/configuracoes/premissas-simulacao` → define uma premissa por
  classe (`SimulationAssumptionUpdate`); 422 se inválida.
- `DELETE /api/configuracoes/premissas-simulacao/{asset_class}` →
  restaura a premissa padrão daquela classe.

## Central de Dados

### `POST /api/data-refresh/prices?portfolio_id=1`
### `POST /api/data-refresh/fundamentals?portfolio_id=1`
### `POST /api/data-refresh/watchlist?portfolio_id=1`
### `POST /api/data-refresh/all?portfolio_id=1`
Todos via `DataRefreshService` — mesmo comportamento da tela Dashboard.
Execução síncrona (request/response) — para a carteira real usada nesta
migração (33 ativos) o tempo de resposta ficou dentro do aceitável em
todas as fases; se o volume de ativos crescer muito, reavaliar resposta
assíncrona (job id + polling) como melhoria futura.

## Dividendos.me (Fase 11 — implementado)

Ver `docs/DIVIDENDOS_ME_FRONT_SYNC.md` para o fluxo completo e
`docs/SECURITY_NOTES.md` para as regras de segurança. Todos os
endpoints sob o prefixo `/api/dividendos-me`. Diferença central em
relação ao Streamlit: as credenciais vêm no body de cada requisição
(nunca de `.env`/`st.secrets`), nunca são persistidas, logadas ou
ecoadas em nenhuma resposta — cada etapa é uma chamada HTTP
independente, sem "token de sessão" guardado em cache/Redis/memória do
processo.

### `GET /api/dividendos-me/status`
→ `DividendosMeStatusView` (Playwright disponível no servidor + data da
última sincronização com sucesso). Nunca depende de credenciais.

### `POST /api/dividendos-me/test-login`
Body: `{ "email": "...", "password": "..." }`.
→ `TestLoginResponse` (`{"success": true}`) ou 401 com mensagem
genérica em caso de credenciais inválidas.

### `POST /api/dividendos-me/dry-run`
Body: `{ "email": "...", "password": "...", "portfolio_id": 1 }`.
→ `DryRunResponse` (embrulha `SyncPreview` + `blocking_reasons_replace`/
`blocking_reasons_update`/`strong_alert_sections` já calculados, para o
frontend nunca duplicar a lógica de bloqueio de segurança). 404 se a
carteira não existir.

### `POST /api/dividendos-me/sync-update`
Body: `{ "email": "...", "password": "...", "portfolio_id": 1, "confirm": true }`.
→ `SyncRunResult`. 422 se `confirm` não vier `true`.

### `POST /api/dividendos-me/sync-replace`
Body: `{ "email": "...", "password": "...", "portfolio_id": 1, "confirmation_phrase": "SUBSTITUIR" }`.
Exige a frase de confirmação exata (mesma trava que já existe no
`service.py::replace`) e é bloqueado se mais de 50% da carteira seria
removida.
→ `SyncRunResult`. 422 se a frase não bater ou o bloqueio de segurança
acionar.

### `POST /api/dividendos-me/income/monthly/preview`
Body: `{ "email": "...", "password": "...", "portfolio_id": 1 }`.
→ `IncomeMonthlySyncPreview` (histórico mensal agregado de proventos).

### `POST /api/dividendos-me/income/monthly/import`
Mesmo body do preview.
→ `IncomeMonthlySyncRunResult` — importação sempre aditiva, com dedup
automático em reimportações.

### `POST /api/dividendos-me/income/calendar/preview`
Body: `{ "email": "...", "password": "...", "portfolio_id": 1 }`.
→ `IncomeSyncPreview` (calendário futuro de proventos).

### `POST /api/dividendos-me/income/calendar/import`
Mesmo body do preview.
→ `IncomeSyncRunResult` — importação sempre aditiva, com dedup
automático.

Todas as rotas mapeiam `DividendosMeAuthError` → 401,
`DividendosMeScrapingError` (inclui "Playwright não instalado") → 503,
`PortfolioNotFoundError` → 404,
`SyncConfirmationRequiredError`/`ExtractionInvalidError` → 422,
qualquer exceção não prevista → 500 com mensagem genérica (nunca vaza
detalhe — toda mensagem passa por `sanitize_message()` antes de virar
resposta HTTP, defesa em profundidade caso alguma lib de terceiro ecoe
a senha por engano).

## Sistema

### `POST /api/system/backup`
Via `scripts/backup_database.py` (reaproveitado como função, não
CLI) — dispara um backup do banco atual.

### `GET /api/system/status`
Healthcheck: versão da API, conectividade com o banco, ambiente
(`ENVIRONMENT`), sem nenhum dado sensível.
