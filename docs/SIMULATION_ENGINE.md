# Monte Carlo Simulation Engine (Sprint 24, Fase 5)

## Contexto

Até aqui a LG INVEST responde "onde estou" (Dashboard), "onde devo aportar
agora" (Decision Engine) e "minha alocação está no alvo" (Target Allocation
Rule Engine). Faltava responder uma pergunta de longo prazo, central para
um investidor Buy and Hold com horizonte de 50+ anos: "para onde minha
carteira pode ir, dado o que tenho hoje e o que pretendo aportar?". O
Monte Carlo Simulation Engine responde isso com uma **faixa de cenários
possíveis**, nunca com um número único "previsto".

## Aviso importante (sempre visível, nunca escondido)

Isto é uma ferramenta de projeção probabilística baseada em premissas de
retorno/volatilidade de longo prazo — **não é uma previsão real de
mercado, não é garantia de retorno futuro e não é recomendação
financeira**. Resultados passados não garantem resultados futuros, e os
números aqui vêm inteiramente das premissas configuradas (ver seção
"Premissas" abaixo), nunca de um "oráculo" da engine.

## Como funciona

Dado o valor atual da carteira, um aporte mensal presumido e um horizonte
em anos, a engine roda `num_simulations` trajetórias independentes
(padrão: 2000). Em cada trajetória, para cada ano do horizonte:

1. Sorteia um retorno anual aleatório para cada classe de ativo presente
   na carteira, de uma distribuição normal com média = retorno esperado e
   desvio padrão = volatilidade da classe (`ClassAssumption`).
2. Combina os retornos por classe usando o peso atual de cada classe na
   carteira (`class_weights`), obtendo o retorno do ano para a carteira
   inteira.
3. Aplica esse retorno ao valor da carteira e soma o aporte anual
   (aporte mensal × 12) ao final do ano.

Ao final das `num_simulations` trajetórias, os valores finais são
resumidos em percentis (padrão: p10, p25, p50, p75, p90) — por exemplo,
"em 90% das simulações, sua carteira terminou acima de X" (p10) e "em 50%
das simulações, terminou acima de Y" (p50/mediana).

## Simplificações assumidas (sempre documentadas, nunca escondidas)

Todo resultado (`SimulationResult`) documenta explicitamente em
`reasons`/`warnings`:

- Retornos anuais de classes diferentes são sorteados de forma
  **independente** (sem correlação entre classes) — na realidade, ações
  brasileiras e americanas podem cair juntas em uma crise global; o
  modelo não captura isso.
- O retorno anual de uma trajetória é limitado a um piso de **-95%**
  (evita um patrimônio negativo em uma amostragem extrema de uma única
  classe/ano).
- Aportes são aplicados **uma vez ao final de cada ano**, não mês a mês —
  simplificação necessária para viabilizar milhares de simulações em
  tempo hábil.
- A composição da carteira (pesos por classe) é mantida **fixa** ao longo
  de todo o horizonte — a simulação não modela rebalanceamento.
- Classes com peso na carteira mas **sem premissa configurada** são
  tratadas como retorno 0% (nem ganho, nem perda) — nunca inventa um
  número; um `warning` explícito lista quais classes ficaram nessa
  situação.

## Premissas de retorno/volatilidade (`SimulationAssumptionsService`)

Cada classe de ativo (`ASSET_CLASSES`: stock, fii, etf, reit, crypto,
bond, cash) tem uma premissa de retorno esperado anual e volatilidade
anual. Defaults didáticos de longo prazo (não dados históricos reais
coletados, nunca uma previsão garantida):

| Classe | Retorno esperado/ano | Volatilidade/ano |
|---|---|---|
| stock | 11% | 22% |
| fii | 9% | 14% |
| etf | 9% | 16% |
| reit | 8% | 18% |
| crypto | 15% | 60% |
| bond | 10% | 3% |
| cash | 8% | 1% |

Persistidas em `data/app_settings.json` (chave `simulation_assumptions`),
mesmo padrão de `fx_settings_service.py`/
`target_allocation_settings_service.py` — sem migration nova. O usuário
pode sobrescrever qualquer classe individualmente
(`SimulationAssumptionsService.set_assumption`) ou voltar ao default
(`reset_assumption`/`reset_all_assumptions`); a origem do valor em uso
(`"default do sistema"` ou `"ajustado pelo usuário"`) é sempre exposta,
nunca escondida.

## Engine pura (`engines/simulation/`)

- `inputs.py`: `ClassAssumption`, `SimulationInput` (valor atual, aporte
  mensal, horizonte, pesos por classe, premissas por classe) e
  `SimulationConfig` (`num_simulations`, `random_seed`, `percentiles`) —
  todos `@dataclass(frozen=True)`.
- `engine.py`: `run_simulation(data, config) -> SimulationResult`, sem
  acesso a banco/rede — recebe tudo já resolvido pelo serviço.
  `MODEL_VERSION = "simulation_v1"`.

`SimulationResult` traz: percentis, mediana, `probability_of_loss`
(fração das trajetórias que terminaram abaixo do total efetivamente
aportado — não abaixo de zero), `reasons` (premissas usadas por classe +
disclaimer de simplificação) e `warnings` (classes sem premissa, horizonte
zerado, etc.).

## Serviço (`SimulationService`)

- `build_input(portfolio_id, monthly_contribution, horizon_years)`:
  resolve o valor atual e os pesos por classe via `build_dashboard_view`
  (com conversão de câmbio, mesma fonte usada pelo Decision Engine 3.0
  para agregados) e as premissas via `simulation_assumptions_service`.
- `run_portfolio_simulation(portfolio_id, monthly_contribution,
  horizon_years, num_simulations=2000, seed=None)`: monta o input e chama
  a engine pura. **Não persiste nada** — é uma projeção sob demanda, como
  `TargetAllocationService.evaluate_portfolio_rules`, não uma
  recomendação para auditar.
- Carteira vazia (sem posições): `class_weights` fica vazio, e a
  simulação só acumula os aportes futuros, sem inventar um componente de
  mercado.

## Exposição na UI (Fase 9)

A tela **Simulação** (nova, `pages_impl/simulacao.py`) expõe formulário de
aporte mensal/horizonte/nº de simulações/semente reproduzível, métricas
(valor inicial, total aportado, mediana projetada, probabilidade de
perda), o gráfico de faixa p10–p90/p25–p75/mediana
(`charts/simulation_charts.py`) e as premissas/avisos usados. As
premissas de retorno/volatilidade por classe são editáveis na tela
**Configurações**, seção "Premissas do Monte Carlo".

## O que ainda não existe

Nenhuma tela mostra uma trajetória ano-a-ano (só a distribuição do valor
final) nem histórico de simulações anteriores — cada execução é
independente e não é persistida.
