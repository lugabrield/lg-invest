# Fundamentals Foundation (Sprint 13; expandido Sprint 21)

## Objetivo

Documentar de onde vêm os fundamentos exibidos na plataforma, quais
campos existem, como a cobertura é calculada e as limitações
conhecidas da fonte de dado (yfinance, proxy gratuito, sem contrato de
disponibilidade).

## Arquitetura

```
YahooFundamentalsProvider (ETL, único ponto que toca yfinance)
        -> FundamentalsService (banco <-> provider, grava snapshots)
                -> FundamentalsRepository (ORM)
                        -> tabela fundamental_snapshots
                -> FundamentalsAnalysisService (calcula CAGR a partir dos snapshots)
                        -> FundamentalsEngine (puro, CAGR + tendência de margem)
```

Nenhum engine acessa banco/yfinance diretamente — apenas o provider e
os serviços.

## Campos coletados (`FundamentalSnapshot` / `FundamentalSnapshotResult`)

28 campos financeiros opcionais, todos `Decimal | None` (mais
`ticker`, `period_end`, `source`, `collected_at`):

`roe, roa, net_margin, ebitda_margin, revenue, net_income, ebitda,
ebit, free_cash_flow, net_debt, debt_to_ebitda, pe_ratio, pb_ratio,
ev_ebitda, dividend_yield, payout_ratio, eps, revenue_per_share, beta,
market_cap, enterprise_value, forward_pe, operating_margin, total_debt,
total_cash, operating_cash_flow, gross_profit, shares_outstanding`.

Os últimos 9 (`market_cap` até `shares_outstanding`) foram adicionados
no Sprint 21 (migration `a1f4e6c2b8d9`, puramente aditiva — ver
`docs/DEPLOYMENT_NOTES.md`).

`FundamentalSnapshotResult.coverage_pct` = fração de campos preenchidos
sobre o total de 28; `missing_fields` lista os campos ausentes
explicitamente. Nenhum campo ausente é tratado como zero.

## Fonte: Yahoo Finance (`YahooFundamentalsProvider`)

Único ponto do sistema que acessa `yfinance` para fundamentos. Duas
operações:

- **`get_latest(ticker)`** — lê o dicionário `info` do yfinance e mapeia
  campo a campo (`returnOnEquity` → `roe`, `totalRevenue` → `revenue`,
  `trailingPE` → `pe_ratio`, etc. — mapeamento completo no código-fonte
  do provider). `net_debt` e `debt_to_ebitda` são calculados
  localmente a partir de `totalDebt`/`totalCash`/`ebitda`. Campo
  ausente ou não numérico no `info` vira `None`, nunca um erro.
- **`get_history(ticker)`** — lê até 4 períodos anuais dos
  demonstrativos (`income_stmt`, `balance_sheet`, `cashflow`), usado
  pelo Fundamentals Engine para calcular CAGR. Linha ausente
  (ex.: "EBIT" não reportado por algumas empresas, cai para "Operating
  Income") ou coluna ausente também vira `None`.

**Cobertura é inconsistente por natureza da fonte gratuita**: ações
brasileiras e americanas de grande porte costumam ter cobertura alta;
FIIs, small caps e a maioria das classes fora de ações/ETFs costumam
retornar um `info` quase vazio. Isso é esperado, não um bug — é por
isso que `coverage_pct`/`missing_fields` existem.

## Classes não aplicáveis

`FundamentalsService.NOT_APPLICABLE_CLASSES = ("crypto", "cash",
"bond")` — a coleta em lote pula essas classes automaticamente (não
tenta buscar fundamentos de empresa para ativos que não são ações).
Ativos marcados como `is_manual=True` também são pulados.

## Fundamentals Engine (CAGR e tendência de margem)

Engine puro (`engines/fundamentals/engine.py`), recebe a lista de
snapshots já coletados de um ativo e calcula:

- **CAGR** de `revenue`, `net_income`, `ebitda`, `free_cash_flow`
  (função pura `compute_cagr` em `engines/fundamentals/cagr.py`).
  Regra de dado ausente: histórico com menos de 2 pontos, valor
  inicial/final não positivo, ou período de tempo insuficiente →
  `None` com razão explícita — nunca um número fabricado.
- **Tendência de margem líquida** (`margin_trend`): compara o primeiro
  e o último snapshot ordenados por `period_end`; variação > 1 ponto
  percentual → "melhorando"/"piorando"; caso contrário "estável";
  menos de 2 pontos → "indeterminado".
- **Confiança**: "alta" se as 4 séries de CAGR forem calculáveis,
  "média" se algumas, "baixa" se nenhuma ou sem snapshot.

## Capital Reinvestment Engine (Sprint 21)

Extraído do agregador de pilares (`ids_methodology/pillars.py`) para um
pacote próprio (`engines/capital_reinvestment/`), no mesmo padrão dos
demais engines (engine + thresholds + schema + service).

- **Fórmula**: `retenção = 1 − payout_ratio`; `score = clamp(0, 100, 50
  + retenção * 50)`.
- **Faixas**: score ≥ 70 → `"forte"`; score ≤ 40 → `"fraco"`; entre os
  dois → `"moderado"`.
- **Aplicável apenas a `stock`/`etf`** (ações puras). FIIs/REITs são
  regulatoriamente obrigados a distribuir a maior parte do resultado —
  payout baixo não indicaria disciplina, só descumprimento — por isso
  a classe recebe `"nao_aplicavel"`, não uma nota. Cripto/renda
  fixa/caixa não têm payout ratio (não são ações).
- Sem `payout_ratio` no snapshot mais recente → `"indeterminado"`,
  confiança baixa, razão explícita.
- Confiança é sempre `"média"` quando calculável (não derivada de
  cobertura de campos, diferente dos demais engines) — reflete que a
  fórmula usa um único indicador (payout ratio), não uma combinação de
  vários.
- **Limitação documentada**: a fórmula não distingue uma empresa madura
  que já não tem onde reinvestir (payout alto por decisão racional) de
  uma empresa que só distribui por falta de disciplina — os dois casos
  reduzem a nota igualmente. Isso é uma simplificação deliberada do
  MVP, não uma afirmação de que payout alto é sempre ruim.

## UI (tela Ativos)

A seção "Fundamentos" mostra: campos-chave (ROE, margem líquida, P/L,
P/VP, dividend yield, dívida/EBITDA, market cap, forward P/E, margem
operacional), fonte, data do período de referência, cobertura, campos
indisponíveis explicitamente listados, CAGR (quando calculável),
tendência de margem, valuation e badges de qualidade de dado. Botões
para coletar fundamentos de um ativo ou em lote.
