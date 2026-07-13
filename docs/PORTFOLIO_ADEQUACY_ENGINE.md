# Adequação de Carteira — ETF/Cripto/Tesouro (Sprint 26, Fase 5)

## Objetivo e escopo declarado

ETFs, cripto (BTC) e Tesouro Direto (`asset_class` "bond") não têm
valuation tradicional aplicável neste projeto: não há DCF, P/L, P/VP
nem Graham para eles (ETF/cripto não têm demonstrações financeiras
societárias comparáveis; Tesouro Direto é renda fixa pública,
precificada por curva de juros, não por múltiplos de empresa). Em vez
de fabricar uma nota de "preço justo" sem dado real por trás — o que
violaria "nunca inventar dado" —, esta análise responde a uma pergunta
diferente e igualmente central: **"esta posição está adequada à minha
política de alocação?"**, reaproveitando o Target Allocation Engine v2
já existente (Sprint 24), nunca recalculando pesos por conta própria.

Nunca gera recomendação de compra/venda — o `alert_message` embutido
(quando existe) já vem pronto do Target Allocation Engine v2, que
segue a mesma disciplina Buy and Hold do resto do projeto (nunca
sugere vender, só pausar aportes ou sinalizar revisão manual).

Escopo: `asset_class in ("etf", "crypto", "bond")`.

## Arquitetura

```
PortfolioAdequacyService (banco <-> engine)
    -> TargetAllocationService.evaluate_portfolio_rules(portfolio_id)
       (Target Allocation Rule Engine v2, Sprint 24 — já existente)
    -> filtra a avaliação pela dimensão "asset" (ticker) e "class" (classe)
    -> PortfolioAdequacyEngine.evaluate(...)  # puro, sem I/O
```

Nenhum cálculo de peso mora aqui — só orquestração e empacotamento no
mesmo formato usado pelas outras análises por ativo (Valuation Engine
2.0, Análise de Renda Imobiliária), para a UI mostrar um card
consistente mesmo quando não há valuation tradicional.

## Precedência: regra de ativo específica > regra de classe

Mesmo espírito de `engines/target_allocation/precedence.py` (regra mais
específica vence). Se existe uma regra de alocação para o TICKER
específico (`dimension_type="asset"`), ela é usada e a confiança fica
`"alta"`. Se não existe, cai para a regra da CLASSE (`dimension_type=
"class"`) como aproximação, confiança `"média"`, com aviso explícito
("nenhuma regra específica para o ticker... usando a regra da
classe..."). Se nenhuma das duas existe, o resultado é indeterminado
com instrução para configurar uma meta em Configurações.

O contexto da classe inteira (`class_current_weight`/
`class_target_weight`) é sempre populado quando disponível, mesmo
quando a avaliação EFETIVA usou a regra de ativo específica — dá
transparência adicional sem afetar qual regra decide o status.

## Status de adequação

Reaproveita literalmente os mesmos valores de
`schemas/target_allocation.py::GAP_STATUSES` (`underweight`/`neutral`/
`overweight`/`blocked`), mais `"indeterminado"` (sem regra configurada
para nem o ativo nem a classe). Nunca inventa uma classificação nova —
é o mesmo vocabulário já usado em Configurações e no Decision Engine
3.0 para consistência em toda a aplicação.

## Arquivos

`engines/portfolio_adequacy/engine.py`, `schemas/portfolio_adequacy.py`,
`services/portfolio_adequacy_service.py`.

## UI (tela Ativos → "Análise Fundamentalista")

Para ETF/cripto/Tesouro: aviso explícito de que a classe não tem
valuation tradicional (`VALUATION_NOT_APPLICABLE_MESSAGE`), badge de
status de adequação, peso atual/alvo/gap, peso da classe na carteira
(com alvo, quando disponível), `alert_message` (quando existe) e aviso
de concentração extrema (quando aplicável — nunca uma sugestão de
venda). Ver `docs/FUNDAMENTAL_ANALYSIS_UI.md`.

## Limitações conhecidas

- Depende inteiramente de o usuário ter configurado uma regra de
  alocação (Target Allocation, Configurações) para o ativo ou para a
  classe — sem isso, o resultado é sempre "indeterminado", mesmo que a
  posição exista na carteira.
- Não avalia qualidade do ETF/cripto/Tesouro em si (ex.: expense
  ratio de um ETF, ou qual Tesouro específico é mais adequado ao
  horizonte do investidor) — só adequação de PESO à política já
  configurada.
