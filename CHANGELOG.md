# Changelog

Todas as mudanças relevantes da LG INVEST são registradas aqui.
O formato segue, de forma simplificada, o padrão Keep a Changelog.

## [0.1.0] - Sprint 1 — Setup do projeto

### Adicionado
- Estrutura de pastas do repositório conforme Volume 14.
- `pyproject.toml`, `requirements.txt` e `requirements-dev.txt` com dependências do MVP.
- `.env.example` documentando variáveis (sem segredos) e `.gitignore` protegendo `.env`, banco e dados pessoais.
- `core/config.py` (settings via pydantic-settings) e `core/logging.py` (logger básico).
- Entrypoint placeholder `backend/app/main.py`.
- Interface Streamlit placeholder navegável `frontend/streamlit_app/app.py`.
- Teste smoke validando carga de configurações, logging e importação do entrypoint.
- Configuração de qualidade: ruff, black, mypy, pytest e pre-commit.
- READMEs por módulo e README principal com instruções de execução.

### Observações
- Nenhuma lógica financeira foi implementada neste sprint.

## [0.2.0] - Sprint 2 — Banco e modelos

### Adicionado
- `Base` (DeclarativeBase) e `TimestampMixin` em `infrastructure/database/base.py`.
- Sessão de banco (`engine`, `SessionLocal`, `get_session`) em `infrastructure/database/session.py`.
- Entidades SQLAlchemy 2.0 (Mapped/mapped_column, Decimal/Numeric): Asset, Portfolio, Position, Price, Recommendation, JournalEntry.
- Schemas Pydantic de entrada/saída para as 6 entidades, com validações (ticker uppercase, moeda ISO, ações de journal restritas, etc.).
- Repositórios (Repository Pattern) para as 6 entidades, isolando todo acesso ao banco.
- `init_db.py` para criação rápida de tabelas em desenvolvimento.
- Alembic configurado (`env.py` lê `settings.database_url` e `Base.metadata`) e migration inicial `6ab223d94e49_create_initial_mvp_tables` criando as 6 tabelas + índices/constraints.
- Seed de demonstração `database/seeds/assets_seed.py` (WEGE3.SA, ITUB4.SA, VOO), idempotente.
- 13 novos testes unitários de persistência (SQLite em memória): criação, busca, duplicidade de ticker, duplicidade asset+date, unicidade portfolio+asset, snapshot de recomendação, listagem de journal.

### Validado
- `alembic upgrade head` cria as 6 tabelas a partir do zero.
- Seed roda e é idempotente (não duplica em execuções repetidas).
- 16/16 testes passando (3 smoke do Sprint 1 + 13 novos).
- `ruff check` e `black --check` limpos (migrations geradas pelo Alembic excluídas do lint/format).

### Observações
- `Position` é única por (portfolio_id, asset_id): MVP usa posição consolidada, não lotes.
- `Portfolio` ainda não tem `user_id` — multiusuário fica fora do MVP (Volume 17); campo será adicionado por migration quando necessário.
- Nenhuma engine financeira foi implementada neste sprint.

## [0.3.0] - Sprint 3 — Cadastro de carteira

### Adicionado
- Leitor de arquivos `etl/importers/file_reader.py` (CSV via stdlib, Excel via openpyxl), com número de linha de origem para mensagens de erro precisas.
- Schemas de importação `schemas/import_row.py` (PositionImportRow, AssetImportRow) com validação de schema/tipo.
- Validadores `etl/validators/portfolio_validators.py`: schema, range, duplicidade no arquivo.
- `etl/importers/import_result.py`: resultado estruturado (total, imported, updated, skipped, errors por linha).
- `etl/importers/position_importer.py`: upsert idempotente de posições por (portfolio_id, asset_id); ticker desconhecido é rejeitado.
- Serviços `services/portfolio_import_service.py` e `services/asset_service.py`.
- CLI `scripts/import_portfolio.py` (importa CSV/Excel; cria carteira com --create-portfolio).
- Templates `database/seeds/positions_template.csv` e `assets_template.csv`.
- Dependência `openpyxl` adicionada (leitura de Excel).
- 10 novos testes: validadores (schema, range, data, duplicidade, uppercase) e importer (CSV válido, idempotência, arquivo com erros, leitura Excel).

### Validado
- Import via CLI: 3 posições importadas a partir do template (banco real).
- Idempotência confirmada no banco: reimportar mantém 3 posições (0 importadas, 3 atualizadas).
- Arquivo com erros: linha válida entra, 4 inválidas viram errors[] sem abortar (ticker inexistente, quantidade negativa, duplicidade, data inválida).
- 26/26 testes passando; ruff e black limpos.

### Decisões
- Importa posições consolidadas (alinhado ao Volume 17), não o livro de transações do Volume 4 — entidade Transaction fica para evolução futura.
- Ticker desconhecido = linha rejeitada (evita criar ativo sem classe/moeda).
- Importação reprocessável via upsert (princípio do Volume 4: reprocessar sem duplicar).

## [0.4.0] - Sprint 4 — Market Data (preços via yfinance)

### Adicionado
- Contrato `etl/contracts/price_data.py` (PriceData) — formato normalizado de preço independente da fonte.
- Interface `etl/providers/base.py` (MarketDataProvider) — provedores de preço substituíveis.
- `etl/providers/yahoo_provider.py` (YahooFinanceProvider) — única classe que importa yfinance; import tardio para permitir mocks.
- Validadores `etl/validators/price_validators.py` — close positivo, data não-futura, coerência OHLC, valores não-negativos.
- Serviço `services/market_data_service.py` — coleta incremental (a partir da última data + 1), upsert idempotente em `prices`, tratamento de falhas por ativo (não derruba o lote), resultados estruturados (UpdateResult/BatchUpdateResult).
- CLI `scripts/update_prices.py` (--ticker / --all).
- Testes: validadores de preço, parsing do YahooFinanceProvider (yfinance mockado, sem rede) e MarketDataService (insert, idempotência, start incremental, rejeição de inválidos, falha de provider, ticker desconhecido, batch).

### Validado
- 41/41 testes passando; ruff e black limpos.
- End-to-end no banco real com provider fake: 1a execução insere 3 preços (seed), 2a execução atualiza 3 sem duplicar (apenas 3 linhas em prices).
- Nenhum teste depende de conexão real (Volume 4 seção 17; Volume 20 prompt 7).

### Decisões
- yfinance isolado atrás de MarketDataProvider — trocar a fonte não impacta serviço nem engines.
- Validação de qualidade antes de inserir em `prices` (dado ruim rejeitado com motivo, não contamina engines).
- Coleta incremental + upsert: pipeline reprocessável sem duplicar (Volume 4).

## [0.5.0] - Sprint 5 — Portfolio Engine v1

### Adicionado
- `engines/portfolio/inputs.py` (PositionInput) — contrato de entrada da engine: dados já tratados, sem SQLAlchemy.
- `engines/portfolio/engine.py` (build_summary) — engine PURA: valor por posição, valor total, peso por ativo/classe, rentabilidade por ativo, rentabilidade total aproximada, maior posição, exposição por moeda.
- `engines/portfolio/concentration.py` — HHI e número efetivo de ativos, isolados.
- `schemas/portfolio_summary.py` — PositionResult, AllocationSlice, PortfolioSummary (saída serializável).
- `services/portfolio_service.py` — fronteira banco↔engine: lê posições + último preço e monta os inputs tratados.
- CLI `scripts/portfolio_summary.py` (--portfolio-id).
- 17 novos testes: engine com valores conhecidos (total, custo, pesos, rentabilidades, maior posição, HHI, alocação por classe, multi-moeda, sem preço, average 0, carteira vazia) e concentração em casos extremos.

### Validado
- 58/58 testes passando; ruff e black limpos.
- End-to-end no banco real: carteira importada + preços (provider fake) → resumo via CLI coerente (total 14.500, maior posição ITUB4, pesos somando 100%, HHI 0,343 ≈ 2,91 ativos efetivos, multi-moeda sinalizada com BRL 70,3% / USD 29,7%).
- Engine é pura: nenhum teste da engine toca banco ou rede (Volume 20 prompt 8).

### Decisões (aprovadas)
- Sem conversão cambial no v1: soma por moeda e sinaliza is_multi_currency (conversor depende de série de câmbio, sprint futuro).
- Rentabilidade = preço atual vs. preço médio (aproximada, não TWR/MWR).
- Engine recebe preço já resolvido pelo serviço; cálculo nunca acessa fontes externas.
- Posição sem preço atual vai para unpriced_tickers e fica fora dos totais (não inventa preço — Volume 18 §8).

## [0.6.0] - Sprint 6 — LG Score v1

### Adicionado
- `engines/lg_score/inputs.py` (ScoreInput) — contrato de entrada: asset_class, price_history, pesos atual/alvo.
- `engines/lg_score/weights.py` (LGScoreWeights) — pesos 35/25/20/10/10, parametrizáveis e validados (somam 1.0).
- `engines/lg_score/normalization.py` — clamp 0..100, média, CAGR, volatilidade, max drawdown.
- `engines/lg_score/pillars.py` — Quality/Valuation/Growth/Risk/Allocation como proxies explícitas, cada uma com razões e confiança local.
- `engines/lg_score/confidence.py` — Confidence Score agregado + rótulo (Alta/Média/Baixa).
- `engines/lg_score/engine.py` (calculate_lg_score) — engine pura: score final 0..100, notas parciais, classificação (Exceptional..Avoid), explicação por pilar, model_version.
- `schemas/lg_score.py` — PillarResult, LGScoreResult.
- `services/lg_score_service.py` — monta inputs do banco; score_ticker e rank_portfolio.
- CLI `scripts/lg_score.py` (--ticker / --portfolio-id).
- 21 novos testes: limites 0..100, pesos, classificação, explicação, neutralidade quando falta dado, proxies de valuation/growth/allocation, confiança por cobertura de histórico.

### Validado
- 79/79 testes passando; ruff e black limpos.
- End-to-end no banco real: carteira + histórico de preços (provider fake) → ranking via CLI coerente (VOO no topo por base de ETF, valuation "caro" em série crescente, risco alto por baixa volatilidade, confiança Baixa sinalizando proxies).
- Engine pura: nenhum teste da engine toca banco ou rede.

### Decisões (aprovadas)
- Pilares por PROXY explícita sobre dados já coletados (classe + histórico de preço), não por fundamentos (ROIC/margens/CAGR de lucro ainda não existem). Confiança baixa sinaliza a limitação (Volume 17 §9).
- LG Score v1 não persiste a tabela lg_scores — entrega só a engine; histórico de score virá quando o Decision Engine precisar.
- Valuation v1 = preço atual vs. média histórica do próprio ativo (proxy de caro/barato), pois não há valor intrínseco (Valuation Engine é pós-MVP).
- Dado ausente → nota neutra (50) + razão explícita + confiança reduzida; nunca otimismo (Volume 18 §8).

## [0.7.0] - Sprint 7 — Decision Engine v1

### Adicionado
- `engines/decision/inputs.py` (DecisionInput, DecisionConfig) — candidatos e limites de alocação (máx 50%, mín 10%, limite de concentração, nº de ativos por faixa de aporte).
- `engines/decision/scoring.py` — score de compra = 0.50*lg_norm + 0.30*gap_alocação + 0.20*concentração_invertida (Volume 17 §10).
- `engines/decision/eligibility.py` — filtra bloqueados e sobreconcentrados, com motivo.
- `engines/decision/allocation.py` — distribui o aporte respeitando min/max e nº de ativos; soma nunca ultrapassa o aporte.
- `engines/decision/engine.py` (recommend) — engine pura: filtra → pontua → distribui → explica → auditoria; alertas e nível de confiança.
- `schemas/recommendation_result.py` — RecommendationItem, IgnoredItem, DecisionAudit, RecommendationResult.
- `services/decision_service.py` — monta inputs (Portfolio + LG Score), chama a engine e persiste a recomendação (auditoria), mantendo a engine pura.
- CLI `scripts/recommend.py` (--portfolio-id, --amount, --blocked, --no-persist).
- 24 novos testes: scoring (componentes e limites), elegibilidade (bloqueado/concentrado), alocação (soma ≤ aporte, min 10%/max 50%, nº por faixa), engine (exemplo R$1000, bloqueio, confiança, auditoria).

### Corrigido
- Bug de alocação: a renormalização após clamp reintroduzia peso acima do teto de 50%. Reescrito `_apply_min_max` para nunca devolver peso acima do máximo (o excedente fica não alocado e é reportado). Detectado por teste.

### Validado
- 103/103 testes passando; ruff e black limpos.
- End-to-end no banco real: carteira + preços → recomendação de R$1000 via CLI, com ativos sobreconcentrados ignorados (com motivo), alerta de valor não alocado e recomendação persistida na tabela recommendations (algo_version decision_v1).
- Engine pura: nenhum teste da engine toca banco ou rede.

### Decisões (aprovadas) e limitações
- Fórmula do MVP (Volume 17), não o SAM completo (Volume 7 §6) — pilares já vivem no LG Score do Sprint 6.
- Sem peso-alvo no MVP → gap de alocação = 0; decisão guiada por LG Score + concentração invertida.
- Recomendação persistida via serviço (engine permanece pura).
- Limitação conhecida: em carteiras pequenas, o limite de concentração de 30% pode barrar a maioria dos ativos e deixar parte do aporte sem alocar — comportamento correto e sinalizado; limite parametrizável em DecisionConfig.

## [0.8.0] - Sprint 8 — Streamlit MVP

### Adicionado
- `frontend/streamlit_app/app.py` — orquestrador das 6 telas com seletor de carteira.
- `frontend/streamlit_app/db.py` — sessão de banco de curta duração por interação.
- `frontend/streamlit_app/pages_impl/` — uma tela por módulo:
  - dashboard: resumo da carteira (PortfolioService) — patrimônio, pesos, alocação, concentração, exposição por moeda.
  - carteira: posições + upload e importação de CSV/Excel (PortfolioImportService) com relatório de erros.
  - ativos: lista de ativos + LG Score explicável por fator (LGScoreService).
  - aporte: formulário de aporte -> recomendação do Decision Engine, com justificativa, alertas e ativos ignorados.
  - journal: registrar e listar teses (JournalService).
  - configuracoes: ambiente + botão de atualização de preços (yfinance).
- `services/journal_service.py` — serviço fino do Investment Journal (add/list).
- 9 smoke tests: import de cada página + render() + JournalService.

### Validado
- 112/112 testes passando; ruff e black limpos.
- Streamlit sobe headless e responde HTTP 200 no healthcheck.
- As 6 telas renderizam sem exceção, verificadas com streamlit.testing AppTest (executa o app de verdade).
- Corrigido aviso de depreciação: use_container_width -> width="stretch".

### Decisões
- Interface consome serviços/engines e não duplica cálculo (Volume 20 prompt 11).
- Sessão de banco curta por interação (adequado ao modelo de reexecução do Streamlit no MVP).
- Atualização de preços é ação explícita na tela Configurações (requer internet).

## [0.9.0] - Sprint 9 — Investment Journal (Memory)

### Adicionado
- Entidades: InvestmentThesis (tese com status open/confirmed/partially_confirmed/invalidated, hipótese, drivers, riscos, horizonte, critério de revisão, preço de entrada), ThesisReview (revisão imutável com classificação) e DecisionSnapshot (foto: preço, peso, LG Score, confiança, valor recomendado, model_version; macro opcional).
- Migration 0002 (425380c796bb) encadeada à inicial, criando as 3 tabelas + índices.
- Schemas: ThesisCreate/Read, ThesisReviewCreate/Read (validação de status e classificação).
- Repositórios: thesis_repository, snapshot_repository.
- Serviço: thesis_service — criar tese, revisar (cria review imutável e atualiza status da tese), criar snapshot, criar por ticker.
- Tela Journal reescrita com abas: Diário | Teses | Revisões.
- 19 novos testes: persistência, ciclo de vida da tese, revisão preserva histórico, mapeamento classificação→status, validação de status/classificação.

### Validado
- 131/131 testes passando; ruff e black limpos.
- Migration encadeada aplica as 3 tabelas a partir do banco existente.
- Tela Journal renderiza sem erro (streamlit AppTest).

### Decisões (aprovadas) e escopo
- 3 entidades no MVP (investment_theses, thesis_reviews, decision_snapshots); thesis_assumptions, outcome_analysis e investment_events ficam pós-MVP.
- DecisionSnapshot sem macro (Selic/IPCA/câmbio) — campos opcionais, dados ainda não coletados.
- Vínculo tese↔aporte é manual (o usuário cria a tese), sem efeito colateral automático no Decision Engine.
- Histórico nunca sobrescrito: revisões acumulam; status reflete a última (Volume 12 §12).

## [1.0.0] - Sprint 10 — Testes e Refinamento / QA Final (MVP completo)

