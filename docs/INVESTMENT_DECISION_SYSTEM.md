# LG INVEST como Investment Decision System (Sprint 24, Fases 1-10)

## Contexto

Este documento fecha a Sprint 24: um plano de 10 fases para evoluir a LG
INVEST de "um dashboard bonito" para o que a descrição geral do projeto
sempre pediu — uma **Investment Intelligence Platform** que responda,
com dados e regras claras, a perguntas de decisão, não só de leitura.
Cada fase foi implementada, testada e documentada isoladamente (ver
CHANGELOG `[1.17.0]` a `[1.25.0]` e os docs individuais linkados
abaixo); este documento é o mapa de como as fases se encaixam e de como
cada pergunta original do projeto é respondida hoje.

## As perguntas originais, respondidas

- **Qual é o valor real da minha carteira?** — Dashboard, seção "Visão
  Geral": patrimônio convertido (câmbio configurável), por moeda, com
  fallback explícito de preço (manual/estimado) sempre visível, nunca
  escondido (`docs/DATA_SOURCES.md`).
- **Qual é a composição por classe de ativo, moeda e concentração?** —
  Dashboard, seções "Composição" e "Riscos & Concentração" (HHI, número
  efetivo de ativos) e, agora, "Risco da Carteira" (Portfolio Risk
  Engine, Fase 6), que soma volatilidade e risco estrutural por ativo ao
  HHI.
- **Onde devo aportar o próximo dinheiro?** — tela Aporte: três motores
  disponíveis (v1 gap de alocação por classe + concentração; v2 LG
  Conviction Score; v3, Fase 4, multi-fator com alocação-alvo detalhada
  por classe/moeda/país/ativo e guardrails da Política de Investimento).
  Todos auditáveis (`recommendations` table) e nenhum jamais sugere
  venda — só pausa aporte.
- **Qual ativo está mais atrativo dentro da minha estratégia?** — tela
  Inteligência: LG Conviction Score v2 por ativo, classificado em
  Aportar/Candidato/Manter/Monitorar/Evitar/Dados insuficientes, com
  rankings por dimensão (valuation, qualidade, crescimento, risco) e
  diagnóstico completo por ativo ("Por que esse ativo?").
- **Minha carteira está concentrada demais?** — HHI no Dashboard +
  fator de concentração no Portfolio Risk Engine (Fase 6) + fator de
  diversificação no Portfolio Health Score (Fase 8) — três ângulos
  complementares, nunca um número inventado quando falta dado.
- **Minha tese de investimento continua válida?** — Investment Journal
  (teses registradas por ativo) lido ao lado do Conviction Score atual
  na Inteligência — o usuário compara a tese original com o diagnóstico
  de hoje.
- **Como minhas decisões evoluíram ao longo do tempo?** — toda
  recomendação (`recommend`/`recommend_v2`/`recommend_v3`) é persistida
  com `model_version`, auditável; o Journal registra decisões e revisões
  ao longo do tempo.

E duas perguntas novas que só passaram a ter resposta nesta sprint:

- **Minha carteira está mais ou menos saudável do que antes?** —
  Portfolio Health Score (Fase 8): um número 0-100 que resume 5 sinais
  (diversificação, alinhamento de risco, aderência à alocação-alvo,
  tendência de renda, confiança dos dados) sem recalcular a lógica de
  nenhuma engine.
- **Se eu continuar aportando assim, aonde eu devo chegar?** — Monte
  Carlo Simulation Engine (Fase 5), tela Simulação: distribuição
  probabilística do patrimônio futuro dado um aporte mensal e um
  horizonte, sempre rotulada como projeção, não previsão.

## As 10 fases

