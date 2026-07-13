# Central de Dados / Data Refresh Center (Sprint 27)

## Objetivo

Dar ao usuário um jeito manual e explícito de atualizar preços,
fundamentos, valuation, traps e dados da watchlist — sem que o
Streamlit precise refazer isso sozinho a cada carregamento de página
(o que seria lento, geraria chamadas excessivas ao Yahoo Finance e
arriscaria salvar dado incompleto no meio de um rerender).

A Central de Dados vive na tela **Dashboard**, logo após a seção "Visão
Geral", e nunca roda sozinha: toda coleta/recomputação só acontece a
partir de um clique explícito num dos 5 botões.

## Por que a atualização é sempre manual

- **Custo**: cada botão pode disparar dezenas de chamadas ao Yahoo
  Finance (uma por ativo). Rodar isso em todo carregamento de página
  tornaria o Dashboard inutilizável.
- **Previsibilidade**: o usuário sabe exatamente quando os dados foram
  atualizados pela última vez (bloco "Última atualização") — não há
  mágica escondida recalculando tudo em segundo plano.
- **Segurança de dado**: uma coleta interrompida no meio nunca deixa o
  banco pela metade — cada ativo é processado e persistido
  individualmente (ver "Falha num ativo não derruba o lote").

## Os 5 botões

| Botão | Método do serviço | Toca a watchlist? | Busca dado externo? |
|---|---|---|---|
| 💰 Preços da carteira | `refresh_portfolio_prices` | Não | Sim (Yahoo Finance, preços) |
| 📊 Fundamentos da carteira | `refresh_portfolio_fundamentals` | Não | Sim (Yahoo Finance, fundamentos) |
| 🔭 Dados da watchlist | `refresh_watchlist_data` | Sim (só ela) | Sim (preços + fundamentos) |
| ♻️ Atualizar tudo | `refresh_all_investment_data` | Sim (além da carteira) | Sim (as três rotinas acima) |
| 🧹 Limpar cache | — (só `clear_all_caches()`) | Não | **Não** |

### 💰 Atualizar preços da carteira

Atualiza o histórico de preços (`MarketDataService.update_asset_prices`)
de cada ativo que tem `Position` na carteira selecionada — nunca da
watchlist. Ativos `is_manual=True` (ex.: Tesouro Direto) são pulados
com status `skipped_manual`, porque o preço deles é sempre cadastrado
manualmente na tela Ativos. Nunca recomputa fundamentos, valuation ou
scores.

### 📊 Atualizar fundamentos da carteira

Para cada ativo da carteira: coleta fundamentos
(`FundamentalsService.collect_for_asset`, que já sabe pular
cripto/caixa/Tesouro e ativos manuais) e, na sequência, tenta
recomputar — sempre que a classe do ativo suporta aquele tipo de
análise, mesmo quando a coleta de fundamentos em si não trouxe dado
novo:

- **Trap Detection** (ações, FIIs, REITs).
- **Valuation Engine 2.0** só para ações.
- **Análise de Renda Imobiliária** só para FIIs/REITs.
- **Adequação de Carteira** só para ETF/cripto/Tesouro.
- **LG Score** e **Conviction Score** para qualquer classe aplicável.

Isso é o que a Central de Dados chama de "recomputar análises" — nunca
um cálculo novo, sempre uma chamada real aos serviços já existentes
(ver `docs/VALUATION_ENGINE_2.md`, `docs/TRAP_DETECTION_ENGINE.md`,
`docs/INCOME_REAL_ESTATE_ANALYSIS.md`, `docs/PORTFOLIO_ADEQUACY_ENGINE.md`).

### 🔭 Atualizar dados da watchlist

Para cada candidato da watchlist (exceto os com status `discarded`):

1. `WatchlistService.collect_data_for_asset` garante o cadastro mestre
   em `assets` (se ainda não existir) — **nunca cria uma `Position`**.
2. `MarketDataService`/`FundamentalsService` coletam preço e
   fundamentos reais do ticker.
3. `WatchlistService.collect_data_for_asset` roda de novo, agora com o
   dado recém-coletado, para recomputar LG Score/Conviction Score.
4. Trap Detection/Valuation (quando aplicável à classe) também são
   recomputados, do mesmo jeito que para a carteira.

`WatchlistRefreshResult.positions_created` e `.patrimonio_changed` são
a garantia central desta rotina — ver "Garantias da Watchlist" abaixo.

### ♻️ Atualizar tudo

Roda as três rotinas acima em sequência (`refresh_portfolio_prices` →
`refresh_portfolio_fundamentals` → `refresh_watchlist_data`) e devolve
um `FullRefreshResult` com os três sub-resultados. Pode demorar bastante
numa carteira grande — por isso a UI exige uma confirmação explícita em
duas etapas antes de disparar (clique em "♻️ Atualizar tudo" → aviso +
botão "✅ Confirmar atualização completa"). Nunca é chamado
automaticamente.

