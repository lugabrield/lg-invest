# Portfolio Health Score (Sprint 24, Fase 8)

## Contexto

As sete fases anteriores da Sprint 24 construíram análises independentes:
Investment Policy e Target Allocation Rule Engine v2 (Fase 3), Decision
Engine 3.0 (Fase 4), Monte Carlo Simulation Engine (Fase 5), Portfolio
Risk Engine (Fase 6) e Income Engine (Fase 7) — além do Data Quality
Layer já existente (Sprint 21). Cada uma responde uma pergunta diferente,
mas nenhuma dá ao usuário um único número para acompanhar "minha carteira
está mais ou menos saudável do que no mês passado?". O Portfolio Health
Score é o "capstone" desta sprint: resume 5 sinais já produzidos por
essas engines/serviços em um único score (0..100, maior = mais saudável),
sem recalcular nenhuma lógica delas.

## Os 5 pilares

| Pilar | O que mede | Fonte |
|---|---|---|
| Diversificação | Número efetivo de ativos (1/HHI) | Portfolio Engine |
| Alinhamento de risco | Risco medido da carteira vs. tolerância declarada | Portfolio Risk Engine (Fase 6) + Investment Policy (Fase 3) |
| Aderência à alocação-alvo | % de dimensões dentro da meta (neutra/underweight) vs. acima/bloqueadas | Target Allocation Rule Engine v2 (Fase 3) |
| Tendência de renda | Crescimento de proventos (TTM vs. período anterior) | Income Engine (Fase 7) |
| Confiança dos dados | % do patrimônio com preço automático, fundamentos e valuation disponíveis | Data Quality Layer (Sprint 21) |

Pesos default (somam 1.0): diversificação 25%, alinhamento de risco 25%,
aderência à alocação-alvo 20%, tendência de renda 15%, confiança dos
dados 15% (`PortfolioHealthConfig`, `engines/portfolio_health/inputs.py`).

## Pilares ausentes nunca são inventados

Se um pilar não puder ser calculado (ex.: nenhuma regra de alocação-alvo
configurada, sem histórico de renda suficiente, sem Investment Policy
configurada), ele fica `available=False`, documentado em `warnings`, e os
pesos dos pilares restantes são renormalizados entre si — mesmo padrão já
validado no Portfolio Risk Engine (Fase 6). Se **nenhum** pilar puder ser
calculado, o resultado é `overall_classification="indeterminado"` com
score `0`, nunca um valor fabricado.

## Classificação final

O score composto (0..100) é classificado em uma das 4 faixas
(`HEALTH_LABELS`): `crítica` (≤40), `atenção` (≤65), `boa` (≤85),
`excelente` (>85) — bandas próprias desta engine, independentes das
`RISK_TOLERANCES` (que vão na direção oposta: lá, mais alto é pior; aqui,
mais alto é melhor).

## Cálculo de cada pilar

- **Diversificação**: `min(100, max(0, (n_eff - 1) / (15 - 1) * 100))` —
  saúde máxima a partir de 15 ativos efetivos.
- **Alinhamento de risco**: `100 - 30 × (faixas acima da tolerância
  declarada)`, usando a mesma ordem de `RISK_TOLERANCES` (baixo <
  moderado < moderado-alto < alto). Carteira mais conservadora que a
  tolerância declarada não é penalizada (só recebe nota 100).
- **Aderência à alocação-alvo**: `100 × dimensões alinhadas / total de
  dimensões avaliadas`.
- **Tendência de renda**: escala linear entre -10% de crescimento (saúde
  0) e +5% de crescimento (saúde 100).
- **Confiança dos dados**: `pct_fundamentals_available` e
  `pct_valuation_available` (Data Quality Layer), em média, convertidos
  para 0..100.

## Engine pura (`engines/portfolio_health/`)

- `inputs.py`: `AllocationAlignmentInput`, `PortfolioHealthInput`,
  `PortfolioHealthConfig` — `@dataclass(frozen=True)`, sem importar
  nenhuma engine/serviço alheio (mantém a regra "engines continuam
  puras" mesmo sendo uma agregação de outras análises).
- `thresholds.py`: bandas de cada pilar + classificação final.
- `engine.py`: `evaluate_portfolio_health(data, config) ->
  PortfolioHealthResult`, sem acesso a banco/rede.
  `MODEL_VERSION = "portfolio_health_v1"`.

## Serviço (`PortfolioHealthService`)

- `build_input(portfolio_id)`: compõe `PortfolioService.get_summary()`,
  `PortfolioRiskService.evaluate()` (Fase 6),
  `TargetAllocationService.evaluate_portfolio_rules()` (Fase 3),
  `IncomeAnalysisService.evaluate()` (Fase 7) e
  `DataQualityService.evaluate_portfolio()` (Sprint 21) — nunca
  recalcula a lógica de nenhum desses serviços, só lê o resultado deles.
- `evaluate(portfolio_id)`: monta os inputs e chama a engine pura. **Não
  persiste nada** — relatório sob demanda, como as demais engines de
  análise das fases anteriores.

## Relatório informativo, nunca uma recomendação

Assim como todas as engines de análise das fases anteriores, o Portfolio
Health Score nunca sugere uma ação de compra ou venda — é um número para
acompanhar ao longo do tempo, com os 5 pilares que o compõem sempre
visíveis para o usuário entender o "porquê" por trás dele.

## Exposição na UI (Fase 9)

A seção "Saúde da Carteira" no **Dashboard** exibe o badge de
classificação geral e o score, uma métrica por pilar disponível e o
detalhamento por pilar (nota ou "indisponível" + motivo) num expander.

## O que ainda não existe

Nenhuma tela mostra o histórico do score ao longo do tempo — cada
carregamento do Dashboard recalcula o score do momento, sem persistir
snapshots anteriores para comparação.