| Fase | O quê | Doc |
|---|---|---|
| 1 | Correção da moeda de BTC-USD (USD, não BRL) | `BTC_CRYPTO_CURRENCY_FIX.md` |
| 2 | Proventos: `income_monthly_summaries` via Central de Proventos/Análise | `DIVIDENDOS_ME_INCOME_SOURCES.md` |
| 3 | Investment Policy + Target Allocation Engine v2 (4 dimensões) | `INVESTMENT_POLICY.md`, `TARGET_ALLOCATION_ENGINE.md` |
| 4 | Decision Engine 3.0 (multi-fator, guardrails da Política) | `DECISION_ENGINE_3.md` |
| 5 | Monte Carlo Simulation Engine | `SIMULATION_ENGINE.md` |
| 6 | Portfolio Risk Engine ("Risk Engine 2.0") | `PORTFOLIO_RISK_ENGINE.md` |
| 7 | Income Engine (tendência + yield on cost) | `INCOME_ENGINE.md` |
| 8 | Portfolio Health Score (capstone de 5 sinais) | `PORTFOLIO_HEALTH_SCORE.md` |
| 9 | Dashboard 2.0 — exposição visual das Fases 4-8 | seções "Exposição na UI" nos docs acima |
| 10 | Performance/cache + esta consolidação final | `PERFORMANCE_CACHE.md` |

## Como as peças se compõem

Nenhuma fase recalculou a lógica de uma fase anterior — cada uma compôs
serviços já existentes:

- O **Portfolio Health Score** (Fase 8) lê o Portfolio Risk Engine
  (Fase 6), o Target Allocation Rule Engine v2 (Fase 3), o Income Engine
  (Fase 7) e a Data Quality Layer (Sprint 21).
- O **Portfolio Risk Engine** (Fase 6) lê o Risk Engine v1 (Sprint 16),
  a Investment Policy (Fase 3) e, quando disponível, a probabilidade de
  perda do Monte Carlo Simulation Engine (Fase 5) — hoje só quando quem
  chama fornece esse número; não há orquestração automática entre as
  duas ainda (ver riscos conhecidos de cada doc).
- O **Decision Engine 3.0** (Fase 4) lê o LG Conviction Score v2
  (Sprint 21), o Target Allocation Rule Engine v2 (Fase 3) e a
  Investment Policy (Fase 3).
- O cache da **Fase 10** não introduz nenhuma lógica nova — só evita
  recalcular essa composição inteira a cada clique dentro da mesma
  janela de 5 minutos.

## Regras que atravessam todas as 10 fases

- **Nunca inventar dado**: todo fator/pilar ausente é marcado como
  indisponível, nunca fabricado; pesos são renormalizados entre os
  fatores disponíveis.
- **Nunca recomendar venda**: Decision Engine (todas as versões),
  Target Allocation Rule Engine v2 e Portfolio Risk Engine só pausam
  aporte ou alertam — nunca geram uma recomendação de venda automática,
  em linha com o perfil Buy and Hold de longuíssimo prazo descrito no
  projeto.
- **Auditabilidade**: toda recomendação persistida guarda
  `model_version`, sem sobrescrever versões anteriores.
- **Separação de camadas**: nenhuma engine importa Streamlit; nenhuma
  tela faz cálculo financeiro — só lê schemas já prontos de um serviço.

## Estado ao final da Fase 10

- **797 testes passando**, 0 falhas. `ruff check` e `black --check
  --fast` limpos.
- 5 novas engines (Fases 4-8), todas com UI (Fase 9) e cache básico
  (Fase 10).
- Nenhuma migration pendente desde a Fase 3 (Fases 4-10 são
  aditivas/apresentação, sem novas tabelas).

## Próximos passos possíveis (fora do escopo desta sprint)

- Orquestração automática entre o Monte Carlo Simulation Engine e o
  fator de risco de cauda do Portfolio Risk Engine.
- Histórico do Portfolio Health Score ao longo do tempo (hoje é sempre
  o score do momento).
- Extração de renda por ativo/mês (Fonte B do Dividendos.me, ainda não
  implementada — `DIVIDENDOS_ME_INCOME_SOURCES.md`).
- Multiusuário e integração direta com corretoras (fora do MVP desde o
  checklist original, `MVP_CHECKLIST.md`).
