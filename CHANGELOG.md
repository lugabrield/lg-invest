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
