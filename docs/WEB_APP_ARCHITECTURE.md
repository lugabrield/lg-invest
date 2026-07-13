# Arquitetura da LG INVEST v1.1 — Premium Web App

> Documento de decisão de arquitetura para a migração Streamlit → Next.js
> (branch `feature/v1.1-premium-web-app`). Ver `docs/V1_1_MIGRATION_PLAN.md`
> para o plano por fases e `docs/API_CONTRACT.md` para o contrato dos
> endpoints.

## Resumo da decisão

| Camada | Onde roda | Por quê |
|---|---|---|
| Frontend (Next.js) | Vercel | É exatamente o que a Vercel faz de melhor: build estático + SSR, CDN global, deploy por push. |
| Backend/API (FastAPI) | **Fora da Vercel** — Render, Fly.io ou Railway (um serviço long-running) | Playwright (Dividendos.me) precisa de um binário de browser real e pode levar minutos — incompatível com função serverless de curta duração da Vercel. Ver seção "Por que não a Vercel para o backend". |
| Banco | Supabase Postgres | SQLAlchemy já é agnóstico a banco (`docs/SUPABASE_MIGRATION_PLAN.md` já mapeava isso desde a Sprint 20) — só troca `DATABASE_URL`. |
| Engines Python | Dentro do backend FastAPI, sem nenhuma mudança de lógica | São a fonte da verdade; o Next.js nunca recalcula nada. |
| Streamlit legado | Continua rodando localmente (`frontend/streamlit_app/`) até o Next.js cobrir o fluxo principal | Ninguém fica sem app funcional durante a migração. |

## Por que não colocar tudo na Vercel

A Vercel é excelente para o frontend, mas tem três limitações que colidem
diretamente com o que a LG INVEST já faz hoje:

1. **Playwright/Dividendos.me.** `backend/app/integrations/dividendos_me/client.py`
   usa `playwright.sync_api.sync_playwright()` de verdade — abre um
   Chromium, navega, espera seletores. Isso não roda em Vercel Functions
   (sem binário de browser disponível, timeout de poucos segundos a ~60s
   mesmo no plano pago, sem estado entre chamadas). Forçar isso na Vercel
   seria a "gambiarra" que o objetivo original pediu para evitar.
2. **Jobs potencialmente longos.** Atualização de preços/fundamentos em
   lote (`DataRefreshService`, usado pela Central de Dados) itera sobre
   todos os ativos da carteira chamando Yahoo Finance um a um — para
   carteiras maiores, isso passa fácil de 10s. Função serverless de
   short-lived não é o lugar certo.
3. **SQLite de desenvolvimento.** Nada na Vercel tem disco persistente
   entre invocações — mas isso já não é um problema novo: a v1.0.0 local
   já usa SQLite só em dev, e produção sempre foi planejada para Postgres
   (Supabase) desde a Sprint 20.

Conclusão: **frontend na Vercel, backend em um serviço long-running**
(Render/Fly/Railway — a escolha exata entre os três é operacional, não
arquitetural; qualquer um dos três roda Python + Playwright sem
problema). Isso não é gambiarra — é a mesma separação frontend/backend
que qualquer produto SaaS sério usa quando tem uma dependência de
browser automation no backend.

## O que muda e o que não muda

**Não muda (reaproveitado 100%):**
- Todas as engines em `backend/app/engines/*` — puras, sem I/O, já
  teste-cobertas. O FastAPI só chama os `services/*` que já orquestram
  essas engines.
- Todos os `services/*` — a API é uma camada fina que serializa o que
  esses services já retornam (schemas Pydantic) em JSON.
- Todos os `schemas/*` (Pydantic) — já são o contrato de dados; o
  FastAPI os expõe quase diretamente como response models.
- `backend/app/integrations/dividendos_me/*` — o `DividendosMeClient`
  já recebe `email`/`password` no construtor (não lê de env/secrets
  internamente), então já está pronto para receber credenciais vindas
  de uma requisição HTTP sem nenhuma mudança de assinatura.
- Alembic, migrations, modelos SQLAlchemy.
- Toda a suíte de 1213 testes de `backend/tests/`.

**Novo (a construir):**
- `apps/api` (ou `backend/api`) — camada FastAPI fina: rotas, DI de
  sessão de banco, serialização, tratamento de erro HTTP. Zero regra de
  negócio nova.
- `frontend-next/` — o app Next.js.
- Testes de API (contrato/serialização) e testes de componente no
  frontend.

**Fica para depois (fora do escopo da v1.1, conforme pedido do usuário):**
- Autenticação multiusuário — v1.1 continua single-user, protegida por
  o backend não ser público/aberto (rede privada ou allowlist de IP/CORS
  restrito ao domínio da Vercel). Autenticação de verdade (Supabase Auth
  ou similar) fica para v1.2.

## Estrutura de pastas proposta

Avaliei as duas opções que o brief trouxe. Recomendo a mais simples:

