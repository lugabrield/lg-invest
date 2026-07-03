# Fundamentals Engine — Plano Técnico

> **Status (Sprint 13):** a camada de coleta e persistência (modelo,
> migration, provider, repositório, serviço, seção na UI de Ativos) foi
> implementada — ver `docs/DATA_SOURCES.md`. O **Fundamentals Engine**
> propriamente dito (cálculo puro de indicadores de qualidade/crescimento
> a partir dos snapshots coletados) é da Sprint 14 e ainda não existe.
> Este documento permanece como plano/contexto de decisão; a seção de
> schema abaixo já reflete o que foi de fato implementado.

## Objetivo

Coletar dados fundamentalistas por ativo (principalmente ações) para
substituir as proxies de preço hoje usadas em `quality_pillar`,
`growth_pillar` e, principalmente, `capital_reinvestment_pillar` (hoje
100% placeholder neutro) tanto no LG Score quanto na IDS Methodology.

## Fonte candidata

`yfinance`, via `Ticker.info` e `Ticker.financials`/`Ticker.balance_sheet`/
`Ticker.cashflow` — mesma biblioteca já em uso para preços, sem
dependência nova nem custo. Candidata de primeira tentativa por já
estar integrada e por não exigir chave de API.

## Limitações conhecidas (a validar na implementação)

- Cobertura inconsistente entre tickers: nem todo ativo (especialmente
  FIIs e ações menores) tem todos os campos preenchidos.
- Sem garantia de atualização tempestiva (dados podem estar
  defasados em relação ao último resultado trimestral divulgado).
- Nomenclatura de campos pode variar entre classes de ativo e ao longo
  do tempo (risco de breaking change silencioso, como já documentado
  para preços em `yahoo_provider.py`).
- Não cobre Tesouro Direto, cripto nem a maioria dos FIIs com a mesma
  profundidade de ações — plano deve tratar ausência de dado com a
  mesma regra do resto do projeto: neutralidade + razão explícita,
  nunca otimismo.

## Campos candidatos (a confirmar na implementação)

- Qualidade: ROE, ROIC (ou proxy via `returnOnEquity`/`returnOnAssets`),
  margem líquida, dívida/patrimônio.
- Crescimento: CAGR de receita e de lucro por ação (múltiplos anos, se
  disponível).
- Capital Reinvestment: payout ratio (`payoutRatio`), taxa de retenção
  de lucro (1 − payout), e, quando possível, retorno sobre o capital
  reinvestido.
- Valuation (uso futuro no Valuation Engine, não neste plano): P/L,
  P/VP, EV/EBITDA já vêm de `Ticker.info` como ponto de partida para
  múltiplos comparáveis — DCF/DDM exigem projeção própria, fora deste
  plano.

## Schema implementado (Sprint 13)

Tabela `fundamental_snapshots`: `asset_id` (FK), `period_end` (indexado,
único junto com `asset_id`), `source` (`yahoo`/`manual`/`unavailable`) e
19 campos nullable — `roe, roa, net_margin, ebitda_margin, revenue,
net_income, ebitda, ebit, free_cash_flow, net_debt, debt_to_ebitda,
pe_ratio, pb_ratio, ev_ebitda, dividend_yield, payout_ratio, eps,
revenue_per_share, beta`. Suporta múltiplos snapshots por ativo (um por
`period_end`), não só "o mais recente" — o snapshot "TTM" (via
`Ticker.info`) e até 4 snapshots anuais históricos (via
`income_stmt`/`balance_sheet`/`cashflow`) convivem na mesma tabela.

`FundamentalsProvider` (ABC) com `get_latest`/`get_history`, implementado
por `YahooFundamentalsProvider`; `FundamentalsRepository` e
`FundamentalsService` seguem a mesma arquitetura em camadas do resto do
projeto (provider → repository → service, sem lógica financeira na UI).
Ativos manuais e classes sem fundamentos de empresa aplicáveis (cripto,
caixa, renda fixa) são pulados com razão explícita, nunca chamam o
provider.

## Riscos

Maior risco é qualidade/cobertura de dado inconsistente da fonte
gratuita — pode exigir, em sprint futura e com aprovação explícita, uma
fonte paga complementar (ex.: Financial Modeling Prep, Finnhub) apenas
para os campos que o Yahoo não cobre bem. Nenhuma decisão sobre isso é
tomada aqui.

## Fora deste plano (Sprint 13)

Cálculo de indicadores (Fundamentals Engine puro, Sprint 14), DCF/DDM,
Monte Carlo, fonte paga complementar — nada disso foi implementado
nesta sprint.
