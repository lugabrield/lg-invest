# Decision Engine 3.0 (Sprint 24, Fase 4)

## Contexto

O Decision Engine 2.0 (Sprint 18) já combinava LG Score, confiança de dado e
proximidade de meta de classe para sugerir aportes. A Fase 4 adiciona uma
terceira versão, `recommend_v3()`, que amplia o score para múltiplos fatores
independentes e passa a consumir a Investment Policy e o Target Allocation
Rule Engine v2 (Fase 3) como fonte de bloqueio e de bônus — sem alterar
`recommend()` (v1) nem `recommend_v2()`, que continuam existindo e sendo
usados exatamente como antes. As três versões coexistem como funções
separadas em `engines/decision/engine.py`.

## Fórmula do score

```
score_v3 = [ W_FUND * fundamentals_norm
           + W_ALLOC * allocation_bonus
           + W_CONC * concentration_inverted
           + W_INTL * international_bonus ] * confidence
```

Pesos (`engines/decision/scoring.py`):

| Peso | Valor | Fator |
|---|---|---|
| `W_FUND_V3` | 0.40 | Fundamentos (qualidade/valuation/growth/risco) |
| `W_ALLOC_V3` | 0.25 | Bônus de alocação-alvo (Target Allocation Rule Engine v2) |
| `W_CONC_V3` | 0.20 | Concentração invertida (mesmo fator do v1/v2: quanto menor o peso atual, maior o bônus) |
| `W_INTL_V3` | 0.15 | Bônus de exposição internacional |

Os quatro pesos somam 1.0 antes do multiplicador de confiança.

## Fundamentos: cadeia de fallback em 3 níveis

A engine nunca inventa dado. `_fundamentals_norm_v3` tenta, em ordem:

1. **Pilares individuais** (`quality_score`, `valuation_score`,
   `growth_score`, `risk_score` — todos 0..100, "maior é melhor", vindos de
   `ConvictionScoreResult` do IDS Methodology): usa a média dos 4, se todos
   presentes.
2. **LG Conviction Score v2** (`conviction_score`, já um blend dos pilares):
   usado se os pilares individuais não estiverem disponíveis.
3. **LG Score** (`lg_score`, o fundamento mais antigo/simples do projeto):
   último recurso, se nem os pilares nem o conviction score existirem.