### Adicionado
- Fixtures de regressão: sample_portfolio_brazil.json, sample_portfolio_global.json, expected_regression.json.
- Helper de regressão (_helpers.py) que popula um banco em memória a partir de uma fixture.
- Testes de regressão (Portfolio, LG Score, Decision) comparando a saída atual com baseline salvo.
- Testes de determinismo das 3 engines (mesma entrada -> mesma saída).
- Testes de casos extremos (500 ativos, preços zerados, aporte negativo, ativo único, todos sobreconcentrados).
- Testes diretos de _apply_min_max cobrindo o branch de soma acima de 1.0.
- docs/QA_REPORT.md — riscos, cobertura por área, limitações e segurança.
- docs/MVP_CHECKLIST.md — critérios de aceite do MVP verificados item a item.

### Validado
- 153/153 testes passando; determinísticos e sem rede.
- Cobertura total 86%; engines 98% (Portfolio 100%, Decision 98%, LG Score 97%), ETL 92%, modelos 100%, serviços 89% — todas acima das metas do Volume 18.
- ruff e black limpos.

### Estado
- MVP completo: os 10 sprints do plano foram entregues.
- Evoluções pós-MVP documentadas (valuation DCF/DDM, risco agregado, Monte Carlo, IA, multiusuário, corretoras).

## [1.1.0] - Sprint 10.1 — Multi-moeda, preço manual e formatação (pós-MVP)

### Adicionado
- `fx_settings_service` — câmbio USD/BRL manual, persistido em `data/app_settings.json`.
- `dashboard_view_service` — camada de apresentação (fora da engine) que converte USD→BRL e aplica fallback de preço (average_price) para ativos sem cotação, só para exibição.
- `frontend/streamlit_app/formatting.py` — `format_brl`, `format_usd`, `format_pct`.
- Cadastro de preço atual manual na tela Ativos (grava um `Price` normal).

### Validado
- 149/149 testes passando (134 anteriores + 15 novos); ruff e black limpos.
- Portfolio Engine, Decision Engine e LG Score inalterados — continuam recebendo dados nominais, sem conversão nem fallback.

## [1.2.0] - Sprint 11 — Product UI/UX Upgrade + Dashboard Intelligence

### Adicionado
- `prices.source` (migration `37287838d417`) — distingue preço automático (Yahoo) de manual, com default `"yahoo"` (retrocompatível).
- Schemas `schemas/dashboard_view.py`, `schemas/portfolio_diagnostics.py`, `schemas/allocation_projection.py`.
- Engine `engines/portfolio_diagnostics` (puro, sem banco/yfinance/Streamlit) — Diagnóstico da Carteira baseado em regras simples e documentadas (`thresholds.py`): concentração por ativo, classe dominante, diversificação (Nº efetivo), Brasil x Exterior, pesos por grupo, múltiplas moedas, preços manuais/estimados.
- `services/portfolio_diagnostics_service.py` e `services/allocation_projection_service.py` (projeção antes/depois do aporte, sem alterar o Decision Engine).
- `frontend/streamlit_app/components/` (cards, tabelas, seções) e `frontend/streamlit_app/charts/` (Plotly: alocação, performance, concentração) — reutilizados por Dashboard, Carteira, Ativos e Aporte.
- `frontend/streamlit_app/styles/` (tema de cores único + CSS global injetado uma vez em `app.py`).
- Dashboard redesenhado: 10 cards principais, gráficos de composição/destaques/riscos, Diagnóstico da Carteira, tabela de posições ordenável e agrupada por classe.
- Aporte redesenhado: comparação antes x depois (patrimônio e pesos por classe/moeda), gráficos, justificativa por ativo.
- Ativos e Carteira redesenhados: origem do preço (automático/manual/estimado), última atualização, destaque de posições negativas/concentradas, resumo de importação.
- `docs/DEPLOYMENT_PLAN.md` e `docs/SUPABASE_MIGRATION_PLAN.md` — planejamento (não executado) de deploy no Streamlit Community Cloud e migração para Supabase/PostgreSQL.
- Nova dependência: `plotly`.

### Validado
- Portfolio Engine, LG Score Engine, Decision Engine e o novo engine de Diagnóstico continuam puros — sem banco, sem yfinance, sem Streamlit (`test_engine_purity.py`).
- Nenhuma mudança no `PortfolioService.get_summary` nem no Decision Engine: CLI (`scripts/portfolio_summary.py`) e recomendação de aporte continuam com o mesmo comportamento de antes.
- `DATABASE_URL` já vem de variável de ambiente e `session.py` já trata SQLite x Postgres condicionalmente — nenhuma mudança de código necessária para a migração futura.

### Fora do escopo
- Valuation Engine, Transaction, multiusuário, IA generativa.
- Migração real para Supabase e deploy real no Streamlit Cloud (só documentados).
- Gráfico de evolução histórica (sem dados reais de série temporal ainda).

## [1.3.0] - Sprint 12 — Market Data Foundation + IDS Methodology

### Adicionado
- `assets.is_manual` (migration `8f1c3a9b2d40`) — marca ativos sem cotação de mercado (ex.: Tesouro Direto); `MarketDataService.update_all_active` passa a pular esses ativos automaticamente, sem heurística por classe.
- Câmbio USD/BRL automático: `etl/providers/fx_provider.py` (interface `FxRateProvider`), `bcb_fx_provider.py` (BCB PTAX, API pública sem chave) e `yahoo_fx_provider.py` (fallback `USDBRL=X`). `services/fx_service.py` orquestra a cadeia BCB -> Yahoo -> última cotação salva, nunca deixando o Dashboard sem número.
- `fx_settings_service` ganha origem e data/hora da cotação (`source`, `quote_date`, `fetched_at`), retrocompatível com arquivos antigos que só tinham `usd_brl_rate`.
- `schemas/market_data.py` — `UpdateResult`/`BatchUpdateResult` migrados para Pydantic (com `skipped_manual`/`total_skipped_manual`) e `FxQuote`.
- IDS Methodology: `engines/ids_methodology/` (`profile.py` com `InvestorProfile` e pesos por classe de ativo, `weights.py` com `IdsPillarWeights`, `pillars.py` reaproveitando Quality/Valuation/Growth/Risk do LG Score e adicionando `capital_reinvestment_pillar` como placeholder neutro explícito, `engine.py` com `calculate_conviction_score`) e `schemas/ids_methodology.py` — fundação do LG Conviction Score, paralelo ao LG Score (Decision Engine continua usando só o LG Score).
- Diagnóstico da Carteira ganha o insight `data_quality`: % do patrimônio com preço automático, com limiares em `thresholds.py`.
- Configurações: botão "Atualizar câmbio automático", com fonte e data/hora exibidas; override manual preservado.
- Ativos: status de preço em 3 estados visíveis (automático/manual/sem preço), botão de atualização individual e alternador para marcar um ativo como manual.
- Dashboard: alerta destacado quando parte relevante do patrimônio está fora de preço automático.
- `settings.bcb_fx_enabled` (`.env`: `BCB_FX_ENABLED`).
- `docs/IDS_METHODOLOGY.md`, `docs/DATA_SOURCES.md`, `docs/FUNDAMENTALS_ENGINE_PLAN.md`.

### Validado
- Engines `ids_methodology` e `portfolio_diagnostics` continuam puros — sem banco, sem yfinance, sem Streamlit (`test_engine_purity.py`).
- Decision Engine e LG Score inalterados: nenhuma mudança de comportamento na recomendação de aporte.
- Cadeia de fallback de câmbio testada com providers fake (sucesso na 1ª fonte, fallback para a 2ª, todas falhando com/sem cotação salva).

### Fora do escopo
- Valuation Engine completo (DCF/DDM/Monte Carlo), Fundamentals Engine real (só planejado em `FUNDAMENTALS_ENGINE_PLAN.md`), IA generativa, multiusuário, Transaction ledger, migração real para Supabase, deploy real, rebalanceamento avançado, otimização quantitativa, scraping frágil, APIs pagas sem aprovação.

## [1.4.0] - Sprint 13 — Fundamentals: coleta e persistência

### Adicionado
- Entidade `FundamentalSnapshot` (roe, roa, margens, receita, lucro, EBITDA/EBIT, FCF, dívida líquida, dívida/EBITDA, P/L, P/VP, EV/EBITDA, dividend yield, payout, LPA, receita por ação, beta) — migration `c4d9e2a17f63_add_fundamental_snapshots`.
- `etl/providers/fundamentals_provider.py` (interface `FundamentalsProvider`) e `yahoo_fundamentals_provider.py` (única classe que fala com yfinance para fundamentos; import tardio para permitir mocks).
- `infrastructure/repositories/fundamentals_repository.py` e `services/fundamentals_service.py` — coleta, validação básica e persistência do snapshot mais recente por ativo.
- Tela Ativos: seção "Fundamentos" mostrando o snapshot mais recente coletado, com aviso explícito quando não há dado (nunca um valor inventado).
- Testes: parsing do provider (yfinance mockado), serviço (persistência, ativo sem dado, atualização) e repositório.

### Validado
- Engine purity mantida (nenhum novo engine neste sprint — Fundamentals é ETL puro + persistência).
- Ativo sem fundamentos coletados aparece com aviso explícito na UI, nunca com número inventado (Volume 18 §8).

### Fora do escopo
- Cálculo de métricas derivadas (CAGR, margens comparadas) — fica para o Fundamentals Engine (Sprint 14).

## [1.5.0] - Sprint 14 — Fundamentals Engine (puro)

### Adicionado
- `engines/fundamentals/` — engine PURA (sem banco/yfinance/Streamlit): `cagr.py` (CAGR de receita/lucro a partir de snapshots históricos) e `engine.py` compondo métricas derivadas a partir de `FundamentalSnapshotResult` já carregados pelo serviço.
- `services/fundamentals_analysis_service.py` — fronteira banco↔engine: busca snapshots do `FundamentalsRepository` e chama a engine pura.
- Testes: CAGR com crescimento/queda/dados insuficientes, engine com snapshots completos/incompletos, purity (`test_engine_purity.py` cobre `engines/fundamentals/` automaticamente).

### Validado
- Dado insuficiente (menos de 2 snapshots) resulta em CAGR `None` com motivo explícito — nunca um valor extrapolado.
- Engine 100% pura: nenhum teste toca banco ou rede.

## [1.6.0] - Sprint 15 — Valuation Engine v1

### Adicionado
- `engines/valuation/` — engine PURA: `thresholds.py` (`MetricBand`, faixas de P/L, P/VP, EV/EBITDA, dividend yield por classe de ativo) e `engine.py` (classificação "cara"/"neutra"/"barata"/"indeterminado" por agregação ponderada de verdicts, com razões explícitas por métrica).
- `schemas/valuation.py` (`ValuationResult`).
- `services/valuation_service.py` — busca o snapshot mais recente e chama a engine.
- Tela Ativos: seção "Valuation" com classificação, confiança e razões por métrica.
- Testes: engine (cada faixa, dado ausente, agregação), serviço, purity.

### Validado
- Ativo sem snapshot ou sem métricas suficientes classifica como "indeterminado" com razão explícita, nunca "barata"/"cara" por suposição.

### Fora do escopo
- DCF/DDM completo (Volume 18, fora do MVP) — v1 usa apenas múltiplos relativos.

## [1.7.0] - Sprint 16 — Quality, Growth e Risk Engines

### Adicionado
- `engines/quality/`, `engines/growth/`, `engines/risk/` — três engines PURAS seguindo o mesmo padrão do Valuation (thresholds por classe + agregação ponderada de verdicts → classificação + razões + confiança).
  - Quality: ROE, ROA, margem líquida, margem EBITDA, dívida/EBITDA.
  - Growth: CAGR de receita e lucro (via Fundamentals Engine, Sprint 14).
  - Risk: beta, dívida/EBITDA, volatilidade de preço.
- `schemas/quality.py`, `schemas/growth.py`, `schemas/risk.py`.
- `services/quality_service.py`, `services/growth_service.py`, `services/risk_service.py`.
- Tela Ativos: seções "Quality", "Growth" e "Risk" com classificação, confiança e razões por métrica, mesma UX do Valuation.
- Testes: engine (cada faixa, dado ausente) e serviço para as três engines; purity automática via `test_engine_purity.py`.

### Validado
- As três engines seguem a mesma doutrina de dado ausente (Volume 18 §8): métrica indisponível não pesa na agregação, e a razão fica registrada.
- Nenhum acoplamento entre as três engines: cada uma é um pacote independente sob `engines/`, com sua própria `thresholds.py` (duplicação deliberada, não uma base compartilhada).

## [1.8.0] - Sprint 17 — LG Conviction Score v2 e Alocação-Alvo

### Adicionado
- `engines/ids_methodology/pillars.py` ganha `quality_pillar_v2`, `valuation_pillar_v2`, `growth_pillar_v2`, `risk_pillar_v2` — cada uma usa o resultado do engine dedicado (Quality/Valuation/Growth/Risk, Sprints 15-16) quando calculável, e cai de volta na proxy de preço v1 *só para aquele pilar* quando o resultado é `None` ou "indeterminado" (nunca degrada o score inteiro por um pilar sem dado).
- `engines/ids_methodology/engine.py` ganha `calculate_conviction_score_v2` (`model_version="ids_conviction_v2"`) — v1 (`calculate_conviction_score`, `"ids_conviction_v1"`) permanece intocado.
- `services/conviction_score_service.py` — fronteira banco↔engine: monta o `ScoreInput` e busca os resultados de Quality/Growth/Risk/Valuation + snapshot mais recente para o pilar de Capital Reinvestment, então chama a engine v2.
- Alocação-alvo: `engines/target_allocation/engine.py` (compara alocação atual por classe com uma meta configurada, classifica "abaixo"/"dentro"/"acima" por classe, aponta a classe mais subalocada) e `services/target_allocation_settings_service.py` (meta persistida em `data/app_settings.json`, mesmo padrão do `fx_settings_service`; **sem meta padrão embutida** — só existe quando o usuário configura, por princípio anti-fabricação).
- `schemas/ids_methodology.py` ganha os campos de pilar v2 (opcionais, retrocompatíveis); `schemas/target_allocation.py` (novo).
- Configurações: seção para configurar a meta de alocação por classe.
- Testes: pilares v2 (fallback por pilar, agregação), `calculate_conviction_score_v2`, `ConvictionScoreService`, Target Allocation Engine e serviço/settings.

### Validado
- `test_ids_methodology_pillars_v2.py` e regressão confirmam que `calculate_conviction_score` v1 (`model_version == "ids_conviction_v1"`) continua bit-a-bit igual ao comportamento anterior — v2 é estritamente aditivo.
- Sem meta de alocação configurada, `TargetAllocationResult.has_target` é `False` e nenhum desvio é calculado — nunca uma meta inventada.

## [1.9.0] - Sprint 18 — Decision Engine 2.0

### Adicionado
- `engines/decision/inputs.py`: `DecisionInput` ganha `conviction_score` e `class_drift_pct` (opcionais, `None` por padrão — não afetam `recommend()` v1).
- `engines/decision/scoring.py`: `compute_buy_score_v2` — usa o LG Conviction Score (Sprint 17) no lugar do LG Score puro quando calculável (com razão explícita de qual fonte foi usada), e substitui o termo de "gap de alocação por ativo" (nunca implementado de fato no v1: `target_weight` por ticker sempre era `None`) por um bônus de classe subalocada, vindo do Target Allocation Engine (Sprint 17).
- `engines/decision/engine.py`: `recommend_v2` (`model_version="decision_v2"`) — mesmo fluxo do v1 (filtrar → pontuar → distribuir → explicar → auditar), pesos `conviction_score_or_lg_score=0.40 / class_underweight_bonus=0.30 / concentration_inverted=0.30`. `recommend()` v1 permanece intocado.
- `services/decision_service.py`: `build_inputs_v2`/`recommend_v2` — monta candidatos com Conviction Score (`ConvictionScoreService`) e desvio de classe (`TargetAllocationService`); um ativo sem Conviction Score calculável ainda entra na lista (Decision Engine 2.0 cai de volta no LG Score só para ele).
- `schemas/recommendation_result.py`: `RecommendationItem` ganha `conviction_score` (opcional, só preenchido pelo v2).
- Tela Aporte: checkbox "Usar Decision Engine 2.0 (LG Conviction Score + alocação-alvo)" — v1 continua sendo o padrão; ao ligar o v2, a tabela de distribuição ganha a coluna Conviction Score.
- Testes: `compute_buy_score_v2`, `recommend_v2` ponta a ponta, `DecisionService` v2 com banco seedado, e dois novos testes de regressão (`test_v2_recommendation_invariants_brazil`, `test_v2_recommendation_is_deterministic`) sobre a mesma fixture usada pelo v1.

### Validado
- Todos os testes do Decision Engine v1 (`test_decision_engine.py`, `test_decision_scoring.py`, `test_decision_allocation.py`, `test_decision_eligibility.py`, `test_decision_allocation_limits.py`, regressão v1) continuam passando sem alteração — v2 é estritamente aditivo.
- Sobre a carteira de exemplo (sem fundamentos coletados na fixture), o v2 degrada graciosamente para a proxy de preço em cada pilar sem quebrar nenhuma invariante da recomendação (soma ≤ aporte, determinismo).

## [1.10.0] - Sprint 19 — Advanced Dashboard Intelligence

