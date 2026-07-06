# IDS Methodology — LG Conviction Score v2 (Sprint 12; revisado Sprint 21)

## Objetivo deste documento

Registrar, de forma explícita e auditável, a metodologia por trás do LG
Conviction Score: por que os pilares existem, por que os pesos são
esses, de onde vêm as ideias gerais que os inspiraram e o que mudou na
evolução v1 → v2 (Sprint 21). Este documento não reproduz texto
protegido de nenhum livro, não usa citações atribuídas a nenhuma pessoa
e não afirma replicar a estratégia exata de nenhum investidor ou
fundo — ele descreve **princípios gerais e amplamente conhecidos** de
análise de investimentos e explica como o LG INVEST os traduziu em
números, pesos e regras próprias, ajustados ao perfil específico do
usuário desta plataforma.

## Perfil de investidor codificado

Os pesos partem do perfil de investidor descrito no projeto
(`backend/app/engines/ids_methodology/profile.py`, `InvestorProfile`) —
Buy & Hold, horizonte superior a 50 anos, aceitação de volatilidade,
prioridade em maximização de patrimônio sobre renda imediata, e meta de
aumentar a exposição internacional ao longo do tempo
(`international_exposure_target = 0.40`, meta de referência, não um
limite rígido).

## O que mudou de v1 para v2 (Sprint 21)

**v1** (`calculate_conviction_score`, ainda existente e inalterada):
todos os cinco pilares usavam a mesma proxy de preço do LG Score
(classe do ativo + estabilidade/CAGR/volatilidade de preço), porque a
plataforma ainda não coletava fundamentos. Classificação em seis
faixas: Exceptional/Excellent/Good/Neutral/Weak/Avoid.

**v2** (`calculate_conviction_score_v2`, caminho recomendado, usado por
Inteligência, Aporte e Ativos): cada pilar agora consome o resultado
real do engine correspondente (Quality/Growth/Risk/Valuation/Capital
Reinvestment, Sprints 14-21) **quando disponível**, e só cai de volta
na proxy de preço v1 daquele pilar especificamente — nunca do score
inteiro — quando o dado real não existe ou o engine devolveu
"indeterminado". A razão registrada em cada pilar sempre indica qual
caminho foi usado (dado real vs. proxy de fallback), nunca um degrau
silencioso.

## Os cinco pilares (v2)

### Quality (Qualidade)

Mede a robustez do negócio. Fonte real: `Quality Engine v1`
(ROE, margem líquida, dívida/EBITDA — ver `docs/QUALITY_GROWTH_RISK_ENGINES.md`),
aplicável hoje a `stock` e `reit`. Para as demais classes, ou quando o
Quality Engine devolve "indeterminado" (sem snapshot, dado ausente),
cai na proxy de preço v1.

### Valuation (Valuation)

Mede se o preço atual parece caro ou barato. Fonte real: `Valuation
Engine v1` (múltiplos P/L, P/VP, EV/EBITDA para ações; P/VP e dividend
yield para FIIs/REITs — ver `docs/VALUATION_ENGINE.md`). Não é um DCF
nem calcula um preço-alvo numérico — classifica caro/neutro/barato por
bandas fixas de múltiplos relativos.

### Growth (Crescimento)

Mede a trajetória de expansão. Fonte real: `Growth Engine v1` (CAGR de
receita e lucro líquido, calculado pelo Fundamentals Engine a partir de
snapshots coletados — ver `docs/FUNDAMENTALS_ENGINE.md`), hoje só
computável para ações com histórico de demonstrativos coletado (mínimo
2 períodos). Demais casos caem na proxy de preço v1.

### Risk (Risco)

Mede risco de balanço/mercado. Fonte real: `Risk Engine v1` (dívida/EBITDA
para ações/FIIs/REITs, beta para ações — ver `docs/QUALITY_GROWTH_RISK_ENGINES.md`).
**Cripto é uma exceção deliberada**: não usa proxy nem fica
"indeterminado" — é classificada `"alto"` por **política da
metodologia** (confiança "alta"), pois cripto não tem fundamentos de
empresa comparáveis, tem volatilidade estruturalmente alta e tese
predominantemente macro. Essa é uma afirmação da plataforma sobre a
classe, não uma leitura de indicador ausente.

### Capital Reinvestment (Reinvestimento de Capital)

Mede a taxa de retenção de lucro (1 − payout ratio) como proxy de
disciplina/capacidade de reinvestimento — alinhado à filosofia de longo
prazo do investidor (priorizar reinvestimento sobre renda imediata).
Fonte real: `Capital Reinvestment Engine v1`, extraído em pacote
próprio no Sprint 21 (ver `docs/FUNDAMENTALS_ENGINE.md` §Capital
Reinvestment), aplicável a `stock`/`etf`. Não aplicável a FIIs/REITs
(obrigação regulatória de distribuir a maior parte do resultado) nem a
cripto/renda fixa/caixa (não são ações).

## Pesos por classe de ativo (revisados no Sprint 21)

```
CONVICTION_SCORE = w_Q*Quality + w_V*Valuation + w_G*Growth
                  + w_R*Risk + w_CR*CapitalReinvestment
```

