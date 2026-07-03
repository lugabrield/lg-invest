# Plano de Deploy — Streamlit Community Cloud (futuro)

> Este documento é só planejamento. Nenhum passo aqui foi executado nesta
> sprint — a LG INVEST continua rodando localmente, com SQLite, até você
> aprovar o deploy explicitamente.

## Objetivo

Publicar a LG INVEST no Streamlit Community Cloud (custo zero) apontando
para um banco Postgres gerenciado (Supabase), acessível de qualquer lugar.

## Pré-requisitos antes de subir

1. **Repositório no GitHub.** Streamlit Community Cloud faz deploy direto
   de um repositório GitHub (público ou privado, com conta autorizada).
2. **Banco migrado para Supabase/PostgreSQL** — ver
   `docs/SUPABASE_MIGRATION_PLAN.md`. O deploy no Streamlit Cloud só faz
   sentido com um banco acessível pela internet; SQLite local não
   sobrevive a um reinício do container do Streamlit Cloud (disco
   efêmero).
3. **Dependências no `requirements.txt`** já cobrem o necessário
   (`sqlalchemy`, `alembic`, `pydantic`, `streamlit`, `plotly`, etc.).
   Quando migrar o banco, adicionar `psycopg2-binary` (driver Postgres) —
   não incluído agora porque o MVP ainda usa SQLite.

## Passo a passo (quando for aprovado)

1. Criar o projeto no Supabase (ver plano de migração) e obter a
   `DATABASE_URL` de produção.
2. No GitHub, garantir que `.env` **não** está commitado (já é o caso —
   ver `.gitignore`) e que `data/lg_invest.db` também não sobe.
3. Criar o app no Streamlit Community Cloud apontando para
   `frontend/streamlit_app/app.py` como entrypoint.
4. Configurar os **Secrets** do app (Settings → Secrets), no formato TOML:
   ```toml
   DATABASE_URL = "postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DATABASE"
   ENVIRONMENT = "production"
   LOG_LEVEL = "INFO"
   ```
   O Streamlit Cloud injeta esses valores como variáveis de ambiente —
   `backend/app/core/config.py` já lê `DATABASE_URL` do ambiente via
   `pydantic-settings`, então nenhuma mudança de código é necessária
   para isso.
5. Rodar `alembic upgrade head` contra o banco de produção **antes** do
   primeiro acesso (localmente, apontando a `DATABASE_URL` para o
   Supabase, ou via um job manual).
6. Validar o app publicado com uma carteira de teste antes de importar a
   carteira real.

## O que fica de fora deste deploy (escopo futuro)

- CI/CD automatizado (deploy hoje seria manual, via push + restart no
  Streamlit Cloud).
- Autenticação/multiusuário — o app publicado ficaria acessível a quem
  tiver o link, a menos que configurado como privado no Streamlit Cloud.
- Backups automáticos do Postgres (o Supabase oferece isso no plano
  pago; no free tier, backups são limitados — ver plano de migração).

## Riscos conhecidos

- **Free tier do Streamlit Cloud** hiberna o app após um período sem
  acesso; o primeiro acesso após hibernar demora mais para carregar.
- **Free tier do Supabase** pausa o projeto após um período de
  inatividade (7 dias sem uso, sujeito a mudança pelas políticas atuais
  do Supabase) — o primeiro acesso após a pausa também demora mais.
- Nenhum dado sensível (senha, token) deve estar em código ou em
  `.env` versionado — só nos Secrets do Streamlit Cloud.
