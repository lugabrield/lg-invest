# Data Coverage Report (Sprint 28)

## Por que este relatório existe

A Central de Dados (Sprint 27) resolveu "como atualizar dados", mas não
"por que a Análise Fundamentalista continua com confiança baixa depois
de atualizar". Um caso real: `ALUP4.SA` — depois de rodar "Fundamentos
da carteira" — continuava mostrando "Valuation Indeterminado, Confiança
baixa, Dados insuficientes para estimar valor justo". A causa não era
bug de cálculo: era falta real de dado. O Yahoo Finance simplesmente
não cobre alguns campos para vários tickers brasileiros (comum em
ações de segunda linha), e nada na plataforma explicava isso — o
usuário só via "confiança baixa" sem saber o que faltava, de onde
viria, ou se dava para consertar.

O Data Coverage Report responde, para qualquer ativo cadastrado:
quais dados fundamentais existem, quais faltam, de onde vieram e
quando foram atualizados, e o quanto essa cobertura permite calcular
cada análise da plataforma — nunca um "confiança baixa" genérico.

## Onde ele mora

- **Engine puro**: `backend/app/engines/data_coverage/engine.py` +
  `thresholds.py` — só recebe dados já buscados e devolve o relatório;
  nunca acessa o banco nem chama um provider.
- **Serviço (ponte com o banco)**:
  `backend/app/services/data_coverage_service.py` —
  `DataCoverageService(db).evaluate_ticker(ticker)` busca o histórico
  real de `FundamentalSnapshot`, roda o Fundamentals Engine (mesma peça
  usada pelo Valuation Engine 2.0) para obter os CAGRs, e devolve um
  `DataCoverageResult` ou `None` se o ticker não estiver cadastrado.
- **Schemas**: `backend/app/schemas/data_coverage.py` —
  `FieldAvailability`, `CoveragePurposeScore`, `DataCoverageResult`,
  e a função `most_missing_fields()` usada pelo resumo da Central de
  Dados.

## Parte 1 — Disponibilidade campo a campo

`DataCoverageResult.fields` é uma lista de `FieldAvailability`, uma
por campo do relatório completo (`REPORT_SNAPSHOT_FIELDS` +
`REPORT_SYNTHETIC_FIELDS` em `thresholds.py`):

- 19 campos fundamentalistas "de snapshot" (market cap, receita, lucro
  líquido, EBITDA, EBIT, FCF, dívida líquida, dívida total, caixa,
  patrimônio líquido, ROE, ROIC, margem líquida, margem operacional,
  P/L, P/VP, EV/EBITDA, dividend yield, payout).
- 4 campos "sintéticos" (não são uma coluna única do banco, são
  derivados): preço atual, histórico de preço (≥ 2 pontos), histórico
  de dividendos (≥ `MIN_PERIODS_FOR_OWN_HISTORY` períodos com dividend
  yield preenchido), histórico de crescimento (algum CAGR calculado
  pelo Fundamentals Engine).

Cada `FieldAvailability` traz `available` (bool), `value` (quando
disponível), `source` (a `FundamentalSnapshot.source` real: `"yahoo"`
ou `"manual_import"` — nunca inventado), e `updated_at` (o
`collected_at` real do snapshot). Um campo ausente nunca vira `0` ou
`"N/A"` fabricado — `value` fica `None` e `available=False`.

## Parte 2 — Score de completude por finalidade (0-100)

`DataCoverageResult` também expõe um `CoveragePurposeScore` por
finalidade — **cada grupo de campos espelha deliberadamente o que a
engine consumidora de fato usa**, nunca uma lista reimplementada à
parte (ver comentário em `thresholds.py`):

| Finalidade | Classes aplicáveis | Campos considerados | Espelha |
|---|---|---|---|
| `quality` | as mesmas de `QualityEngine` | roe, net_margin, debt_to_ebitda | `engines/quality/thresholds.py::QUALITY_BANDS` |
| `valuation` | `stock` | FCF, ações em circulação, dívida líquida, beta, LPA, patrimônio líquido, P/L, P/VP + histórico de crescimento | `engines/valuation_v2/engine.py` |
| `trap_detection` | `stock`, `fii`, `reit` | (ações) P/L, P/VP, ROE, Dívida/EBITDA, cobertura de juros; (FII/REIT) apenas Dividend Yield + histórico ≥ 2 períodos | `engines/trap_detection/*` |
| `income` | `fii`, `reit` | P/VP, Dividend Yield + histórico de DY | `engines/income_real_estate/*` |
| `decision_engine` | qualquer classe com ao menos uma finalidade aplicável | média simples dos scores aplicáveis (valuation/trap_detection/income) | Decision Engine v3 |

Classificação por faixa de score (`classify_score`,
`SCORE_SUFFICIENT=70`, `SCORE_PARTIAL=30`):