Fonte: `backend/app/engines/ids_methodology/profile.py`,
`ASSET_CLASS_PROFILES` (cada linha soma 1.0, validado em runtime):

| Classe | Quality | Valuation | Growth | Risk | Capital Reinv. |
|---|---|---|---|---|---|
| Ações (stock) | 30% | 25% | 20% | 15% | 10% |
| ETF | 15% | 10% | 20% | 35% | 20% |
| FII | 30% | 40% | 5% | 20% | 5% |
| REIT | 30% | 35% | 15% | 15% | 5% |
| Cripto | 10% | 10% | 10% | 65% | 5% |
| Renda fixa (bond) | 20% | 10% | 0% | 70% | 0% |
| Caixa (cash) | 50% | 10% | 5% | 30% | 5% |

**Decisão deliberada de não fabricar pilares por classe.** A
especificação original do produto sugeria conceitos diferentes por
classe (ex.: "Diversificação"/"Custo-Liquidez" para ETF, "Papel na
carteira" para Renda Fixa, "Tese macro" para Cripto). O Sprint 21
manteve os **mesmos cinco pilares** para todas as classes, em vez de
criar pilares que exigiriam dados que a plataforma não coleta (nº de
holdings do ETF, expense ratio, tracking error, rating de crédito do
título) — inventar esses números violaria a regra de não fabricar dados
(Volume 18 §8). Onde a metodologia original pedia uma dimensão sem
pilar equivalente, ela foi absorvida pelo pilar mais próximo:

- **ETF** — "Diversificação/Exposição" e "Custo/Liquidez" viraram peso
  extra em Risk (35%, maior de todas as classes) e em Capital
  Reinvestment (20%, lido como "fit com estratégia de acumulação").
- **FII/REIT** — "Income/Yield" é capturado pelo pilar Valuation
  (dividend yield é uma das duas métricas de valuation usadas para
  FII/REIT).
- **Cripto** — "Allocation limit" e "Macro thesis" são absorvidos pelo
  peso dominante de Risk (65%) e pela política de risco "alto" fixo.
- **Renda fixa** — "Real rate/duration", "Credit/issuer risk" e
  "Liquidity" são todos dimensões de risco, concentradas no pilar Risk
  (70%); "Papel na carteira" (proteção/estabilidade) é lido no pilar
  Quality (20%).

## Classificação e confiança (v2)

`calculate_conviction_score_v2` produz um rótulo de **decisão**, não
apenas uma nota — `_classify_v2` em `engines/ids_methodology/engine.py`:

| Faixa de score | Confiança mínima (35%) | Classificação | Label PT (`theme.py`) |
|---|---|---|---|
| ≥ 80 | atingida | `strong_buy` | Aportar |
| 65–79 | atingida | `buy` | Candidato |
| 50–64 | atingida | `hold` | Manter |
| 35–49 | atingida | `watch` | Monitorar |
| < 35 | atingida | `avoid` | Evitar |
| qualquer | **não** atingida (< 35%) | `insufficient_data` | Dados insuficientes |

A confiança agregada é a média ponderada (mesmos pesos dos pilares) das
confianças de cada pilar. Quando a confiança fica abaixo de 35%, a
plataforma se recusa a sugerir uma direção — o score numérico existe
como referência, mas a classificação vira `insufficient_data` e o campo
`recommendation_hint` explica exatamente por quê (nunca esconde a
limitação atrás de um número). Entre 35% e 60%, o `recommendation_hint`
ainda inclui um aviso de confiança média/baixa.

## Relação com o LG Score existente

O Conviction Score é **paralelo** ao LG Score. O Decision Engine v1
(`recommend()`) continua usando o LG Score puro; o Decision Engine v2
(`recommend_v2()`, Sprint 18/21) usa o Conviction Score v2 quando
calculável, com fallback para o LG Score — ver
`docs/DECISION_ENGINE_V2.md`.

## Inspirações conceituais (sem citações, sem replicar estratégias)

Os pilares e a ênfase em qualidade + preço pago + crescimento
sustentável + gestão de risco + reinvestimento de capital refletem
princípios amplamente ensinados e publicados na literatura de análise
fundamentalista, investimento em valor, finanças comportamentais e
gestão de portfólio — não uma cópia da obra ou fórmula de nenhum autor,
investidor ou fundo específico. O LG INVEST não afirma replicar a
estratégia de nenhuma pessoa ou instituição: os pesos, thresholds e
fórmulas aqui são uma síntese própria, ajustada ao perfil de investidor
de longo prazo descrito neste projeto.

## Limitações conhecidas (v2)

- Valuation não calcula preço justo numérico nem margem de segurança
  percentual — apenas caro/neutro/barato por bandas de múltiplos.
- Growth só é computável para ações com ≥2 snapshots de fundamentos
  coletados; a cobertura de dado do yfinance para FIIs/small caps é
  inconsistente.
- Capital Reinvestment não distingue "empresa madura que já não tem
  onde reinvestir" de "empresa que só distribui por falta de
  disciplina" — payout alto reduz a nota nos dois casos.
- Pesos por classe são uma síntese de julgamento do autor da
  plataforma, não calibrados estatisticamente contra retornos
  históricos.
