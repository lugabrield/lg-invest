# Portfolio Risk Engine — "Risk Engine 2.0" (Sprint 24, Fase 6)

## Contexto

O Risk Engine v1 (Sprint 16) já classifica o risco de balanço/mercado de
**um ativo individual** (baixo/médio/alto/indeterminado), a partir de
indicadores fundamentalistas. Faltava uma visão agregada: "minha carteira
inteira está arriscada?". A Fase 6 responde isso com uma segunda engine,
nova e complementar — o Portfolio Risk Engine — que combina 4 fatores de
risco independentes em um único score composto (0..100) e o classifica
nas mesmas 4 faixas de `RISK_TOLERANCES` já usadas pela Investment Policy
(Fase 3), permitindo comparar diretamente o risco medido da carteira com
a tolerância que o usuário declarou.

**Nomenclatura**: "Risk Engine 2.0" é o nome da fase (segunda geração de
capacidade de risco na plataforma — agora no nível da carteira), não uma
nova versão que substitui o Risk Engine v1. O `MODEL_VERSION` interno é
`"portfolio_risk_v1"` (primeira versão desta engine nova). O Risk Engine
v1 (`engines/risk/`) continua existindo e sendo usado exatamente como
antes — os dois convivem, respondendo perguntas diferentes.

## Os 4 fatores de risco

| Fator | O que mede | Fonte |
|---|---|---|
| Volatilidade | Volatilidade anual ponderada da carteira (Σ peso × volatilidade por classe) | Mesmas premissas do Monte Carlo Simulation Engine (Fase 5) |
| Concentração | HHI (Herfindahl-Hirschman) da carteira | Já calculado pelo Portfolio Engine (`PortfolioSummary.concentration_hhi`) |
| Risco estrutural por ativo | Média ponderada das classificações de risco por ativo (baixo=1, médio=2, alto=3) | Risk Engine v1, reaproveitado — nunca recalculado |
| Risco de cauda | Probabilidade de a carteira terminar uma simulação Monte Carlo abaixo do total efetivamente aportado | Monte Carlo Simulation Engine (Fase 5), opcional |

Cada fator é convertido para uma escala 0..100 (100 = mais arriscado),
usando bandas próprias documentadas em `engines/portfolio_risk/thresholds.py`
— deliberadamente independentes das bandas de
`portfolio_diagnostics/thresholds.py` (que servem para gerar *insights*
textuais, não um score).

## Fatores ausentes nunca são inventados

Se um fator não puder ser calculado (ex.: nenhuma classe da carteira tem
volatilidade configurada; nenhum ativo tem classificação de risco
disponível; nenhuma simulação Monte Carlo foi rodada), ele é marcado
`available=False`, documentado em `warnings`, e **os pesos dos fatores
restantes são renormalizados entre si** — o score composto nunca usa um
valor inventado no lugar do fator ausente. Isso segue a regra do projeto
"se dado não existe, marcar como indisponível".

O fator de risco estrutural por ativo, especificamente, exclui sinais
`"indeterminado"` do cálculo (mas os inclui na lista de fatores, para
transparência), documentando a fração do patrimônio que ficou de fora.

## Risco de cauda é opcional

O fator de risco de cauda (`probability_of_loss`) só existe se uma
simulação Monte Carlo (Fase 5) já tiver sido rodada e seu resultado
passado ao `PortfolioRiskService.evaluate(portfolio_id,
probability_of_loss=...)`. A engine **não roda uma simulação
automaticamente** (isso teria custo e aleatoriedade a cada avaliação) —
sem esse valor, o fator fica `available=False` e os outros 3 pesos são
renormalizados.

## Score composto e comparação com a tolerância declarada

O score composto (0..100) é classificado em uma das 4 faixas de
`RISK_TOLERANCES` (`baixo`, `moderado`, `moderado-alto`, `alto`) — as
mesmas usadas por `InvestmentPolicy.risk_tolerance`. Se o usuário já
declarou sua tolerância na Investment Policy, o resultado inclui
`tolerance_alert`: uma mensagem informativa (nunca uma recomendação de
compra/venda) dizendo se o risco medido está acima ou abaixo do que ele
declarou tolerar.

Exemplo de mensagem quando o risco medido excede a tolerância declarada:
> "o risco medido da carteira ('alto') está acima da sua tolerância
> declarada ('moderado') — isto é apenas informativo, não é uma
> recomendação de compra ou venda."

## Engine pura (`engines/portfolio_risk/`)

- `inputs.py`: `AssetRiskSignal`, `PortfolioRiskInput`, `PortfolioRiskConfig`
  (pesos dos 4 fatores, somam 1.0) — todos `@dataclass(frozen=True)`.
- `thresholds.py`: bandas de cada fator + mapeamento do score composto
  para as 4 faixas de `RISK_TOLERANCES`.
- `engine.py`: `evaluate_portfolio_risk(data, config) -> PortfolioRiskResult`,
  sem acesso a banco/rede.

## Serviço (`PortfolioRiskService`)

- `build_input(portfolio_id, probability_of_loss=None)`: resolve
  concentração/número efetivo de ativos (`PortfolioService`), pesos por
  classe e exposição internacional (`build_dashboard_view`), volatilidade
  por classe (`simulation_assumptions_service`, mesma fonte da Fase 5),
  classificação de risco por ativo (`RiskService`, Risk Engine v1) e a
  tolerância declarada (`InvestmentPolicyService`).
- `evaluate(portfolio_id, probability_of_loss=None)`: monta os inputs e
  chama a engine pura. **Não persiste nada** — relatório sob demanda,
  como o Monte Carlo Simulation Engine e o Target Allocation Rule Engine v2.

## Exposição na UI (Fase 9)

A seção "Risco da Carteira" no **Dashboard** exibe a classificação geral,
a tolerância declarada e o alerta quando o risco medido diverge dela, os
fatores disponíveis como métricas e o detalhamento por fator num
expander.

## O que ainda não existe

Não há, ainda, uma orquestração automática que rode o Monte Carlo
Simulation Engine e alimente `probability_of_loss` neste serviço — isso
continua sendo responsabilidade de quem chamar (ex.: uma futura tela que
rode os dois em sequência); por isso o Dashboard chama `evaluate()` sem
esse argumento, e o fator de risco de cauda aparece como indisponível até
o usuário rodar a tela Simulação manualmente.
