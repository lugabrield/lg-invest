# Post-Allocation Constraints Engine (Sprint 29)

## O bug

Um teste extremo relatado pelo usuário: simular um aporte de **R$ 1.000.000**
numa carteira de aproximadamente **R$ 40.000**, com o máximo de exposição em
USD configurado em **60%**. O resultado foi:

```
Patrimônio antes:            ~R$ 40.365
Patrimônio depois:           ~R$ 1.040.365
Exposição internacional depois: 97,23%
```

97,23% de exposição em USD, com o máximo configurado em 60%. A política foi
completamente ignorada.

### Causa raiz

O Decision Engine v3 tinha duas camadas de proteção contra concentração, e
nenhuma das duas via o problema:

1. `eligibility.py` (`filter_eligible_v3`) só verificava se um ativo/dimensão
   já estava sobreconcentrado **antes** do aporte. Se USD estava em 28,7%
   (abaixo do máximo de 60%), nada bloqueava a entrada.
2. `allocation.py` (`select_and_distribute`) limitava cada ativo a uma
   fração **do próprio aporte** (`max_single_weight=50%`), nunca a uma
   fração do patrimônio resultante. Um aporte grande o suficiente sempre
   conseguia estourar qualquer limite configurado, porque nenhuma das duas
   camadas simulava o peso **depois** de somar o aporte ao patrimônio atual.

## A correção

Um novo motor puro, `backend/app/engines/decision/post_allocation.py`, roda
**depois** que `select_and_distribute` já decidiu a distribuição inicial e
**antes** de a recomendação ser retornada. Ele simula o patrimônio depois do
aporte e corta proporcionalmente qualquer dimensão (classe, moeda, país,
ativo ou exposição internacional) que ultrapassaria seu máximo configurado.

### Fórmula (pedida explicitamente pelo usuário)

```
portfolio_value_after      = portfolio_value_before + contribution_amount
dimension_value_before     = dimension.current_weight * portfolio_value_before
max_dimension_value_after  = dimension.max_weight * portfolio_value_after
room                        = max(0, max_dimension_value_after - dimension_value_before)
```

`room` é o valor em R$ que ainda cabe naquela dimensão sem ultrapassar o
máximo configurado. Se a soma do que `select_and_distribute` já havia
decidido alocar para os ativos daquela dimensão exceder `room`, todos os
ativos do grupo são cortados proporcionalmente (`scale = room / group_total`).

### Exemplo (o cenário relatado)

USD atual = 28,7%, máximo = 60%, aporte = R$ 1.000.000, patrimônio = R$ 40.000:

```
portfolio_value_after     = 40.000 + 1.000.000 = 1.040.000
dimension_value_before    = 0,287 * 40.000 = 11.480
max_dimension_value_after = 0,60 * 1.040.000 = 624.000
room                       = 624.000 - 11.480 = 612.520
```

Se `select_and_distribute` havia decidido alocar R$ 500.000 em cada um de
dois ETFs americanos (R$ 1.000.000 total em USD), o motor corta
proporcionalmente para R$ 306.260 em cada um (total R$ 612.520) — o peso
resultante de USD fecha em **exatamente 60,0%**, nunca mais 97,23%. Os
R$ 387.480 restantes ficam **não alocados**.

### Precedência de limites

Mesma regra já estabelecida em `eligibility.py::filter_eligible_v3` (Sprint
25, Parte 1): quando existe uma **regra detalhada** do Target Allocation
Rule Engine v2 com `max_weight` para uma dimensão, ela é a fonte de verdade
— a Investment Policy nunca é consultada para essa MESMA dimensão. A
Investment Policy só entra como *fallback* para as combinações que ela
cobre hoje: peso por ativo (`max_asset_weight`), classe `crypto`
(`max_crypto_weight`) e classe `fii` (`target_fii_max`). Exposição
internacional é sempre um limite da Investment Policy
(`target_international_max`) — não existe uma 5ª dimensão detalhada
equivalente.

