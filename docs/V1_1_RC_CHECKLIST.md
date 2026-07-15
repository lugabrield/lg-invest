# Release Checklist — LG INVEST v1.1.0-rc1

Checklist de prontidão da Release Candidate v1.1 (Premium Web App —
Next.js + FastAPI), branch `feature/v1.1-premium-web-app`, fechada em
14/07/2026. Cada item tem evidência concreta desta rodada de validação.
Ver `docs/RELEASE_NOTES_v1.1.md` para o resumo completo e
`docs/RELEASE_CHECKLIST.md` (v1.0.0) para o checklist equivalente do
Streamlit legado.

## 1. Dashboard (Next.js)

✅ Tela consome `GET /api/dashboard` real (via `lib/adapt-dashboard.ts`), agregando `DashboardView`, diagnósticos, resumo de inteligência, data quality, health e risk — mesma composição do `cached_dashboard_bundle` do Streamlit. Auditoria da RC confirmou zero dado mockado renderizado (`frontend-next/lib/mock/dashboard.ts` contém só tipos de apresentação reusados, nenhuma constante de dado).

## 2. Carteira

✅ Consome `GET /api/portfolio/summary`, `GET /api/portfolio/positions` e `POST /api/portfolio/import` reais (Fase 4). Importação de CSV/Excel testada via `backend/tests/unit/test_api_portfolio.py`.

## 3. Aporte v3

✅ Consome `POST /api/recommendations/aporte` real (Fase 3), mapeando 1:1 para `DecisionService.recommend_v3`. Explicação por ativo (`score_breakdown`), origem de bloqueio e Post-Allocation Constraints Engine (nunca ultrapassa limites pós-aporte, nunca sugere venda) preservados sem nenhuma mudança de regra.

## 4. Inteligência

✅ Consome `GET /api/intelligence` real (Fase 5) — ranking por LG Conviction Score v2, blocos interpretativos, mesma composição do `cached_intelligence_bundle`.

## 5. Ativos

✅ Consome `GET /api/assets`, `GET /api/assets/{ticker}`, `GET /api/assets/{ticker}/fundamentals` e `POST /api/assets/{ticker}/fundamentals/import` reais (Fase 6) — Análise Fundamentalista completa (Valuation Engine 2.0, análise de renda FII/REIT, adequação de política, Trap Detection) por ativo.

## 6. Radar / Watchlist

✅ Consome `GET /api/radar`, `POST /api/radar/watchlist` e `PATCH /api/radar/watchlist/{ticker}` reais (Fase 7) — funil de candidatos preservado.

## 7. Simulação

✅ Consome `POST /api/simulation/monte-carlo` real (Fase 8) mediante clique explícito do usuário (por design, mesmo comportamento do Streamlit) — não é um resíduo de mock, é a única tela cuja chamada à API depende de uma ação do usuário em vez de carregar ao montar.

## 8. Journal

✅ Consome `GET`/`POST /api/journal`, `GET`/`POST /api/theses` e `POST /api/theses/{id}/reviews` reais (Fase 9) — teses, decisões e revisões preservadas sem mudança de modelo.

## 9. Configurações

✅ Consome os endpoints reais sob `/api/configuracoes/*` (Fase 10) — câmbio (`fx`), preços (`precos/refresh`), as três camadas de alocação-alvo (`alocacao-simples`, `regras-alocacao`, `politica`), visão geral de precedência (`visao-geral`) e premissas de simulação (`premissas-simulacao`). Todas as validações (soma 100%, min/target/max, conflitos) preservadas nos services, não duplicadas no frontend.

## 10. Sincronizar Dividendos.me

✅ Consome os 9 endpoints reais sob `/api/dividendos-me/*` (Fase 11) — status, test-login, dry-run, sync-update, sync-replace, e os 4 endpoints de proventos (mensal/calendário, preview/import). Fluxo de credenciais redesenhado para a web (modal, reenvio a cada etapa, nunca persistidas/logadas/ecoadas) conforme `docs/DIVIDENDOS_ME_FRONT_SYNC.md`. 23 testes dedicados em `test_api_dividendos_me.py`, incluindo 2 testes de segurança que confirmam que senha/e-mail nunca aparecem em nenhuma resposta HTTP.

## 11. Backend FastAPI

✅ `backend/app/api/` com 10 routers registrados (`dashboard`, `system`, `aporte`, `portfolio`, `intelligence`, `ativos`, `radar`, `simulacao`, `journal`, `configuracoes`, `dividendos_me`), todos camada fina sobre `services/*` já validados — nenhuma regra de negócio nova. CORS configurável via `API_CORS_ORIGINS` (nunca `*` em produção). Roda localmente com `uvicorn backend.app.api.app:app --reload --port 8000`. Suíte completa validada nesta RC: **1331 testes passando** (`pytest -q`), `ruff check .` e `black --check .` limpos.

## 12. Supabase / Postgres

⚠️ **Parcialmente validado — não é um problema novo desta RC.** `SQLAlchemy` já é agnóstico a banco e `DATABASE_URL` já foi validada contra um Supabase Postgres real em produção na Sprint 20 (v1.0.0 — projeto criado, dados migrados, sequências realinhadas, app publicado e testado nas 6 telas da época, ver `CHANGELOG.md` "Sprint 20"). Nenhum modelo, migration ou camada de acesso a banco mudou na migração para FastAPI — o backend v1.1 usa exatamente a mesma `session.py`/`models/*` já provados contra Postgres. **O que esta RC especificamente não fez:** rodar a suíte de testes de API do FastAPI contra um banco Postgres real (a suíte automatizada usa SQLite via fixture `db_session`, como sempre) e não executou um deploy real do backend FastAPI contra o Supabase — isso fica para a fase de deploy real (`docs/VERCEL_DEPLOYMENT.md`), depois da aprovação desta RC.

## 13. Streamlit legado intacto

✅ Nenhum arquivo em `frontend/streamlit_app/` foi alterado durante as 11 fases da migração (confirmado por essa ter sido uma regra seguida em cada fase, reforçada nesta RC) — o app Streamlit v1.0.0 continua rodando exatamente como estava, com `streamlit run frontend/streamlit_app/app.py`, usando o mesmo banco (`data/lg_invest.db` em dev local) que o backend FastAPI. Serve como fallback funcional enquanto a v1.1 é avaliada.

## Resumo da validação final desta RC

```bash
python -m pytest -q          # 1331 testes, 0 falhas
python -m ruff check .        # limpo
python -m black --check .     # limpo (463 arquivos)
npm run typecheck             # limpo
npm run lint                  # limpo
npm run build                 # falha só no fetch de fonte do Google Fonts
                               # (ambiente de validação sem internet — não é bug)
```

## Estado dos branches

- `main` — v1.0.0, sem alterações (`git diff --stat v1.0.0 main` vazio).
- `feature/v1.1-premium-web-app` — as 11 fases completas, RC-ready.
- **Nenhum merge e nenhuma tag criados nesta rodada** — decisão explícita do usuário, aguardando revisão.