### Adicionado
- `schemas/intelligence_dashboard.py` (`AssetIntelligence`, `IntelligenceDashboardView`) e `services/intelligence_dashboard_service.py` — compõe, por ativo da carteira, o LG Conviction Score v2 (Sprint 17) com pilares e razões, e agrega Conviction Score médio, cobertura (fração do patrimônio com score calculável), maior/menor convicção e contagem por classificação. Um ativo sem Conviction Score calculável entra na lista com `has_conviction_score=False` e um motivo explícito — nunca é omitido nem recebe um valor inventado.
- Nova tela **Inteligência** (`frontend/streamlit_app/pages_impl/inteligencia.py`): KPIs de convicção da carteira, gráfico de Conviction Score por ativo (`charts/intelligence_charts.py`), tabela detalhada com classificação/confiança por ativo, justificativa por pilar em expander, e a tabela de alocação-alvo por classe (Target Allocation Engine, Sprint 17) com a classe mais subalocada em destaque.
- Tela Aporte: checkbox liga o Decision Engine 2.0 (Sprint 18) diretamente na recomendação, deixando o painel de Inteligência e a simulação de aporte na mesma base de dados.
- Testes: `test_intelligence_dashboard_service.py` (cobertura, agregações, carteira sem meta configurada, carteira vazia); `test_streamlit_smoke.py` ganha a nova página na lista de módulos verificados.

### Validado
- 420 testes passando (356 no run principal do sandbox + 64 no run com shim de `datetime.UTC` para os módulos que dependem de yfinance/BCB); `ruff check` e `black --check` limpos em todo o projeto.
- Nenhuma engine nova neste sprint — a tela de Inteligência só compõe o que `ConvictionScoreService` e `TargetAllocationService` (Sprint 17) já calculam; `test_engine_purity.py` continua cobrindo as mesmas engines.
- Decision Engine v1 continua sendo o padrão na tela Aporte; v2 é opt-in.

### Estado do plano de sprints (13-19 concluído)
- Os 10 módulos do plano original (Market Data, Fundamentals, Valuation, Quality, Growth, Risk, Capital Reinvestment, LG Conviction Score, Decision Engine 2.0, Dashboard Intelligence) estão implementados e testados.
- Migração para Supabase e deploy real continuam fora de escopo, aguardando aprovação explícita (Sprint 20, não iniciado).

## [1.11.0] - Sprint 20 — Migração para Supabase/PostgreSQL + Deploy (aprovado pelo usuário)

### Adicionado
- `psycopg2-binary` adicionado às dependências (`requirements.txt`, `pyproject.toml`) — driver Postgres, usado só quando `DATABASE_URL` aponta para `postgresql+psycopg2://...`.
- `scripts/migrate_sqlite_to_postgres.py` — CLI de migração de dados (passo 5 de `docs/SUPABASE_MIGRATION_PLAN.md`): copia tabela por tabela do SQLite local para o Postgres de destino respeitando a ordem de dependência de FK (`Base.metadata.sorted_tables`), com modo dry-run por padrão, `--execute` para gravar de fato, `--wipe-target` para reexecuções idempotentes, e validação automática de contagem de linhas origem x destino ao final.
- `scripts/fix_postgres_sequences.py` — CLI que realinha as sequências de `id` do Postgres após a migração de dados: quando linhas são copiadas com o `id` original do SQLite, a sequência de autoincremento do Postgres não avança sozinha, e o primeiro INSERT feito pela aplicação colide com um `id` já existente (`IntegrityError`). O script roda `setval(pg_get_serial_sequence(...), MAX(id)+1)` para cada tabela; idempotente.
- `frontend/streamlit_app/pages_impl/configuracoes.py`: `_redact_database_url()` mascara usuário:senha na exibição de `DATABASE_URL` na tela Configurações — a URL completa (com a senha do Supabase) estava sendo exibida em texto puro no app publicado.

### Executado (com aprovação explícita do usuário — "APROVADO")
- Projeto Supabase criado pelo usuário; `alembic upgrade head` rodado contra o Postgres do Supabase (pooler em modo *session*, porta 5432) — cadeia completa de migrations aplicada, de `6ab223d94e49` até `c4d9e2a17f63`.
- Dados migrados do SQLite local (`data/lg_invest.db`) para o Supabase via `scripts/migrate_sqlite_to_postgres.py --execute`, usando o pooler em modo *transaction* (porta 6543) para a cópia. Contagens confirmadas batendo em todas as 10 tabelas: 27 assets, 1 portfolio, 27 positions, 6622 prices, 4 recommendations (demais tabelas — decision_snapshots, fundamental_snapshots, investment_theses, journal_entries, thesis_reviews — vazias tanto na origem quanto no destino, esperado).
- Deploy real no Streamlit Community Cloud: usuário criou o repositório no GitHub e o app em share.streamlit.io, com `DATABASE_URL` (pooler *transaction*, porta 6543, `?sslmode=require`) configurada nos Secrets.
- Erro de `IntegrityError` ao salvar recomendação pela tela Aporte (chave primária duplicada, causado pelas sequências desalinhadas) corrigido rodando `scripts/fix_postgres_sequences.py` contra o Supabase — recomendação gerada e persistida com sucesso depois da correção.
- App publicado e validado nas 6 telas (Dashboard, Carteira, Ativos, Inteligência, Aporte, Configurações) com os dados reais migrados.

### Notas técnicas (armadilhas encontradas durante a execução)
- O hostname de conexão direta do Supabase (`db.<ref>.supabase.co:5432`) só resolve por IPv6 em projetos novos; em rede sem IPv6 funcional, a conexão falha com "could not translate host name to address". Solução: usar a **Connection Pooling** (Supavisor), que tem endereço IPv4 garantido — modo *session* (porta 5432) para migrations (DDL), modo *transaction* (porta 6543) para cópia de dados em lote.
- No PowerShell, `set VAR=valor` não define uma variável de ambiente (é sintaxe do CMD) — o comando correto é `$env:VAR = "valor"`. Isso causou uma primeira tentativa de `alembic upgrade head` rodar silenciosamente contra o SQLite local em vez do Supabase.
- O `--source` do script de migração usa `settings.database_url` (lido do ambiente) como padrão; como o `$env:DATABASE_URL` da etapa anterior (alembic) permanecia setado na mesma sessão do PowerShell, a primeira tentativa de migração copiou do Supabase para o próprio Supabase (ambos vazios). Corrigido passando `--source` explicitamente.
- No Streamlit Community Cloud, a conexão inicial falhou com `OperationalError` (mensagem redigida pelo Streamlit Cloud) até adicionar `?sslmode=require` à `DATABASE_URL` — o Supabase exige SSL e o driver não negociava automaticamente nesse ambiente.

### Segurança
- A senha do banco Supabase foi compartilhada em texto puro durante a conversa (necessário para o usuário colar a Connection String) — recomendado ao usuário rotacionar essa senha em Project Settings → Database → Reset Password.
- A tela Configurações exibia a `DATABASE_URL` completa (com senha) em texto puro no app publicado, antes da correção `_redact_database_url()` — reforça a recomendação de rotacionar a senha do Supabase mesmo após o fix, já que ficou exposta por um período no app ao vivo.

## [1.12.0] - Sprint 21 — UX Premium Fix, Data Quality Layer, Fundamentals Foundation, LG Conviction Score v2 e Decision Engine 2.0 (evolução completa aprovada pelo usuário)

### Contexto
Evolução grande e explicitamente aprovada pelo usuário ("Pode implementar a versão completa"), cobrindo 14 blocos: correção de contraste visual, Dashboard executivo, Data Quality Layer, Fundamentals Foundation expandida, Valuation/Quality/Growth/Risk/Capital Reinvestment Engines, LG Conviction Score v2, Decision Engine 2.0, Inteligência reformulada, Aporte com explicação avançada, Ativos com dados visíveis, documentação e testes.

### Adicionado
- **UX/UI**: `.streamlit/config.toml` (tema fixo `base="dark"`) — corrige o bug de contraste (cards brancos com texto claro) causado pela ausência de um tema fixo combinado com CSS hardcoded para tema claro. `styles/theme.py` e `styles/custom_css.py` reescritos com paleta escura completa (fundos, bordas, texto, cores semânticas e de classificação, todas explícitas — nunca herdadas do navegador). `components/badges.py` novo (badges de classificação/confiança/qualidade de dado). `charts/_theme.py::apply_dark_layout()` aplicado a todos os gráficos Plotly da plataforma.
- **Data Quality Layer** (`engines/data_quality/`, `schemas/data_quality.py`, `services/data_quality_service.py`): classifica preço (automático/manual/estimado/ausente), fundamentos (completo/parcial/ausente/não aplicável, limiar de 70% de cobertura), valuation (real/não aplicável/ausente) e confiança do score por ativo, e agrega em resumo ponderado por peso na carteira. Nunca inventa "completo" quando o dado é parcial.
- **Fundamentals Foundation expandida**: 9 novos campos nullable em `fundamental_snapshots` (`market_cap`, `enterprise_value`, `forward_pe`, `operating_margin`, `total_debt`, `total_cash`, `operating_cash_flow`, `gross_profit`, `shares_outstanding`) — migration `a1f4e6c2b8d9`, puramente aditiva. `YahooFundamentalsProvider` populando os novos campos.
- **Capital Reinvestment Engine v1** (`engines/capital_reinvestment/`, `schemas/capital_reinvestment.py`, `services/capital_reinvestment_service.py`): extraído do agregador de pilares para pacote próprio, mesmo padrão dos demais engines. Fórmula de retenção de lucro (1 − payout ratio), aplicável a `stock`/`etf`.
- **Risk Engine — cripto por política**: cripto passa a ser classificada `"alto"` risco por decisão explícita de metodologia (confiança "alta"), não mais "indeterminado" por dado ausente — documentado em `docs/QUALITY_GROWTH_RISK_ENGINES.md`.
- **Quality/Risk Engines — classes aplicáveis expandidas**: Quality agora cobre `stock` e `reit` (antes só `stock`).
- **LG Conviction Score v2**: pesos por classe revisados (`profile.py`) para refletir ênfase pedida por classe sem fabricar pilares novos (decisão documentada em `docs/IDS_METHODOLOGY.md`); nova classificação de decisão (`strong_buy`/`buy`/`hold`/`watch`/`avoid`/`insufficient_data`, com gate de confiança mínima de 35%) substituindo os rótulos antigos (Exceptional/Excellent/.../Avoid) no caminho v2; campo `recommendation_hint` explicando a classificação e alertando quando a confiança é baixa.
- **Decision Engine 2.0 — alertas de baixa confiança**: `_build_alerts()` reescrito para nomear os tickers específicos afetados por baixa confiança em vez de um aviso genérico; novo campo `item_confidence` por item da recomendação.
- **Dashboard**: nova seção "Oportunidades & Riscos" (top oportunidades/riscos por Conviction Score v2, classe mais subalocada, métricas de qualidade de dado da carteira).
- **Inteligência**: reformulação completa — de tabela+gráfico simples para painel organizado por classificação (buckets com contagem), rankings por dimensão (mais baratos/caros, maior qualidade/crescimento/risco), e seção "Por que esse ativo?" com diagnóstico completo por ativo (pilares, motivos, o que melhoraria/pioraria a nota).
- **Aporte**: exibição de `item_confidence` por ativo recomendado; impacto do aporte na concentração (HHI) e na exposição internacional, antes/depois.
- **Ativos**: nova seção "LG Conviction Score v2" com pilares, motivos e badges de qualidade de dado; 3 novas métricas de fundamentos (market cap, forward P/E, margem operacional).
- **Documentação**: `docs/IDS_METHODOLOGY.md` atualizado para v2; novos `docs/FUNDAMENTALS_ENGINE.md`, `docs/VALUATION_ENGINE.md`, `docs/QUALITY_GROWTH_RISK_ENGINES.md`, `docs/DECISION_ENGINE_V2.md`, `docs/DATA_QUALITY.md`, `docs/UX_GUIDELINES.md`, `docs/DEPLOYMENT_NOTES.md`.

### Testes
- `test_risk_engine.py`: teste de cripto atualizado para refletir a política de risco "alto" (era esperado "indeterminado"); teste de classe não aplicável trocado para `bond`.
- `test_decision_engine.py`: assert de alerta de baixa confiança atualizado para o novo formato com tickers nomeados.
- `test_ids_methodology_pillars_v2.py`: testes de `capital_reinvestment_pillar_v2` corrigidos para usar `ReinvestmentResult` (schema real do Capital Reinvestment Engine) em vez do `FundamentalSnapshotResult` da assinatura antiga, pré-extração do engine.
- Suíte completa: **426 testes passando**, 0 falhas.

### Notas técnicas
- Durante a verificação desta sprint, um número expressivo de arquivos editados via ferramenta de edição direta (não via terminal) apresentava conteúdo desatualizado/truncado quando lido a partir do ambiente de verificação em sandbox — não um problema real no projeto do usuário, mas uma dessincronia pontual entre a visão do arquivo usada para editar e a usada para verificar. Todos os arquivos afetados foram identificados (via checagem de importação de todos os módulos + configuração de mappers do SQLAlchemy, mais forte que apenas verificar sintaxe) e resincronizados antes da suíte de testes ser considerada válida.
- Ambiente de verificação rodou em Python 3.10 (sandbox), enquanto o projeto requer Python ≥3.11 (`pyproject.toml`, já usado no `.venv` local do usuário) — necessário um shim mínimo e local ao sandbox (não commitado ao projeto) para suprir `datetime.UTC` (disponível nativamente a partir do Python 3.11) só para permitir a execução da suíte nesse ambiente específico.

### Limitações conhecidas (documentadas, não escondidas)
- Valuation Engine v1 não calcula `fair_value_low/base/high` nem margem de segurança numérica — decisão deliberada para não fabricar projeções sem dado de fluxo de caixa/taxa de desconto reais (ver `docs/VALUATION_ENGINE.md`).
- Pesos por classe do Conviction Score v2 são síntese de julgamento do autor da plataforma, não calibrados estatisticamente.
- `target_weight` por ticker individual no Decision Engine nunca foi implementado — só a meta por classe influencia a v2.
- Cobertura de fundamentos via yfinance continua inconsistente para FIIs/small caps — esperado, não um bug.
- `DATABASE_URL` real nunca foi escrita em nenhum arquivo versionado nem no `.env.example` — só usada via variável de ambiente/argumento de linha de comando nas sessões do usuário, e nos Secrets do Streamlit Cloud (não versionados).

## [1.13.0] - Sprint 22 — Correção de qualidade, consistência financeira e ajustes de UX

### Contexto
Sprint de correção pedida explicitamente pelo usuário após a evolução do Sprint 21: "não quero criar novas features grandes... quero corrigir lógica, normalização de dados, classificação por classe e UX". Seis problemas reportados diretamente pelo usuário ao usar a plataforma com a carteira real, sem DCF, sem IA generativa e sem reescrita do app.

### Corrigido
- **Tesouro/ativos manuais aparecendo como "sem preço cadastrado"**: `Asset.is_manual` agora tem prioridade sobre a origem do `Price` em três pontos da fronteira banco↔apresentação — `engines/data_quality/engine.py::classify_price_status()`, `services/data_quality_service.py` (parâmetro `is_manual` em `evaluate_ticker`) e `services/dashboard_view_service.py` (`_load_price_rows` passa a resolver `is_manual` por ticker e prioriza esse sinal antes de qualquer inferência por `Price`). Um ativo manual nunca mais aparece como "ausente"/"estimado", mesmo sem nenhuma linha de `Price` ainda cadastrada. `services/data_quality_service.py::evaluate_portfolio()` também passou a avaliar tickers sem preço resolvido (antes ficavam de fora do resumo de qualidade de dado por completo, já que a Portfolio Engine os exclui de `summary.positions`).
- **Dividend Yield de BTLG11 exibido como 950%**: novo `_normalize_percentage()` em `etl/providers/yahoo_fundamentals_provider.py` — quando o yfinance devolve um campo percentual já multiplicado por 100 (ex.: `9.5` em vez de `0.095`), o valor é dividido por 100 antes de virar `FundamentalData`; valores já corretos como fração (`<= 1` em módulo) não são alterados. Aplicado a `roe`, `roa`, `net_margin`, `ebitda_margin`, `dividend_yield`, `payout_ratio` e `operating_margin`. Deliberadamente **não** aplicado às margens/CAGR calculados internamente em `get_history()`/`fundamentals_analysis_service` (computados a partir de valores em R$, sem risco de escala) nem à multiplicação de banda de valuation (`pe_ratio`/`pb_ratio`/`ev_ebitda`, que não são percentuais).
- **BTC-USD no ranking "mais baratos por valuation" com nota 100**: `pages_impl/inteligencia.py::_ranking()` agora filtra por classe aplicável a cada pilar (`_RANKING_APPLICABLE_CLASSES`, usando os `APPLICABLE_CLASSES` já existentes/expandidos de `valuation`/`quality`/`growth`) e exclui ativos com `has_conviction_score=False` ou `classification == "insufficient_data"`. Cripto passa a ficar fora dos rankings de valuation/qualidade/crescimento (não são medidas reais para essa classe — só o proxy de preço v1 de fallback); risco continua sem filtro de classe (cripto tem risco "alto" por política real, Sprint 21, não fallback).
- **FIIs avaliados como se fossem ações comuns**: `pages_impl/ativos.py` passa a exibir um aviso explícito quando `asset_class == "fii"` explicando que ROE/P-L/margem vêm do Yahoo como proxy MVP e não são indicadores significativos para fundos; `services/data_quality_service.py` agora calcula a cobertura de fundamentos de FII só sobre `pb_ratio`/`dividend_yield` (as métricas realmente usadas pelo Valuation Engine para essa classe), em vez dos 28 campos completos usados para ações — evita inflar artificialmente a confiança/cobertura de FII com campos que não deveriam pesar.
- **Tela Carteira com tabela estreita/espremida**: `components/tables.py::render_positions_table()`/`render_grouped_positions()` ganharam parâmetro `simplified`, que restringe a exibição às colunas essenciais (ticker, grupo, quantidade, preço, valor, peso, rentabilidade); `pages_impl/carteira.py` usa o modo simplificado por padrão nas tabelas principal e agrupada, com um expander "Ver detalhes" para moeda, preço médio, origem do preço e alertas.