### Por que "cortar e deixar sem alocar" em vez de redistribuir

Pedido explícito do usuário: **"Não forçar alocação só para chegar em
100%."** Quando uma dimensão bate no limite, o motor reduz a alocação
daquela dimensão ao teto e para por aí — não tenta empurrar o valor cortado
para outro ativo. Se não houver espaço elegível suficiente no restante da
carteira, parte do aporte fica genuinamente sem sugestão, e o motivo é
sempre explicado (nunca um corte silencioso).

### Alertas de aporte grande/extremo

Além do corte em si, `recommend_v3` compara o valor do aporte com o
patrimônio atual e adiciona um alerta textual **antes** de o usuário ler a
distribuição:

- Aporte > 25% do patrimônio atual: "Este aporte é grande em relação ao
  patrimônio atual. A recomendação foi limitada por regras de alocação
  pós-aporte."
- Aporte > 100% do patrimônio atual: "Aporte maior que a carteira atual. A
  simulação muda drasticamente a alocação e pode exigir uma estratégia de
  entrada gradual."

## Onde isso aparece

### `RecommendationResult.capped_dimensions`

Novo campo em `schemas/recommendation_result.py` — lista de
`CappedDimensionResult` (dimension_type, dimension_key, label, weight_before,
weight_after, max_weight, source), uma entrada por dimensão que precisou de
corte. Vazio quando `recommend_v3` roda sem `portfolio_value_before` (nenhuma
simulação pós-aporte disponível) ou quando nenhuma dimensão bateu no limite.

### `RecommendationResult.alerts`

Os motivos de cada corte (texto legível, ex.: *"moeda 'USD' atingiria 60,0%
da carteira após o aporte, acima do limite máximo de 60,0% (regra detalhada
de alocação-alvo) — parte do aporte para ativo(s) dessa dimensão não foi
alocada. Nenhuma venda é sugerida."*) são anexados aos alertas já existentes
da recomendação — mesma disciplina do resto do Decision Engine: nunca um
bloqueio sem explicação.

### Tela Aporte — "Limites pós-aporte atingidos" e "Saldo não alocado"

`frontend/streamlit_app/pages_impl/aporte.py` ganhou duas seções novas,
visíveis sempre que `result.capped_dimensions` não está vazio (mesmo quando
`result.items` fica vazio, se toda a alocação de uma dimensão foi zerada):

- **Limites pós-aporte atingidos**: tabela com dimensão, item, peso atual,
  peso depois do aporte, limite máximo, origem do limite e status
  ("Limite atingido" / "Dentro do limite").
- **Saldo não alocado**: valor alocado vs. não alocado, com o motivo
  (quais dimensões impediram alocar o restante) e a recomendação de
  considerar entrada gradual ou revisar os limites configurados.

## Escopo

Só `recommend_v3` (Decision Engine 3.0) recebe o corte pós-aporte — `recommend`
(v1) e `recommend_v2` continuam inalterados, já que só o v3 recebe
`policy`/`aggregates`/`portfolio_value_before` do `DecisionService`.
`portfolio_value_before` é opcional (`Decimal | None = None`): quando o
chamador não tem esse dado disponível, a simulação pós-aporte simplesmente
não roda — o motor nunca inventa um patrimônio para simular a restrição.

## Testes

- `backend/tests/unit/test_post_allocation_constraints.py` — engine pura,
  números exatos calculados à mão (cenários 3-8 e 13 da especificação).
- `backend/tests/unit/test_decision_service_v3_post_allocation.py` —
  ponta-a-ponta via `DecisionService.recommend_v3` (cenários 1, 2, 3, 9, 10,
  11 e 12), verificando invariantes (nunca ultrapassar o limite, nunca
  sugerir venda, sempre explicar um corte) já que os pesos exatos dependem
  do câmbio USD/BRL configurado e do LG Score calculado a partir do
  histórico de preços.

Ver `CHANGELOG.md` `[1.35.0]` para a lista completa de arquivos alterados.