```
lg-invest/
├── backend/                  # inalterado — engines, services, models, migrations, testes
│   └── app/
│       └── api/               # NOVO: FastAPI (routers, dependencies, main.py)
├── frontend/
│   └── streamlit_app/         # legado — mantido rodando até o Next.js cobrir o fluxo principal
├── frontend-next/             # NOVO: Next.js App Router + TypeScript + Tailwind
├── docs/
└── scripts/
```

Por quê `backend/app/api/` em vez de `apps/api/` separado: o FastAPI
importa diretamente `backend.app.services.*`, `backend.app.engines.*` e
`backend.app.schemas.*` — colocá-lo dentro de `backend/app/` evita
qualquer ginástica de path/import entre pacotes (o padrão
`from backend.app...` já usado em todo o projeto continua igual) e
mantém uma única árvore de dependências Python. Um `apps/` monorepo faz
sentido quando backend e frontend Python são projetos Python
independentes com seus próprios `pyproject.toml` — não é o caso aqui: o
FastAPI é literalmente uma nova forma de expor o mesmo `backend/`.

`frontend-next/` (não `apps/web/`) porque não há um segundo app Python
disputando o nome `apps/` — um nome direto ao ponto evita indireção
desnecessária.

## Fluxo de dados (visão geral)

```
Next.js (Vercel)
   │  fetch (HTTPS, JSON)
   ▼
FastAPI (Render/Fly/Railway)
   │  chama services/engines existentes
   ▼
SQLAlchemy
   │
   ▼
Supabase Postgres (produção) / SQLite (dev local)
```

O Next.js **nunca** acessa o banco diretamente e **nunca** importa
código Python — toda leitura/escrita passa pela API.

## Variáveis de ambiente e segredos

| Variável | Onde vive | Pública? |
|---|---|---|
| `DATABASE_URL` (Postgres) | Backend (Render/Fly/Railway secrets) | Não — nunca no frontend, nunca em `NEXT_PUBLIC_*` |
| `NEXT_PUBLIC_API_URL` | Frontend (Vercel env var) | Sim — é só a URL pública da API, sem credenciais |
| `CORS_ALLOWED_ORIGINS` | Backend | Não é segredo, mas fica só no backend (restringe a origem ao domínio da Vercel) |
| Credenciais do Dividendos.me | Nunca armazenadas — vêm em cada requisição, usadas em memória, descartadas | N/A — ver `docs/DIVIDENDOS_ME_FRONT_SYNC.md` |
| `YAHOO_FINANCE_ENABLED`, `BCB_FX_ENABLED`, `LOG_LEVEL` | Backend | Não |

## Riscos

1. **Cold start do backend em serviços gratuitos** (Render free tier
   "dorme" após inatividade) — primeira requisição depois de um tempo
   parado pode levar ~30s. Mitigação: documentar isso claramente
   (`docs/VERCEL_DEPLOYMENT.md`, a escrever na Fase 9) e considerar um
   plano pago baixo custo se o cold start incomodar no uso real.
2. **Playwright em produção é a parte mais frágil já hoje** (dependente
   de o Dividendos.me não mudar a estrutura da página) — isso não piora
   com a migração, mas também não melhora sozinho; a Fase 8 do plano
   trata isso à parte.
3. **CORS mal configurado** expõe a API a qualquer origem — mitigado
   documentando explicitamente a lista de origens permitidas em
   `docs/SECURITY_NOTES.md` e testando isso.
4. **Duplicar sem querer alguma regra no frontend** (ex.: formatar uma
   classificação de risco com uma cor "na mão" em vez de vir pronta da
   API) — mitigado pela regra explícita (também do usuário): frontend
   nunca calcula, só apresenta. Reforçado em `docs/API_CONTRACT.md`
   (a API já devolve labels/cores/status prontos, não só números crus).
5. **Dessincronia entre Streamlit e Next.js durante a migração** — as
   duas UIs vão coexistir por várias fases; se uma regra mudar, as duas
   têm que refletir. Mitigado porque nenhuma regra muda nesta migração
   (só camada de apresentação nova) — mudanças de regra ficam
   congeladas até o Next.js substituir o Streamlit.

## Como os testes atuais são preservados

- Nenhum arquivo em `backend/tests/` muda de comportamento — a suíte de
  1213 testes continua rodando exatamente como está, validando
  engines/services independentemente de qual frontend os consome.
- Novos testes de API (Fase 2 em diante) vivem em
  `backend/tests/api/` (ou `backend/tests/unit/test_api_*.py`, a
  decidir na Fase 2), usando `fastapi.testclient.TestClient` — mesma
  fixture `db_session` já usada pelos testes de service.
- Novos testes de frontend (Next.js) vivem em `frontend-next/` com
  Vitest/Testing Library (ou Playwright para e2e, se fizer sentido mais
  adiante) — não competem nem duplicam os testes Python.