### Adicionado (novas constantes de classificação)
- `engines/growth/thresholds.py::APPLICABLE_CLASSES = ("stock", "reit")` — CAGR de receita/lucro só é medida real para essas classes.
- `engines/valuation/thresholds.py::APPLICABLE_CLASSES = ("stock", "fii", "reit")` — forma positiva do `NOT_APPLICABLE_CLASSES` já existente, usada pelo filtro de ranking da Inteligência.

### Testes
- `test_yahoo_fundamentals_provider.py`: 7 novos testes de `_normalize_percentage()` (fração passa direto, escala percentual é dividida, `None`, limite em `1`, valores negativos) e reprodução direta do bug relatado (BTLG11 com `dividendYield=9.5` → `0.095`), mais um teste garantindo que margens já corretas (WEGE3) não são distorcidas.
- `test_data_quality_engine.py` (novo arquivo): cobre `classify_price_status()` com `is_manual` sobrepondo qualquer origem de preço, e `build_asset_data_quality()` gerando a mensagem específica de ativo manual sem preço (não a mensagem genérica de "ausente").
- `test_data_quality_service.py` (novo arquivo): cobre `evaluate_ticker()` com `is_manual=True` (com e sem linha de `Price`), cobertura de fundamentos restrita a `pb_ratio`/`dividend_yield` para FII vs. os 28 campos completos para ações, e `evaluate_portfolio()` propagando `is_manual` a partir do `Asset` (incluindo o caso de ticker sem preço resolvido, que antes desaparecia do resumo).
- `test_dashboard_view_service.py`: 2 novos testes cobrindo `asset.is_manual=True` sem nenhuma linha de `Price` e com uma linha de `Price` de origem não-manual — em ambos os casos o resultado deve ser `price_source="manual"`.
- `test_inteligencia_ranking.py` (novo arquivo): 7 testes cobrindo exclusão de cripto do ranking de valuation, exclusão de ETF do ranking de crescimento, exclusão de renda fixa do ranking de valuation, exclusão de ativos com dados insuficientes, ausência de filtro de classe no ranking de risco (cripto deve continuar aparecendo), exclusão de valores `None` e respeito ao `top_n`.
- Suíte completa: **461 testes passando**, 0 falhas (435 anteriores + 26 novos desta sprint).

### Riscos e limitações conhecidas
- `_normalize_percentage()` usa um limiar fixo (`> 100%` em módulo) para decidir se um valor já está em escala percentual — ROE/ROA de empresas com alavancagem extrema podem, em casos raros e legítimos, superar 100% e seriam incorretamente divididos por 100. Não há forma de distinguir os dois casos só a partir do valor numérico isolado; documentado no docstring da função.
- FIIs continuam usando o Yahoo Finance como fonte de fundamentos (proxy MVP) — a sprint tornou isso mais explícito e restringiu a cobertura calculada às métricas relevantes, mas não trocou de fonte de dado nem implementou um provider dedicado a FIIs.
- Os rankings da Inteligência agora dependem de duas listas de classes aplicáveis por pilar (`valuation`/`quality`/`growth`) mantidas manualmente em `thresholds.py` de cada engine — se uma classe nova for adicionada ao sistema, essas listas precisam ser revisadas manualmente (mesmo padrão de risco documentado desde o Sprint 21 para `NOT_APPLICABLE_CLASSES`).
- Ambiente de verificação em sandbox (Python 3.10 + shim de `datetime.UTC`) apresentou instabilidade de sincronização de arquivos mais severa que a observada no Sprint 21 — não limitada a arquivos recém-editados, afetando também arquivos não tocados nesta sessão, de forma assíncrona e recorrente. A suíte final foi validada a partir de uma cópia local estável no próprio sandbox, com cada arquivo conferido byte a byte (contagem de linhas + final do arquivo) contra o conteúdo lido diretamente do projeto real antes de cada execução — o projeto do usuário em si (fora do sandbox de verificação) nunca foi afetado, já que toda edição foi feita diretamente nos arquivos reais.

## [1.14.0] - Sprint 23 — Integração com Dividendos.me (sincronização de posições)

### Contexto
Decisão de produto do usuário: Dividendos.me passa a ser a fonte oficial das posições reais da carteira (ações BR, FIIs, ações/ETFs/REITs internacionais, criptomoedas, Tesouro Direto — hoje distribuídas em duas carteiras no Dividendos.me, Brasil e internacional). A LG INVEST continua sendo a camada de inteligência (LG Conviction Score, Decision Engine, Journal) e passa a consumir essas posições já sincronizadas e consolidadas num único `portfolio_id`, em vez de depender só de importação manual/CSV. Investigação técnica ao vivo (login real + inspeção de rede) precedeu a implementação e foi aprovada explicitamente pelo usuário antes de qualquer código ser escrito.

### Adicionado
- **`backend/app/integrations/dividendos_me/`** (pacote isolado de scraping/automação, nunca importado por `engines/`/`services/` de cálculo financeiro):
  - `secrets.py`: leitura de credenciais só via `.env` local (`DIVIDENDOS_ME_EMAIL`/`DIVIDENDOS_ME_PASSWORD`) ou `st.secrets["dividendos_me"]` no Streamlit Cloud; nunca hardcoded, nunca logado, nunca salvo em banco; `has_dividendos_me_credentials()`/`mask_secret()` para a UI mostrar só "configurado: sim/não".
  - `schemas.py`: DTOs Pydantic (`ExtractedPosition`, `SyncDiff`, `SyncPreview`, `SyncRunResult`, `NormalizedTicker`) e as origens `ORIGIN_B3`/`ORIGIN_INTERNATIONAL`.
  - `parser.py`: normalização pura (sem I/O) de número BR/US (`R$ 1.234,56`, `US$ 1,234.56`, `6,52%`, parênteses para negativo), percentual (convertido para fração 0..1, mesma convenção do Sprint 22) e ticker por seção — Brasil (`.SA` por subgrupo Ações/FIIs/ETFs/BDRs), EUA (remove `.SA`, subgrupo Ações/ETFs/REITs), Criptomoedas (`BTC` → `BTC-USD`, demais moedas ficam `review_required`) e Renda Fixa (sintetiza `TESOURO-{INDEXADOR}-{ANO}` a partir do nome/ticker, ativo `is_manual=True`). Qualquer combinação não reconhecida vira `review_required=True` em vez de classificada silenciosamente errada.
  - `auth.py`: login via Playwright com mensagem de erro sempre genérica e segura (`"Falha ao autenticar no Dividendos.me. Verifique credenciais ou tente novamente."`) — nunca loga nem propaga e-mail/senha/detalhe da exceção original.
  - `client.py` (`DividendosMeClient`): sessão Playwright efêmera (login do zero a cada execução, sem `storage_state` salvo em disco); extrai as tabelas já renderizadas em "Tabela de Ativos" via `page.evaluate()`, mapeando colunas pelo texto do cabeçalho (não por posição fixa); cada seção (Brasil, EUA, Criptomoedas, Renda Fixa) roda isolada em try/except — uma falha vira entrada em `sections_failed` sem abortar as demais.
  - `service.py` (`DividendosMeSyncService`): orquestra `client`+`parser`, consolida posições duplicadas entre seções (mesmo ticker vindo de mais de uma seção — soma quantidade, preço médio ponderado), calcula o diff contra o `portfolio_id` alvo (mantidos/atualizados/novos/removidos) e implementa os 3 modos de sincronização.
- **Modos de sincronização**: `dry-run` (busca + preview, nunca grava — modo padrão), `replace` (substitui 100% das posições do `portfolio_id` pelas do Dividendos.me; exige `confirm=True`), `update` (cria/atualiza sem remover; opcional, uso futuro; também exige `confirm=True`). Posições `review_required` nunca são criadas/atualizadas em nenhum modo.
- **Migration `d4a8f21e9c07`** (puramente aditiva): `positions.source` (nullable, rastreia `dividendos_me:b3`/`dividendos_me:international`/`None`) e tabela `external_sync_runs` (auditoria: provider, modo, status, contadores de criadas/atualizadas/removidas, `summary_json` com snapshot do estado anterior — nunca senha/cookie/token).
- **`scripts/sync_dividendos_me.py`** (CLI local): `python -m scripts.sync_dividendos_me --portfolio-id 1 --mode dry-run|replace|update [--confirm]`; credenciais só via `.env`, nunca por argumento de linha de comando; nunca exibe a senha.
- **Tela "Sincronizar Dividendos.me"** (`pages_impl/sincronizar_dividendos_me.py` + `components/import_preview.py`, registrada em `app.py`): status (credenciais configuradas sim/não, Playwright disponível sim/não, última sincronização); "Testar login"; "Buscar carteira" (preview com patrimônio total, ativos encontrados, diff, seções com falha, ativos para revisão); confirmação por modo exigindo a palavra exata digitada (`SUBSTITUIR` para replace, `ATUALIZAR` para update); resumo final com sugestão de atualizar preços/fundamentos em seguida. Botões desabilitados automaticamente quando credenciais ou Playwright não estão disponíveis (`is_playwright_available()`).
- `playwright` adicionado a `requirements.txt`/`pyproject.toml` (uso recomendado só local — Streamlit Cloud não roda a sincronização, só lê o resultado); `.env.example` e `.gitignore` atualizados (`.streamlit/secrets.toml` também ignorado); `docs/DIVIDENDOS_ME_INTEGRATION.md` novo, documentando arquitetura, decisão Playwright-vs-API, segurança de credenciais, fluxo completo e limitações conhecidas.

### Testes
- `test_dividendos_me_secrets.py`: credenciais ausentes/parciais, leitura de `.env` e fallback para `st.secrets`, `__repr__` nunca vazando e-mail/senha, `mask_secret()`, `sanitize_message()`.
- `test_dividendos_me_parser.py`: parser de número (BR, US, símbolos de moeda, parênteses, sinal `+`) e percentual; normalização de ticker para todas as classes (ação BR com `.SA`, FII, ação US sem `.SA`, ETF, REIT, BTC → `BTC-USD`, cripto não reconhecida, Tesouro IPCA+/SELIC, renda fixa não identificada, ticker vazio, seção desconhecida).
- `test_dividendos_me_auth.py`: falha de login sempre retorna a mensagem genérica; log de falha nunca contém e-mail/senha (verificado via `caplog`); login bem-sucedido não levanta exceção.
- `test_dividendos_me_client.py`: extração de tabela e mapeamento de linha→`ExtractedPosition` por rótulo de cabeçalho (com `page` falsa, sem Playwright real); campos ausentes ficam `None` em vez de inventados; `DividendosMeScrapingError` quando Playwright não está instalado.
- `test_dividendos_me_service.py`: dry-run nunca grava nada; replace/update exigem `confirm=True`; replace cria ativo+posição nova, remove posições ausentes na fonte e grava em `external_sync_runs`; update mantém posições ausentes na fonte; posições `review_required` nunca são gravadas; seções com falha aparecem como erro no resultado; Tesouro é criado como ativo manual; consolidação de ticker duplicado entre seções (soma quantidade, preço médio ponderado).
- Suíte completa: **525 testes passando**, 0 falhas (461 anteriores + 64 novos desta sprint).

### Segurança (verificado nesta sprint)
- Nenhuma credencial hardcoded ou commitada — só `.env` local (fora do git) ou `st.secrets` no Streamlit Cloud.
- Nenhum teste, log ou mensagem de erro desta integração expõe e-mail/senha/cookie/token — verificado explicitamente via `caplog` no teste de falha de login.
- A sincronização nunca roda automaticamente: só via clique explícito na tela ou comando explícito no terminal.
- `replace`/`update` exigem `confirm=True` programaticamente e a palavra de confirmação exata na UI — sem isso, `SyncConfirmationRequiredError` impede qualquer gravação.

### Limitações conhecidas
- Os caminhos de URL das seções "Criptomoedas" e "Renda Fixa" no Dividendos.me não foram confirmados ao vivo (a navegação ficou instável durante a investigação antes de chegar lá) — são heurísticas best-effort; se falharem, aparecem em `sections_failed` no preview sem interromper as demais seções.
- A coluna "DIV" da tabela do Dividendos.me foi interpretada como dividend yield percentual, não como valor de dividendos recebidos em R$ — não havia confirmação suficiente para tratá-la como valor monetário.
- `Position.opened_at` é preenchido com a data da sincronização (o Dividendos.me não expõe data de abertura da posição) — campo informativo, não usado em nenhum cálculo de rentabilidade.
- A sincronização depende de Playwright e é recomendada só para uso local; no Streamlit Cloud a tela detecta a ausência do Playwright e desabilita os botões, mas a leitura das posições já sincronizadas continua funcionando normalmente.

## [1.14.1] - Correção pós-Sprint 23 — `.env` não era lido para as credenciais do Dividendos.me

### Corrigido
- **Bug real reportado pelo usuário**: mesmo com `DIVIDENDOS_ME_EMAIL`/`DIVIDENDOS_ME_PASSWORD` corretamente definidos no `.env`, a tela e o CLI continuavam mostrando "Credenciais do Dividendos.me não configuradas". Causa raiz: `backend/app/core/config.py` usa `pydantic-settings` com `env_file=".env"`, que só popula os atributos da classe `Settings` — nunca escreve em `os.environ`. Como as credenciais do Dividendos.me foram propositalmente mantidas fora da classe `Settings` (Sprint 23, para reduzir risco de aparecerem em log/repr), `backend/app/integrations/dividendos_me/secrets.py::_read_from_env()` chamava só `os.getenv(...)` diretamente, que nunca via os valores do `.env`.
- **Correção**: `_read_from_env()` agora chama `load_dotenv()` (python-dotenv, já dependência do projeto) antes de `os.getenv(...)`. `load_dotenv()` localiza o `.env` subindo a partir do próprio arquivo `secrets.py` (não depende do diretório de onde o comando é executado) e só define variáveis ainda ausentes em `os.environ` — nunca sobrescreve uma variável de ambiente já exportada manualmente pelo usuário.

### Testes
- Novo `test_read_from_env_calls_load_dotenv` confirmando a chamada.
- Três testes existentes (`test_missing_credentials_returns_none`, `test_missing_one_field_still_returns_none`, `test_credentials_fallback_to_streamlit_secrets`) ajustados para neutralizar `load_dotenv()` via monkeypatch — sem isso, rodar a suíte numa máquina com um `.env` real preenchido (como a do usuário) reintroduziria as credenciais reais depois do `delenv()` do próprio teste, quebrando o isolamento do teste.
- Suíte completa: **526 testes passando**, 0 falhas.

## [1.14.2] - Sprint 23.1 — Extração real quebrada (agregado/ticker vazio) + bloqueios de segurança obrigatórios

### Corrigido
- **Bug real reportado pelo usuário**: o dry-run fazia login com sucesso, mas a extração vinha errada — um único "ativo" com ticker vazio e quantidade/valor iguais à soma de toda a carteira, e o diff mostrava quase todos os 27 tickers reais como "serão removidos". Causa raiz, encontrada por investigação ao vivo do DOM real do Dividendos.me, foram **três bugs distintos que se somavam**:
  1. O `<th>` da coluna atualmente ordenada vem com uma seta de ordenação e quebra de linha (ex.: `"ATIVO\n↑"`), então `row.get("ATIVO")` nunca batia e todo `raw_ticker` saía vazio.
  2. O rótulo do subgrupo (ex.: "Fundos Imobiliários") não é irmão direto da `<table>` — é irmão do **wrapper** da tabela, um nível acima. O código antigo nunca subia para o `parentElement`, então nunca encontrava o subcabeçalho.
  3. Navegar direto via `page.goto(url)` para uma seção diferente da padrão (EUA, Criptomoedas, Renda Fixa) carrega conteúdo em branco/errado — o Dividendos.me guarda o país/categoria selecionado em estado interno do cliente (SPA), não na URL. A navegação precisa ser client-side (clique real no menu lateral, expandindo o acordeão quando necessário).
  - Como `service.py` consolida posições por ticker, e todo ticker saía vazio (bug 1), todas as linhas de todas as seções colapsaram numa única posição agregada — exatamente o bug relatado.
