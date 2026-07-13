# Runbook Local — LG INVEST v1.0

Comandos do dia a dia para operar a LG INVEST já instalada. Para a instalação inicial, ver `docs/INSTALLATION.md`.

Todos os comandos abaixo assumem que você está na raiz do projeto com o ambiente virtual ativado:

```bash
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

## Abrir o app

```bash
streamlit run frontend/streamlit_app/app.py
```

Abre em `http://localhost:8501`. Feche o terminal (ou `Ctrl+C`) para encerrar.

## Antes de abrir: garantir que o banco está atualizado

```bash
python -m alembic upgrade head
```

Seguro rodar sempre — não faz nada se já estiver em dia. Rode isso sempre depois de atualizar o código do app (`git pull` ou similar), antes de abrir a interface.

## Fazer backup do banco

Antes de qualquer operação arriscada (sincronizar Dividendos.me em modo `replace`, aplicar uma migration nova, testar algo):

```bash
python -m scripts.backup_database
```

Copia `data/lg_invest.db` para `data/backups/lg_invest_YYYYMMDD_HHMMSS.db`. Para manter só os N backups mais recentes:

```bash
python -m scripts.backup_database --keep-last 10
```

Sem essa flag, nenhum backup antigo é apagado — só acumula.

## Atualizar dados de mercado

Pela interface (recomendado): Dashboard → "Atualizar dados e análises" → escolha preços/fundamentos/watchlist/tudo.

Por linha de comando:

```bash
python -m scripts.update_prices --all                 # todos os ativos ativos
python -m scripts.update_prices --ticker WEGE3.SA      # um ativo específico
```

## Importar/atualizar a carteira

```bash
python -m scripts.import_portfolio --portfolio-id 1 --file caminho/arquivo.csv
```

Reimportar o mesmo arquivo atualiza posições existentes, não duplica.

## Sincronizar com o Dividendos.me (linha de comando)

```bash
python -m scripts.sync_dividendos_me --portfolio-id 1 --mode dry-run
python -m scripts.sync_dividendos_me --portfolio-id 1 --mode update --confirm
python -m scripts.sync_dividendos_me --portfolio-id 1 --mode replace --confirm
```

`dry-run` nunca altera nada. `replace`/`update` sem `--confirm` só mostram o preview e param — a confirmação é sempre uma decisão explícita. Credenciais vêm sempre de `.env` (`DIVIDENDOS_ME_EMAIL`/`DIVIDENDOS_ME_PASSWORD`), nunca de argumento de linha de comando.

## Gerar um resumo/recomendação sem abrir a interface

```bash
python -m scripts.portfolio_summary --portfolio-id 1
python -m scripts.lg_score --portfolio-id 1
python -m scripts.recommend --portfolio-id 1 --amount 1000
```

Todos imprimem JSON — úteis para automação ou depuração rápida.

## Rodar os testes

```bash
python -m pytest -q
```

## Checar qualidade de código (antes de propor uma mudança)

```bash
python -m ruff check .
python -m black --check .
```

Para autoformatar:

```bash
python -m black .
```

## Atualizar o app para uma versão nova (git pull)

```bash
git pull
pip install -r requirements-dev.txt   # se dependências mudaram
python -m alembic upgrade head        # sempre, antes de abrir
streamlit run frontend/streamlit_app/app.py
```

**Recomendado:** rode `python -m scripts.backup_database` antes de atualizar, especialmente se a versão nova trouxer uma migration.

## Onde ficam os dados

- Banco: `data/lg_invest.db` (SQLite, não versionado).
- Backups: `data/backups/` (não versionado).
- Configurações salvas (câmbio manual, alocação-alvo, etc.): tabelas do próprio banco — não há arquivos de config soltos além do `.env`.

## Se algo der errado

Ver `docs/TROUBLESHOOTING.md`.
