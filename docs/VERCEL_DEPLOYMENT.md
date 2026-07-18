# Deploy da LG INVEST v1.1 — Vercel (frontend) + Render (backend)

> Guia de deploy para a v1.1 (Next.js + FastAPI). Ver `docs/WEB_APP_ARCHITECTURE.md`
> para a decisão de arquitetura por trás desta separação e
> `docs/SECURITY_NOTES.md` para as regras de segurança (CORS, credenciais).
> Este documento cobre **como fazer o deploy quando o usuário decidir**
> — nenhum deploy foi executado como parte da RC v1.1.0-rc1.
>
> **Estado conhecido (14/07/2026):** o repositório GitHub
> (`lugabrield/lg-invest`) já tem a branch `feature/v1.1-premium-web-app`
> enviada. O projeto Supabase Postgres já existe (criado na Sprint 20,
> usado em produção pelo Streamlit v1.0.0) — não é preciso criar um
> banco novo, só reaproveitar a mesma Connection String. Falta só criar
> as contas/serviços no Vercel e no Render e conectá-los a este repo.

## Visão geral

```
Next.js (frontend-next/)   →  Vercel
FastAPI (backend/app/api/) →  Render (Web Service via Blueprint — render.yaml)
Banco                       →  Supabase Postgres (já existe, reaproveitado da Sprint 20)
```

O frontend nunca acessa o banco nem chama Python diretamente — toda leitura/escrita passa pela API via `NEXT_PUBLIC_API_URL`.

## Por que o backend não vai para a Vercel

Resumo (detalhes completos em `docs/WEB_APP_ARCHITECTURE.md`): Playwright (usado na sincronização com o Dividendos.me) precisa de um binário de browser real e pode levar mais tempo do que o limite de uma função serverless da Vercel, e a atualização de preços/fundamentos em lote também pode passar de alguns segundos para carteiras maiores. Por isso o backend precisa de um processo long-running de verdade — escolhido o Render.

## 1. Deploy do backend (Render, via Blueprint)

O repositório já tem `render.yaml` no root, pronto para o modo **Blueprint** do Render — ele lê o arquivo e propõe criar o serviço automaticamente, sem precisar preencher build/start command na mão.

