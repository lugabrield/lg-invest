# LG INVEST

**Investment Intelligence Platform** — transforma dados financeiros da sua carteira em decisões de investimento explicáveis, auditáveis e reproduzíveis. Feita para um investidor Buy & Hold de longo prazo (horizonte de décadas), com carteira em ações brasileiras, FIIs, ações americanas, ETFs, REITs, Bitcoin e Tesouro Direto.

A LG INVEST não é uma planilha nem um clone de Status Invest. O objetivo é responder perguntas de decisão: **qual é o valor real da minha carteira, onde devo aportar o próximo dinheiro, por quê, com qual nível de confiança, e como isso muda a composição da carteira.**

> **Status atual: v1.0.0 — app local estável, pronto para uso diário.**
> Ver `docs/RELEASE_NOTES_v1.0.md` para o resumo completo da versão e
> `docs/RELEASE_CHECKLIST.md` para os 24 critérios de prontidão verificados.

## O que a LG INVEST faz

- **Centraliza a carteira** (ações BR/EUA, FIIs, ETFs, REITs, Bitcoin, Tesouro Direto), com preços automáticos via Yahoo Finance e câmbio USD/BRL automático (BCB PTAX, com fallback).
- **Calcula qualidade dos ativos** com o LG Score e o LG Conviction Score v2 (fundamentos, valuation, crescimento, risco, reinvestimento de capital), sempre com explicação por fator e um nível de confiança que reflete a qualidade do dado disponível — nunca esconde dado ausente.
- **Sugere onde aportar** (Aporte v3 / Decision Engine 3.0), respeitando sua política de alocação, limites por classe/moeda/país/ativo e o que a carteira ficaria depois do aporte — nunca sugere vender uma posição existente.
- **Organiza candidatos novos** (Radar/Watchlist) antes de virarem posição.
- **Analisa fundamentos** por ativo (Valuation Engine 2.0 para ações, análise de renda para FIIs/REITs, adequação de política para ETF/cripto/Tesouro, detecção de armadilhas de valuation).
- **Simula cenários futuros** com Monte Carlo (Simulação), sempre como projeção probabilística, nunca uma previsão.
- **Sincroniza com o Dividendos.me** (opcional) para importar posições e proventos automaticamente, sempre com preview e confirmação explícita antes de qualquer alteração.
- **Registra a memória de investimento** (Journal): teses, decisões e revisões ao longo do tempo.

A LG INVEST **nunca executa ordens, nunca recomenda venda automática e nunca é aconselhamento financeiro** — ver "Aviso importante" abaixo.

## Perfil do investidor que este app foi feito para atender

Investidor de longo prazo, filosofia Buy & Hold, horizonte superior a 50 anos, foco em construção de patrimônio e independência financeira. Aceita volatilidade, busca maximização de patrimônio (não só dividendos imediatos), investe no Brasil e no exterior, deseja aumentar exposição internacional ao longo do tempo, e prefere decisões explicáveis a recomendações genéricas.

## Fluxo de uso principal

1. **Sincronizar Dividendos.me** (opcional) ou importar a carteira manualmente (CSV/Excel) na tela **Carteira**.
2. **Atualizar dados** — preços, fundamentos e watchlist na Central de Dados (dentro do Dashboard).
3. **Configurar** política de investimento e alocação-alvo em **Configurações**.
4. Revisar o **Dashboard** — visão geral, alertas, saúde e risco da carteira.
5. Explorar a **Inteligência** — ranking de ativos por LG Conviction Score v2.
6. Simular um aporte em **Aporte** (Decision Engine v3) e ver o impacto na carteira.
7. Avaliar candidatos novos no **Radar/Watchlist** antes de decidir iniciar posição.
8. Estudar fundamentos de um ativo específico em **Ativos** (Análise Fundamentalista).
9. Rodar cenários de longo prazo em **Simulação** (Monte Carlo).
10. **Decidir manualmente, fora do app** — a LG INVEST nunca compra, vende nem executa nada sozinha.

Ver `docs/USER_GUIDE.md` para o passo a passo detalhado de cada tela.

## Telas do app

| Tela | O que faz |
|---|---|
| Dashboard | Visão geral, alertas, Portfolio Health Score, risco da carteira, Central de Dados (atualização manual de preços/fundamentos/watchlist) |
| Carteira | Posições, importação de carteira (CSV/Excel), filtros e composição |
| Aporte | Recomendação de distribuição de um novo aporte (Decision Engine v1/v2/v3), com explicação por ativo e projeção "como a carteira ficaria depois" |
| Inteligência | Ranking de ativos por LG Conviction Score v2, blocos interpretativos |
| Ativos | Cadastro mestre, status de preço, fundamentos, LG Score e Análise Fundamentalista completa por ativo |
| Radar | Watchlist de candidatos — classificação, coleta de dados, funil de status |
| Simulação | Projeção Monte Carlo de patrimônio futuro |
| Journal | Teses de investimento, decisões e revisões ao longo do tempo |
| Sincronizar Dividendos.me | Importação opcional de carteira e proventos via Dividendos.me (dry-run/replace/update) |
| Configurações | Ambiente, câmbio, atualização de preços, e as três camadas de alocação-alvo (simples/regras detalhadas/política geral) |

## Stack

