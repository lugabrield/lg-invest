# Data Quality Layer (Sprint 21)

## Objetivo

Ter uma superfície única e explícita para responder "quão confiável é
o que a LG INVEST está mostrando" — por ativo e para a carteira como um
todo — sem recalcular nada: o Data Quality Layer só **compõe** sinais
que outros serviços já produzem (origem do preço, cobertura de
fundamentos, classificação de valuation, confiança do LG Conviction
Score).

## Arquitetura

```
DataQualityService (banco <-> engine)
    -> resolve sinais brutos por ativo (PriceRepository, FundamentalsRepository,
       ValuationService, ConvictionScoreService)
    -> engines/data_quality/engine.py (puro)
        build_asset_data_quality()      # por ativo
        build_portfolio_summary()       # agregado, ponderado por peso na carteira
```

## Dimensões e estados possíveis (`schemas/data_quality.py`)

**Preço** (`PRICE_STATUSES`): `automatico` | `manual` | `estimado` |
`ausente`.
- `estimado` = não há nenhum preço cadastrado; o Dashboard usa o preço
  médio de compra como estimativa temporária (não é uma cotação real).
- `ausente` é teoricamente inalcançável no fluxo atual (mantido como
  branch de segurança no engine), porque a plataforma sempre cai para
  "estimado" antes de "ausente".

**Fundamentos** (`FUNDAMENTALS_STATUSES`): `completo` | `parcial` |
`ausente` | `nao_aplicavel`.
- `nao_aplicavel`: classe fora do escopo do Fundamentals Provider
  (`crypto`, `cash`, `bond`).
- `ausente`: zero campos preenchidos no snapshot mais recente (ou
  nenhum snapshot).
- `completo`: cobertura ≥ 70% dos 28 campos rastreados
  (`_FUNDAMENTALS_COMPLETE_RATIO = 0,7`) — limiar de julgamento do
  autor da plataforma, não calibrado estatisticamente.
- `parcial`: entre 1 campo e o limiar de 70%.

**Valuation** (`VALUATION_STATUSES`): `real` | `proxy` | `nao_aplicavel`
| `ausente`.
- `nao_aplicavel`: classe fora do escopo do Valuation Engine (`crypto`,
  `cash`, `bond`, `etf`).
- `ausente`: classe aplicável, mas o Valuation Engine devolveu
  `"indeterminado"` (sem snapshot ou métrica ausente).
- `real`: o Valuation Engine devolveu uma classificação efetiva
  (`barato`/`neutro`/`caro`).

**Confiança do score** (`SCORE_CONFIDENCE_STATUSES`): `alta` | `média` |
`baixa` | `indisponivel` — herdado diretamente de `confidence_label` do
LG Conviction Score v2.

## Agregação por carteira (`PortfolioDataQualitySummary`)

Ponderada pelo peso de cada ativo na carteira (não uma média simples
por contagem de ativos) — um ativo pequeno com dado ruim pesa menos no
resumo do que uma posição grande com dado ruim:

- `pct_price_automatic` / `pct_price_manual` / `pct_price_estimated`
- `pct_fundamentals_available` (soma dos pesos com status `completo` ou
  `parcial`)
- `pct_valuation_available` (soma dos pesos com status `real` — hoje
  não há distinção operacional entre `real` e `proxy` na agregação)
- Listas de tickers: `assets_insufficient_data` (fundamentos **e**
  valuation ambos ausentes), `assets_manual`, `assets_price_estimated`,
  `assets_unsupported_by_provider` (classe fora do escopo do
  Fundamentals Provider)

Carteira vazia nunca gera erro — devolve um resumo com todos os
percentuais zerados.

## Onde aparece na UI

- **Dashboard** — seção "Oportunidades & Riscos": três métricas (%
  preço automático, % com fundamentos, % com valuation calculável) e a
  lista de tickers com dado insuficiente.
- **Inteligência** — cada ativo no bucket "Dados insuficientes" mostra
  o motivo textual (`unavailable_reason`), nunca um score inventado.
- **Ativos** — badges de qualidade de dado (preço, fundamentos,
  valuation) por ativo selecionado, ao lado do LG Conviction Score v2.

## Princípio central: nunca inventar "completo"

A regra do engine é sempre conservadora: na dúvida, classifica para
baixo. Um snapshot com 1 de 28 campos preenchidos é `"parcial"`, nunca
`"completo"`. Um ativo sem nenhum preço cadastrado nunca aparece como
tendo preço "automático". Isso é deliberado — o objetivo do Data
Quality Layer é alertar o usuário, não inflar a aparência de
confiabilidade da plataforma.

## Limitação conhecida

O limiar de 70% de cobertura para "completo" foi escolhido por
julgamento, não por análise estatística de quais campos são realmente
necessários para um LG Conviction Score confiável — dois snapshots com
70% de cobertura podem ter qualidade de sinal muito diferente
dependendo de quais campos especificamente estão presentes (ex.: ROE e
margem preenchidos vs. apenas campos menos relevantes para os
engines).
