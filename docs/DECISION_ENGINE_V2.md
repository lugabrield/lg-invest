# Decision Engine 2.0 (Sprint 18; explicação de confiança Sprint 21)

## Objetivo

Responder "tenho R$ X, onde aportar?" com uma distribuição sugerida,
justificativa por ativo, e avisos explícitos sempre que a recomendação
se apoiar em dado de baixa confiança — nunca sugerir aporte silencioso
em ativo com dado ruim (pedido explícito do usuário, Sprint 21).

## v1 vs. v2

O motor de decisão tem dois caminhos, ambos disponíveis na tela Aporte
via um checkbox:

- **v1** (`recommend()`, `MODEL_VERSION = "decision_v1"`): usa o LG
  Score puro (proxy de preço, sem fundamentos).
- **v2** (`recommend_v2()`, `MODEL_VERSION_V2 = "decision_v2"`): usa o
  LG Conviction Score v2 quando calculável (com fallback para o LG
  Score quando não), mais um bônus para classes subalocadas frente à
  meta de alocação configurada em Configurações.

Ambos compartilham o mesmo fluxo: filtrar elegíveis → pontuar →
distribuir → explicar → auditar.

## Fluxo: elegibilidade (`engines/decision/eligibility.py`)

Um ativo é excluído da distribuição, com razão registrada em
`ignored`, quando:

- está na lista de bloqueados informada pelo usuário na tela Aporte
  (`"ativo bloqueado pelo usuário"`);
- o peso atual do ativo na carteira já ultrapassa 30%
  (`over_concentration_limit`) — `"sobreconcentrado: peso atual X%
  acima do limite 30%"`.

## Fluxo: pontuação (`engines/decision/scoring.py`)

**v1** — `buy_score = 0,50·(LG Score/100) + 0,30·gap_de_alocação +
0,20·(1 − peso_atual)`. `gap_de_alocação` só é diferente de zero se
houver `target_weight` por ticker configurado (recurso que nunca foi
implementado de fato no MVP — na prática, esse termo quase sempre é 0).

**v2** — `buy_score = 0,40·qualidade_normalizada + 0,30·bônus_de_classe
+ 0,30·(1 − peso_atual)`. `qualidade_normalizada` usa o Conviction
Score v2 (`/100`) quando disponível, senão o LG Score (`/100`) — nunca
um valor fabricado. `bônus_de_classe` é 0 se não houver meta de
alocação configurada ou se a classe do ativo já estiver na meta ou
acima dela; caso contrário, é o desvio percentual (capado em 100 p.p.)
entre o peso atual da classe e a meta — quanto mais subalocada a
classe, maior o bônus.

Em ambos os casos, `1 − peso_atual` favorece ativos menos concentrados
na carteira, reduzindo o risco de concentrar ainda mais uma posição já
grande.

## Fluxo: distribuição (`engines/decision/allocation.py`)

1. Número de candidatos considerados depende do valor do aporte:
   ≤R$500 → 2 ativos; ≤R$1.000 → 4; ≤R$3.000 → 6; acima disso → 8
   (nunca mais de 10, mesmo para aportes muito altos).
2. Candidatos com `buy_score` não positivo são descartados.
3. Pesos brutos proporcionais ao score; depois ajustados para respeitar
   o mínimo de 10% e o máximo de 50% por ativo — o teto de 50% é
   inviolável: se o ajuste não couber em 100% do valor, o excedente
   fica **não alocado** (nunca força um valor acima do teto).
4. Valores são calculados em centavos (arredondamento para baixo), e o
   último ativo da lista absorve o resto da divisão, sempre respeitando
   o teto de 50%.

## Alertas explícitos (Sprint 21)

`_build_alerts()` nomeia os ativos afetados em vez de emitir um aviso
genérico:

- **Nenhum ativo elegível**: "Nenhum ativo elegível para aporte:
  verifique bloqueios e concentração."
- **Confiança baixa por ativo** (`item_confidence < 0,60` para algum
  item selecionado): lista os tickers específicos — "Recomendação com
  baixa confiança por falta de fundamentos/valuation em: {tickers}. O
  sistema ainda inclui esses ativos na distribuição (não bloqueia por
  confiança baixa), mas o motivo está registrado — revise antes de
  aportar." O sistema **não** bloqueia o ativo, apenas avisa — decisão
  final continua com o usuário.
- **Valor não totalmente alocado**: informa o resto não distribuído por
  restrições de mínimo/máximo por ativo.

`confidence_label` da recomendação: >80% → "Alta"; 60–80% → "Média";
<60% → "Baixa" — calculada como a média das confianças dos ativos
efetivamente escolhidos (`item_confidence`, vindo do LG Score ou
Conviction Score de cada ativo).

## Auditoria

Cada recomendação carrega um `DecisionAudit` com: valor do aporte,
tickers elegíveis, tickers bloqueados, versão do modelo
(`decision_v1`/`decision_v2`) e os pesos exatos usados na fórmula de
pontuação — permite reconstruir manualmente por que cada ativo recebeu
o valor que recebeu.

## Projeção antes/depois (`allocation_projection_service.py`)

Camada de apresentação (não altera a decisão): projeta como os pesos
por classe, por moeda, a concentração (índice de Herfindahl-Hirschman)
e a exposição internacional mudariam se a recomendação fosse aplicada
integralmente. Simplificação assumida: o valor do aporte é somado ao
valor já convertido da posição recomendada — não simula custo de
câmbio nem a compra em moeda estrangeira.

## Limitações conhecidas

- `target_weight` por ticker individual nunca foi implementado — só a
  meta por classe (Target Allocation Engine, Sprint 17) influencia a
  v2.
- O bloqueio de concentração (30%) é fixo e igual para todas as
  classes — não diferencia, por exemplo, um ETF amplamente
  diversificado de uma ação individual.
- A recomendação nunca é auto-aplicada: o usuário decide se e quando
  registrar a compra manualmente na tela Carteira/Ativos.
