# Deployment Notes — Sprint 21

Notas específicas desta sprint. Para o plano de deploy completo e a
migração inicial SQLite → Supabase, ver `docs/DEPLOYMENT_PLAN.md` e
`docs/SUPABASE_MIGRATION_PLAN.md` (já aplicados em sprint anterior — a
plataforma já está em produção no Streamlit Community Cloud com
Supabase/PostgreSQL).

## O que mudou no banco nesta sprint

Uma única migration Alembic, puramente aditiva:

```
c4d9e2a17f63 -> a1f4e6c2b8d9 (head)  "add fundamentals extra fields"
```

Adiciona 9 colunas `nullable`, sem `default`, à tabela
`fundamental_snapshots`: `market_cap`, `enterprise_value`, `forward_pe`,
`operating_margin`, `total_debt`, `total_cash`, `operating_cash_flow`,
`gross_profit`, `shares_outstanding`. Não altera, renomeia nem remove
nenhuma coluna existente; não faz backfill; não recria nem dropa
tabelas. Linhas já existentes simplesmente ficam com essas 9 colunas em
`NULL` até a próxima coleta de fundamentos. `downgrade()` é simétrico
(remove as 9 colunas, sem perda de dado nas colunas originais).

**Nenhuma outra alteração de schema foi feita nesta sprint** — Data
Quality Layer, Capital Reinvestment Engine e as mudanças de pesos/
classificação do Conviction Score v2 são puramente de código
(engines/services/UI), sem impacto em banco.

## Como rodar localmente

```powershell
# a partir da raiz do projeto, com o .venv já ativado (Python 3.11+)
python -m alembic upgrade head
python -m pytest -v
python -m ruff check .
python -m black --check .
streamlit run frontend/streamlit_app/app.py
```

## Como aplicar no Supabase (produção)

1. Confirme que a `DATABASE_URL` configurada aponta para o projeto
   Supabase correto (nunca rodar migration contra o banco errado).
2. Rode `python -m alembic upgrade head` com essa `DATABASE_URL` — o
   Alembic aplica apenas a migration `a1f4e6c2b8d9` (todas as
   anteriores já estão marcadas como aplicadas na tabela
   `alembic_version`).
3. Como a migration só adiciona colunas nullable, não há downtime
   nem necessidade de manutenção programada — o app pode continuar
   rodando durante a aplicação.
4. Verifique com `alembic current` que o head do banco de produção
   ficou em `a1f4e6c2b8d9`.

## Como validar no Streamlit Cloud

1. Faça o deploy do commit mais recente (o Streamlit Cloud rebuilda
   automaticamente ao detectar push na branch configurada).
2. Confirme visualmente que o tema escuro está ativo (fundo escuro,
   texto claro, sem cards brancos) — isso depende de
   `.streamlit/config.toml` estar presente no repositório e ser lido
   pelo Streamlit Cloud no boot do app.
3. Abra a tela **Ativos**, selecione um ativo com fundamentos
   coletados, e confirme que a seção "LG Conviction Score v2" e os
   badges de qualidade de dado aparecem sem erro.
4. Abra a tela **Inteligência** e confirme que os buckets de
   classificação (Aportar/Candidato/Manter/Monitorar/Evitar/Dados
   insuficientes) renderizam e que "Por que esse ativo?" funciona para
   pelo menos um ativo.
5. Abra a tela **Aporte**, gere uma recomendação com o checkbox
   "Decision Engine 2.0" marcado, e confirme que a seção "Como a
   carteira ficaria depois" mostra HHI e exposição internacional
   antes/depois.
6. Se algum ativo aparecer com dado que parece incompleto ou uma seção
   vazia, isso é esperado quando fundamentos ainda não foram coletados
   para aquele ativo — use o botão "Coletar fundamentos de todos os
   ativos" na tela Ativos.

## Segredos e configuração

Nenhuma variável nova de ambiente foi introduzida nesta sprint. A
`DATABASE_URL` e demais segredos continuam vindo de `st.secrets`
(Streamlit Cloud) ou `.env` (local, não versionado) — sem mudança de
mecanismo.

## Rollback

Se necessário reverter apenas a mudança desta sprint:
`python -m alembic downgrade c4d9e2a17f63` remove as 9 colunas novas
sem afetar nenhum outro dado. Reverter o código (git revert/checkout de
commit anterior) é seguro independentemente do estado do banco, pois o
código antigo simplesmente não lê os 9 campos novos.
