# Investment Policy (Sprint 24, Fase 3)

## O que é

`InvestmentPolicy` é uma tabela nova (`investment_policy`) que guarda, por
carteira, o perfil do investidor e os limites/parâmetros que orientam o
Decision Engine (hoje) e, no futuro, o Simulation Engine (Monte Carlo) e o
Risk Engine 2.0.

Não é uma engine e não calcula nada sozinha. É configuração explícita do
usuário — a LG INVEST não é uma consultoria de investimentos e nenhum dos
valores aqui é uma "recomendação". Os campos existem para que as engines
parem de hardcodar limites (ex.: "peso máximo de 15% por ativo") dentro do
próprio código e passem a ler de um lugar único, editável, com histórico.

## Por que existe

Antes da Fase 3, regras como "não deixar um ativo passar de X% da carteira"
ou "manter exposição internacional entre Y% e Z%" não existiam em lugar
nenhum do sistema — ou estavam implícitas no código do Decision Engine 2.0,
ou simplesmente não eram verificadas. Isso violava o princípio central do
projeto (LG INVEST como Investment Decision System, não como dashboard): um
sistema de decisão precisa de regras explícitas e editáveis, não de números
soltos dentro de uma função Python.

## Campos

### Perfil

| Campo | Tipo | Descrição |
|---|---|---|
| `investor_profile` | string | Descrição livre do perfil (ex.: "Buy and Hold - crescimento de longuíssimo prazo") |
| `horizon_years` | int | Horizonte de investimento em anos |
| `base_currency` | string(3) | Moeda de referência para relatórios (ex.: `BRL`) |
| `risk_tolerance` | string | Um de `RISK_TOLERANCES = ("baixo", "moderado", "moderado-alto", "alto")` |

### Limites (guardrails)

| Campo | Descrição |
|---|---|
| `max_asset_weight` | Peso máximo permitido para um único ativo na carteira |
| `max_crypto_weight` | Peso máximo permitido para a classe `crypto` |
| `target_international_min` / `target_international_max` | Faixa desejada de exposição internacional |
| `target_fii_max` | Peso máximo desejado em FIIs |

### Metas de referência (informativas)

`target_brazil_equity`, `target_us_equity`, `target_etf`, `target_reit`,
`target_fixed_income` — usadas hoje apenas para contextualizar explicações
do Decision Engine. **Não são a mesma coisa que `target_allocation_rules`**
(ver `docs/TARGET_ALLOCATION_ENGINE.md`): se o usuário configurar metas
granulares lá, aquelas têm prioridade operacional sobre estes campos
informativos.

### Aportes e rebalanceamento

| Campo | Descrição |
|---|---|
| `rebalance_threshold` | Desvio (em fração, ex.: `0.05` = 5%) a partir do qual uma dimensão é considerada fora da meta |
| `monthly_contribution_default` | Valor de aporte mensal usado como sugestão de ponto de partida em telas de simulação |

`notes` é um campo de texto livre, também editável.

## Defaults da primeira leitura

Quando `InvestmentPolicyService.get_or_create(portfolio_id)` é chamado pela
primeira vez para uma carteira, uma linha é criada com os seguintes
defaults — escolhidos para refletir o perfil descrito pelo usuário do MVP
(investidor jovem, horizonte de 50+ anos, Buy and Hold, tolerância
moderada/alta a volatilidade, intenção de crescer exposição internacional,
FIIs úteis mas não centrais, Bitcoin pequeno e limitado):

```python
investor_profile = "Buy and Hold - crescimento de longuíssimo prazo"
horizon_years = 50
base_currency = "BRL"
risk_tolerance = "moderado-alto"
max_asset_weight = 0.15          # 15%
max_crypto_weight = 0.05         # 5%
target_international_min = 0.30  # 30%
target_international_max = 0.60  # 60%
target_fii_max = 0.15            # 15%
target_brazil_equity = 0.25
target_us_equity = 0.30
target_etf = 0.15
target_reit = 0.05
target_fixed_income = 0.10
rebalance_threshold = 0.05       # 5%
monthly_contribution_default = 1000.00
```

Estes números **não são uma recomendação financeira** — são só um ponto de
partida sensato para o usuário editar. O campo `notes` já nasce com um
texto explicando isso, e a tela de Configurações reforça o mesmo aviso.

Depois da primeira criação, a linha vira registro real no banco e é
sempre editável em Configurações → "Política de investimento" — a lógica
de defaults nunca sobrescreve um valor já salvo.

## Onde é usado

- **Configurações** (`frontend/streamlit_app/pages_impl/configuracoes.py`):
  seção "Política de investimento" — visualiza e edita todos os campos.
- **Decision Engine 3.0** (Fase 4, ainda não implementada): vai consumir
  `max_asset_weight`, `max_crypto_weight`, `target_international_min/max`,
  `target_fii_max` e `rebalance_threshold` como regras de bloqueio/alerta.
- **Simulation Engine / Risk Engine 2.0** (Fases 5 e 6, ainda não
  implementadas): vão consumir `horizon_years`, `risk_tolerance` e
  `monthly_contribution_default` como parâmetros de simulação.

## O que NÃO faz

- Não calcula alocação atual (isso é o Portfolio Engine).
- Não compara alocação atual x meta (isso é o Target Allocation Engine —
  ver `docs/TARGET_ALLOCATION_ENGINE.md`).
- Não decide comprar/vender nada sozinho.
- Não é populada com dados "reais" de mercado — é 100% configuração do
  usuário.

## Migration

`database/migrations/versions/f1993c6433b8_create_investment_policy_and_target_allocation_rules.py`
cria a tabela `investment_policy` (e, na mesma migration, também
`target_allocation_rules` — ver o outro doc). É puramente aditiva: não
altera nenhuma tabela existente, não faz backfill de dados. Testada nesta
sprint com `alembic upgrade head` → `downgrade -1` → `upgrade head`
novamente contra um banco SQLite descartável, confirmando que aplica e
reverte de forma limpa. **Não foi executada contra o banco de
desenvolvimento real (`data/lg_invest.db`)** nesta sessão — ver seção de
riscos na entrega da Fase 3 no `CHANGELOG.md`.
