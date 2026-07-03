# IDS Methodology — LG Conviction Score (Sprint 12)

## Objetivo deste documento

Registrar, de forma explícita e auditável, a metodologia por trás do
LG Conviction Score: por que os pilares existem, por que os pesos são
esses e de onde vêm as ideias gerais que os inspiraram. Este documento
não reproduz texto protegido de nenhum livro, não usa citações
atribuídas a nenhuma pessoa e não afirma replicar a estratégia exata de
nenhum investidor ou fundo — ele descreve **princípios gerais e
amplamente conhecidos** de análise de investimentos (ensinados em
cursos, livros didáticos e a prática de mercado há décadas) e explica
como o LG INVEST os traduziu em números, pesos e regras próprias,
ajustados ao perfil específico do usuário desta plataforma.

## Perfil de investidor codificado

O LG Conviction Score não é genérico: os pesos partem do perfil de
investidor descrito no projeto (`backend/app/engines/ids_methodology/profile.py`,
`InvestorProfile`) — Buy & Hold, horizonte superior a 50 anos, aceitação
de volatilidade, prioridade em maximização de patrimônio sobre renda
imediata, e meta de aumentar a exposição internacional ao longo do
tempo. Esse perfil é código, não só um texto no Investment Journal: ele
determina, por exemplo, por que Growth e Capital Reinvestment pesam
mais em ações e ETFs do que em Renda Fixa.

## Os cinco pilares

### Quality (Qualidade)

Mede a robustez do negócio ou do ativo. Ideia geral: preferir negócios
previsíveis e bem estabelecidos a apostas especulativas — um princípio
comum a praticamente toda a literatura de investimento em valor e em
qualidade. **Estado atual (v1):** proxy por classe de ativo + estabilidade
de preço, exatamente a mesma lógica do LG Score
(`engines/lg_score/pillars.py::quality_pillar`), reaproveitada aqui em
vez de duplicada. **Estado futuro:** ROE, ROIC, margens, dívida/patrimônio,
quando o Fundamentals Engine existir.

### Valuation (Valuation)

