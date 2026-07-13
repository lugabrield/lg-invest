# Valuation Engine 2.0 (Sprint 26, Fases 1-2)

## Objetivo e escopo declarado

O Valuation Engine v1 (`docs/VALUATION_ENGINE.md`) é uma heurística de
bandas fixas de múltiplo único — nunca produziu uma faixa de valor
justo numérica nem margem de segurança. O Valuation Engine 2.0 resolve
essa limitação para **ações** (`asset_class == "stock"`), combinando
três métodos independentes — DCF simplificado em 3 cenários, múltiplos
normalizados pelo próprio histórico do ativo e Graham Number como
checagem de sanidade — numa faixa de valor justo (`fair_value_range`),
nunca um ponto único.

Continua nunca gerando recomendação de compra/venda: a saída é sempre
classificação (`subvalorizado`/`valor_justo`/`sobrevalorizado`/
`indeterminado`), faixa, margem de segurança, expectativa implícita do
mercado (reverse DCF), confiança e avisos. Quando os dados são
insuficientes para qualquer estimativa, `valuation_status` fica
`"indeterminado"` e `reason` traz literalmente "Dados insuficientes
para estimar valor justo com confiança." (nunca um valor aproximado ou
inventado — Volume 18 §8).

**Fora de escopo nesta fase**: FIIs/REITs (têm sua própria análise, ver
`docs/INCOME_REAL_ESTATE_ANALYSIS.md`), ETFs, cripto e Tesouro Direto
(têm sua própria adequação, ver `docs/PORTFOLIO_ADEQUACY_ENGINE.md`) —
todas essas classes voltam `indeterminado` com o motivo explícito de
estarem fora do escopo do Valuation Engine 2.0.

## Fase 1 — dados expandidos (pré-requisito)

Antes de construir o DCF, três campos novos foram adicionados ao
snapshot de fundamentos (migration `d8a2f5c7b104_add_fundamentals_roic_fields`,
puramente aditiva):

- **`total_equity`** — patrimônio líquido, lido de `Stockholders
  Equity` (ou `Common Stock Equity` como fallback) nos demonstrativos
  anuais do yfinance.
- **`roic`** — retorno sobre capital investido: `NOPAT / capital
  investido`, onde `NOPAT = EBIT x (1 - taxa efetiva de imposto)` e
  `capital investido = dívida total + patrimônio líquido - caixa`.
  Só calculado quando EBIT, taxa efetiva de imposto, dívida total,
  patrimônio líquido e caixa estão TODOS disponíveis — nenhuma
  aproximação parcial.
- **`interest_coverage`** — cobertura de juros: `EBIT / despesa
  financeira`. Só calculado quando ambos os componentes existem e a
  despesa financeira é diferente de zero.

Os três vêm exclusivamente de `get_history()` (demonstrativos anuais
reais) — `.info` do yfinance não expõe taxa efetiva de imposto nem
despesa financeira de forma confiável, então esses campos nunca são
preenchidos a partir do snapshot "rápido" (`get_latest()`), só do
histórico anual. Qualquer componente ausente faz o resultado
correspondente ficar `None`, nunca aproximado (Volume 18 §8).

Com isso, `FundamentalSnapshotResult` passa de 27 para **30 campos**
financeiros considerados no cálculo de `coverage_pct`/`missing_fields`
(ver `docs/FUNDAMENTALS_ENGINE.md`).

## Arquitetura

```
ValuationServiceV2 (banco <-> engine)
    -> busca snapshot mais recente + histórico + FundamentalsAnalysisResult
       (CAGR, via FundamentalsAnalysisService) + classificação de qualidade
       (via ConvictionScoreService, pilar quality)
    -> ValuationEngineV2.evaluate(...)  # puro, sem I/O
        -> dcf.py            (DCF simplificado, 3 cenários)
        -> multiples.py      (múltiplos normalizados pelo próprio histórico)
        -> graham.py         (Graham Number, checagem de sanidade)
        -> reverse_dcf.py    (crescimento implícito no preço atual)
        -> constants.py      (premissas macro, isoladas e documentadas)
```

`engines/valuation_v2/` é um pacote próprio, seguindo o mesmo padrão
dos demais engines (pacote com módulos puros + schema + service).