Qual nível foi usado fica sempre registrado em `reasons` (ex.: "fundamentos
(média de 4 pilares)", "LG Conviction Score", "LG Score"), nunca escondido.

## Bônus de alocação-alvo (multi-dimensão)

Cada candidato pode trazer zero ou mais `AllocationRuleSignal` (espelho
pontual de uma `AllocationRuleEvaluation` do Target Allocation Rule Engine
v2, resolvido pelo `DecisionService`, nunca pela engine). Regras:

- Só sinais com `gap_status == "underweight"` contribuem — `overweight`,
  `neutral` e `blocked` nunca aumentam o bônus (blocked, aliás, impede o
  candidato de ser elegível — ver seção de bloqueio abaixo).
- Quando há mais de uma dimensão underweight para o mesmo candidato (ex.:
  classe E moeda), usa-se a de maior `contribution_priority`.
- `contribution_priority` satura em 20 pontos (`_ALLOC_PRIORITY_SATURATION_V3`)
  antes de normalizar para a escala 0..1 do bônus — evita que uma prioridade
  manual desproporcional (definida pelo usuário na regra) distorça o peso
  relativo dos outros 3 fatores do score.

## Bônus de exposição internacional

- Zero para ativos nacionais (`is_international=False`) — nunca há bônus
  por ser doméstico nem penalidade por ser internacional.
- Zero sem `PolicyLimits.target_international_min` configurado — a engine
  não assume uma meta que o usuário não definiu.
- Aplica-se apenas quando o ativo é internacional **e** o peso
  internacional agregado da carteira (`PortfolioAggregates.international_weight`)
  está abaixo da meta mínima configurada. Se a carteira já está dentro da
  meta, o bônus é zero mesmo para ativos internacionais.

## Escala pela confiança do dado

Novidade real desta versão (v1/v2 apenas alertavam sobre baixa confiança,
nunca alteravam o score em si): `score = raw_score * data.confidence`.
Implementa literalmente a regra "se confiança baixa, reduzir score" — com
`confidence=0`, o score final é sempre `0`, não importa quão bons sejam os
outros fatores.

## Bloqueio (`filter_eligible_v3`)

Aplicado **em cima** do filtro v1 inalterado (`filter_eligible`: bloqueio
manual do usuário + sobreconcentração via `over_concentration_limit`).
Camadas adicionais, todas opcionais (a engine funciona normalmente sem
`policy`/`aggregates`, simplesmente sem aplicar essas checagens):

1. **Por ativo**: `current_weight > policy.max_asset_weight`.
2. **Por classe agregada**: `asset_class == "crypto"` com
   `aggregates.crypto_weight > policy.max_crypto_weight`, ou
   `asset_class == "fii"` com `aggregates.fii_weight > policy.target_fii_max`
   — nota: usa o peso agregado da **carteira inteira** nessa classe, não o
   peso do ativo isolado.
3. **Por sinal de regra**: qualquer `AllocationRuleSignal` com
   `gap_status == "blocked"` (Target Allocation Rule Engine v2).

### Regra de ouro: nunca recomendar venda

Testada explicitamente (`test_never_recommends_sell_even_when_blocked`,
`test_recommend_v3_end_to_end_never_suggests_sell`,
`test_recommend_v3_never_mentions_selling`): todo bloqueio impede **apenas**
que o ativo receba um novo aporte nesta rodada. Nenhum caminho de código do
Decision Engine 3.0 gera, sugere ou aciona uma recomendação de venda — as
mensagens de bloqueio dizem explicitamente "não é recomendação de venda" /
"Nenhuma venda é recomendada — apenas pausa de aporte", e os testes
verificam que a palavra "vender" nunca aparece em `explanation`, `alerts`
ou nos motivos de `ignored`.

## Engines puras, impureza isolada no serviço

`PolicyLimits` e `PortfolioAggregates` (`engines/decision/inputs.py`) são
dataclasses congeladas que espelham pontualmente `InvestmentPolicy` e
agregados de carteira — a engine nunca importa ORM, schemas de dashboard ou
faz consulta a banco. Toda resolução impura (leitura de `InvestmentPolicy`,
soma de pesos por classe/país) acontece em
`DecisionService._policy_limits_and_aggregates()`, mantendo a regra do
projeto "engines continuam puras".

## Serviço (`DecisionService`)

- `build_inputs_v3(portfolio_id)`: monta os `DecisionInput` a partir de
  `PortfolioService`, `LGScoreService`, `ConvictionScoreService` (lendo os
  pilares direto de `ConvictionScoreResult`) e
  `TargetAllocationService.evaluate_portfolio_rules()` (convertido em
  `AllocationRuleSignal` por candidato, cruzando `AssetRepository` para
  país/moeda).
- `_policy_limits_and_aggregates(portfolio_id)`: resolve os limites via
  `InvestmentPolicyService.get_or_create()` e os agregados somando pesos de
  `build_dashboard_view()` por classe/país.
- `recommend_v3(portfolio_id, amount, ...)`: monta inputs + limites,
  chama a engine pura, persiste o resultado com
  `MODEL_VERSION_V3 = "decision_v3"` (auditável, sem sobrescrever
  recomendações de v1/v2 já salvas).

## Exposição na UI (Fase 9)

A tela **Aporte** expõe um seletor "Motor de recomendação" (v1/v2/v3) —
escolher v3 chama `recommend_v3()` e reaproveita a mesma tabela de
distribuição/justificativa por ativo já usada para v1/v2 (o schema
`RecommendationItem` já tinha `conviction_score`/`item_confidence`
populados por v3, sem necessidade de UI dedicada). O texto de ajuda do
seletor reitera que nenhuma versão jamais recomenda venda, apenas pausa
aporte.

## O que ainda não existe

Nenhuma tela mostra a evolução de `recommend_v3()` ao longo do tempo
(histórico de recomendações v3 vs. v1/v2) — só o resultado da última
chamada.