- **suficiente** — score ≥ 70.
- **parcial** — 30 ≤ score < 70.
- **insuficiente** — score < 30.
- **não aplicável** — a classe do ativo está fora do escopo dessa
  finalidade (ex.: `valuation` para um ETF). `score` fica `None`
  nesse caso — nunca um `0` fabricado para algo que nem deveria
  existir para essa classe.

`missing_labels` lista, em português, exatamente o que falta para
aquela finalidade — nunca só "dados insuficientes".

## Dados desatualizados reduzem a confiança do Decision Engine

Novidade desta sprint: um snapshot de fundamentos com `collected_at`
mais antigo que `STALE_DATA_THRESHOLD_DAYS = 400` dias (~13 meses —
folga sobre o ciclo anual normal de balanços) faz o score do
`decision_engine` ser multiplicado por `STALE_DATA_SCORE_FACTOR =
0.85`, e o motivo passa a dizer explicitamente "dados desatualizados
há X dias (confiança reduzida)". Antes desta sprint, um dado de dois
anos atrás era tratado exatamente igual a um dado de ontem — nada
modelava a idade do dado. `stale_days` é calculado só quando existe
um snapshot com `collected_at` real; nunca uma idade inventada para um
ativo sem dado algum.

## Resumo textual (`summary`)

`DataCoverageResult.summary` é uma frase pronta, ex.: `"Valuation:
insuficiente (38%) — faltam: FCF (fluxo de caixa livre), Patrimônio
líquido, Histórico de receita/lucro/FCF (para taxa de crescimento).
Trap Detection: parcial (60%) — faltam: Cobertura de juros."` —
montada concatenando as finalidades aplicáveis, sempre a partir dos
mesmos dados de `fields`/`missing_labels`, nunca um texto solto
independente do restante do relatório.

## Como consultar um relatório

```python
from backend.app.services.data_coverage_service import DataCoverageService

result = DataCoverageService(db).evaluate_ticker("ALUP4.SA")
if result is None:
    ...  # ticker não cadastrado
else:
    result.summary                    # frase pronta
    result.missing_field_labels       # todos os campos ausentes (Parte 1)
    result.valuation.classification   # "insuficiente" / "parcial" / "suficiente" / "não aplicável"
    result.valuation.missing_labels   # o que falta especificamente para valuation
```

## Onde este relatório aparece

- **Tela Ativos** → seção "Análise Fundamentalista" → bloco "Dados
  usados e dados ausentes" (ver `docs/FUNDAMENTAL_ANALYSIS_UI.md`).
- **Central de Dados** (Dashboard) → resumo de execução do botão
  "Fundamentos da carteira" (ver `docs/DATA_REFRESH_CENTER.md`).
- **Decision Engine v3** → avisos explícitos de baixa cobertura, com
  penalidade de confiança real (ver `docs/DECISION_ENGINE_3.md` e a
  seção "Data quality no Decision Engine" abaixo).

## Data quality no Decision Engine

Antes desta sprint, cobertura de dado insuficiente só se refletia
indiretamente (via Trap Detection ou ausência de faixa de valuation).
Agora, `DecisionService` consulta o Data Coverage Report de cada
ticker e, quando `decision_engine.score < SCORE_SUFFICIENT (70)`,
aplica uma penalidade de confiança real:

- score < 30 (insuficiente): `_COVERAGE_INSUFFICIENT_CONFIDENCE_PENALTY
  = 0.10`.
- 30 ≤ score < 70 (parcial): `_COVERAGE_PARTIAL_CONFIDENCE_PENALTY =
  0.05`.

Essas penalidades foram calibradas para bater com a escala já usada
pelo Trap Detection Engine (`CONFIDENCE_PENALTY_BY_SEVERITY`: baixa
0.05 / média 0.10 / alta 0.20) — cobertura insuficiente ≈ trap de
severidade média, cobertura parcial ≈ trap de severidade baixa. O
aviso gerado é sempre explícito, ex.: `"ALUP4.SA tem cobertura de
dados fundamentais insuficiente (38%) — faltam: FCF (fluxo de caixa
livre), Patrimônio líquido, P/L, P/VP, Beta. Score reduzido por baixa
cobertura de dados."` — nunca mais um "confiança baixa" sem explicação.

## Limitações conhecidas

- O relatório reflete o que está salvo no banco no momento da consulta
  — ele não busca dado novo sozinho (isso é papel da Central de
  Dados/importação manual).
- Os grupos de campos por finalidade são um espelho best-effort do que
  cada engine usa hoje; se uma engine mudar seus campos no futuro, os
  grupos em `thresholds.py` precisam ser atualizados junto (não há
  verificação automática de sincronismo entre os dois lugares).
- `STALE_DATA_THRESHOLD_DAYS`/`STALE_DATA_SCORE_FACTOR` são heurísticas
  MVP, não calibradas estatisticamente — mesmo espírito dos demais
  limiares do projeto (documentado no próprio `thresholds.py`).