Python 3.11+ · SQLite (padrão local) ou PostgreSQL/Supabase (opcional) · SQLAlchemy 2.0 · Alembic · Pydantic · pandas/numpy · yfinance · Streamlit · Plotly · Playwright (só para sincronizar com o Dividendos.me) · pytest · ruff/black.

## Estrutura do repositório

```
lg-invest/
├── backend/app/        # core, models, schemas, engines, etl, services, infrastructure, integrations
├── frontend/            # interface Streamlit (app.py + pages_impl/*.py)
├── database/            # migrations (Alembic) e seeds
├── data/                # banco SQLite, backups e dados locais (não versionados)
├── docs/                 # documentação por módulo
└── scripts/              # rotinas de linha de comando (importar, atualizar preços, backup, etc.)
```

## Instalação e primeira execução

Guia completo em `docs/INSTALLATION.md`. Resumo rápido:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
python -m alembic upgrade head
streamlit run frontend/streamlit_app/app.py
```

## Como usar no dia a dia

Guia completo em `docs/USER_GUIDE.md` — cobre cada tela, o fluxo principal (acima) e como interpretar os principais indicadores (LG Score, Conviction Score, Portfolio Health Score, limites pós-aporte).

Para operar o app já rodando (comandos do dia a dia, sem reinstalar nada), ver `docs/LOCAL_RUNBOOK.md`.

## Backup do banco

Antes de sincronizar o Dividendos.me em modo `replace`, aplicar uma migration, ou qualquer operação arriscada, faça um backup simples:

```bash
python -m scripts.backup_database
python -m scripts.backup_database --keep-last 10   # mantém só os 10 mais recentes
```

Copia `data/lg_invest.db` para `data/backups/lg_invest_YYYYMMDD_HHMMSS.db`. Sem agendamento automático, sem compressão — só uma cópia simples e confiável. Só funciona para SQLite local; bancos Postgres/Supabase já têm backup automático do provedor.

## Qualidade de código

```bash
python -m alembic upgrade head   # migrations em dia
python -m pytest -q              # suíte de testes
python -m ruff check .           # lint
python -m black --check .        # formatação
```

## Problemas comuns

Ver `docs/TROUBLESHOOTING.md` — cobre erros de instalação, banco desatualizado, Playwright ausente, sincronização do Dividendos.me falhando, preços não atualizando, e como reportar um problema.

## Princípios

Toda recomendação deve ser **explicável, auditável e baseada em evidências**. Regras financeiras nunca se misturam com a interface (engines puras, sem I/O). Nenhuma chave de API ou credencial no código — tudo via `.env`. A LG INVEST **nunca recomenda vender uma posição existente** — quando uma dimensão está acima do alvo/máximo, o único efeito é pausar novos aportes ali, nunca sugerir venda.

## Limitações conhecidas (v1.0)

- **Não é aconselhamento financeiro automatizado.** Toda recomendação é um ponto de partida explicável para uma decisão que você toma manualmente, fora do app. A LG INVEST nunca executa ordens nem se conecta a corretoras.
- **Fundamentos via Yahoo Finance (proxy MVP).** Cobertura varia por classe e ticker, especialmente para ações brasileiras menores e FIIs — campos ausentes aparecem como indisponíveis, nunca são inventados. Há importação manual de fundamentos (CSV/Excel) como fallback.
- **Câmbio USD/BRL é só para exibição** (conversão de saldo consolidado no Dashboard) — Decision Engine, LG Score e Portfolio Engine sempre trabalham com os valores nominais por moeda, sem conversão.
- **Sincronização com o Dividendos.me é opcional e depende de scraping (Playwright)** — sujeita a mudanças no site de terceiros. Sempre roda em modo `dry-run` por padrão; `replace`/`update` exigem confirmação explícita.
- **Uso local single-user.** Não há multiusuário, autenticação ou deploy multiusuário nesta versão — pensado para rodar na sua máquina.
- **Simulação Monte Carlo usa premissas de retorno/volatilidade configuráveis, não dados de mercado real coletados** — sempre uma projeção didática, nunca uma previsão.

## Aviso importante

A LG INVEST é uma ferramenta pessoal de organização e análise, **não é uma consultoria de investimentos e não constitui aconselhamento financeiro.** Nenhuma sugestão do app deve ser seguida sem sua própria avaliação. Decisões de investimento envolvem risco, incluindo perda de capital.

## Mais documentação

- `docs/USER_GUIDE.md` — como usar cada tela
- `docs/INSTALLATION.md` — instalação detalhada
- `docs/LOCAL_RUNBOOK.md` — operar o app no dia a dia
- `docs/TROUBLESHOOTING.md` — solução de problemas
- `docs/RELEASE_NOTES_v1.0.md` — o que tem nesta versão
- `docs/RELEASE_CHECKLIST.md` — critérios de prontidão verificados
- `docs/UX_UI_GUIDE.md` — Design System da interface
- `docs/INVESTMENT_DECISION_SYSTEM.md`, `docs/DECISION_ENGINE_3.md`, `docs/POST_ALLOCATION_CONSTRAINTS.md` — como o Decision Engine decide
- `docs/DATA_REFRESH_CENTER.md`, `docs/DATA_COVERAGE_REPORT.md` — atualização e qualidade de dados
- `docs/WATCHLIST_RADAR.md` — Radar/Watchlist
- `CHANGELOG.md` — histórico completo de mudanças
