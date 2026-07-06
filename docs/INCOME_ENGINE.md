# Income Engine (Sprint 24, Fase 7)

## Contexto

A integração Dividendos.me (Sprint 23) já coleta e persiste proventos
recebidos, mas até esta fase eles só existiam como dado bruto de
sincronização (`income_events`, `income_monthly_summaries`) — nenhuma
engine ou tela analisava essa renda. A Fase 7 adiciona a primeira camada
de análise: quanto a carteira rendeu, se essa renda está crescendo, de
quais ativos ela vem, e qual é o "aluguel" (yield) sobre o capital
efetivamente investido — métrica central para um investidor Buy and Hold
de longuíssimo prazo, que se importa mais com a renda crescendo sobre o
que já pagou do que com o yield sobre o preço de mercado atual.

## Duas fontes, nunca somadas entre si

O banco guarda dois tipos de proventos com semânticas diferentes
(Sprint 23.2/23.3):

- **`income_monthly_summaries`**: agregado mensal por carteira (aba
  "Análise" do Dividendos.me) — sem ticker, sem data exata.
- **`income_events`**: calendário individual por ativo (aba "Próximos
  Dividendos") — com ticker e data de pagamento, mas sem cobrir o
  histórico completo de todos os meses.

Somar as duas arriscaria contar o mesmo provento duas vezes (uma fonte é
agregada, a outra é granular por ativo, e não há garantia de que cobrem
exatamente o mesmo conjunto de eventos). Por isso o Income Engine
**nunca soma as duas fontes** — ele produz dois resultados lado a lado:

1. `PortfolioIncomeTrend` (a partir de `income_monthly_summaries`):
   tendência agregada da carteira inteira.
2. `TickerIncomeBreakdown` (a partir de `income_events`): renda por
   ativo, yield on cost, concentração.

## `PortfolioIncomeTrend`

- `ttm_total`: soma da renda mensal agregada nos últimos 12 meses
  (trailing twelve months) a partir da data de referência.
- `prior_ttm_total`: soma dos 12 meses anteriores a esses. Se não houver
  dado suficiente nesse período anterior, fica em `0` e `growth_pct` fica
  `None` (nunca inventa uma taxa de crescimento sem base de comparação).
- `growth_pct`: `(ttm_total - prior_ttm_total) / prior_ttm_total`, quando
  calculável.
- `projected_next_12_months`: uma **extrapolação simples (naive)** —
  aplica a taxa de crescimento observada sobre o TTM atual, ou repete o
  TTM atual se não houver taxa de crescimento calculável. Sempre
  documentado como não sendo garantia de recebimento futuro.
- `monthly_series`: os últimos `config.months_lookback` meses (padrão:
  24), para visualizar consistência/sazonalidade — dado bruto, sem
  interpretação.

## `TickerIncomeBreakdown`

- Para cada ativo com evento de renda nos últimos 12 meses: `ttm_income`
  e, se a posição correspondente ainda existir na carteira com custo de
  aquisição conhecido (`quantidade × preço médio`), o **yield on cost**:
  `ttm_income / custo_de_aquisição`. Este é o "aluguel sobre o que você
  pagou", não sobre o valor de mercado atual — cresce com o tempo se a
  empresa/fundo aumenta o provento, mesmo que o preço da ação suba junto
  (o que reduziria o yield calculado sobre o preço atual).
- Eventos de ativos que não têm mais posição na carteira (venda, ou dado
  de posição indisponível) são excluídos do yield on cost mas contam na
  concentração de renda — documentado em
  `excluded_tickers_without_position`.
- `concentration_hhi`: Herfindahl-Hirschman sobre a participação de cada
  ativo na renda dos últimos 12 meses — "quanto da minha renda depende de
  um único pagador".
- `portfolio_yield_on_cost`: soma da renda / soma do custo de aquisição,
  só entre os ativos com custo conhecido.

## Nada é inventado

Toda ausência de dado vira `None`/lista vazia + uma entrada em
`warnings`, nunca um valor fabricado: sem período anterior suficiente →
`growth_pct=None`; sem histórico algum → projeção zerada; sem custo de
aquisição conhecido → `yield_on_cost=None` naquele ativo (e
`portfolio_yield_on_cost=None` se nenhum ativo tiver custo conhecido).

## Engine pura (`engines/income/`)

- `inputs.py`: `MonthlyIncomeTotal`, `TickerIncomeEvent`,
  `IncomeEngineInput`, `IncomeConfig` (`months_lookback=24`,
  `projection_months=12`) — todos `@dataclass(frozen=True)`.
- `engine.py`: `analyze_income(data, config) -> IncomeAnalysisResult`,
  sem acesso a banco/rede. `MODEL_VERSION = "income_v1"`.

## Serviço (`IncomeAnalysisService`)

- `build_input(portfolio_id, reference_date=None)`: lê
  `IncomeMonthlySummaryRepository.list_by_portfolio` e
  `IncomeEventRepository.list_by_portfolio` (filtrando eventos sem
  ticker/data, que pertencem só ao agregado mensal), converte tudo para
  BRL (`fx_settings_service`, mesma conversão do Dashboard/Decision
  Engine 3.0/Simulation Engine) e resolve o custo de aquisição de cada
  posição via `PortfolioService.get_summary()`.
- `evaluate(portfolio_id, reference_date=None)`: monta os inputs e chama
  a engine pura. **Não persiste nada** — análise sob demanda, como as
  demais engines das fases anteriores.

## Exposição na UI (Fase 9)

A seção "Renda de Proventos" na tela **Inteligência** exibe a renda dos
últimos 12 meses, o crescimento vs. período anterior, a projeção para os
próximos 12 meses e a tabela de yield on cost por ativo (com o yield on
cost agregado da carteira quando calculável).

## O que ainda não existe

A extração de renda por ativo/mês (Fonte B, documentada como limitação
em `docs/DIVIDENDOS_ME_INCOME_SOURCES.md`) continua sem implementação —
o `TickerIncomeBreakdown` depende inteiramente do calendário de eventos
já coletado (Fonte C), que pode não cobrir o histórico completo de todos
os pagamentos passados.