- **Extração de Criptomoedas e Renda Fixa reformulada**: não existe uma "Tabela de Ativos" para essas seções (suposição da Sprint 23 estava incorreta). Confirmado ao vivo: Criptomoedas usa `/criptos/extrato` e Renda Fixa usa `/renda-fixa/meu-resumo`, ambas com ativos representados como **cards** (`div`), não linhas de tabela. Nova extração por assinatura de texto (`Quantidade:`/`Preço Médio:`/`Total:` para cripto; `Valor atual` para Renda Fixa) com `parser.parse_card_lines()`.
- **Normalização de ticker dos EUA**: ações de classe dupla como "BRK.B" (formato do Dividendos.me) agora convertem para "BRK-B" (formato do Yahoo Finance, fonte de preço da LG INVEST) — sem isso, a mesma posição virava um ticker "novo" a cada sincronização.
- **Subcabeçalho por substring**: o rótulo de ETFs nos EUA vem concatenado como `"ETF\nETFs"` — o casamento agora usa substring em vez de igualdade exata.

### Adicionado — bloqueios de segurança obrigatórios (nunca contornáveis pela UI)
Estas regras rodam em `service.py` (`extraction_blocking_reasons`) e valem tanto para o CLI quanto para a UI, já que ambos chamam o mesmo serviço. Não existe nenhum parâmetro de force/bypass, em nenhuma camada:
- Extração com **1 posição ou menos e ticker vazio** bloqueia `replace`/`update`.
- Qualquer posição marcada para **revisão manual com ticker vazio** bloqueia `replace`/`update`.
- Mais de **50% da carteira atual** apareceria em "não veio da fonte, seria removida" bloqueia especificamente o `replace` (único modo que remove posições) — com exatamente 50% ou menos, a substituição segue normalmente.
- Mensagem exibida em todos os casos, sempre a mesma: **"Extração inválida ou incompleta. Substituição bloqueada para evitar perda de carteira."** (nova exceção `ExtractionInvalidError`).
- Seções que falharem e forem Criptomoedas/Renda Fixa agora disparam um **alerta forte** (não só um item de lista) na UI e no CLI, já que essas seções não têm sobreposição com Brasil/EUA — perdê-las esconde ativos que não aparecem em nenhum outro lugar do preview.

### Adicionado — status success/partial/failed e diagnóstico
- `SyncPreview.status` (`"success"` | `"partial"` | `"failed"`): nunca mais "success" com patrimônio encontrado mas sem ativos válidos o suficiente. Regra: 0 ativos válidos → `"failed"`; menos de `MIN_VALID_ASSETS_FOR_SUCCESS` (2) ativos válidos, ou alguma seção falhou → `"partial"`; caso contrário → `"success"`.
- `SyncPreview.total_assets`/`SyncRunResult.assets_found` agora contam **só** posições com ticker reconhecido e `review_required=False` — nunca mais incluem a posição agregada/vazia do bug relatado.
- Novo `SectionDiagnostics` por seção (linhas brutas detectadas, válidas, rejeitadas, motivos de rejeição já sanitizados, seletor usado) — nunca inclui HTML bruto nem dado sensível. Exposto no preview (`SyncPreview.diagnostics`), no JSON do CLI e num expander na UI.

### Alterado
- `DividendosMeClient.fetch_portfolio()` agora devolve uma tripla `(posições, seções_falhas, diagnósticos)` em vez de um par.
- Navegação entre seções passou a ser sempre por clique real (`page.click`/`get_by_text`), nunca `page.goto()`, depois do login inicial.

## [1.15.0] - Sprint 23.2 — Correção do BTC e Proventos/Dividendos do Dividendos.me

### Corrigido — BTC saía com ticker vazio
- **Bug real reportado pelo usuário**: no dry-run, todo o restante da carteira (Brasil, EUA, Renda Fixa) saía correto, mas Bitcoin vinha com `ticker: ""` e `review_required=True`, apesar de quantidade/preço médio/preço atual/valor atual identificarem claramente o BTC. Causa raiz, confirmada ao vivo comparando a extração antes/depois diretamente no console do navegador: o card de cripto no `/criptos/extrato` tem uma div interna ("stats") que também bate a assinatura de texto usada para selecionar o card (`Quantidade:`/`Preço Médio:`/`Total:`), mas sem o nome do ativo (que fica num nível acima, no card completo). O seletor antigo escolhia essa div interna em vez do card inteiro, perdendo o nome — nunca foi um problema de reconhecimento de texto "Bitcoin"/"BTC" (o parser já reconhecia corretamente).
- **Correção**: `_EXTRACT_CRYPTO_CARDS_JS` agora exige também "Ver Opera" (rodapé de ação presente só no card completo) na assinatura — força a seleção do card certo, com o nome do ativo incluído.
- **Rede de segurança adicional** (`_apply_btc_fallback` em `service.py`, defesa em profundidade mesmo com o bug de raiz corrigido): se a seção "criptomoedas" trouxer exatamente uma posição sem ticker e a carteira atual já tiver `BTC-USD`, remapeia automaticamente para `BTC-USD`. Nunca dispara com mais de uma cripto sem ticker (ambíguo demais) nem se `BTC-USD` não existir já na carteira atual (nunca inventa uma posição nova).

### Adicionado — Proventos / Dividendos (Investigação e escopo reduzido, aprovado pelo usuário)
- **Investigação ao vivo confirmou um teto real de dado**: mesmo com conta Premium/PRO (confirmado pelo usuário) e inspeção do CSV exportável da aba "Histórico", o Dividendos.me **não expõe, em lugar nenhum**, um evento individual por ativo com data exata + tipo + valor já pago. As únicas fontes confiáveis encontradas foram (a) o agregado mensal por carteira (aba "Análise", tabela ano×mês, BR/Dólar, status "recebido", sem ticker) e (b) o calendário de próximos dividendos por ativo (aba "Próximos Dividendos", status "anunciado", nunca "recebido"). Esta limitação está documentada no código (`income_parser.py`) e na tela — não é uma escolha de design, é o teto real da fonte.
- **Nova tabela `income_events`** (migration `e7b3f0a915c2`, puramente aditiva — não altera nenhuma tabela existente): `id`, `portfolio_id`, `asset_id` (nullable), `ticker` (nullable), `source`, `event_type`, `status`, `ex_date`/`payment_date`/`declared_date`, `quantity`, `amount_per_share`, `amount_total`, `currency`, `raw_payload_json`, `created_at`/`updated_at`. Nunca mistura proventos com `positions` — proventos são histórico/eventos, posições são estado atual da carteira.
- **`income_parser.py`** (normalização pura, sem Playwright/rede): `parse_monthly_aggregate` (pula meses com R$ 0,00 — não é erro, só não houve provento), `parse_upcoming_dividends` (agrupamento por dia de pagamento, inferência de ano por virada de mês), normalização de ticker (`.SA` para BR, sem sufixo para EUA), detecção de moeda pelo valor **nativo** do ativo (nunca o convertido para BRL, para não fixar uma taxa de câmbio num evento histórico), e guarda defensiva que **nunca gera evento de provento para Tesouro** (BTC nunca passa por este parser, pois `client.py` não chama proventos para a seção de criptomoedas).
- **`DividendosMeClient.fetch_income_events()`**: sessão Playwright própria, **totalmente isolada** de `fetch_portfolio()` — uma falha aqui nunca impede nem é impedida pela sincronização da carteira. Navega para "Central de Proventos" (`/dividends`) e usa clique real (`page.click`/`get_by_text().click()`) para trocar de aba — confirmado ao vivo que cliques síntéticos via JavaScript puro não trocam de aba neste hub, só cliques de verdade (nível do SO via CDP).
- **`IncomeSyncService`** (`build_preview`, `dry_run`, `import_events`): busca proventos uma única vez por operação (nunca faz login duas vezes), deduplica em lote e contra o banco (chave: `portfolio_id + ticker + payment_date + event_type + amount_total + source`), e é **puramente aditivo** — `import_events` nunca remove proventos já salvos.
- **CLI** (`scripts/sync_dividendos_me.py`): `--include-income` (padrão) e `--skip-income`; dry-run e replace/update agora também mostram um resumo de proventos no JSON de saída, sem nunca bloquear a sincronização da carteira em caso de falha isolada.
- **UI Streamlit** ("Sincronizar Dividendos.me"): nova seção "5. Proventos / Dividendos" com "Buscar proventos" (preview) e "Importar proventos encontrados" (aditivo, sem palavra de confirmação — nunca destrutivo). Falha na extração de proventos mostra só um alerta ("Carteira sincronizada, mas proventos não foram extraídos.") e nunca bloqueia a tela nem a sincronização da carteira.

### Corrigido — bug real encontrado durante a verificação desta sprint
- **`replace` apagava e recriava posições que continuavam presentes na extração** (não só as ausentes): a versão anterior de `_apply_sync` deletava incondicionalmente **todas** as posições atuais em modo `replace`, mesmo as que vieram de novo na extração, perdendo `id`/`opened_at` à toa. Corrigido para remover só o que está em `preview.diff.missing_in_source` e atualizar em lugar o que continua presente — capturado por dois testes pré-existentes (`test_replace_removes_positions_missing_from_source`, `test_replace_allowed_when_missing_ratio_is_exactly_half`) que já expressavam o comportamento correto mas não estavam sendo exercitados.

### Segurança (mantido, sem exceções)
- Não loga senha; não salva cookies/tokens; não exibe HTML bruto; não expõe dado sensível (`raw_payload_json` só guarda metadados já sanitizados); erro amigável em toda falha; sem sincronização automática (tudo requer clique explícito do usuário).

### Testes
- Novos: `test_dividendos_me_income_parser.py` (agregado mensal, detecção de moeda, normalização de ticker, guarda de Tesouro, inferência de data com virada de ano, calendário futuro, deduplicação em lote), `test_dividendos_me_income_service.py` (preview/dry-run/import, dedup contra o banco, status success/partial/failed, isolamento total entre proventos e posições).
- Atualizados: `test_dividendos_me_client.py` (card-boundary do BTC, campo `section` preservado) e `test_dividendos_me_service.py` (`_apply_btc_fallback`: mapeia com exatamente uma cripto sem ticker + BTC-USD já na carteira; nunca mapeia com mais de uma cripto sem ticker; nunca mapeia sem BTC-USD já presente; nunca mapeia fora da seção "criptomoedas").
- Suíte completa: **604 testes passando**, 0 falhas. `ruff check` e `black --check` limpos.

### Testes
- Reescritos `test_dividendos_me_client.py` (navegação por clique, extração de tabela e de cards, mapeamento de posição de tabela/card, diagnóstico por seção) e `test_dividendos_me_service.py` (status success/partial/failed, todos os bloqueios de segurança com e sem gatilho, nunca remove a carteira quando a extração é inválida, `update` bloqueia extração quebrada mas não a regra de remoção).
- Suíte completa: **526 testes passando**, 0 falhas. `ruff check` e `black --check` limpos.

### Limitações conhecidas
- As subseções de ETFs/BDRs do Brasil (dentro de Renda Variável) não puderam ser testadas ao vivo com dados reais (a carteira do usuário não tem esses ativos hoje) — só Fundos Imobiliários e Ações foram confirmados. A extração é defensiva (por rótulo de cabeçalho + substring de subgrupo, com fallback `review_required` para subgrupo não reconhecido), mas um formato inédito ainda pode exigir ajuste.

## [1.15.1] - Correção pós-Sprint 23.2 — tela certa de cripto ("Extrato"), moeda BRL e origem própria

### Contexto
O usuário encontrou a tela correta de posição de cripto no Dividendos.me: **"Criptomoedas → Extrato"** (`/criptos/extrato`), não "Meu Resumo". Essa navegação já estava correta no código desde a Sprint 23.2 (nenhuma URL de "meu-resumo" jamais existiu para cripto), mas o card real dessa tela tem um formato ligeiramente diferente do assumido nos testes anteriores, e os valores vêm em R$ (BRL) — não em USD como o código assumia.

### Corrigido
- **`parse_card_lines()` não tratava o prefixo "Carteira:"**: o card real de "Criptomoedas → Extrato" começa com o par `"Carteira:"` / `"Carteira Criptomoeda (Manual)"` antes do nome do ativo (`"btc"`). Sem tratamento, esse par era absorvido como parte do nome do ativo (`__name` virava `"Carteira: Carteira Criptomoeda (Manual) btc"`), quebrando o reconhecimento do ticker. Corrigido com um novo conjunto `_CARD_LABELED_IGNORED = {"carteira"}` que descarta o par label+valor por inteiro, antes de composição do nome — distinto de `_CARD_FIELD_LABELS` (que extrai valor) e de `_CARD_IGNORED_LABELS` (rótulos de ação de uma linha só, como "Ver Operações").
- **Moeda da posição de cripto**: `_normalize_crypto()` retornava `currency="USD"` incondicionalmente. A tela "Criptomoedas → Extrato" exibe quantidade/preço médio/preço atual/valor atual em R$ — corrigido para `currency="BRL"` em todos os ramos. `currency` em `ExtractedPosition`/`NormalizedTicker` passa a documentar explicitamente que descreve a moeda dos **valores extraídos**, não necessariamente a moeda de cotação do ativo (o ticker continua `BTC-USD`, convenção do Yahoo Finance).
- **Origem própria para cripto**: nova constante `ORIGIN_CRYPTO = "dividendos_me:crypto"` (`schemas.py`), com `origin_for_section("criptomoedas"|"cripto"|"crypto")` agora retornando `ORIGIN_CRYPTO` em vez de reaproveitar `ORIGIN_INTERNATIONAL` — evita confundir posições de cripto com ações/ETFs/REITs internacionais no rastreamento de origem.

### Adicionado — proteção específica para BTC-USD no modo `replace`
- Nova constante `_ALWAYS_PROTECTED_TICKERS = frozenset({"BTC-USD"})` em `service.py`: se `BTC-USD` já existe na carteira atual da LG INVEST e a extração desta vez **não** trouxer `BTC-USD` de volta (card não encontrado, layout mudou, etc.), o `replace` é bloqueado — **independentemente do percentual da carteira afetado**. A regra pré-existente de bloqueio (mais de 50% da carteira "some" na extração) não cobre o caso de uma carteira grande e diversificada perder só o BTC-USD sozinho (ex.: 1 de 50 ativos, bem abaixo de 50%). A checagem usa a mesma exceção `ExtractionInvalidError` e a mesma mensagem fixa **"Extração inválida ou incompleta. Substituição bloqueada para evitar perda de carteira."** — sem nenhum parâmetro de force/bypass, consistente com as demais regras de segurança do projeto.

### Testes
- `test_dividendos_me_parser.py`: `parse_card_lines` descarta corretamente o par "Carteira:"/valor (com e sem o prefixo); `_normalize_crypto` retorna `currency="BRL"`; `origin_for_section("criptomoedas"|"cripto"|"crypto")` retorna `ORIGIN_CRYPTO`.
- `test_dividendos_me_client.py`: novo teste com o card real exato informado pelo usuário (ticker `btc`, quantidade `0,00584925`, preço médio `R$ 76.308,58`, preço atual `R$ 62.404,96`, total `R$ 365,02`, rentabilidade `-18,22`) confirmando `ticker=BTC-USD`, `currency=BRL`, `origin=ORIGIN_CRYPTO`, `review_required=False`; `test_card_to_extracted_position_crypto` atualizado (USD→BRL, `ORIGIN_INTERNATIONAL`→`ORIGIN_CRYPTO`); novo teste confirmando que a seção de cripto nunca usa uma URL "meu-resumo".
- `test_dividendos_me_service.py`: novo teste confirmando que BTC-USD corretamente reconhecido aparece em `preview.positions` e nunca em `preview.diff.missing_in_source`; novo teste-alvo da regressão (`test_replace_blocks_when_btc_usd_missing_even_under_50_percent_ratio`) provando que o `replace` é bloqueado quando BTC-USD some da extração mesmo num cenário onde a regra geral de >50% não dispararia (1 de 4 ativos = 25%).
- Suíte completa: **610 testes passando**, 0 falhas. `ruff check` e `black --check --fast` limpos.

## [1.16.0] - Sprint 23.3 — Seções esperadas, bloqueio de replace por seção vazia e separação histórico/calendário de proventos

### Contexto
Um dry-run real reportou `status: success` com `assets_found: 18` e `total_patrimonio` só de Brasil, mas EUA, Criptomoedas e Renda Fixa vieram completamente vazios (`sections_failed: []`, `review_required_tickers: []`) — a carteira real tem BRK-B, KO, MSFT, PG, QQQ, VOO (EUA), BTC-USD (Criptomoedas) e TESOURO-IPCA-2050 (Renda Fixa), que teriam aparecido como `missing_in_source_will_be_removed` num `replace`. Separadamente, a extração de proventos usava "Próximos Dividendos" (calendário futuro) como se fosse o histórico mensal já recebido, em vez de "Central de Proventos → Renda Variável → Brasil → Análise" (tabela ano x mês por carteira).

