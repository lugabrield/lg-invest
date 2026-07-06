# Valuation Engine v1 (Sprint 15)

## Objetivo e escopo declarado

Valuation Engine v1 é uma **heurística de múltiplos relativos**, não um
DCF, não um dividend discount model e não um cálculo de valor
intrínseco/preço-justo numérico. Ele responde apenas "esse ativo
parece caro, neutro ou barato frente a bandas fixas de múltiplos" —
uma primeira aproximação auditável, deliberadamente simples, para não
fabricar uma precisão que o MVP não sustenta (Volume 18 §8).

**Não existe `fair_value_low/base/high` nem `margin_of_safety`
numérico nesta versão.** A especificação original do produto pedia
essas saídas; a decisão tomada no Sprint 21 foi não implementá-las,
porque um range de preço justo defensável exigiria projeções de fluxo
de caixa, taxa de desconto e premissas de crescimento que a plataforma
não coleta hoje — inventar esses números violaria a regra de não
fabricar dados. Essa é uma limitação conhecida, documentada aqui e no
resumo de entrega, não um recurso escondido.

## Arquitetura

```
ValuationService (banco <-> engine)
    -> busca o snapshot de fundamentos mais recente do ativo
    -> ValuationEngine.evaluate(ticker, asset_class, snapshot)  # puro
```

## Classes não aplicáveis

`NOT_APPLICABLE_CLASSES = ("crypto", "cash", "bond", "etf")`. Cripto
não tem múltiplos de empresa; caixa e renda fixa não são avaliados por
múltiplos de mercado de ações; ETFs não têm P/L ou EV/EBITDA
próprios — avaliá-los exigiria dados de composição/custo que a
plataforma não coleta (número de holdings, expense ratio, tracking
error), então o pilar de Valuation para ETF cai inteiramente na proxy
de preço v1 do LG Score (preço atual vs. média histórica), nunca em um
valuation fabricado.

## Bandas por classe (`engines/valuation/thresholds.py`)

Direção importa: para P/L, P/VP e EV/EBITDA, **menor é mais barato**;
para dividend yield de FII/REIT, **maior é mais barato** (mais
atrativo).

**Ações (`stock`):**

| Métrica | Barato (≤) | Caro (≥) |
|---|---|---|
| P/L (`pe_ratio`) | 12 | 20 |
| P/VP (`pb_ratio`) | 1,5 | 3,0 |
| EV/EBITDA (`ev_ebitda`) | 8 | 14 |

**FIIs e REITs (`fii`, `reit`):**

| Métrica | Barato | Caro |
|---|---|---|
| P/VP (`pb_ratio`) | ≤ 0,9 | ≥ 1,1 |
| Dividend Yield (`dividend_yield`) | ≥ 9% | ≤ 6% |

Valores entre os dois limiares recebem veredito `"neutro"`.

## Classificação agregada

Cada métrica aplicável gera um veredito (`barato`/`neutro`/`caro`/
`indeterminado` se o valor não existir no snapshot). O veredito geral
soma pesos (`barato=-1, neutro=0, caro=+1`): soma negativa →
`"barato"`; soma positiva → `"caro"`; soma zero → `"neutro"`; nenhuma
métrica disponível → `"indeterminado"`.

## Confiança

Nenhuma métrica disponível → `"baixa"`; algumas → `"média"`; todas as
métricas da classe disponíveis → `"alta"`.

## Casos de "não aplicável" vs. "indeterminado"

- **Não aplicável**: a classe do ativo está em `NOT_APPLICABLE_CLASSES`
  ou não há nenhuma banda definida para ela — a plataforma afirma que
  este tipo de valuation não se aplica a essa classe.
- **Indeterminado**: a classe é aplicável, mas não há snapshot de
  fundamentos coletado ainda, ou o campo específico está ausente no
  snapshot — é uma lacuna de dado, não uma afirmação metodológica.

Os dois casos usam a mesma classificação textual (`"indeterminado"`)
na saída do engine, mas a razão (`reason`) sempre distingue os dois
motivos por extenso.

## Limitações conhecidas

- Bandas são fixas (não ajustadas por setor, ciclo econômico, taxa de
  juros vigente ou porte da empresa) — um P/L de 18 pode ser caro para
  uma utility e barato para uma empresa de tecnologia em crescimento;
  o engine não faz essa distinção.
- Não existe comparação com pares do mesmo setor nem com a série
  histórica de múltiplos do próprio ativo (diferente do pilar de
  Valuation v1 do LG Score legado, que usa preço vs. média histórica).
- ETF, cripto, renda fixa e caixa não recebem valuation por múltiplos
  — ver "Classes não aplicáveis" acima.
- Sem `fair_value` numérico nem margem de segurança percentual, por
  decisão deliberada (ver "Objetivo e escopo declarado").