## DCF simplificado (`dcf.py`)

Modelo de 2 estágios: `DCF_PROJECTION_YEARS = 5` anos de fluxo de caixa
livre (FCF) projetado a uma taxa de crescimento constante, seguido de
valor terminal por perpetuidade (Gordon growth), descontados a uma taxa
via CAPM simplificado.

- **Taxa de desconto (CAPM)**: `risk_free_rate + beta x
  equity_risk_premium`. Beta ausente no snapshot usa o beta de mercado
  (`DEFAULT_BETA = 1.0`) como aproximação padrão — nunca um beta
  "estimado" para a empresa — com aviso explícito emitido.
- **Premissas macro por moeda** (`constants.py::_MACRO_BY_CURRENCY`,
  proxies de longo prazo, não cotações ao vivo):

  | Moeda | Risk-free rate | Equity risk premium | Crescimento terminal máximo |
  |---|---|---|---|
  | BRL | 10,0% | 5,5% | 4,5% |
  | USD | 4,5% | 5,0% | 2,5% |

- **Crescimento assumido**: prioriza CAGR de FCF (mais direto para
  DCF); se ausente, cai para CAGR de lucro líquido; se ausente, para
  CAGR de receita — sempre do `FundamentalsAnalysisService` já
  existente, nunca recalculado aqui. Clampado à faixa de sanidade
  `GROWTH_RATE_SANE_MIN = -30%` / `GROWTH_RATE_SANE_MAX = 40%` (evita
  extrapolar uma recuperação pontual de lucro para 5 anos sem
  correção), com aviso quando o clamp é aplicado.
- **3 cenários**: pessimista (crescimento −5pp, desconto +1,5pp),
  base, otimista (crescimento +5pp, desconto −1,5pp) — spreads em
  `SCENARIO_GROWTH_SPREAD`/`SCENARIO_DISCOUNT_SPREAD`.
- **Motivo de `None` explícito** em qualquer etapa: FCF inicial não
  positivo, ações em circulação indisponíveis, taxa de desconto que
  não excede o crescimento terminal (denominador do valor terminal não
  positivo), ou valor de equity implícito não positivo (dívida líquida
  elevada frente ao fluxo projetado). Dívida líquida ausente é tratada
  como neutra (nem soma nem subtrai), com aviso explícito.

## Múltiplos normalizados pelo próprio histórico (`multiples.py`)

Rejeita deliberadamente a regra "P/L baixo = barato" (banda fixa
arbitrária, abordagem do Valuation Engine v1). Em vez disso, usa a
**média histórica de P/L e/ou P/VP do próprio ativo** como referência —
o preço que o mercado pagaria hoje se o múltiplo voltasse à sua média
histórica, aplicada ao EPS/valor patrimonial por ação mais recente.
Nunca compara com pares do setor (não coletado). Exige no mínimo
`MIN_PERIODS_FOR_OWN_HISTORY = 2` períodos com múltiplo positivo
disponível; caso contrário, `None` com motivo explícito.

## Graham Number (`graham.py`) — checagem de sanidade, nunca método primário

Fórmula clássica: `sqrt(22.5 x EPS x VPA)`. Usado **somente** como
cross-check contra a faixa combinada (DCF + múltiplos) — nunca como
estimativa isolada (Volume — proibição de concluir com base em um
único múltiplo). Nunca aplicado quando EPS ou VPA não são positivos.
Divergência acima de `GRAHAM_DIVERGENCE_WARNING_THRESHOLD = 40%` da
estimativa combinada gera aviso, nunca corrige a estimativa.

## Reverse DCF (`reverse_dcf.py`)

Inverte a pergunta do DCF: "que taxa de crescimento constante faria o
valor justo coincidir com o preço atual de mercado?". Resolvido por
bisseção (`_MAX_ITERATIONS = 60`, tolerância de 1 centavo) sobre o
mesmo modelo de DCF simplificado — a função valor-justo(crescimento) é
monotonicamente crescente, então bisseção converge sem derivadas.
Resultado vira texto em linguagem natural (`implied_expectation`) e
fração numérica (`implied_growth_rate`, usada pelo Trap Detection
Engine — ver `docs/TRAP_DETECTION_ENGINE.md`). Preço que implica
crescimento acima do limite de sanidade considerado gera aviso, nunca
uma extrapolação além do modelo.