1. Criar conta em [render.com](https://render.com) (grátis) e conectar sua conta GitHub.
2. No painel, **"New +" → "Blueprint"**.
3. Selecionar o repositório `lugabrield/lg-invest`. O Render vai detectar `render.yaml` automaticamente e mostrar o serviço `lg-invest-api` (branch `feature/v1.1-premium-web-app`, plano free) pronto para criar.
4. Antes de confirmar, o Render vai pedir os valores das duas variáveis marcadas `sync: false` no `render.yaml` (nunca ficam no arquivo versionado):

   | Variável | Valor | Onde conseguir |
   |---|---|---|
   | `DATABASE_URL` | Connection String do Supabase (pooler modo *transaction*, porta 6543, `?sslmode=require`) | Painel do Supabase → Project Settings → Database → Connection Pooling. **Mesma string já usada no deploy do Streamlit v1.0.0 na Sprint 20** — não precisa criar um projeto novo. |
   | `API_CORS_ORIGINS` | domínio da Vercel (ex.: `https://lg-invest.vercel.app`) | Só existe **depois** do passo 2 (deploy do frontend) — pode deixar um valor temporário (`http://localhost:3000`) agora e atualizar depois, sem precisar recriar o serviço. |

5. Confirmar a criação. O Render vai: instalar as dependências (`pip install -e .`), instalar o Chromium do Playwright (`playwright install --with-deps chromium`) e subir o serviço (`uvicorn ... --port $PORT`). O primeiro build demora mais por causa do Playwright (alguns minutos) — builds seguintes são mais rápidos com cache.
6. Depois que o serviço subir, rodar as migrations contra o Postgres do Supabase (**a cadeia de migrations já está aplicada desde a Sprint 20** — só confirmar que não há nada pendente):
   ```bash
   # localmente, com DATABASE_URL apontando para o Supabase:
   python -m alembic upgrade head
   ```
7. Testar o healthcheck: `https://<seu-serviço>.onrender.com/api/system/status` deve responder 200.
8. Copiar a URL pública do serviço (ex.: `https://lg-invest-api.onrender.com`) — vai ser usada como `NEXT_PUBLIC_API_URL` no passo 2.

### Cold start (plano gratuito)

O plano free do Render "dorme" após um período de inatividade — a primeira requisição depois disso pode levar até ~30s enquanto o serviço acorda. Isso é esperado, não um bug. Se isso incomodar no uso real, considerar o plano pago mais barato (mantém o processo sempre ativo).

### Sobre o Chromium/Playwright no plano free

O plano free do Render tem RAM limitada (512MB). O Chromium do Playwright roda dentro desse limite para uma sincronização isolada (não concorrente), mas se a sincronização com o Dividendos.me falhar por falta de memória em produção, o sintoma mais provável é um erro genérico/timeout na rota `/api/dividendos-me/*` — nesse caso, considerar o plano pago de entrada do Render (mais RAM) só para esse serviço.

## 2. Deploy do frontend (Vercel)

1. Criar conta em [vercel.com](https://vercel.com) (grátis) e conectar sua conta GitHub.
2. **"Add New..." → "Project"** → selecionar `lugabrield/lg-invest`.
3. **Root Directory:** `frontend-next/` (ajustar esse campo na tela de configuração do projeto — a Vercel detecta Next.js automaticamente a partir daí).
4. **Branch:** `feature/v1.1-premium-web-app` (a Vercel também vai gerar preview deploys automáticos para outras branches/PRs, se quiser usar depois).
5. Variável de ambiente do projeto:

   | Nome | Valor | Ambiente |
   |---|---|---|
   | `NEXT_PUBLIC_API_URL` | URL do backend no Render (do passo 1.8, ex.: `https://lg-invest-api.onrender.com`) | Production, Preview, Development |

6. Deploy. Cada push na branch conectada gera um novo deploy automaticamente daí em diante.
7. Depois que o domínio da Vercel existir (ex.: `https://lg-invest.vercel.app`), voltar ao painel do Render e atualizar `API_CORS_ORIGINS` com esse domínio real (passo 1.4 tinha um placeholder) — o serviço reinicia sozinho ao salvar a variável.

**Atenção (limitação conhecida, não é bug):** o build depende de acesso à internet para buscar a fonte Inter via `next/font/google` (`app/layout.tsx`). Isso funciona normalmente na Vercel (que tem acesso à internet real durante o build) — só falhou no sandbox usado para validar a RC (sem rede).

## 3. Banco de dados (Supabase Postgres — já existe)

Nenhuma ação nova necessária aqui além de reaproveitar a Connection String já usada na Sprint 20 (ver passo 1.4). SQLAlchemy já é agnóstico a banco — o backend v1.1 usa a mesma camada de acesso a dados do Streamlit v1.0.0, sem nenhuma mudança de modelo ou migration nesta versão. Ver `docs/SUPABASE_MIGRATION_PLAN.md` para o histórico completo da migração original, se precisar relembrar os detalhes (pooler session x transaction, IPv4/IPv6, etc.).

## 4. Checklist antes de apontar o domínio de produção

- [ ] `NEXT_PUBLIC_API_URL` na Vercel aponta para a URL final do Render (não `localhost`).
- [ ] `API_CORS_ORIGINS` no Render lista exatamente o domínio da Vercel usado em produção (sem `*`).
- [ ] `DATABASE_URL` no Render aponta para o Supabase Postgres (pooler *transaction*, `?sslmode=require`), não para SQLite.
- [ ] `python -m alembic upgrade head` confirmado sem pendências contra o Supabase.
- [ ] Chromium instalado no build do Render (`playwright install --with-deps chromium` — já no `buildCommand` do `render.yaml`) — testar a sincronização com o Dividendos.me uma vez em produção antes de anunciar a feature como disponível.
- [ ] Healthcheck `GET /api/system/status` respondendo 200 no domínio do Render.
- [ ] Nenhuma credencial (Dividendos.me, `DATABASE_URL`) versionada em `.env` no repositório — todas configuradas via painel do Render/Vercel.

## 5. Rollback

Como o Streamlit legado (`frontend/streamlit_app/`) continua funcional e usando o mesmo banco Supabase, ele serve como fallback natural: se o deploy da v1.1 apresentar um problema, você pode continuar operando via Streamlit (local ou o deploy existente no Streamlit Community Cloud da Sprint 20) enquanto o problema é investigado — não há necessidade de reverter dados, já que nenhuma migration ou regra de negócio mudou nesta versão.
