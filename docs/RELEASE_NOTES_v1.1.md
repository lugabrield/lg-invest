# LG INVEST v1.1.0-rc1 — Release Notes

**Data:** 14 de julho de 2026
**Codinome:** "Premium Web App" — Release Candidate 1
**Branch:** `feature/v1.1-premium-web-app` (não mesclada em `main`)

## Resumo

A v1.1 migra a interface da LG INVEST de Streamlit para uma stack web moderna — **Next.js (frontend) + FastAPI (API)** — mantendo o Streamlit v1.0.0 intacto e funcional em paralelo, como fallback. Nenhuma engine, regra de negócio, cálculo financeiro ou schema de dados mudou nesta migração: é uma mudança de **camada de apresentação e transporte**, não de comportamento. Todas as 11 telas do plano (`docs/V1_1_MIGRATION_PLAN.md`) foram entregues, cada uma consumindo dados reais do backend via uma API REST fina sobre os `services/*` já existentes e testados.

Esta é uma **Release Candidate**: pronta para revisão do usuário, mas ainda não mesclada em `main` e sem tag de versão — por decisão explícita, o merge e a criação da tag ficam para depois da revisão.

## Escopo desta versão (as 11 fases)

| Fase | Tela / componente | Status |
|---|---|---|
| 0-1 | Scaffolding Next.js + arquitetura + contrato de API | ✅ |
| 2 | API real + Dashboard conectado | ✅ |
| 3 | Aporte v3 (Decision Engine v3) | ✅ |
| 4 | Carteira | ✅ |
| 5 | Inteligência | ✅ |
| 6 | Ativos (Análise Fundamentalista completa) | ✅ |
| 7 | Radar / Watchlist | ✅ |
| 8 | Simulação (Monte Carlo) | ✅ |
| 9 | Journal (teses, decisões, revisões) | ✅ |
| 10 | Configurações (câmbio, alocação-alvo, política, premissas) | ✅ |
| 11 | Sincronizar Dividendos.me | ✅ |

Todas as telas consomem `lib/api.ts` contra o FastAPI real — não há dado mockado renderizado em nenhuma tela (a Simulação só chama a API mediante clique explícito do usuário, por design, igual ao Streamlit).

## O que mudou

### Adicionado
- `backend/app/api/` — camada FastAPI completa: 10 routers (`dashboard`, `system`, `aporte`, `portfolio`, `intelligence`, `ativos`, `radar`, `simulacao`, `journal`, `configuracoes`, `dividendos_me`), todos camada fina sobre `services/*` existentes, com CORS restrito por configuração.
- `frontend-next/` — app Next.js (App Router, TypeScript, Tailwind), 11 telas, componentes de apresentação reutilizáveis, funções de adaptação (`lib/adapt-*.ts`) que transformam a resposta da API nos tipos de apresentação usados pelos componentes.
- Fluxo de credenciais do Dividendos.me redesenhado para a web: em vez de `.env`/`st.secrets` (única forma no Streamlit), o usuário digita e-mail/senha no modal a cada sincronização — nunca persistidas, nunca logadas, nunca ecoadas em resposta HTTP (ver `docs/DIVIDENDOS_ME_FRONT_SYNC.md` e `docs/SECURITY_NOTES.md`).
- Documentação nova/atualizada: `docs/WEB_APP_ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `docs/DIVIDENDOS_ME_FRONT_SYNC.md`, `docs/SECURITY_NOTES.md`, `docs/STREAMLIT_TO_NEXTJS_MIGRATION.md`, `docs/VERCEL_DEPLOYMENT.md` (novo), `docs/V1_1_RC_CHECKLIST.md` (novo).

### Não mudou (preservado 100%)
- Todas as engines em `backend/app/engines/*` — puras, sem I/O, mesma cobertura de testes de sempre.
- Todos os `services/*`, `schemas/*` (Pydantic), modelos SQLAlchemy e migrations Alembic.
- O app Streamlit completo (`frontend/streamlit_app/`) — continua rodando, sem nenhuma alteração de comportamento, como fallback enquanto a v1.1 é avaliada.
- `main` — continua exatamente igual à tag `v1.0.0` (nenhum commit desta migração tocou esse branch).

## Como rodar localmente

**Backend (FastAPI):**
```bash
cd lg-invest
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -e .
uvicorn backend.app.api.app:app --reload --port 8000
```

**Frontend (Next.js):**
```bash
cd frontend-next
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Frontend em `http://localhost:3000`, API em `http://localhost:8000`. O Streamlit legado continua disponível em paralelo com `streamlit run frontend/streamlit_app/app.py` (porta padrão 8501) — os dois consomem o mesmo banco (`data/lg_invest.db` em dev local).

## Validação desta RC

```bash
python -m pytest -q          # 1331 testes, 0 falhas
python -m ruff check .        # limpo
python -m black --check .     # limpo (463 arquivos)
npm run typecheck             # limpo
npm run lint                  # limpo
npm run build                 # falha só no fetch de fonte do Google Fonts (ambiente
                               # de validação sem acesso à internet externa — não é
                               # um bug de código; completa normalmente com acesso à
                               # internet real, como em dev local ou na Vercel)
```

## Limitações conhecidas (v1.1, além das já documentadas na v1.0)

- **Single-user/single-portfolio, sem autenticação** — decisão de escopo explícita desde a Fase 0 (`docs/WEB_APP_ARCHITECTURE.md`); autenticação multiusuário fica para uma versão futura (v1.2+).
- **Playwright não roda na Vercel** — por isso o backend precisa de um serviço long-running (Render/Fly.io/Railway), não a própria Vercel; ver `docs/VERCEL_DEPLOYMENT.md`.
- **Cold start em planos gratuitos** de hospedagem de backend (ex.: Render free tier) pode levar a primeira requisição a demorar ~30s após um período de inatividade.
- **Build do Next.js depende de acesso à internet** para buscar a fonte Inter via `next/font/google` — sem rede, o build falha nesse único ponto (não afeta `dev`/`typecheck`/`lint`).
- Limitações herdadas da v1.0.0 continuam válidas (Yahoo Finance como proxy de fundamentos, câmbio só para exibição, Dividendos.me depende de scraping e é opcional) — ver `README.md`.

## Próximos passos (documentados aqui, **não executados** nesta RC)

1. Revisão do usuário sobre esta RC (visual já validado; falta a revisão final de conteúdo/documentação).
2. Deploy real: frontend na Vercel (`docs/VERCEL_DEPLOYMENT.md`), backend em Render/Fly/Railway, banco migrado para Supabase Postgres (`docs/SUPABASE_MIGRATION_PLAN.md`).
3. Merge de `feature/v1.1-premium-web-app` em `main` — **não feito nesta RC**, por decisão explícita do usuário.
4. Criação da tag `v1.1.0` — **não feita nesta RC**, mesma decisão.
5. Após o merge, avaliar quando descontinuar o Streamlit legado (ou mantê-lo como fallback permanente — decisão do usuário, não técnica).

## Estado dos branches

- `main` — v1.0.0, sem alterações (`git diff --stat v1.0.0 main` vazio).
- `feature/v1.1-premium-web-app` — as 11 fases da migração, RC-ready, aguardando revisão do usuário.
