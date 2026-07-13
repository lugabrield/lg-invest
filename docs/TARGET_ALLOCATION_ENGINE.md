# Target Allocation Engine v2 (Sprint 24, Fase 3)

## Contexto

A Sprint 17 introduziu o `TargetAllocationEngine` (v1): comparação simples
entre alocação atual e meta, **só por classe de ativo**, armazenada em JSON
(`data/app_settings.json`, chave `"target_allocation"`, via
`target_allocation_settings_service.py`). Isso resolveu o caso mais comum,
mas deixou de fora três dimensões importantes que o usuário explicitamente
pediu: moeda, país e ativo individual.

A Fase 3 adiciona uma segunda engine, `TargetAllocationRuleEngine` (v2),
**sem remover ou alterar a v1**. As duas convivem: telas e códigos que já
usam `TargetAllocationEngine.compare()` continuam funcionando exatamente
como antes.

## Por que duas engines em vez de estender a v1

- A v1 usa um `dict[str, Decimal]` simples (classe → peso). Generalizar
  isso para 4 dimensões exigiria mudar a assinatura e o schema de saída,
  quebrando quem já consome `TargetAllocationResult`.
- O Decision Engine 2.0 e o Dashboard atual dependem do formato da v1.
  Trocar por baixo dos panos violaria a regra de segurança do projeto:
  "nunca fazer replace inseguro" / "engines continuam puras e estáveis".
- A v2 cobre um caso de uso mais rico (peso mínimo, prioridade manual,
  status "blocked" para limite duro) que não faz sentido forçar na v1.

## As 4 dimensões

```python
TARGET_ALLOCATION_DIMENSIONS = ("class", "currency", "country", "asset")
```

Cada regra (`TargetAllocationRule`, tabela `target_allocation_rules`) vale
para **uma dimensão só**. Nunca existe uma regra que misture, por exemplo,
"classe FII" com "moeda USD" na mesma linha — isso é reforçado tanto no
schema (dimension_type + dimension_key) quanto na engine, que agrupa
avaliações por dimensão via `TargetAllocationEvaluation.by_dimension(...)`.

Exemplos de `dimension_key` por dimensão:

| dimension_type | dimension_key (exemplos) |
|---|---|
| `class` | `stock`, `fii`, `etf`, `reit`, `crypto`, `bond` |
| `currency` | `BRL`, `USD` |
| `country` | `BR`, `US` |
| `asset` | `VOO`, `WEGE3.SA`, `HGLG11.SA` |

## Nenhuma regra é pré-cadastrada