### 🧹 Limpar cache / Recarregar análises

Só chama `clear_all_caches()` (invalida `cached_dashboard_bundle` e
`cached_intelligence_bundle`, ver `docs/PERFORMANCE_CACHE.md`) e
`st.rerun()`. **Nunca busca dado externo** — as telas voltam a mostrar
o que já está salvo no banco, recalculado a partir do zero pelas
engines de leitura (Dashboard/Inteligência/Aporte/Radar já sempre leem
direto do banco a cada chamada; o cache só evita reler/reprocessar
dentro da janela de 5 minutos).

## Arquitetura

```
DataRefreshService (backend/app/services/data_refresh_service.py)
    -> MarketDataService(db, YahooFinanceProvider())       # preços
    -> FundamentalsService(db, YahooFundamentalsProvider())# fundamentos
    -> TrapDetectionService(db)                            # traps
    -> ValuationServiceV2(db)                              # ações
    -> IncomeRealEstateService(db)                         # FII/REIT
    -> PortfolioAdequacyService(db)                        # ETF/cripto/Tesouro
    -> LGScoreService(db) / ConvictionScoreService(db)      # scores
    -> WatchlistService(db)                                # watchlist

data_refresh_status_service.py  # JSON: data/refresh_status.json
    <- timestamps + resumo da última execução de cada rotina

pages_impl/dashboard.py  # camada de apresentação
    -> chama DataRefreshService, mostra spinner, mostra resumo,
       chama clear_all_caches() — nenhum cálculo mora aqui.
```

Nenhuma engine nova foi criada nesta sprint — o `DataRefreshService` é
uma camada de orquestração pura de I/O, chamando serviços que já
existiam desde os Sprints 12, 13 e 26.

## Vocabulário de status por ativo

Cada ativo processado vira um `AssetRefreshOutcome` (ver
`schemas/data_refresh.py`) com um destes status:

- **`updated`** — o provider devolveu dado novo e ele foi persistido.
- **`insufficient_data`** — a coleta rodou, mas o provider não devolveu
  nada aproveitável (ex.: ticker sem cobertura no Yahoo Finance).
- **`not_applicable`** — a classe do ativo não usa esse tipo de coleta
  (ex.: fundamentos de empresa para cripto/Tesouro) — não é uma falha.
- **`skipped_manual`** — ativo `is_manual=True` (ex.: Tesouro Direto).
- **`failed`** — houve uma exceção real na coleta (rede, parsing etc.).

Nenhum desses status é inventado: são sempre derivados diretamente do
que `MarketDataService`/`FundamentalsService` devolveram (Volume 18
§8 — nunca inventar dado).

## Resumo de execução

Depois de qualquer botão (exceto "Limpar cache"), a UI mostra um
"Resumo da última execução" com, por rotina: processados, atualizados,
dados insuficientes, falhas (com os tickers que falharam), fontes
usadas, e — quando aplicável — valuation recalculado / traps
recalculadas / scores recalculados / posições criadas / patrimônio
alterado. Todas essas contagens são `@property` calculadas a partir da
lista real de `outcomes`, nunca um contador mantido à parte — se algum
dia divergirem, é porque o código mudou de verdade, não porque um
contador ficou desatualizado.

## Garantias da Watchlist

Reafirmando as regras do Sprint 25 (`docs/WATCHLIST_RADAR.md`), agora
também garantidas pelos testes desta sprint:

- `refresh_watchlist_data` **nunca cria uma `Position`** —
  `positions_created` é a contagem REAL de `Position` na carteira antes
  e depois da rotina (`positions_after - positions_before`), não um
  valor fixo. Se uma regressão futura fizer a watchlist criar posição,
  esse campo deixa de ser 0 e os testes acusam.
- `patrimonio_changed` é sempre `False` — a rotina nunca escreve nada
  que o Portfolio Engine leia para calcular patrimônio.
- Candidatos com status `discarded` são ignorados pela rotina (não vale
  a pena gastar chamada de rede num ticker que o usuário já descartou).
- `bought`, `blocked`, `candidate` e `watching` são todos processados
  normalmente — a rotina não muda o `status` de nenhum registro.

## Última atualização (timestamps)

`data_refresh_status_service.py` persiste em
`data/refresh_status.json` (mesma técnica de `fx_settings_service.py`,
sem migration nova) os timestamps de:

- `prices_at` — última vez que "Preços da carteira" rodou.
- `fundamentals_at` — última vez que "Fundamentos da carteira" rodou.
- `watchlist_at` — última vez que "Dados da watchlist" rodou.
- `valuation_at` / `trap_detection_at` — atualizados tanto pela rotina
  de fundamentos quanto pela de watchlist (as duas recomputam essas
  análises).
- `cache_cleared_at` — última vez que "Limpar cache" foi clicado.

Todos ficam ausentes (a UI mostra "nunca") até a primeira execução —
nunca uma data fabricada.

## Como lidar com falha de fonte externa

`MarketDataService`/`FundamentalsService` já capturam qualquer exceção
do provider (`except Exception`) e devolvem um resultado com `error`
preenchido, sem derrubar o restante do lote — o `DataRefreshService`
simplesmente lê esse `error` e marca o ativo como `failed`, seguindo
para o próximo. Isso significa que a Central de Dados continua
funcionando (e persistindo o que já conseguiu) mesmo se a máquina não
tiver acesso à internet, ou se o Yahoo Finance estiver fora do ar —
comportamento validado nos testes com um provider fake que sempre
levanta exceção.

## Como o refresh afeta o Decision Engine 3.0 e o Radar

Nenhum deles é chamado diretamente pela Central de Dados. Como
`ValuationServiceV2`/`TrapDetectionService`/`IncomeRealEstateService`/
`PortfolioAdequacyService` sempre leem o snapshot mais recente do banco
(nunca guardam estado próprio), o Decision Engine 3.0
(`docs/DECISION_ENGINE_3.md`) e o Radar
(`docs/WATCHLIST_RADAR.md`) automaticamente passam a refletir o dado
novo na PRÓXIMA vez que forem chamados — não é preciso nenhuma
integração especial, só que o cache do Streamlit tenha sido invalidado
(o que todo botão da Central de Dados já faz).

## Como validar localmente

1. Rode o app (`streamlit run frontend/streamlit_app/app.py` a partir
   da raiz do projeto, com o `.venv` ativado) e abra o Dashboard.
2. Clique em "💰 Preços da carteira" — o bloco "Última atualização"
   deve mostrar `prices_at` recém-atualizado e o resumo deve mostrar
   `processados` igual ao número de ativos com posição.
3. Clique em "📊 Fundamentos da carteira" — confira no resumo que
   `valuation_recalculado`/`traps_recalculadas`/`scores_recalculados`
   são maiores que zero quando a carteira tem ações/FIIs/REITs.
4. Cadastre um candidato na tela Radar, clique em "🔭 Dados da
   watchlist" e confira que `posições criadas: 0` e `patrimônio
   alterado: não` no resumo — e que o patrimônio total no Dashboard não
   mudou.
5. Clique em "♻️ Atualizar tudo" — confirme que aparece o aviso de
   confirmação antes de qualquer chamada de rede.
6. Clique em "🧹 Limpar cache" — confirme (via log ou observando que a
   ação é instantânea) que nenhuma chamada de rede foi feita.
7. Testes automatizados:
   `PYTHONPATH=... python -m pytest backend/tests/unit/test_data_refresh_service.py -v`.

## Resumo de cobertura de dados (Sprint 28)

Depois do botão "Fundamentos da carteira", o "Resumo da última
execução" ganhou uma linha adicional que a Central de Dados não tinha
antes desta sprint: quantos ativos processados ficaram com cobertura
de dados **suficiente**, **parcial** ou **insuficiente** (contagens
reais, derivadas do Data Coverage Report de cada ativo — ver
`docs/DATA_COVERAGE_REPORT.md`), mais os campos que mais aparecem como
ausentes entre os ativos processados ("Campos mais ausentes: FCF,
Patrimônio líquido, ROIC..."). Antes, o resumo só dizia "atualizados:
N" — sem indicar que "atualizado" não é sinônimo de "com dado
suficiente para as análises". `AssetRefreshOutcome` agora também
carrega `data_completeness_score` e `missing_fields` por ativo
(`backend/app/schemas/data_refresh.py`), e `LastRefreshStatus`
persiste esse resumo (`dados_suficientes`/`dados_parciais`/
`dados_insuficientes_cobertura`/`campos_mais_ausentes`) no mesmo JSON
de sempre.

## O que ficou fora desta sprint

- Fontes de dado adicionais (Fundamentus, Status Invest, CVM/B3,
  Dividendos.me como fonte de preço/fundamentos) — a arquitetura já
  permite (o provider é injetado no serviço), mas nenhuma nova foi
  implementada.
- Execução em background/assíncrona — cada botão bloqueia o request do
  Streamlit até terminar (com spinner); não há fila de jobs nem
  progresso incremental por ativo.
- Agendamento automático — deliberadamente fora de escopo, por decisão
  explícita: a atualização é sempre manual.
