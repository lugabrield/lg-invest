# Deploy da LG INVEST v1.1 — Vercel (frontend) + Backend long-running

> Guia de deploy para a v1.1 (Next.js + FastAPI). Ver `docs/WEB_APP_ARCHITECTURE.md`
> para a decisão de arquitetura por trás desta separação e
> `docs/SECURITY_NOTES.md` para as regras de segurança (CORS, credenciais).
> Este documento cobre **como fazer o deploy quando o usuário decidir**
> — nenhum deploy foi executado como parte da RC v1.1.0-rc1.

## Visão geral

```
Next.js (frontend-next/)  →  Vercel
FastAPI (backend/app/api/) →  Render, Fly.io ou Railway (não a Vercel)
Banco                       →  Supabase Postgres (produção) — SQLite só em dev local
```

O frontend nunca acessa o banco nem chama Python diretamente — toda leitura/escrita passa pela API via `NEXT_PUBLIC_API_URL`.

## Por que o backend não vai para a Vercel

Resumo (detalhes completos em `docs/WEB_APP_ARCHITECTURE.md`): Playwright (usado na sincronização com o Dividendos.me) precisa de um binário de browser real e pode levar mais tempo do que o limite de uma função serverless da Vercel, e a atualização de preços/fundamentos em lote também pode passar de alguns segundos para carteiras maiores. Por isso o backend precisa de um processo long-running de verdade.

## 1. Deploy do frontend (Vercel)

1. Conectar o repositório GitHub à Vercel (ou `vercel link` via CLI).
2. **Root Directory:** `frontend-next/` (a Vercel detecta Next.js automaticamente).
3. Build command padrão (`next build`) e output padrão — nenhuma configuração extra necessária além da variável de ambiente abaixo.
4. Variável de ambiente no projeto Vercel:

   | Nome | Valor | Ambiente |
   |---|---|---|
   | `NEXT_PUBLIC_API_URL` | URL pública do backend (ex.: `https://lg-invest-api.onrender.com`) | Production, Preview, Development |

5. Deploy por push — cada push na branch conectada gera um novo deploy (ou preview deploy para outras branches/PRs).

**Atenção (limitação conhecida, não é bug):** o build depende de acesso à internet para buscar a fonte Inter via `next/font/google` (`app/layout.tsx`). Isso funciona normalmente na Vercel (que tem acesso à internet real durante o build) — só falha em ambientes de build sem rede, como foi o caso do sandbox usado para validar esta RC.

## 2. Deploy do backend (Render, Fly.io ou Railway)

A escolha entre os três é operacional, não arquitetural — qualquer um roda Python + Playwright sem problema. Passos genéricos (adaptar à interface específica do serviço escolhido):

1. **Root/build:** apontar para a raiz do repositório (não `frontend-next/`); o serviço precisa rodar `pip install -e .` (ou equivalente ao `pyproject.toml`) e `playwright install chromium --with-deps` (necessário para a sincronização com o Dividendos.me funcionar em produção).
2. **Start command:**
   ```bash
   uvicorn backend.app.api.app:app --host 0.0.0.0 --port $PORT
   ```
3. **Variáveis de ambiente** (nunca versionadas — configurar direto no painel do serviço):

   | Nome | Valor | Observação |
   |---|---|---|
   | `ENVIRONMENT` | `production` | |
   | `DATABASE_URL` | string de conexão do Supabase Postgres | `postgresql+psycopg2://...` — ver `docs/SUPABASE_MIGRATION_PLAN.md` |
   | `API_CORS_ORIGINS` | domínio(s) da Vercel, separados por vírgula (ex.: `https://lg-invest.vercel.app`) | **Nunca `*`** — restringe quem pode chamar a API pelo navegador (ver `docs/SECURITY_NOTES.md`) |
   | `YAHOO_FINANCE_ENABLED` | `true` | |
   | `BCB_FX_ENABLED` | `true` | |
   | `LOG_LEVEL` | `INFO` | |
   | Credenciais do Dividendos.me | **não configurar aqui** | Na v1.1, e-mail/senha vêm no body de cada requisição do frontend (modal), nunca de variável de ambiente do servidor — ver `docs/DIVIDENDOS_ME_FRONT_SYNC.md` |

4. Rodar as migrations Alembic contra o banco de produção antes do primeiro deploy (ou como parte do processo de start, conforme a política do serviço escolhido):
   ```bash
   python -m alembic upgrade head
   ```

### Cold start (plano gratuito)

Serviços gratuitos (ex.: Render free tier) "dormem" após um período de inatividade — a primeira requisição depois disso pode levar até ~30s enquanto o serviço acorda. Isso é esperado, não um bug. Se isso incomodar no uso real, considerar um plano pago de baixo custo (mantém o processo sempre ativo).

## 3. Banco de dados (Supabase Postgres)

SQLAlchemy já é agnóstico a banco — a migração de SQLite (dev) para Postgres (produção) é só trocar `DATABASE_URL`, sem mudança de código. Ver `docs/SUPABASE_MIGRATION_PLAN.md` para o passo a passo completo de criação do projeto Supabase e migração de dados existentes.

## 4. Checklist antes de apontar o domínio de produção

- [ ] `NEXT_PUBLIC_API_URL` na Vercel aponta para a URL final do backend (não `localhost`).
- [ ] `API_CORS_ORIGINS` no backend lista exatamente o(s) domínio(s) da Vercel usados em produção (sem `*`).
- [ ] `DATABASE_URL` do backend aponta para o Supabase Postgres de produção, não para o SQLite de dev.
- [ ] Migrations Alembic aplicadas contra o banco de produção (`alembic upgrade head`).
- [ ] Playwright instalado no serviço do backend (`playwright install chromium --with-deps`) — testar a sincronização com o Dividendos.me uma vez em produção antes de anunciar a feature como disponível.
- [ ] Nenhuma credencial (Dividendos.me, `DATABASE_URL`) versionada em `.env` no repositório — todas configuradas via painel do serviço/Vercel.

## 5. Rollback

Como o Streamlit legado (`frontend/streamlit_app/`) continua funcional e usando o mesmo banco, ele serve como fallback natural: se o deploy da v1.1 apresentar um problema, o usuário pode continuar operando via Streamlit local enquanto o problema é investigado — não há necessidade de reverter dados, já que nenhuma migration ou regra de negócio mudou nesta versão.