### Corrigido — seções esperadas + bloqueio de replace (`service.py`)
- Novo conceito de **"seções esperadas"**, derivado da própria carteira ATUAL da LG INVEST (`_expected_sections_from_current`) — não uma lista fixa de tickers: se a carteira já tem um ativo `crypto`, "criptomoedas" passa a ser esperada nesta extração; `bond` → "renda_fixa"; país `US` → "eua"; país `BR` → "brasil". Mais robusto que listas fixas: cobre qualquer ativo novo na mesma classe sem manutenção manual.
- `build_preview` agora calcula `sections_with_data` a partir de `ExtractedPosition.section` e trata como **seção falha** qualquer seção esperada que não produziu nenhuma posição nesta execução, mesmo sem erro de navegação (`sections_missing`). O conjunto efetivo (`sections_failed` no preview) passa a ser a união de falhas reais do cliente com essas seções "vazias silenciosas" — isso alimenta tanto o `status` (nunca mais "success" nesse cenário) quanto o bloqueio de `replace`.
- Novo campo `SyncPreview.sections_expected` (lista) e `SyncPreview.total_patrimonio_status` (`"consolidated"` | `"partial"`) — `"partial"` sempre que houver seção esperada ausente; CLI/UI nunca devem apresentar `total_patrimonio` como consolidado nesse caso.
- Novo bloqueio obrigatório `_section_gap_reasons`: `replace` é bloqueado sempre que uma seção esperada vier vazia, **independentemente do percentual afetado** e mesmo sem nenhum ticker "sempre protegido" envolvido — complementar (não substitui) o `_ALWAYS_PROTECTED_TICKERS` (BTC-USD) já existente, que continua cobrindo o caso mais estreito de a seção trazer ALGUM dado mas não o ticker protegido específico.
- Nova mensagem fixa **"Extração incompleta: uma ou mais seções da carteira não foram carregadas. Substituição bloqueada para evitar perda de ativos."** (`EXTRACTION_INCOMPLETE_SECTIONS_MESSAGE`), usada em vez da mensagem genérica quando o motivo do bloqueio inclui seção vazia — nova função pública `has_section_gap(preview)` permite à UI/CLI escolher a mensagem certa sem duplicar a lógica de decisão. Nenhum parâmetro de force/bypass em nenhuma camada.
- `strong_alert_sections` generalizado: além de Criptomoedas/Renda Fixa (piso fixo), agora inclui qualquer seção em `sections_expected` — EUA também vira alerta forte quando a carteira atual tem ativos internacionais.

### Corrigido — instrumentação de navegação (`client.py`)
- `_goto_section` agora devolve um `_NavigationOutcome` (acordeão encontrado/clicado, URL final após o clique) gravado em `SectionDiagnostics.navigation_detail` — nunca dado sensível, só sinais de diagnóstico (a URL do Dividendos.me não é mais sensível que a barra de endereço do usuário).
- `_extract_table_section`/`_extract_card_section` agora tentam ler de novo (uma vez, após espera extra de 1.8s) se a primeira leitura vier vazia sem erro, antes de desistir da seção — elimina a hipótese mais simples de timing antes de precisar investigar um problema de navegação mais profundo. **Isso não garante sozinho a correção do problema real relatado** (não há acesso a Playwright/rede ao vivo neste ambiente para confirmar a causa) — mas deixa o diagnóstico (`navigation_detail`) explícito o bastante para a próxima investigação com dado real.

### Adicionado — histórico mensal de proventos separado do calendário futuro
- Nova tabela **`income_monthly_summaries`** (migration `b2f6a1d84c33`, puramente aditiva): `portfolio_id`, `wallet_name`, `year`, `month`, `amount_total`, `currency`, `source`, `status` (`recebido`/`anunciado`), `annual_total`, `annual_average` (sempre lidos direto das colunas TOTAL/MÉDIA da tabela "Análise", nunca recalculados), `raw_payload_json`. Dedup por `portfolio_id+wallet_name+year+month+currency+source`.
- `income_parser.py`: novo `parse_monthly_summary`/`NormalizedMonthlySummary`/`deduplicate_monthly_summaries_in_batch`, substituindo o antigo `parse_monthly_aggregate` (que forçava o agregado mensal no formato de evento por ticker — nunca deveria ter sido um evento, já que a fonte não tem ticker nem data exata).
- `client.py`: `fetch_income_events()` agora cobre **só** o calendário futuro (aba "Próximos Dividendos", única seção possível: `"income_calendar"`); novo `fetch_income_monthly_summaries()`, sessão própria, cobre só o histórico mensal (única seção possível: `"income_monthly"`). Os dois fluxos nunca compartilham extração/diagnóstico.
- `income_service.py`: novos `build_monthly_preview`/`dry_run_monthly`/`import_monthly_summaries` (grava em `income_monthly_summaries`, nunca em `income_events`), paralelos aos já existentes `build_preview`/`dry_run`/`import_events` (calendário, `income_events`). Uma falha num fluxo nunca afeta o outro nem a carteira.
- Novos schemas `IncomeMonthlySummaryPreviewItem`, `IncomeMonthlySyncPreview`, `IncomeMonthlySyncRunResult`.
- **Sem backfill/migração automática**: linhas antigas em `income_events` com `source` no formato de agregado mensal (de antes desta sprint) são deixadas exatamente como estão — decisão explícita do usuário, não migradas nem apagadas.

### Alterado — CLI e UI
- `scripts/sync_dividendos_me.py`: saída agora tem dois blocos completamente separados, `income_monthly` (`monthly_income_found`, `years_found`, `months_found`, `wallets_found`, `total_by_year`, `total_by_currency`) e `income_calendar` (`calendar_events_found`, `calendar_period_start`, `calendar_period_end`); `_preview_to_dict` da carteira ganhou `sections_expected`, `total_patrimonio_status` e `strong_alert_sections`.
- `frontend/streamlit_app/pages_impl/sincronizar_dividendos_me.py`: seção "5. Proventos/Dividendos" dividida em **"5A. Proventos — Histórico mensal"** e **"5B. Proventos — Calendário futuro"**, cada uma com seu próprio botão de busca/importação e chave de `session_state`.
- Novo componente `frontend/streamlit_app/components/monthly_summary_preview.py` (histórico mensal); `income_preview.py` reduzido a calendário-apenas; `import_preview.py` passa a exibir `sections_expected`, `total_patrimonio_status` (com aviso quando "partial") e escolhe a mensagem de bloqueio certa via `has_section_gap`.

### Testes
- `test_dividendos_me_service.py`: `_extracted()` passa a default `section="brasil"` (evita falso-positivo de seção ausente nos testes que já seedavam carteira BR); novos testes de `_expected_sections_from_current` (cobre stock/etf/crypto/bond), bloqueio de `replace` com EUA/Criptomoedas/Renda Fixa esperados e vazios (mensagem exata `EXTRACTION_INCOMPLETE_SECTIONS_MESSAGE`), `update` nunca bloqueado por seção vazia, `strong_alert_sections` incluindo EUA, `total_patrimonio_status` partial/consolidated, `has_section_gap`.
- `test_dividendos_me_client.py`: `_FakePage` ganhou `.url` e `evaluate_results` (sequência de retornos, para testar retry); testes de `_goto_section` verificando o `_NavigationOutcome` devolvido; testes de retry-on-empty para `_extract_table_section`/`_extract_card_section`; novo teste de `fetch_income_monthly_summaries` exigindo Playwright.
- `test_dividendos_me_income_parser.py`: testes de `parse_monthly_aggregate` substituídos por `parse_monthly_summary` (recebido/anunciado por data de referência injetada, TOTAL/MÉDIA nunca recalculados); novos testes de `deduplicate_monthly_summaries_in_batch`.
- `test_dividendos_me_income_service.py`: novo `_FakeMonthlyClient`; cobertura completa do fluxo mensal (`build_monthly_preview`/`dry_run_monthly`/`import_monthly_summaries` — nunca escreve em dry-run, dedup em lote e contra o banco, nunca deleta, nunca mistura com `income_events`); teste renomeado (`test_import_events_allows_null_asset_id_when_ticker_is_none`, já que o cenário original de agregado-sem-ticker não passa mais por `import_events`).
- Suíte completa: **649 testes passando**, 0 falhas. `ruff check` e `black --check --fast` limpos.

### Riscos conhecidos
- A causa raiz de EUA/Criptomoedas/Renda Fixa navegarem sem erro mas voltarem vazias **não foi confirmada** neste ambiente (sem acesso a Playwright/rede ao vivo) — a instrumentação (`navigation_detail`) e o retry deixam mais diagnóstico disponível no próximo dry-run real, mas podem não resolver sozinhos se a causa for, por exemplo, um clique adicional/seleção de carteira ainda não identificado.
- Linhas antigas em `income_events` com `source` de agregado mensal continuam lá, sem sinalização especial — uma decisão futura de limpeza/migração fica pendente (explicitamente adiada pelo usuário).

## [1.17.0] - Sprint 24 (Fase 1) — Correção da moeda de BTC-USD (USD, não BRL)

### Contexto
Depois do primeiro `replace` real bem-sucedido (27 posições, incluindo Brasil/EUA/FIIs/ETFs/REITs/BTC/Tesouro), o usuário conferiu a conta do BTC-USD extraído: quantidade `0.00584925` × preço atual `63121.45` ≈ `369`, batendo com `current_value` só se preço/valor forem tratados como **USD**. Tratar esses mesmos números como BRL (decisão da Sprint 23.2) subavaliava a posição de BTC em ~5x no patrimônio consolidado, porque `to_brl()` (`dashboard_view_service.py`) só multiplica pelo câmbio quando `currency == "USD"` — com `currency="BRL"`, o valor passava direto sem conversão.

### Corrigido — `_normalize_crypto` (`parser.py`)
- `currency` de qualquer par de cripto (`BTC-USD`, e qualquer outro `"XXX-USD"`) passa a ser **`"USD"`**, nunca mais `"BRL"`. O símbolo visual "R$" mostrado na tela "Criptomoedas → Extrato" do Dividendos.me **nunca** deve ser usado como fonte de verdade para a moeda de um ativo cripto — a moeda é inferida pelo próprio ticker/natureza do ativo (par `-USD` do Yahoo Finance, fonte de preço da LG INVEST), do mesmo jeito que já funciona para ações/ETFs/REITs dos EUA.
- Nenhuma outra camada precisou de mudança: `service.py` (`_apply_sync`, `_consolidate_positions`, `_apply_btc_fallback`) só propaga o `currency` recebido, sem nunca fazer conversão cambial; `dashboard_view_service.to_brl()` já converte corretamente qualquer posição com `currency == "USD"` (mesma lógica já usada para VOO/ações americanas) — a correção do parser propaga sozinha até o patrimônio consolidado, a tabela de posições (`components/tables.py`, coluna "Moeda") e os agrupamentos Brasil/Exterior (`carteira.py`, `allocation_charts.py`, `dashboard.py`).

### Testes
- `test_dividendos_me_parser.py`: `test_normalize_btc_becomes_btc_usd` e `test_normalize_unknown_crypto_flags_review` agora exigem `currency == "USD"`.
- `test_dividendos_me_client.py`: `test_card_to_extracted_position_crypto` e `test_card_to_extracted_position_crypto_real_card_from_extrato_screen` corrigidos para `currency == "USD"` (o teste antigo esperava `"BRL"` — estava testando o comportamento errado).
- `test_dividendos_me_service.py`: fixtures de `Asset`/`Position`/`_extracted` para BTC-USD trocadas de `currency="BRL"` para `"USD"` (consistente com o restante da suíte, que já usava `"USD"` nos testes de `_apply_btc_fallback`).
- Novo em `test_dashboard_view_service.py`: `test_btc_usd_converted_to_brl_using_exchange_rate` (conversão pelo câmbio configurado, igual a qualquer ativo USD), `test_btc_not_undervalued_as_if_already_in_brl` (regressão-alvo: garante que o total convertido não fica ~5x menor como acontecia antes), `test_btc_currency_exposure_counts_as_usd` (BTC conta como exposição USD, não BRL, no gráfico Brasil vs. Exterior).
- Corrigido de passagem: `test_fetch_income_monthly_summaries_requires_playwright` (`test_dividendos_me_client.py`) tinha uma chamada de método incompleta (`client.fetch_income_monthly` em vez de `client.fetch_income_monthly_summaries()`) que nunca chegou a ser exercitada corretamente antes desta verificação — corrigida.
- Suíte completa: **652 testes passando**, 0 falhas. `ruff check` e `black --check --fast` limpos.

### Riscos conhecidos
- Só `BTC-USD` foi confirmado ao vivo pelo usuário; qualquer outra criptomoeda (par `"XXX-USD"`) segue a mesma regra de moeda USD mas continua marcada `review_required=True` até ser validada contra a fonte real (comportamento herdado, sem mudança nesta correção).

## [1.18.0] - Sprint 24 (Fase 2) — Confirmação da Fonte A de proventos, investigação da Fonte B e placeholder na UI

### Contexto
Continuação da Sprint 24: revisão da extração de histórico mensal de proventos (Fonte A, já implementada na Sprint 23.3) contra dados reais informados pelo usuário, e investigação de uma segunda fonte possível — "Renda Variável → Brasil → Gráficos → Dividendos por Ativo" (Fonte B) — para detalhamento de proventos por ativo/mês.

### Confirmado — Fonte A (Central de Proventos → Análise) já implementada corretamente
- Revisão contra os dados reais fornecidos pelo usuário (ano 2026 mês a mês, e totais anuais de 2021 a 2025) confirmou que `parse_monthly_summary` (`income_parser.py`), a tabela `income_monthly_summaries` e o fluxo `IncomeSyncService.build_monthly_preview`/`dry_run_monthly`/`import_monthly_summaries` já implementam exatamente essa fonte: tabela ano × mês por carteira (`"Carteira (B3)"`/`"Carteira Dolar"`), `TOTAL`/`MÉDIA` lidos direto da tabela (nunca recalculados), status `recebido`/`anunciado` por comparação de data real, dedup por `portfolio_id+wallet_name+year+month+currency+source`. Nenhuma mudança de código foi necessária nesta fonte — só testes de regressão novos com os números reais do usuário.
- Novos testes com dados reais: `test_parse_monthly_summary_matches_real_2026_data_reported_by_user` (2026 mês a mês) e `test_parse_monthly_summary_multi_year_matches_real_totals_reported_by_user` (totais/médias anuais de 2021-2025), em `test_dividendos_me_income_parser.py`.

### Investigado — Fonte B (Dividendos por Ativo) — não implementada, limitação documentada
- A tela `/dividendos-por-ativo?country=1` mostra os dados dentro de um gráfico de barras empilhado (não uma tabela HTML simples como as outras fontes) — extrair isso de forma confiável exigiria inspecionar ao vivo (DevTools/aba Network/estrutura interna do gráfico) qual mecanismo alimenta o componente, o que não foi possível confirmar neste ambiente (sem acesso a Playwright/rede ao vivo).
- Seguindo a regra de nunca inventar dado: esta fonte NÃO foi implementada nesta sprint. Documentada em `docs/DIVIDENDOS_ME_INCOME_SOURCES.md`, incluindo o desenho já rascunhado de uma futura tabela `income_monthly_by_asset` (dedup `portfolio_id+wallet_name+year+month+ticker+currency+source`, `source="dividendos_me:income_monthly_by_asset"`) para quando a extração puder ser validada contra a página real.

### Adicionado — UI
- Nova seção **"5C. Proventos — Por ativo/mês"** na tela "Sincronizar Dividendos.me" (`sincronizar_dividendos_me.py`), entre o histórico mensal (5A) e o calendário futuro (5B), mostrando a mensagem "Fonte detectada, extração ainda não disponível" com o motivo e um link para a documentação — nunca esconde a limitação nem finge que a extração existe.

### Documentação
- Novo `docs/DIVIDENDOS_ME_INCOME_SOURCES.md`: descreve as três fontes (A implementada, B não implementada/limitação documentada, C implementada), por que nunca se misturam, e o schema rascunhado da Fonte B para uma implementação futura.

### Testes
- Suíte completa: **654 testes passando**, 0 falhas. `ruff check` e `black --check --fast` limpos.

### Riscos conhecidos
- Fonte B (Dividendos por Ativo) continua sem extração — qualquer renda por ativo/mês só pode vir, por enquanto, do agregado mensal por carteira (Fonte A) ou do calendário futuro por ativo (Fonte C), nunca de um detalhamento histórico por ativo.

## [1.24.0] - Sprint 24 (Fase 8) — Portfolio Health Score

### Contexto
Oitava fase da evolução da LG INVEST de dashboard para Investment Decision System: o "capstone" que resume, num único score (0..100, maior = mais saudável), 5 sinais já produzidos pelas engines/serviços das fases anteriores — sem recalcular a lógica de nenhuma delas. Responde "minha carteira está mais ou menos saudável do que antes?" com um número acompanhável ao longo do tempo, sempre com o breakdown por pilar visível.