## Faixa de valor justo, margem de segurança e status

- **`fair_value_range.low/high`**: mínimo/máximo entre os cenários de
  DCF disponíveis e o valor de múltiplos (quando disponível).
- **`fair_value_range.base`**: média entre o DCF base e o valor de
  múltiplos (quando ambos disponíveis) — se nenhum dos dois existir,
  `base` fica `None` e o resultado inteiro vira `indeterminado`.
- **Margem de segurança exigida**, escalada pela qualidade do ativo
  (pilar Quality do LG Conviction Score — Volume: "margem de segurança
  proporcional à qualidade"):

  | Qualidade | Margem exigida |
  |---|---|
  | alta | 15% |
  | média | 25% |
  | baixa | 35% |
  | indeterminado/ausente | 30% |

- **Classificação**: `margem_de_segurança = (base - preço_atual) /
  base`. `margem >= margem_exigida` → `subvalorizado`; `margem <=
  -margem_exigida` → `sobrevalorizado`; entre os dois → `valor_justo`.
  Preço atual ausente → `indeterminado`, com aviso explícito.

## Confiança

`"alta"` exige simultaneamente: pelo menos 2 métodos contribuindo
(DCF + múltiplos), dispersão entre `low`/`high` não superior a
`HIGH_DISPERSION_THRESHOLD = 40%` do valor base, e pelo menos 3
períodos de histórico de fundamentos usados no CAGR. `"média"` com
pelo menos 1 método disponível. `"baixa"` sem nenhum método aplicável.
Dispersão alta entre métodos gera aviso próprio (metodologias
discordando fortemente é, em si, sinal de baixa confiança — nunca uma
média que concilia silenciosamente).

## Arquivos

`engines/valuation_v2/{constants,dcf,multiples,graham,reverse_dcf,engine}.py`,
`schemas/valuation_v2.py`, `services/valuation_v2_service.py`.

## UI (tela Ativos → "Análise Fundamentalista")

Para ações: badge de status + confiança, faixa mínima/base/máxima,
preço atual, margem de segurança (exigida vs. obtida), expectativa
implícita de mercado, Graham Number como checagem, cenários individuais
num expander, avisos e métodos usados. Ver
`docs/FUNDAMENTAL_ANALYSIS_UI.md` para a seção completa (inclui também
FII/REIT e ETF/cripto/Tesouro).

## Limitações conhecidas

- Premissas macro (`_MACRO_BY_CURRENCY`) são proxies fixos de longo
  prazo, não cotações ao vivo de taxa de juros — revisão manual
  periódica recomendada.
- DCF de 2 estágios não modela mudanças de margem, capex ou estrutura
  de capital ano a ano (mesma limitação de qualquer DCF didático).
- Múltiplos normalizados usam só o histórico do PRÓPRIO ativo, nunca
  pares do setor (dado não coletado).
- Beta ausente sempre cai para o beta de mercado (1.0) — nunca uma
  estimativa de beta específica da empresa.

## Por que "Dados insuficientes para estimar valor justo" acontece (Sprint 28)

Esse `reason` (linha 19 acima) não era acompanhado de nenhuma
explicação de QUAIS campos faltavam — o usuário via só a frase
genérica, mesmo sabendo que o ativo já tinha alguns fundamentos
coletados (caso real: `ALUP4.SA`, com ROE preenchido mas FCF e
patrimônio líquido ausentes no Yahoo Finance). O Data Coverage Report
(`docs/DATA_COVERAGE_REPORT.md`) resolve isso: para qualquer ticker, a
finalidade `valuation` do relatório lista exatamente os campos que
faltam (`missing_labels`) dentre os 8 campos de snapshot usados por
esta engine (FCF, ações em circulação, dívida líquida, beta, LPA,
patrimônio líquido, P/L, P/VP) mais o histórico de crescimento. Esse
relatório aparece na tela Ativos junto da própria seção de valuation
("Dados usados e dados ausentes"), e o usuário tem agora um caminho
concreto para resolver a lacuna: a Importação Manual de Fundamentos
(`docs/MANUAL_FUNDAMENTALS_IMPORT.md`).
