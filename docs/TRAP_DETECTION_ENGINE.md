# Trap Detection Engine (Sprint 26, Fases 3-4)

## Objetivo e escopo declarado

Detecta padrões clássicos de "armadilha de valuation" — situações em
que uma leitura ingênua de um único múltiplo (P/L baixo = barato, P/VP
baixo = barato, DY alto = renda boa) pode estar enganosa dado o resto
do quadro fundamentalista. Cada flag documenta o que foi observado
(`affected_metric`, `explanation`), o quão sério é (`severity`), como
isso deveria pesar na leitura do score/confiança (`impact_on_score`) e
o que vale a pena investigar (`recommended_interpretation` — sempre em
termos de "investigar", nunca "vender"/"comprar"). **Nenhum detector
decide compra/venda**; cada um só descreve um padrão e devolve uma
penalidade de confiança que quem consome o resultado deve aplicar.

**Defesa central contra a regra ingênua**: nenhum múltiplo baixo
isolado dispara um flag sozinho — sempre precisa de um segundo sinal
concordando (ex.: P/L baixo + lucro em queda, nunca P/L baixo
sozinho). Essa é a regra que a especificação da sprint proíbe
explicitamente de violar.

## Escopo por classe de ativo

`_APPLICABLE_ASSET_CLASSES = ("stock", "fii", "reit")`. Ações usam os 5
detectores da Fase 3; FIIs/REITs usam os 2 detectores da Fase 4 —
**nunca** os detectores de ações, que dependem de conceitos (P/L, DCF)
que não se aplicam a fundos/REITs. ETF, cripto e Tesouro Direto ficam
fora de escopo (sem valuation tradicional — ver
`docs/PORTFOLIO_ADEQUACY_ENGINE.md`), devolvendo `reason` explícito.

## Arquitetura

```
TrapDetectionService (banco <-> engine)
    -> busca snapshot mais recente + FundamentalsAnalysisResult (CAGR)
       + ValuationV2Result (ações) ou IncomeRealEstateAnalysisResult (FII/REIT)
    -> TrapDetectionEngine.evaluate(...)  # puro, sem I/O
        -> detectors.py  (7 funções puras, uma por flag)
        -> thresholds.py (limiares isolados e documentados)
```

## Os 7 flags nomeados

### Ações (Fase 3)

**1. Armadilha do P/L baixo** (`low_pe_trap`) — P/L abaixo de `8` (não
basta sozinho) **e** (lucro líquido em CAGR negativo **ou** margem
líquida piorando ao longo do histórico). Severidade alta se os dois
sinais concordarem, média se só um.

**2. Armadilha do P/VP baixo** (`low_pb_trap`) — P/VP abaixo de `1,0`
**e** ROE abaixo de `5%`. Severidade alta se ROE negativo, média caso
contrário.

**3. Crescimento supervalorizado** (`growth_overpriced_trap`) —
diferença entre o crescimento implícito no preço atual (reverse DCF do
Valuation Engine 2.0) e o crescimento histórico real do próprio ativo
acima de `8pp` (média) ou `15pp` (alta). O mercado está "comprando a
história", não os números já entregues.

**4. Alavancagem elevada** (`leverage_trap`) — dívida líquida/EBITDA
acima de `4x` **ou** cobertura de juros abaixo de `2x`. Severidade alta
se os dois concordarem, ou se dívida/EBITDA `> 6x`, ou se cobertura
`< 1x`.

**5. Dado insuficiente para confiança** (`data_quality_trap`) —
cobertura de fundamentos abaixo de `50%` **ou** menos de `2` períodos
de histórico disponíveis. Severidade alta se cobertura `< 30%`.

### FIIs/REITs (Fase 4)

**6. Dividend Yield muito alto** (`high_dy_trap`) — DY anual acima de
`12%` (média) ou `18%` (alta). DY muito alto isolado nunca é conclusão
de "renda boa" — pode refletir queda de preço recente, distribuição
pontual de capital não recorrente, ou insustentabilidade.

**7. Pico de yield não recorrente** (`fii_yield_trap`) — razão entre o
DY do período mais recente e a média histórica do PRÓPRIO ativo acima
de `1,4x` (média) ou `1,8x` (alta). Reaproveita
`dy_own_history_average` já calculado pela Análise de Renda Imobiliária
(`docs/INCOME_REAL_ESTATE_ANALYSIS.md`) — nunca recalcula essa média
aqui.

## Penalidade de confiança

Cada severidade tem uma penalidade fixa (`CONFIDENCE_PENALTY_BY_SEVERITY`,
`schemas/trap_detection.py`):

| Severidade | Penalidade |
|---|---|
| baixa | 0,05 |
| média | 0,10 |
| alta | 0,20 |

`confidence_penalty` do resultado é a **soma** das penalidades de
todos os flags ativos, capada em `1,0` (nunca reduz a confiança abaixo
de zero na origem — quem consome subtrai isso da confiança existente e
já clampa em zero, ver `docs/DECISION_ENGINE_3.md`).

## Arquivos

`engines/trap_detection/{thresholds,detectors,engine}.py`,
`schemas/trap_detection.py`, `services/trap_detection_service.py`.

## Integração com o Decision Engine 3.0

Ver `docs/DECISION_ENGINE_3.md`, seção "Sprint 26, Fase 6" — a
penalidade de confiança é subtraída de `DecisionInput.confidence` na
origem (dentro do serviço), então o mecanismo já existente de
"confiança baixa reduz score" propaga o efeito automaticamente, sem
peso novo na fórmula de score.

## UI (tela Ativos → "Análise Fundamentalista")

Flags exibidos com badge de severidade, explicação e "como interpretar"
— sempre abaixo do bloco de valuation/análise específico da classe. Ver
`docs/FUNDAMENTAL_ANALYSIS_UI.md`.

## Limitações conhecidas

- Limiares são heurística MVP própria, não calibrada por setor nem
  estatisticamente — mesma natureza das bandas do Valuation Engine v1.
- Cada detector roda de forma independente; não há combinação
  ponderada entre flags além da soma simples de penalidade (capada em
  1,0).
- FIIs/REITs não recebem os 5 detectores de ações mesmo quando algum
  conceito seria tecnicamente aplicável (ex.: alavancagem de um FII de
  papel) — decisão deliberada de manter o escopo estrito por classe
  nesta fase.