Mede se o preço atual parece caro ou barato. Ideia geral: o preço pago
importa tanto quanto a qualidade do ativo — pagar caro demais reduz o
retorno esperado, mesmo em bons negócios. **Estado atual (v1):** preço
atual vs. média histórica do próprio ativo (proxy simples de "caro ou
barato" relativo, sem valor intrínseco). **Estado futuro:** DCF, DDM,
múltiplos comparáveis (P/L, EV/EBITDA, P/VP), quando o Valuation Engine
existir.

### Growth (Crescimento)

Mede a trajetória de expansão do ativo. Ideia geral: negócios que
reinvestem e crescem de forma sustentável compõem valor ao longo de
décadas — central para um horizonte de 50+ anos. **Estado atual (v1):**
CAGR do preço histórico (proxy de crescimento de mercado, não de
lucro). **Estado futuro:** CAGR de receita/lucro/FCF por ação, quando
fundamentos existirem.

### Risk (Risco)

Mede volatilidade e quedas históricas. Ideia geral: o risco de perda
permanente de capital importa tanto quanto o retorno esperado — não
basta buscar retorno sem entender o que pode dar errado.
**Estado atual (v1):** volatilidade de preço + maior drawdown histórico.
**Estado futuro:** métricas de risco agregado da carteira (correlação
entre ativos, VaR, downside deviation), fora do escopo desta sprint.

### Capital Reinvestment (Reinvestimento de Capital)

Mede quanto do lucro gerado é reinvestido no próprio negócio — uma
aproximação do efeito de juros compostos internos, especialmente
relevante para quem tem horizonte de décadas e prioriza crescimento de
patrimônio sobre renda imediata. **Este pilar não existia no LG Score.**
**Estado atual (v1):** placeholder neutro e explícito — a plataforma
ainda não coleta lucro, fluxo de caixa ou payout, então o pilar retorna
nota 50 (neutra) com confiança baixa e a razão exata da ausência de
dado, nunca um número otimista inventado (mesma regra de dado ausente
usada em todo o projeto). **Estado futuro:** payout ratio, retenção de
lucro, retorno sobre capital reinvestido, quando o Fundamentals Engine
existir.

## Pesos padrão e por classe de ativo

```
CONVICTION_SCORE = w_Q*Quality + w_V*Valuation + w_G*Growth
                  + w_R*Risk + w_CR*CapitalReinvestment
```

Pesos-padrão (`engines/ids_methodology/weights.py`, `DEFAULT_WEIGHTS`):
Quality 30% · Valuation 25% · Growth 20% · Risk 15% · Capital
Reinvestment 10%.

Cada classe de ativo tem seu próprio perfil de pesos
(`engines/ids_methodology/profile.py`, `ASSET_CLASS_PROFILES`), somando
sempre 1.0 (validado em runtime):

| Classe | Quality | Valuation | Growth | Risk | Capital Reinv. | Racional |
|---|---|---|---|---|---|---|
| Ações (stock) | 30% | 25% | 25% | 10% | 10% | Growth pesa mais — composição de longo prazo. |
| ETFs | 30% | 20% | 25% | 15% | 10% | Growth ainda relevante, risco um pouco maior por diversificação implícita. |
| FIIs | 35% | 25% | 10% | 25% | 5% | Risco pesa mais — dependência de renda imobiliária local. |
| REITs | 35% | 25% | 10% | 25% | 5% | Mesmo racional dos FIIs, mercado americano. |
| Cripto | 20% | 15% | 20% | 40% | 5% | Sem fundamentos e alta volatilidade — Risco domina. |
| Renda Fixa (bond) | 40% | 15% | 5% | 35% | 5% | Qualidade (do emissor) e Risco dominam; Growth quase irrelevante. |
| Caixa (cash) | 50% | 10% | 5% | 30% | 5% | Preservação, não crescimento. |

## Como interpretar o LG Conviction Score

Mesma escala e classificação do LG Score (0 a 100; Exceptional ≥ 90,
Excellent ≥ 80, Good ≥ 70, Neutral ≥ 60, Weak ≥ 40, Avoid < 40), com
confiança agregada (Alta/Média/Baixa) refletindo a cobertura real de
dado por trás de cada pilar. Quando a confiança é baixa, o número deve
ser lido como "ainda pouco informativo", não como "ativo ruim" — a
plataforma nunca deve transmitir mais certeza do que os dados
sustentam (Volume 18 §8 do projeto).

## Relação com o LG Score existente

O Conviction Score é **paralelo** ao LG Score, não um substituto: o
Decision Engine (sugestão de aporte) continua usando exclusivamente o
LG Score nesta sprint. Os dois hoje calculam pilares com a mesma
lógica de proxy (reaproveitada, não duplicada) porque a plataforma
ainda não tem fundamentos reais — a diferença de hoje está na
estrutura (pesos por classe de ativo, pilar de Capital Reinvestment,
perfil de investidor codificado), que é a fundação sobre a qual as
próximas sprints constroem cálculo real.

## Inspirações conceituais (sem citações, sem replicar estratégias)

Os pilares e a ênfase em qualidade + preço pago + crescimento
sustentável + gestão de risco + reinvestimento de capital refletem
princípios amplamente ensinados e publicados na literatura de análise
fundamentalista, investimento em valor, finanças comportamentais e
gestão de portfólio ao longo do século XX e XXI — não uma cópia da obra
ou fórmula de nenhum autor, investidor ou fundo específico. O LG INVEST
não afirma replicar a estratégia de nenhuma pessoa ou instituição:
os pesos, thresholds e fórmulas aqui são uma síntese própria, ajustada
ao perfil de investidor de longo prazo descrito neste projeto, e devem
ser lidos como isso — uma metodologia própria, documentada e ajustável,
não uma cópia.

## Roadmap: como isso prepara os próximos engines

- **Valuation Engine** (DCF, DDM, múltiplos): substitui o `valuation_pillar`
  atual por cálculo real, sem alterar o agregador nem os pesos.
- **Fundamentals Engine** (ROIC, margens, payout, CAGR de lucro):
  substitui `quality_pillar`, `growth_pillar` e, principalmente,
  `capital_reinvestment_pillar` (hoje o único 100% placeholder).
- **Decision System completo**: quando o Conviction Score tiver
  confiança suficiente, pode se tornar um input adicional do Decision
  Engine (hoje só usa o LG Score) — decisão a ser tomada e aprovada em
  sprint futura, não implementada aqui.
