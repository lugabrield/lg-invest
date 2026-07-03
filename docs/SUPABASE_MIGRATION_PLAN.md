# Plano de Migração — SQLite → Supabase/PostgreSQL (futuro)

> Este documento é só planejamento. A migração **não** foi executada
> nesta sprint — o banco de desenvolvimento continua sendo
> `data/lg_invest.db` (SQLite) até você aprovar.

## Por que Supabase/PostgreSQL

- SQLite local vive num único arquivo no seu computador: sem acesso
  remoto, sem múltiplos escritores simultâneos, e qualquer deploy num
  serviço com disco efêmero (como o Streamlit Community Cloud) perde os
  dados a cada reinício do container.
- Supabase oferece Postgres gerenciado com um free tier funcional,
  acesso via internet e backups básicos — persistência real fora do seu
  PC, sem custo inicial.
- O projeto já foi construído para essa transição: `SQLAlchemy` é a
  única camada de acesso a banco, `DATABASE_URL` já vem de variável de
  ambiente (`backend/app/core/config.py`), e `session.py` já trata
  SQLite x Postgres condicionalmente (`check_same_thread` só se aplica a
  SQLite).

## Riscos de continuar só com SQLite

- Sem acesso de qualquer lugar (preso ao seu PC/pasta local).
- Sem backup automático — perda do arquivo `.db` é perda de todo o
  histórico de carteira, preços e recomendações.
- Não sobrevive a deploy em ambiente com disco efêmero.
- Sem suporte real a acesso concorrente (não é um problema hoje, de uso
  pessoal e local, mas seria num app publicado).

## O que muda (e o que não muda) no código

**Não muda:**
- `backend/app/infrastructure/database/session.py` — já lê
  `settings.database_url` e já decide `connect_args` condicionalmente.
- Nenhum repositório, service ou engine — todos usam SQLAlchemy de forma
  agnóstica ao banco por trás.
- Modelos (`backend/app/infrastructure/database/models/*.py`) — tipos
  `Numeric`, `String`, `Date`, `DateTime` são todos suportados por
  Postgres sem alteração.

**Muda:**
- `DATABASE_URL` passa de `sqlite:///./data/lg_invest.db` para algo como
  `postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DATABASE` (placeholder —
  a URL real nunca deve ir para o repositório).
- Nova dependência: `psycopg2-binary` (driver Postgres para Python) —
  precisa ser adicionada ao `requirements.txt`/`pyproject.toml` quando a
  migração for aprovada. Não incluída ainda porque o MVP roda em SQLite.
- `alembic upgrade head` passa a rodar contra o Postgres em vez do
  SQLite — as migrations já existentes (`database/migrations/versions/`)
  são compatíveis, pois usam tipos genéricos do SQLAlchemy/Alembic.

## Passo a passo (quando for aprovado)

1. Criar um projeto no Supabase e copiar a **Connection String**
   (formato `postgresql://...`) — trocar o driver para
   `postgresql+psycopg2://...` para uso com SQLAlchemy + psycopg2.
2. Adicionar `psycopg2-binary` às dependências.
3. Definir `DATABASE_URL` (local, via `.env`; em produção, via Secrets do
   Streamlit Cloud) apontando para o Supabase.
4. Rodar `alembic upgrade head` contra o Postgres vazio — cria todas as
   tabelas do zero (mesmas migrations já existentes).
5. **Migrar os dados existentes** do SQLite local: como o MVP ainda é de
   uso pessoal (poucos registros), o caminho mais simples é exportar cada
   tabela relevante (`assets`, `portfolios`, `positions`, `prices`,
   `recommendations`, `journal_entries`, `investment_theses`,
   `thesis_reviews`, `decision_snapshots`) e reimportar no Postgres — via
   um script simples de leitura SQLite + escrita Postgres usando os
   próprios repositórios/SQLAlchemy (evita reescrever SQL manualmente e
   respeita as validações de cada model).
6. Validar com `python -m pytest` apontando `DATABASE_URL` para um banco
   Postgres de teste (não o de produção) antes de considerar a migração
   concluída.
7. Só depois disso, seguir para o deploy (`docs/DEPLOYMENT_PLAN.md`).

## O que fica fora do escopo

- Migração automática/script pronto — esta sprint só documenta o plano;
  o script de migração de dados é trabalho de uma sprint futura,
  dedicada e aprovada separadamente.
- Multiusuário / Row Level Security do Supabase — hoje a LG INVEST é de
  uso pessoal (Volume 17); RLS só faria sentido com múltiplos usuários.
- Connection pooling avançado (PgBouncer) — o free tier do Supabase já
  inclui um pooler básico (modo transaction), suficiente para o volume
  de uso de um app pessoal.

## Segurança

- Nunca commitar `.env` (já protegido pelo `.gitignore`).
- Nunca escrever a `DATABASE_URL` real em código, documentação ou
  mensagens de commit — usar sempre o placeholder
  `postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DATABASE`.
- Credenciais de produção só devem existir nos Secrets do Streamlit
  Community Cloud (ou no `.env` local, nunca versionado).