A tabela `target_allocation_rules` começa **vazia** para toda carteira nova.
O `TargetAllocationRuleService.set_rule(...)` não roda nunca automaticamente
— só quando o usuário explicitamente salva uma regra na tela de
Configurações. Isso segue a mesma regra da v1 ("nunca inventar uma alocação
recomendada") e a regra geral do projeto de nunca fabricar dado.

Importante: os campos de `investment_policy` (ex.: `target_brazil_equity`,
`target_us_equity`) **não são copiados automaticamente** para
`target_allocation_rules`. Foi uma decisão deliberada desta sprint — mapear
"classe" para "país" de forma automática seria ambíguo (uma ação americana
listada via BDR na B3 é "classe stock, país US, moeda BRL", por exemplo) e
inventaria uma regra que o usuário não pediu explicitamente. Se o usuário
quiser essas metas refletidas como regras granulares, ele cadastra
manualmente em Configurações.

## Os 4 status (`GAP_STATUSES`)

```python
GAP_STATUSES = ("underweight", "neutral", "overweight", "blocked")
```

- **underweight**: peso atual abaixo da meta, além da tolerância de
  rebalanceamento (`rebalance_threshold`, default 3% se não especificado
  por chamada). Candidato a receber o próximo aporte.
- **neutral**: dentro da tolerância em torno da meta (ou sem meta
  configurada, só com `max_weight`, e ainda abaixo dele).
- **overweight**: acima da meta, mas ainda **abaixo** do peso máximo (se
  houver). Recomendação: pausar novos aportes ali, nunca vender.
- **blocked**: peso atual **ultrapassou o peso máximo configurado**. Aporte
  bloqueado nesta dimensão (o Decision Engine 3.0, na Fase 4, vai usar isso
  como regra de bloqueio real).

## Regra de ouro: nunca recomendar venda

Este é o ponto mais importante da engine, e está testado explicitamente em
`test_target_allocation_rule_engine.py`:

- `contribution_priority` é sempre `0` (nunca positivo) para os status
  `overweight` e `blocked` — a engine nunca "recomenda" um ativo já acima
  da meta para receber mais aporte, mas também nunca sugere reduzir a
  posição existente.
- A mensagem de alerta (`alert_message`) para `overweight` usa
  explicitamente a frase "não vender" e explica que a estratégia Buy and
  Hold prioriza não piorar a concentração, não reduzir posições.
- Mesmo em `extreme_overweight` (peso atual > 1.5x o peso máximo
  configurado — `EXTREME_OVERWEIGHT_MULTIPLIER = Decimal("1.5")`), a
  engine só torna a mensagem mais enfática ("considere revisar
  manualmente"); em nenhum caminho de código a engine gera uma ação de
  venda.

Isso implementa literalmente a instrução do usuário: *"Nunca forçar venda
como recomendação padrão (...) priorizar 'não aportar' em vez de 'vender',
exceto se passar limites extremos"* — e mesmo no caso extremo, o que muda é
só o texto do alerta, nunca uma ação automática.

## Prioridade de aporte (`contribution_priority`)

Calculada em `_contribution_priority()`:

- `0` para `overweight`/`blocked` (nunca prioriza).
- Para `underweight`: soma um "bônus de magnitude" (gap em pontos
  percentuais inteiros, ex.: 7 pontos de gap → +7) à `priority` manual que
  o usuário definiu ao cadastrar a regra. Isso permite que o usuário
  desempate manualmente entre duas dimensões igualmente underweight (ex.:
  "prefiro sempre priorizar FIIs sobre ETFs quando os dois estiverem
  underweight, mesmo que o gap seja parecido").
- Para `neutral` sem gap: usa só a `priority` manual.

## Schemas

`backend/app/schemas/target_allocation.py`:

- `AllocationClassDrift` / `TargetAllocationResult` — v1, inalterados.
- `AllocationRuleEvaluation` — avaliação de uma regra (uma dimensão/chave).
- `TargetAllocationEvaluation` — resultado agregado, com o helper
  `by_dimension(dimension_type)` para a UI renderizar seções separadas por
  classe/moeda/país/ativo.

## Serviço

`TargetAllocationService.evaluate_portfolio_rules(portfolio_id)` (novo,
convive com `evaluate_portfolio()` da v1):

1. Lê as regras salvas via `TargetAllocationRuleRepository`.
2. Calcula os pesos atuais por dimensão via `_current_weights_by_dimension`
   — usa `build_dashboard_view()` (já com conversão de câmbio) para pesos
   por classe/ativo/moeda, e `AssetRepository.get_by_ticker()` para
   descobrir o país de cada ativo.
3. Chama `TargetAllocationRuleEngine.evaluate()` (pura, sem banco/rede).

## Onde é editado

Tela Configurações → seção "Alocação-alvo detalhada (classe / moeda / país
/ ativo)": lista as regras existentes em tabela, permite adicionar/editar
(upsert por `portfolio_id + dimension_type + dimension_key`) e remover.
Validações (`TargetAllocationRuleService.set_rule`): `dimension_type` tem
que ser um dos 4 valores válidos, `dimension_key` não pode ser vazio, pesos
não podem ser negativos, `min_weight <= max_weight` e
`target_weight <= max_weight`.

## Precedência sobre a Investment Policy (Sprint 25, Parte 1)

Desde a Fase 4, o Decision Engine 3.0 consome `evaluate_portfolio_rules()`
tanto para bônus de aporte (dimensão underweight) quanto para bloqueio
(`gap_status == "blocked"`). A Investment Policy (`max_asset_weight`,
`max_crypto_weight`, `target_fii_max`) também define limites, de forma
independente. Na Sprint 25 corrigimos um bug de precedência: quando as
duas fontes tinham um limite configurado para a mesma dimensão (ex.:
`class=fii` com `max_weight=25%` aqui E `target_fii_max=15%` na política),
o Decision Engine 3.0 usava por engano o limite da política na mensagem
de bloqueio, mesmo esta regra (mais específica) devendo mandar.

A regra agora é: **esta engine (regra detalhada) sempre tem precedência**
sobre a Investment Policy para qualquer dimensão em que `max_weight`
esteja definido; a política só é usada como fallback quando não há
regra aqui para aquela dimensão. Ver `docs/DECISION_ENGINE_3.md` (seção
"Precedência entre regra detalhada e Investment Policy") para o detalhe
completo e os testes (`test_decision_limit_precedence.py`).

## O que ainda não existe

- Nenhum histórico de como `evaluate_portfolio_rules()` mudou ao longo do
  tempo — cada carregamento recalcula contra os pesos atuais, sem
  comparar com avaliações anteriores.

## Migration

Mesma migration de `investment_policy` —
`f1993c6433b8_create_investment_policy_and_target_allocation_rules.py`,
tabela `target_allocation_rules` com índice único
`ix_target_allocation_rules_portfolio_dimension` em
`(portfolio_id, dimension_type, dimension_key)`. Testada nesta sprint via
`alembic upgrade head` / `downgrade -1` / `upgrade head` contra um banco
descartável — ver `docs/INVESTMENT_POLICY.md` para detalhes.

## UX de Configurações/alocação (pós-Sprint 25) — precedência visível, presets e detecção de conflitos

A LG INVEST sempre teve três formas independentes de configurar meta de
alocação — alocação-alvo simples por classe (Sprint 17), regras
detalhadas por dimensão (esta engine, Sprint 24) e a Investment Policy
(Sprint 24) — mas nunca as três tinham sido mostradas juntas numa mesma
tela, com a precedência entre elas explícita. Este ajuste (pós-Sprint 25)
reorganiza a tela Configurações em torno dessas três camadas e adiciona
um motor de exibição (não decisório) para deixar claro qual camada está
valendo em cada dimensão.

### Módulo `engines/target_allocation/precedence.py`

Módulo puro (sem banco, rede ou Streamlit) com duas funções:

- **`resolve_effective_limits(rules, policy)`** — calcula o limite
  máximo *efetivo* por dimensão, replicando a MESMA precedência já usada
  pelo Decision Engine 3.0 para bloquear aportes
  (`engines/decision/eligibility.py::filter_eligible_v3`): **regra
  detalhada > política geral > nenhum limite**. Esta função não decide
  nada e não é chamada pelo Decision Engine — existe só para a tela de
  Configurações exibir, de forma explícita, a mesma precedência que já
  vale de verdade no bloqueio de aportes. Qualquer mudança na precedência
  real de `eligibility.py` precisa ser espelhada aqui.
- **`detect_conflicts(rules, simple_allocation)`** — detecta
  inconsistências *informativas* entre as camadas. Nunca bloqueia nada e
  nunca corrige nada sozinho, só avisa o usuário para ele decidir.

Nem toda classe de ativo tem fallback de Investment Policy: hoje só
`crypto` (via `max_crypto_weight`) e `fii` (via `target_fii_max`) têm um
campo dedicado de limite máximo na política
(`POLICY_CLASS_MAX_FIELDS`). As demais classes (`stock`, `etf`, `reit`,
`bond`, `cash`) só têm limite se houver uma regra detalhada própria —
sem ela, não existe limite nenhum (a engine nunca inventa um). Para a
dimensão `asset`, o fallback é `max_asset_weight`: uma regra de ativo
com `max_weight` sempre vence (a política nunca sobrescreve um limite de
ticker específico); a política só aparece como uma linha "genérica"
(`dimension_key = "(qualquer ativo sem regra própria)"`) para tickers
sem regra própria. As dimensões `currency` e `country` não têm nenhum
fallback de política — só aparecem se tiverem regra detalhada com
`max_weight`.

### Os 3 tipos de conflito detectados

- **`simple_vs_detailed`** — a meta da alocação-alvo simples (Camada 1)
  para uma classe diverge do `target_weight` da regra detalhada (Camada
  2) para a mesma classe. A regra detalhada tem precedência; o aviso só
  existe para o usuário perceber que a Camada 1 está "desatualizada" e
  decidir se quer alinhar as duas.
- **`sum_not_100`** — a soma dos `target_weight` das regras detalhadas
  por classe não fecha 100%. Regras parciais são permitidas (é válido
  configurar só algumas classes) — o aviso é só um lembrete para o caso
  de a intenção ter sido cobrir a carteira inteira.
- **`min_greater_than_target`** — numa mesma regra, `min_weight` maior
  que `target_weight` (ver também a validação equivalente em
  `TargetAllocationRuleService.set_rule`, abaixo).

Todos os três tipos são só avisos: nenhum bloqueia salvar uma regra e
nenhum corrige nada automaticamente.

### `allocation_presets_service.py` — presets de alocação simples

Cinco modelos prontos de alocação-alvo simples (Camada 1), cada um só um
**ponto de partida comum**, nunca uma recomendação financeira:
`conservador`, `moderado`, `crescimento_global`,
`buy_and_hold_internacional` e `personalizado` (este último não aplica
nada — sinaliza "configure manualmente"). Módulo só de dados + getters
puros (`list_presets()`, `get_preset(key)`); os quatro presets com
alocação são conferidos em tempo de import: cobrem só classes conhecidas
(`ASSET_CLASSES`) e somam exatamente 100%.

Aplicar um preset na UI sempre exige pré-visualização (tabela com a
alocação do modelo) seguida de confirmação explícita numa etapa
separada — nunca é aplicado com um único clique. Depois de aplicado, o
usuário edita livremente cada classe pelo mesmo formulário que já
existia para a alocação-alvo simples.

### `allocation_overview_service.py` — visão consolidada para a UI

`build_allocation_overview(db, portfolio_id)` só lê (regras detalhadas
via `TargetAllocationRuleRepository`, Investment Policy via
`InvestmentPolicyService.get_or_create`, alocação simples via
`target_allocation_settings_service.get_target_allocation`), monta os
dataclasses puros de `precedence.py` e devolve um `AllocationOverview`
(schema Pydantic). Nunca grava nada e não é usado pelo Decision Engine —
existe só para alimentar a tela Configurações.

### Schemas novos em `schemas/target_allocation.py`

- `EffectiveLimitView` — um limite máximo efetivo (`dimension_type`,
  `dimension_key`, `max_weight`, `source` ∈ `EFFECTIVE_LIMIT_SOURCES`
  (`"regra_detalhada"` / `"politica_geral"`), e
  `overridden_policy_value` opcional — quando a regra detalhada venceu e
  a política também tinha um valor para a mesma dimensão, o valor
  sobrescrito fica visível).
- `AllocationConflictView` — `kind` (∈ `CONFLICT_KINDS`) + `message`
  pronta para exibição.
- `AllocationOverview` — `effective_limits: list[EffectiveLimitView]` +
  `conflicts: list[AllocationConflictView]`.

### Validação nova em `TargetAllocationRuleService.set_rule`

Além das validações já existentes (`min_weight <= max_weight`,
`target_weight <= max_weight`, pesos não negativos, `dimension_type`
válido), `set_rule` agora também rejeita `min_weight > target_weight`
("o mínimo aceitável não pode ficar acima do alvo desejado") — faltava
essa checagem antes; só `min > max` e `target > max` eram bloqueados.

### Tela Configurações — nova organização

`frontend/streamlit_app/pages_impl/configuracoes.py` foi reorganizada em
torno das três camadas, nesta ordem:

1. **Introdução** ("Como funciona a alocação-alvo") — explica as 3
   camadas e a ordem de precedência ANTES de qualquer formulário, com o
   aviso fixo de que estas regras nunca geram venda automática (só
   pausam novos aportes na dimensão acima do alvo/máximo).
2. **Camada 1 — Alocação-alvo simples por classe**, agora com o
   expander "Aplicar um modelo pronto (preset)": seleção de preset,
   pré-visualização em tabela e confirmação em duas etapas
   (`preview_preset` → `confirm_preset`) antes de sobrescrever a meta
   atual.
3. **Camada 3 — Política de investimento geral** (mantida, com o texto
   de fallback explícito nos campos `max_asset_weight`,
   `max_crypto_weight` e `target_fii_max`).
4. **Camada 2 — Regras detalhadas**, agora com:
   - lista de regras cadastradas **agrupada por dimensão** (Classe /
     Moeda / País / Ativo), uma tabela por grupo;
   - botão "Editar" por linha, que pré-preenche o formulário
     (`_prefill_rule_form`) sem precisar remover e recriar a regra
     (a escrita já era upsert);
   - **cadastro rápido**: botões de atalho para dimensões comuns — USD,
     BRL, FIIs, ETFs, BTC (`asset=BTC-USD`), Tesouro (`class=bond`), VOO
     e QQQ — que só preenchem dimensão/chave no formulário; o usuário
     ainda define os pesos e clica em "Salvar regra" (nunca salva
     sozinho).
5. **"Limite efetivo por dimensão e conflitos"** (nova seção, via
   `_render_effective_limits_and_conflicts` → `build_allocation_overview`):
   tabela com o limite máximo efetivo por dimensão (origem e, quando
   aplicável, o valor de política sobrescrito) e a lista de conflitos
   detectados entre as camadas. Section puramente informativa — não
   corrige nada sozinha.

O aviso "não gera venda automática" (`_NEVER_SELLS_DISCLAIMER`) é
repetido em toda seção que lida com alocação-alvo, em vez de aparecer
uma única vez — decisão deliberada para nunca deixar implícito.
