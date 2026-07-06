# Quality, Growth e Risk Engines v1 (Sprint 16; Risk expandido Sprint 21)

Os três engines seguem o mesmo padrão arquitetural: pacote próprio
(`engine.py` + `thresholds.py`), função pura `evaluate()`/`analyze()`
sem acesso a banco/yfinance/Streamlit, veredito por métrica + veredito
agregado, e nunca um erro para dado ausente — sempre `"indeterminado"`
com razão explícita (Volume 18 §8).

## Quality Engine

**Aplicável a:** `stock`, `reit` (`APPLICABLE_CLASSES`). Demais classes
→ `"indeterminado"`, razão "indicadores de qualidade para a classe
'{classe}' ainda não implementados".

**Bandas (`engines/quality/thresholds.py`):**

| Métrica | Forte (melhor) | Fraca (pior) |
|---|---|---|
| ROE (`roe`) | ≥ 15% | ≤ 8% |
| Margem líquida (`net_margin`) | ≥ 15% | ≤ 5% |
| Dívida/EBITDA (`debt_to_ebitda`) | ≤ 2 | ≥ 4 |

ROE e margem: maior é melhor. Dívida/EBITDA: menor é melhor.

**Classificação agregada** (`alta`/`média`/`baixa`/`indeterminado`):
soma de pesos por veredito (`forte=-1, média=0, fraca=+1`) — soma
negativa → `"alta"`; soma positiva → `"baixa"`; soma zero → `"média"`;
nenhuma métrica disponível → `"indeterminado"`.

**Limitação documentada**: REITs americanos costumam reportar ROE/
margem/dívida como uma ação comum via yfinance, mas o indicador padrão
do setor é FFO/AFFO (Funds From Operations), fora do escopo do MVP.
FIIs brasileiros normalmente não publicam esses campos via yfinance na
prática — a maioria recebe `"indeterminado"` por dado ausente, não por
exclusão de classe (FII está fora de `APPLICABLE_CLASSES`).

## Growth Engine

**Fonte:** consome `FundamentalsAnalysisResult` (CAGR já calculado pelo
Fundamentals Engine — ver `docs/FUNDAMENTALS_ENGINE.md`), não acessa
snapshots diretamente. Sem períodos suficientes (`periods_used == 0`)
→ `"indeterminado"`.

**Bandas (`engines/growth/thresholds.py`):**

| Métrica | Forte | Fraca |
|---|---|---|
| CAGR de receita | ≥ 15% | ≤ 5% |
| CAGR de lucro líquido | ≥ 15% | ≤ 5% |

**Classificação agregada**: `"forte"`/`"moderado"`/`"fraco"`/
`"indeterminado"` — mesma lógica de soma de pesos dos demais engines.

**Cobertura real hoje**: apenas ações com pelo menos 2 snapshots de
fundamentos coletados em datas diferentes têm CAGR calculável. Isso
depende do usuário rodar a coleta de fundamentos mais de uma vez ao
longo do tempo, ou do yfinance devolver múltiplos períodos históricos
na mesma consulta (`get_history`, até 4 períodos).

## Risk Engine

**Bandas de balanço/mercado (`engines/risk/thresholds.py`):**

| Métrica | Aplicável a | Baixo risco | Alto risco |
|---|---|---|---|
| Dívida/EBITDA | stock, fii, reit | ≤ 2 | ≥ 4 |
| Beta | stock | ≤ 0,8 | ≥ 1,2 |

**Classes fora do escopo de indicador de balanço**: `NOT_APPLICABLE_CLASSES
= ("crypto", "cash", "bond")` — exceto cripto, que tem uma regra
diferente (ver abaixo). Caixa e renda fixa recebem `"indeterminado"`,
razão explícita de que indicadores de risco para essas classes ainda
não foram implementados.

**Cripto — risco por política, não por indicador (Sprint 21):**

Diferente de todas as outras classes fora de escopo, cripto **não**
recebe `"indeterminado"`. `_POLICY_HIGH_RISK_CLASSES = ("crypto",)`
força classificação `"alto"` com confiança `"alta"` e uma razão
explícita: cripto não tem fundamentos de empresa comparáveis
(ROE/dívida/beta), tem volatilidade estruturalmente alta, e a tese de
investimento é predominantemente macro. Esta é uma **afirmação
deliberada da metodologia sobre a classe** — o LG Conviction Score usa
essa classificação, combinada com o peso dominante de Risk (65%) no
perfil de pesos de cripto, como proxy do "limite de exposição" e "tese
macro" pedidos na especificação original do produto, em vez de
inventar um pilar novo sem dado real por trás.

**Classificação agregada**: `"baixo"`/`"médio"`/`"alto"`/
`"indeterminado"`, mesma lógica de soma de pesos.

## Padrão de confiança (comum aos três engines, exceto Capital Reinvestment)

- Nenhuma métrica disponível → `"baixa"`
- Algumas métricas disponíveis → `"média"`
- Todas as métricas da classe disponíveis → `"alta"`

## Limitações conhecidas

- Bandas fixas, não ajustadas por setor/porte/ciclo.
- Quality e Risk cobrem apenas indicadores de balanço estático — não
  incluem correlação entre ativos, VaR ou downside deviation em nível
  de carteira (isso é responsabilidade do Portfolio Diagnostics
  Engine, Sprint 9, não destes engines por ativo).
- FIIs brasileiros têm cobertura de dado tipicamente baixa via
  yfinance para Quality; a maior parte recai em "indeterminado" por
  ausência de dado, não por decisão metodológica.