### Adicionado — Engine
- `engines/portfolio_health/inputs.py`: `AllocationAlignmentInput`, `PortfolioHealthInput`, `PortfolioHealthConfig` (pesos dos 5 pilares, somam 1.0) — `@dataclass(frozen=True)`, sem importar nenhuma engine/serviço alheio.
- `engines/portfolio_health/thresholds.py`: bandas de diversificação, alinhamento de risco, tendência de renda, e classificação final (`HEALTH_LABELS`: crítica/atenção/boa/excelente — direção oposta a `RISK_TOLERANCES`, aqui mais alto é melhor).
- `engines/portfolio_health/engine.py`: `evaluate_portfolio_health()` (pura, `MODEL_VERSION = "portfolio_health_v1"`) — combina 5 pilares: diversificação (Portfolio Engine), alinhamento de risco (Portfolio Risk Engine + Investment Policy), aderência à alocação-alvo (Target Allocation Rule Engine v2), tendência de renda (Income Engine) e confiança dos dados (Data Quality Layer).
- Pilares ausentes (sem regra de alocação configurada, sem histórico de renda, sem Investment Policy) nunca são inventados: ficam `available=False`, documentados em `warnings`, e os pesos dos pilares restantes são renormalizados — mesmo padrão já validado no Portfolio Risk Engine (Fase 6). Se nenhum pilar estiver disponível, o resultado é `"indeterminado"`, nunca um valor fabricado.

### Adicionado — Serviço
- `services/portfolio_health_service.py`: `build_input(portfolio_id)` compõe `PortfolioService`, `PortfolioRiskService` (Fase 6), `TargetAllocationService.evaluate_portfolio_rules` (Fase 3), `IncomeAnalysisService` (Fase 7) e `DataQualityService` (Sprint 21); `evaluate(...)` monta os inputs e chama a engine pura. Não persiste nada.
- `schemas/portfolio_health.py`: `HealthFactorView`, `PortfolioHealthResultView` (Pydantic v2).

### Documentação
- Novo `docs/PORTFOLIO_HEALTH_SCORE.md`.

### Testes
- Novo `test_portfolio_health_engine.py` (12 testes): todos os pilares disponíveis, efeito de diversificação/risco/renda maiores ou menores, pilares ausentes renormalizando pesos, todos os pilares indisponíveis, classificação sempre em uma das 4 faixas.
- Novo `test_portfolio_health_service.py` (3 testes): wiring com carteira real (composição dos 5 serviços), execução ponta a ponta, carteira vazia sem erro.
- Suíte completa: **781 testes passando**, 0 falhas. `ruff check` e `black --check --fast` limpos.

### Riscos conhecidos
- Nenhuma migration nova nesta fase — sem ação de banco pendente.
- Nenhuma tela ainda exibe o score — a exposição visual fica para a Fase 9, mesma decisão já registrada para as engines das fases anteriores.

## [1.23.0] - Sprint 24 (Fase 7) — Income Engine

### Contexto
Sétima fase da evolução da LG INVEST de dashboard para Investment Decision System: a primeira camada de análise sobre os proventos já coletados pela integração Dividendos.me (Sprint 23), até então apenas dado bruto de sincronização. Responde "minha renda está crescendo?", "de quais ativos ela vem?" e "qual é o yield sobre o que eu efetivamente paguei?" (yield on cost) — métrica central para quem segue Buy and Hold de longuíssimo prazo.

### Adicionado — Engine
- `engines/income/inputs.py`: `MonthlyIncomeTotal`, `TickerIncomeEvent`, `IncomeEngineInput`, `IncomeConfig` (`months_lookback=24`) — `@dataclass(frozen=True)`.
- `engines/income/engine.py`: `analyze_income()` (pura, `MODEL_VERSION = "income_v1"`) — produz duas análises deliberadamente separadas e nunca somadas entre si (uma fonte é agregada por carteira, a outra é granular por ativo, e somá-las arriscaria contar o mesmo provento duas vezes):
  - `PortfolioIncomeTrend` (fonte: `income_monthly_summaries`): renda dos últimos 12 meses (TTM), comparação com os 12 meses anteriores (crescimento de renda, `None` quando não há base de comparação), série mensal para visualizar consistência, e uma projeção simples (naive) dos próximos 12 meses, sempre rotulada como não sendo garantia de recebimento futuro.
  - `TickerIncomeBreakdown` (fonte: `income_events`): renda dos últimos 12 meses por ativo, *yield on cost* (renda / custo de aquisição — nunca sobre o preço de mercado atual) e concentração de renda entre ativos (HHI). Eventos sem posição correspondente na carteira atual são excluídos do yield on cost mas contam na concentração.
- Nenhum dado ausente é inventado: sem período anterior suficiente → `growth_pct=None`; sem histórico → projeção zerada; sem custo de aquisição conhecido → `yield_on_cost=None`. Tudo documentado em `warnings`.

### Adicionado — Serviço
- `services/income_analysis_service.py`: `build_input(portfolio_id, reference_date=None)` lê `IncomeMonthlySummaryRepository`/`IncomeEventRepository`, converte tudo para BRL (mesma conversão do Dashboard/Decision Engine 3.0/Simulation Engine) e resolve custo de aquisição via `PortfolioService`; `evaluate(...)` monta os inputs e chama a engine pura. Não persiste nada.
- `schemas/income_analysis.py`: `MonthlyPointView`, `PortfolioIncomeTrendView`, `TickerIncomeRowView`, `TickerIncomeBreakdownView`, `IncomeAnalysisResultView` (Pydantic v2).

### Documentação
- Novo `docs/INCOME_ENGINE.md`.

### Testes
- Novo `test_income_engine.py` (12 testes): TTM/período anterior, crescimento de renda, projeção naive, janela de série mensal, yield on cost, exclusão de tickers sem posição, concentração, as duas fontes nunca somadas.
- Novo `test_income_analysis_service.py` (3 testes): wiring com carteira real (conversão para BRL, custo de aquisição), execução ponta a ponta, carteira vazia sem erro.
- Suíte completa: **751 testes passando**, 0 falhas. `ruff check` e `black --check --fast` limpos.

### Riscos conhecidos
- Nenhuma migration nova nesta fase — sem ação de banco pendente.
- Nenhuma tela ainda exibe a análise de renda — a exposição visual fica para a Fase 9, mesma decisão já registrada para as engines das fases anteriores.
- `TickerIncomeBreakdown` depende inteiramente do calendário de eventos por ativo (Fonte C, `income_events`), que pode não cobrir o histórico completo de todos os pagamentos passados — a extração de renda por ativo/mês (Fonte B) continua sem implementação, limitação já documentada em `docs/DIVIDENDOS_ME_INCOME_SOURCES.md`.

## [1.22.0] - Sprint 24 (Fase 6) — Portfolio Risk Engine ("Risk Engine 2.0")

### Contexto
Sexta fase da evolução da LG INVEST de dashboard para Investment Decision System: uma segunda engine de risco, nova e complementar ao Risk Engine v1 (Sprint 16, que classifica risco por ativo individual). O Portfolio Risk Engine agrega risco no nível da carteira inteira em um score composto (0..100), classificado nas mesmas 4 faixas de `RISK_TOLERANCES` da Investment Policy — permitindo comparar o risco medido com a tolerância declarada pelo usuário. "2.0" é o nome da fase (segunda geração de risco na plataforma), não uma versão que substitui o v1: os dois convivem.

### Adicionado — Engine
- `engines/portfolio_risk/inputs.py`: `AssetRiskSignal`, `PortfolioRiskInput`, `PortfolioRiskConfig` (pesos dos 4 fatores, somam 1.0) — `@dataclass(frozen=True)`.
- `engines/portfolio_risk/thresholds.py`: bandas de volatilidade, concentração (HHI), risco estrutural por ativo e risco de cauda, além do mapeamento do score composto para as 4 faixas de `RISK_TOLERANCES`.
- `engines/portfolio_risk/engine.py`: `evaluate_portfolio_risk()` (pura, `MODEL_VERSION = "portfolio_risk_v1"`) — combina 4 fatores: volatilidade ponderada (mesmas premissas do Simulation Engine, Fase 5), concentração (HHI já calculado pelo Portfolio Engine), risco estrutural por ativo (reaproveita as classificações do Risk Engine v1, nunca recalcula) e risco de cauda (probabilidade de perda de uma simulação Monte Carlo, opcional).
- Fatores ausentes (sem volatilidade configurada, sem classificação de risco disponível, sem simulação rodada) nunca são inventados: ficam `available=False`, documentados em `warnings`, e os pesos dos fatores restantes são renormalizados entre si.
- `tolerance_alert`: mensagem informativa (nunca uma recomendação de compra/venda) quando o risco medido diverge da tolerância declarada na Investment Policy.

### Adicionado — Serviço
- `services/portfolio_risk_service.py`: `build_input(portfolio_id, probability_of_loss=None)` resolve concentração/número efetivo de ativos (`PortfolioService`), pesos por classe e exposição internacional (`build_dashboard_view`), volatilidade por classe (`simulation_assumptions_service`, mesma fonte da Fase 5), classificação de risco por ativo (`RiskService`, Risk Engine v1) e tolerância declarada (`InvestmentPolicyService`); `evaluate(...)` monta os inputs e chama a engine pura. Não persiste nada — relatório sob demanda.
- `schemas/portfolio_risk.py`: `RiskFactorView`, `PortfolioRiskResultView` (Pydantic v2).

### Documentação
- Novo `docs/PORTFOLIO_RISK_ENGINE.md`.

### Testes
- Novo `test_portfolio_risk_engine.py` (12 testes): todos os fatores disponíveis, efeito de volatilidade/concentração maiores, fatores ausentes renormalizando pesos, sinais indeterminados excluídos, alerta de tolerância em ambas as direções, classificação sempre em uma das 4 faixas.
- Novo `test_portfolio_risk_service.py` (5 testes): wiring com carteira real (pesos, concentração, sinais de risco por ativo), classificação de política para cripto reaproveitada do Risk Engine v1, tolerância default da Investment Policy, execução com e sem risco de cauda.
- Suíte completa: **736 testes passando**, 0 falhas. `ruff check` e `black --check --fast` limpos.

### Riscos conhecidos
- Nenhuma migration nova nesta fase — sem ação de banco pendente.
- Nenhuma tela ainda exibe o resultado — a exposição visual fica para a Fase 9 (Dashboard 2.0), mesma decisão já registrada para as engines das fases anteriores.
- Não há orquestração automática que rode o Monte Carlo Simulation Engine e alimente `probability_of_loss` neste serviço — isso fica a cargo de quem chamar (ex.: uma futura tela que rode os dois em sequência).

## [1.21.0] - Sprint 24 (Fase 5) — Monte Carlo Simulation Engine

### Contexto
Quinta fase da evolução da LG INVEST de dashboard para Investment Decision System: uma ferramenta de projeção probabilística de longo prazo (Monte Carlo), respondendo "para onde minha carteira pode ir" dado o valor atual, um aporte mensal presumido e um horizonte em anos — sempre como uma faixa de cenários possíveis (percentis), nunca como um número único "previsto", e sempre explicitamente rotulada como não sendo previsão de mercado nem recomendação financeira.

### Adicionado — Engine
- `engines/simulation/inputs.py`: `ClassAssumption` (retorno esperado e volatilidade anual por classe, com `source` sempre exposto), `SimulationInput` (valor atual, aporte mensal, horizonte, pesos e premissas por classe) e `SimulationConfig` (`num_simulations`, `random_seed`, `percentiles`) — todos `@dataclass(frozen=True)`.
- `engines/simulation/engine.py`: `run_simulation()` (pura, `MODEL_VERSION = "simulation_v1"`) — roda `num_simulations` trajetórias independentes (retornos anuais normais por classe, sem correlação entre classes, aporte aplicado ao final de cada ano, composição fixa ao longo do horizonte) e resume em percentis (p10/p25/p50/p75/p90), mediana e `probability_of_loss` (fração de trajetórias abaixo do total efetivamente aportado).
- Toda simplificação do modelo (sem correlação entre classes, piso de retorno anual de -95%, aporte anualizado, sem rebalanceamento simulado, classes sem premissa tratadas como retorno 0%) é documentada explicitamente em `reasons`/`warnings` do resultado, nunca escondida.

### Adicionado — Premissas de retorno/volatilidade
- `services/simulation_assumptions_service.py`: uma premissa (retorno esperado + volatilidade anual) por classe de ativo (`ASSET_CLASSES`), com defaults didáticos de longo prazo documentados em `docs/SIMULATION_ENGINE.md` — nunca dados históricos reais coletados, sempre editáveis. Persistência em `data/app_settings.json` (chave `simulation_assumptions`), mesmo padrão de `fx_settings_service.py`, sem migration nova.
- `get_all_assumptions`/`get_assumption`/`set_assumption`/`reset_assumption`/`reset_all_assumptions`, com validação de classe conhecida e volatilidade não-negativa.

### Adicionado — Serviço
- `services/simulation_service.py`: `build_input(portfolio_id, monthly_contribution, horizon_years)` resolve valor atual e pesos por classe via `build_dashboard_view` (com conversão de câmbio); `run_portfolio_simulation(...)` monta o input e chama a engine pura. Não persiste nada — projeção sob demanda, como `TargetAllocationService.evaluate_portfolio_rules`.
- `schemas/simulation.py`: `ClassAssumptionView`, `SimulationAssumptionsView`, `SimulationAssumptionUpdate`, `SimulationResultView` (Pydantic v2).

### Documentação
- Novo `docs/SIMULATION_ENGINE.md`.

### Testes
- Novo `test_simulation_engine.py` (10 testes): percentis ordenados, determinismo com seed fixo, equivalência analítica com volatilidade zero, efeito de aporte/horizonte maiores, horizonte zerado, classe sem premissa configurada, total aportado, disclaimers presentes.
- Novo `test_simulation_assumptions_service.py` (7 testes): defaults para todas as classes, persistência de override, validações, reset individual/completo, isolamento entre classes.
- Novo `test_simulation_service.py` (4 testes): wiring com carteira real (pesos e valor corretos), uso de premissas customizadas, execução ponta a ponta, carteira vazia.
- Suíte completa: **719 testes passando**, 0 falhas. `ruff check` e `black --check --fast` limpos.

### Riscos conhecidos
- Nenhuma migration nova nesta fase (premissas guardadas em JSON, sem nova tabela) — sem ação de banco pendente.
- Nenhuma tela ainda exibe a simulação — a exposição visual fica para a Fase 9 (Dashboard 2.0), mesma decisão já registrada para o Target Allocation Rule Engine v2 e o Decision Engine 3.0.
- O modelo não correlaciona retornos entre classes de ativo (ex.: uma queda simultânea de ações BR e US em uma crise global não é capturada) — limitação documentada tanto no código quanto em `docs/SIMULATION_ENGINE.md`.

## [1.20.0] - Sprint 24 (Fase 4) — Decision Engine 3.0

### Contexto
Quarta fase da evolução da LG INVEST de dashboard para Investment Decision System: uma terceira versão do Decision Engine, combinando fundamentos, alocação-alvo multi-dimensão, concentração e exposição internacional em um único score, além de passar a respeitar os bloqueios da Investment Policy e do Target Allocation Rule Engine v2 (Fase 3). `recommend()` (v1) e `recommend_v2()` não foram alterados nem removidos — tudo aditivo.

### Adicionado — Engine
- `compute_buy_score_v3()` (`engines/decision/scoring.py`): score multi-fator — fundamentos (40%), bônus de alocação-alvo (25%), concentração invertida (20%), bônus de internacionalização (15%), escalado ao final pela confiança do dado (`score = raw * confidence`).
- Fundamentos com cadeia de fallback em 3 níveis, sempre registrada em `reasons`: pilares individuais (`quality_score`/`valuation_score`/`growth_score`/`risk_score`) → `conviction_score` (LG Conviction Score v2) → `lg_score`. Nunca inventa um valor ausente.
- Bônus de alocação-alvo lê `AllocationRuleSignal` (espelho pontual de uma avaliação do Target Allocation Rule Engine v2, resolvido pelo serviço, nunca pela engine): só sinais `underweight` contribuem, com prioridade saturada em 20 pontos antes de normalizar.
- Bônus de internacionalização: zero para ativos nacionais, zero sem meta configurada (`policy.target_international_min`), e só se aplica quando o agregado internacional da carteira ainda está abaixo da meta.
- `filter_eligible_v3()` (`engines/decision/eligibility.py`): mantém o filtro v1 (bloqueio manual + sobreconcentração) e acrescenta bloqueio por peso máximo por ativo, por classe agregada (`crypto`/`fii` acima do limite da política) e por qualquer `AllocationRuleSignal` com `gap_status == "blocked"`.
- `recommend_v3()` (`engines/decision/engine.py`), com `MODEL_VERSION_V3 = "decision_v3"` para auditoria — convive com `recommend()`/`recommend_v2()` sem sobrescrever recomendações anteriores.
- Novas dataclasses puras em `engines/decision/inputs.py`: `AllocationRuleSignal`, `PolicyLimits`, `PortfolioAggregates` — espelham `InvestmentPolicy`/agregados de carteira sem importar ORM ou schemas de dashboard, preservando a regra de engines puras.

