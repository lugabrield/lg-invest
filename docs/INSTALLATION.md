# Instalação — LG INVEST v1.0

Guia completo para instalar e rodar a LG INVEST localmente pela primeira vez. Para o uso do dia a dia depois de já instalado, ver `docs/LOCAL_RUNBOOK.md`.

## Pré-requisitos

- **Python 3.11 ou superior** (obrigatório).
- Conexão com a internet, para buscar preços/fundamentos via Yahoo Finance e câmbio via BCB — o app funciona offline só com os dados já salvos no banco.
- (Opcional) Uma conta no [Dividendos.me](https://dividendos.me), se você quiser sincronizar a carteira automaticamente em vez de importar CSV/Excel manualmente.

## Passo a passo

### 1. Entrar na pasta do projeto

```bash
cd lg-invest
```

### 2. Criar e ativar um ambiente virtual

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 3. Instalar as dependências

```bash
pip install -r requirements-dev.txt
```

Isso instala tanto as dependências do app (`requirements.txt`) quanto as de desenvolvimento (pytest, ruff, black, mypy, pre-commit).

Se você pretende usar a sincronização com o Dividendos.me, instale também o navegador do Playwright (só precisa rodar uma vez):

```bash
playwright install chromium
```

Sem isso, a tela "Sincronizar Dividendos.me" detecta a ausência do Playwright e desabilita os botões de sincronização automaticamente — o resto do app funciona normalmente.

### 4. Configurar as variáveis de ambiente

```bash
cp .env.example .env
```

Abra o `.env` e revise:

| Variável | Obrigatório? | Descrição |
|---|---|---|
| `ENVIRONMENT` | Não (default `development`) | `development` ou `production`. |
| `DATABASE_URL` | Não (default SQLite local) | `sqlite:///./data/lg_invest.db` por padrão. Para Postgres/Supabase, ver `docs/SUPABASE_MIGRATION_PLAN.md`. |
| `YAHOO_FINANCE_ENABLED` | Não (default `true`) | Desligar impede qualquer chamada ao Yahoo Finance. |
| `BCB_FX_ENABLED` | Não (default `true`) | Desligar pula direto para o fallback Yahoo Finance/manual no câmbio USD/BRL. |
| `LOG_LEVEL` | Não (default `INFO`) | `DEBUG`, `INFO`, `WARNING` ou `ERROR`. |
| `DIVIDENDOS_ME_EMAIL` / `DIVIDENDOS_ME_PASSWORD` | Só se for usar a sincronização | Credenciais da SUA conta no Dividendos.me. Nunca são salvas em banco, nunca aparecem em log, nunca são exibidas na interface (a tela só mostra "configurado: sim/não"). |

**Nunca versione o arquivo `.env` real** — ele já está no `.gitignore`. Nenhuma chave de API ou credencial deve aparecer em nenhum arquivo versionado.

### 5. Aplicar as migrations do banco

```bash
python -m alembic upgrade head
```

Isso cria `data/lg_invest.db` (SQLite) do zero, com todas as tabelas e colunas atuais. Rodar este comando de novo em um banco já atualizado não faz nada (idempotente) — é seguro rodar sempre que for atualizar o app.

### 6. (Opcional) Popular ativos de demonstração

```bash
python -m database.seeds.assets_seed
```

Idempotente — não duplica se rodar de novo.

### 7. Importar sua carteira

**Opção A — manualmente via CSV/Excel:**

```bash
python -m scripts.import_portfolio \
    --portfolio-id 1 \
    --file database/seeds/positions_template.csv \
    --create-portfolio
```

Use `database/seeds/positions_template.csv` como modelo do formato esperado. Reimportar o mesmo arquivo atualiza as posições existentes (não duplica). Linhas inválidas geram um relatório de erro por linha, sem abortar a importação das linhas válidas.

**Opção B — via Dividendos.me (dentro do app, depois de abrir):** ver `docs/USER_GUIDE.md`, seção "Sincronizar Dividendos.me".

### 8. Abrir o app

```bash
streamlit run frontend/streamlit_app/app.py
```

Abre no navegador em `http://localhost:8501` por padrão. A sidebar mostra a versão atual da LG INVEST no rodapé.

### 9. Validar que está tudo funcionando

```bash
python -m pytest -q
```

Deve terminar sem falhas. Ver `docs/TROUBLESHOOTING.md` se algo der errado.

## Instalação em uma máquina nova (checklist rápido)

1. Python 3.11+ instalado.
2. `python -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements-dev.txt`
4. `playwright install chromium` (só se for usar Dividendos.me)
5. `cp .env.example .env` e preencher o que for necessário
6. `python -m alembic upgrade head`
7. Importar a carteira (CSV/Excel ou Dividendos.me)
8. `streamlit run frontend/streamlit_app/app.py`

## Próximos passos

- `docs/USER_GUIDE.md` — como usar cada tela.
- `docs/LOCAL_RUNBOOK.md` — comandos do dia a dia depois de instalado.
- `docs/TROUBLESHOOTING.md` — se algo der errado durante a instalação.