### Adicionado — Serviço
- `DecisionService.build_inputs_v3(portfolio_id)`: monta os candidatos combinando `PortfolioService`, `LGScoreService`, `ConvictionScoreService` (pilares direto de `ConvictionScoreResult`) e `TargetAllocationService.evaluate_portfolio_rules()`.
- `DecisionService._policy_limits_and_aggregates(portfolio_id)`: resolve os limites via `InvestmentPolicyService.get_or_create()` e agrega pesos por classe/país via `build_dashboard_view()`.
- `DecisionService.recommend_v3(portfolio_id, amount, ...)`: orquestra os dois métodos acima e persiste o resultado sob `MODEL_VERSION_V3`.

### Regra de ouro: nunca recomendar venda
Reforçada em toda a Fase 4, com testes dedicados: todo bloqueio (por ativo, por classe agregada ou por sinal de regra) impede apenas um novo aporte nesta rodada. Nenhum caminho de código gera, sugere ou aciona uma recomendação de venda — mensagens de bloqueio dizem explicitamente "não é recomendação de venda" / "Nenhuma venda é recomendada — apenas pausa de aporte", e os testes verificam que a palavra "vender" nunca aparece em `explanation`, `alerts` ou nos motivos de `ignored`.

### Documentação
- Novo `docs/DECISION_ENGINE_3.md`.

### Testes
- Novo `test_decision_engine_v3.py` (21 testes): fallback de fundamentos, bônus de alocação-alvo multi-dimensão, bônus de internacionalização, escala por confiança, bloqueio por política/classe/sinal de regra, regra de nunca recomendar venda.
- Novo `test_decision_service_v3.py` (8 testes): montagem de inputs a partir do banco, marcação correta de internacionalização, sinais de regra anexados só quando há regras configuradas, agregados de política, bloqueio de cripto acima do limite, totais respeitando o valor de aporte, nunca mencionar venda.
- Suíte completa: **712 testes passando**, 0 falhas. `ruff check` e `black --check --fast` limpos.

### Riscos conhecidos
- Mesmo risco herdado da Fase 3: o banco de desenvolvimento real (`data/lg_invest.db`) não pôde ser lido no ambiente de sandbox usado nesta sessão. Nenhuma migration nova foi criada nesta fase (Decision Engine 3.0 não requer mudança de schema), então não há ação de migration pendente para esta fase especificamente.
- Nenhuma tela ainda exibe o resultado de `recommend_v3()` — a exposição visual fica para a Fase 9 (Dashboard 2.0), mesma decisão já registrada para o Target Allocation Rule Engine v2.

## [1.19.0] - Sprint 24 (Fase 3) — Investment Policy e Target Allocation Engine v2

### Contexto
Terceira fase da evolução da LG INVEST de dashboard para Investment Decision System: criação da fundação de configuração explícita (Investment Policy) e da segunda versão do Target Allocation Engine, cobrindo 4 dimensões independentes (classe, moeda, país, ativo) em vez de só classe. Nenhuma engine ou tela existente foi alterada de forma destrutiva — tudo aditivo.

### Adicionado — Investment Policy
- Nova tabela `investment_policy` (uma linha por carteira): perfil do investidor, horizonte, moeda base, tolerância a risco, limites (`max_asset_weight`, `max_crypto_weight`, `target_international_min/max`, `target_fii_max`), metas de referência informativas por classe/mercado, `rebalance_threshold`, `monthly_contribution_default` e `notes`.
- `InvestmentPolicyRepository` (get/create/update) e `InvestmentPolicyService` (`get_or_create`, `update` com `exclude_unset` para edição parcial).
- Defaults de primeira leitura coerentes com o perfil descrito pelo usuário (investidor jovem, horizonte 50+ anos, Buy and Hold, tolerância moderada/alta, internacionalização crescente, FIIs úteis mas não centrais, BTC pequeno) — sempre editáveis, nunca uma recomendação financeira (aviso explícito em `notes` e na UI).
- Schemas `InvestmentPolicyView`/`InvestmentPolicyUpdate` (Pydantic v2).

### Adicionado — Target Allocation Engine v2
- Nova tabela `target_allocation_rules`: meta granular por dimensão (`class`/`currency`/`country`/`asset`), com peso mínimo/alvo/máximo e prioridade manual de aporte. Índice único por `(portfolio_id, dimension_type, dimension_key)`. Começa vazia — nenhuma regra é pré-cadastrada com valor inventado.
- `TargetAllocationRuleEngine` (pura, nova classe em `engines/target_allocation/engine.py`, convivendo sem alterar `TargetAllocationEngine` v1): calcula `gap_status` (`underweight`/`neutral`/`overweight`/`blocked`), `contribution_priority`, `rebalance_required`, `extreme_overweight` (peso > 1.5x o máximo) e `alert_message` por regra.
- Regra de segurança reforçada por teste: `overweight`/`blocked` nunca têm `contribution_priority` > 0, e a mensagem de `overweight` usa explicitamente "não vender" — mesmo em desvio extremo, a engine só torna o alerta mais forte, nunca gera uma recomendação de venda automática.
- `TargetAllocationRuleRepository` (list/get/upsert/delete) e `TargetAllocationRuleService` (`list_rules`, `set_rule` com validação de dimensão/pesos negativos/min<=max/target<=max, `delete_rule`).
- `TargetAllocationService.evaluate_portfolio_rules(portfolio_id)` (novo, ao lado do `evaluate_portfolio()` v1 inalterado): calcula pesos atuais por dimensão via `build_dashboard_view()` + `AssetRepository` e avalia contra as regras salvas.

### Adicionado — UI (Configurações)
- Nova seção "Política de investimento": visualiza e edita todos os campos de `InvestmentPolicy`, com aviso permanente de que não é recomendação financeira.
- Nova seção "Alocação-alvo detalhada (classe / moeda / país / ativo)": lista regras existentes em tabela, formulário para adicionar/editar (upsert) e remover regra por dimensão/chave.

### Migration
- `f1993c6433b8_create_investment_policy_and_target_allocation_rules` — cria as duas tabelas novas, puramente aditiva (`downgrade()` completo). Testada nesta sessão com `alembic upgrade head` → `downgrade -1` → `upgrade head` novamente contra um banco SQLite descartável (não o banco de desenvolvimento real, que apresentou corrupção de leitura no ambiente de sandbox usado nesta sessão — ver Riscos conhecidos).

### Documentação
- Novo `docs/INVESTMENT_POLICY.md` e novo `docs/TARGET_ALLOCATION_ENGINE.md`.

### Testes
- Novo `test_target_allocation_rule_engine.py` (11 testes): status por dimensão, prioridade de aporte, `rebalance_required`, regra de nunca recomendar venda, independência entre dimensões.
- Novo `test_investment_policy_service.py` (6 testes): defaults na primeira leitura, persistência real em banco, não duplicação, atualização parcial.
- Novo `test_target_allocation_rule_service.py` (12 testes): validações de dimensão/chave/pesos, upsert sem duplicar, delete, independência entre dimensões com a mesma chave.
- Suíte completa: **683 testes passando**, 0 falhas. `ruff check` e `black --check --fast` limpos.

### Riscos conhecidos
- O banco de desenvolvimento real (`data/lg_invest.db`) não pôde ser lido neste ambiente de sandbox nesta sessão (`sqlite3.DatabaseError: database disk image is malformed` ao tentar `alembic current`/`upgrade` contra ele) — por segurança, a migration **não foi executada contra ele**. A migration foi validada de ponta a ponta (upgrade/downgrade/upgrade) contra um banco SQLite descartável criado do zero, incluindo toda a cadeia de migrations anteriores. **Ação necessária do usuário**: rodar `alembic upgrade head` localmente, no ambiente Windows onde o banco real está íntegro, antes de usar as novas telas de Configurações.
- Nenhuma tela ainda exibe o resultado de `evaluate_portfolio_rules()` (gaps, prioridades, alertas) — só o cadastro de regras existe nesta fase. A visualização fica para a Fase 9 ou antes, se o Decision Engine 3.0 precisar dela.
- Os campos de `investment_policy` (ex.: `target_brazil_equity`) não são copiados automaticamente para `target_allocation_rules` — são conceitualmente separados por decisão desta sprint (ver `docs/TARGET_ALLOCATION_ENGINE.md`).

## [1.25.0] - Sprint 24 (Fase 9) — Dashboard 2.0: exposição visual das 5 engines das Fases 4-8

### Contexto
Nona fase da evolução da LG INVEST de dashboard para Investment Decision System: nenhuma engine nova — o trabalho foi só de UI, expondo nas telas Streamlit os cinco motores construídos e testados nas Fases 4 a 8 (Decision Engine 3.0, Monte Carlo Simulation Engine, Portfolio Risk Engine, Income Engine, Portfolio Health Score), que até aqui só existiam como serviço/engine testados por trás.

### Adicionado — Tela nova: Simulação
- `pages_impl/simulacao.py` (nova tela, registrada em `app.py` e no smoke test): formulário de aporte mensal presumido, horizonte em anos, número de simulações e semente fixa opcional (resultado reproduzível); chama `SimulationService.run_portfolio_simulation`.
- `charts/simulation_charts.py`: `chart_simulation_percentiles()` — gráfico de faixa horizontal mostrando p10–p90 (faixa clara), p25–p75 (faixa destacada) e a mediana marcada, já que a engine devolve só os percentis do valor final, não uma trajetória ano a ano.
- Métricas (valor inicial, total aportado no horizonte, mediana projetada, probabilidade de perda), tabela de percentis, premissas/simplificações usadas e avisos da engine, sempre com o aviso de que é uma projeção probabilística, não uma previsão real de mercado nem recomendação financeira.

### Adicionado — Dashboard: Saúde da Carteira e Risco da Carteira
- Nova seção "Saúde da Carteira" (`PortfolioHealthService`, Fase 8): badge de classificação + score, métrica por pilar disponível, detalhamento por pilar (nota ou "indisponível" + motivo) num expander, avisos da engine.
- Nova seção "Risco da Carteira" (`PortfolioRiskService`, Fase 6): badge de classificação, tolerância declarada, alerta quando o risco medido diverge da tolerância, métrica por fator disponível, detalhamento por fator num expander.
- Ambas posicionadas entre "Visão Geral" e "Oportunidades & Riscos", sempre deixando claro que são relatórios informativos — nunca uma recomendação de compra ou venda.

### Adicionado — Inteligência: Renda de Proventos
- Nova seção "Renda de Proventos" (`IncomeAnalysisService`, Fase 7): renda dos últimos 12 meses, crescimento vs. período anterior, projeção para os próximos 12 meses, e tabela de yield on cost por ativo (custo de aquisição, não preço de mercado atual) com o yield on cost agregado da carteira quando calculável. Tendência (fonte agregada por carteira) e breakdown por ativo (fonte granular) permanecem explicitamente separados, nunca somados entre si.

### Adicionado — Aporte: seletor de motor v1/v2/v3
- `st.radio` "Motor de recomendação" substitui o antigo checkbox `use_v2`, agora com três opções (v1/v2/v3) e texto de ajuda explicando a diferença de cada uma. `recommend_v3()` (Decision Engine 3.0, Fase 4) passa a ser chamável direto da tela, reaproveitando a mesma tabela de distribuição/justificativa por ativo já usada para v1/v2 — o schema `RecommendationItem` já expunha `conviction_score`/`item_confidence` para v3 sem mudança de schema. Texto de ajuda reitera que nenhuma versão jamais recomenda venda, apenas pausa aporte.

### Adicionado — Configurações: premissas do Monte Carlo
- Nova seção "Premissas do Monte Carlo (retorno e volatilidade por classe)": tabela com a premissa atual de cada classe, e um expander para editar/resetar por classe individual, reaproveitando `simulation_assumptions_service` (Fase 5) — a mesma fonte usada pela tela Simulação e pelo fator de volatilidade do Portfolio Risk Engine.

### Documentação
- Atualizadas as seções "O que ainda não existe" de `docs/DECISION_ENGINE_3.md`, `docs/SIMULATION_ENGINE.md`, `docs/PORTFOLIO_RISK_ENGINE.md`, `docs/INCOME_ENGINE.md` e `docs/PORTFOLIO_HEALTH_SCORE.md`, que diziam "a exposição visual fica para a Fase 9" — agora descrevem onde cada resultado aparece na UI e o que de fato ainda falta (histórico ao longo do tempo, trajetória ano a ano, orquestração automática entre engines).

### Testes
- `test_streamlit_smoke.py`: `simulacao` adicionado a `PAGE_MODULES`.
- Nenhuma lógica nova de engine/serviço nesta fase — os testes das Fases 4-8 continuam cobrindo o cálculo; a UI em si segue a convenção do projeto de não ter teste unitário dedicado além do smoke de import.
- Suíte completa: **795 testes passando**, 0 falhas. `ruff check` e `black --check --fast` limpos.

### Riscos conhecidos
- Nenhuma migration nova nesta fase — sem ação de banco pendente.
- O Dashboard agora chama `PortfolioHealthService.evaluate()` e `PortfolioRiskService.evaluate()` (que por sua vez compõem várias outras engines/serviços) a cada carregamento de página, sem cache — aceitável para o MVP, mas candidato natural de otimização na Fase 10 (Performance/cache).
- `PortfolioRiskService.evaluate()` é chamado no Dashboard sem `probability_of_loss` (que viria do Monte Carlo Simulation Engine) — o fator de risco de cauda aparece como indisponível até o usuário rodar a tela Simulação manualmente; não há, ainda, orquestração automática entre as duas engines.

## [1.26.0] - Sprint 24 (Fase 10) — Cache, testes finais e consolidação do Investment Decision System

### Contexto
Décima e última fase do plano de 10 fases da Sprint 24: cache básico para as leituras mais caras introduzidas na Fase 9, verificação final da suíte inteira e um documento de consolidação amarrando as 10 fases — do "dashboard bonito" ao Investment Decision System pedido no início da sprint.

### Adicionado — Cache
- Novo `frontend/streamlit_app/cache.py`: `cached_dashboard_bundle(portfolio_id, exchange_rate)` (substitui as 6 chamadas de serviço que a tela Dashboard fazia a cada carregamento) e `cached_intelligence_bundle(portfolio_id)` (substitui as 2 chamadas da tela Inteligência), ambos decorados com `st.cache_data(ttl=300)`. `clear_all_caches()` invalida os dois.
- Dashboard ganhou um botão "🔄 Atualizar dados" que força `clear_all_caches()` e recarrega.
- `clear_all_caches()` é chamado explicitamente logo após qualquer ação de escrita que os dois bundles leem: em Configurações (atualizar preços em lote, alocação-alvo simples, política de investimento, regra de alocação-alvo detalhada, premissas do Monte Carlo), em Ativos (atualizar preço de um ativo, coletar fundamentos, marcar/desmarcar manual, salvar preço manual) e em Carteira (importar posições). O TTL de 5 minutos funciona só como rede de segurança adicional, nunca como única defesa contra dado desatualizado.
- A taxa de câmbio não precisa de invalidação explícita: por já ser parte da chave de cache de `cached_dashboard_bundle` (um `Decimal` hasheável), atualizá-la já produz uma nova entrada de cache automaticamente.

### Documentação
- Novo `docs/PERFORMANCE_CACHE.md`: descreve a camada de cache, por que o TTL é curto, e todos os pontos que chamam `clear_all_caches()`.
- Novo `docs/INVESTMENT_DECISION_SYSTEM.md`: documento de consolidação das 10 fases — mapeia cada pergunta original do projeto (valor real da carteira, onde aportar, o que é mais atrativo, concentração, validade da tese, evolução das decisões) para a engine/tela que a responde hoje, e lista como as fases se compõem sem nenhuma recalcular a lógica de outra.

### Testes
- Novo `test_streamlit_cache.py` (2 testes): os dois bundles são de fato memoizados pelo `st.cache_data` (têm `.clear()`), e `clear_all_caches()` não lança erro. Segue a mesma convenção da camada Streamlit (sem teste de renderização) — o cálculo em si já é coberto pelos testes dos serviços que cada bundle compõe.
- Suíte completa: **797 testes passando**, 0 falhas. `ruff check` e `black --check --fast` limpos.

### Riscos conhecidos
- Nenhuma migration nova nesta fase.
- Cache não é compartilhado entre sessões/processos diferentes do Streamlit — suficiente para o uso local de um único usuário do MVP, mas não seria para um cenário multiusuário real.
- Uma escrita direta no banco fora da UI (ex.: script rodado em paralelo) só é refletida quando o TTL de 5 minutos expirar, já que não há trigger de invalidação no nível do banco.
- Com a Fase 10 concluída, o plano de 10 fases da Sprint 24 está encerrado — próximos passos possíveis (orquestração automática Simulation Engine → Risk Engine, histórico do Health Score ao longo do tempo, Fonte B de proventos) estão listados em `docs/INVESTMENT_DECISION_SYSTEM.md`.
