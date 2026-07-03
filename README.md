# LG INVEST

**Investment Intelligence Platform** — transforma dados financeiros em decisões de investimento explicáveis, auditáveis e reproduzíveis para um investidor Buy & Hold de longo prazo.

A LG INVEST não é uma planilha nem um dashboard. O objetivo é responder perguntas de decisão: **onde aportar, por quê, com qual nível de confiança e qual o impacto na carteira de longo prazo.**

> Status atual: **MVP COMPLETO — 10 sprints entregues.** Cadastro de carteira,
> ETL de preços, Portfolio Engine, LG Score, Decision Engine, LG Terminal
> (Streamlit) e Investment Journal, com 153 testes (cobertura 86%; engines 98%),
> fixtures de regressão e QA final. Ver `docs/QA_REPORT.md` e `docs/MVP_CHECKLIST.md`.

## Escopo do MVP

Incluído: cadastro manual de carteira, preços via yfinance, SQLite, Portfolio Engine, LG Score v1, Decision Engine v1, interface Streamlit, Investment Journal básico, testes das fórmulas.

Fora do MVP: integração com corretoras, multiusuário, React/Next.js, machine learning, IA generativa, Monte Carlo, execução de ordens.

## Stack do MVP

Python 3.11+ · SQLite · SQLAlchemy 2.0 · Alembic · Pydantic · pandas/numpy · yfinance · Streamlit · pytest · ruff/black.

## Estrutura do repositório

```
lg-invest/
├── backend/app/        # core, models, schemas, engines, etl, services, infrastructure
├── frontend/           # interface Streamlit (LG Terminal)
├── database/           # migrations (Alembic) e seeds
├── data/               # banco SQLite e dados (não versionados)
├── docs/               # documentação por módulo
├── scripts/            # rotinas auxiliares
└── docker/             # containers (adotado cedo, não obrigatório no dia 1)
```

## Como rodar localmente (< 10 minutos)

1. **Pré-requisitos:** Python 3.11 ou superior.

2. **Clonar e entrar no projeto:**
   ```bash
   cd lg-invest
   ```

3. **Criar ambiente virtual e ativar:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   ```

4. **Instalar dependências:**
   ```bash
   pip install -r requirements-dev.txt
   ```

5. **Configurar variáveis de ambiente:**
   ```bash
   cp .env.example .env
   ```

6. **Validar o setup (entrypoint do backend):**
   ```bash
   python -m backend.app.main
   ```

7. **Aplicar as migrations do banco (cria `data/lg_invest.db`):**
   ```bash
   python -m alembic upgrade head
   ```

8. **Popular ativos de demonstração (idempotente):**
   ```bash
   python -m database.seeds.assets_seed
   ```

9. **Importar uma carteira de exemplo (cria a carteira e importa posições):**
   ```bash
   python -m scripts.import_portfolio \
       --portfolio-id 1 \
       --file database/seeds/positions_template.csv \
       --create-portfolio
   ```
   Aceita CSV e Excel. Reimportar o mesmo arquivo atualiza as posições (não duplica).
   Linhas inválidas geram um relatório de erros por linha sem abortar as válidas.

10. **Atualizar preços de mercado (via yfinance; requer internet):**
    ```bash
    python -m scripts.update_prices --ticker WEGE3.SA
    python -m scripts.update_prices --all
    ```
    A coleta é incremental (busca só a partir da última data registrada) e
    idempotente (não duplica preços). Preços inválidos são rejeitados com motivo.

11. **Ver o resumo consolidado da carteira (Portfolio Engine):**
    ```bash
    python -m scripts.portfolio_summary --portfolio-id 1
    ```
    Mostra valor total, pesos por ativo/classe, rentabilidade, maior posição,
    concentração (HHI) e exposição por moeda. Carteiras com mais de uma moeda
    são sinalizadas (`is_multi_currency`) — o v1 não converte câmbio.

12. **Calcular o LG Score (score de um ativo ou ranking da carteira):**
    ```bash
    python -m scripts.lg_score --ticker WEGE3.SA
    python -m scripts.lg_score --portfolio-id 1
    ```
    Cada ativo recebe nota 0–100 com as 5 notas parciais, classificação,
    Confidence Score e explicação por fator. No v1 os pilares são proxies
    sobre os dados disponíveis; confiança baixa sinaliza essa limitação.

13. **Gerar recomendação de aporte (Decision Engine):**
    ```bash
    python -m scripts.recommend --portfolio-id 1 --amount 1000
    python -m scripts.recommend --portfolio-id 1 --amount 1000 --blocked VOO
    ```
    Devolve a distribuição do aporte com justificativa por ativo, score de compra,
    alertas de concentração, ativos ignorados (com motivo) e nível de confiança.
    A soma nunca ultrapassa o aporte; a recomendação é salva para auditoria
    (use `--no-persist` para não salvar).

14. **Rodar os testes:**
    ```bash
    pytest
    ```

15. **Abrir a interface (LG Terminal — MVP funcional):**
    ```bash
    streamlit run frontend/streamlit_app/app.py
    ```
    Seis telas ligadas aos engines: Dashboard (resumo da carteira), Carteira
    (posições + importar CSV/Excel), Ativos (lista + LG Score explicável),
    Aporte (recomendação do Decision Engine), Journal (teses) e Configurações
    (ambiente + atualizar preços). A interface consome os serviços; não recalcula.

## Qualidade de código

```bash
black .          # formatação
ruff check .     # lint
pytest --cov     # testes com cobertura
```

## Princípios

Toda recomendação deve ser **explicável, auditável e baseada em evidências**. Regras financeiras nunca se misturam com a interface. Nenhuma chave de API no código — tudo via `.env`. Cada cálculo financeiro relevante terá teste unitário.

## Limitações conhecidas (MVP)

- **Câmbio não convertido:** o Portfolio Engine soma por moeda e sinaliza `is_multi_currency`; não há conversão BRL/USD (depende de série de câmbio, sprint futuro).
- **LG Score por proxy:** os pilares derivam de classe do ativo e histórico de preços, não de fundamentos (ROIC, margens, CAGR de lucro), que ainda não são coletados. A confiança baixa sinaliza essa limitação.
- **Decision Engine e carteiras pequenas:** com o limite de concentração de 30%, carteiras com poucos ativos podem ter a maioria barrada por sobreconcentração, deixando parte do aporte sem alocar. É o comportamento correto e honesto (ignora com motivo e alerta), mas o limite é parametrizável (`DecisionConfig.over_concentration_limit`) e deve ser ajustável por perfil no futuro.
- **Sem peso-alvo:** sem política de alocação definida, o gap de alocação é 0 e a decisão é guiada por LG Score + concentração invertida.

## Roadmap de sprints

| Sprint | Tema |
|---|---|
| 1 ✅ | Setup do projeto |
| 2 ✅ | Banco e modelos (SQLAlchemy + SQLite + Alembic) |
| 3 ✅ | Cadastro de carteira (importação CSV/Excel) |
| 4 ✅ | Preços via yfinance (ETL) |
| 5 ✅ | Portfolio Engine v1 |
| 6 ✅ | LG Score v1 |
| 7 ✅ | Decision Engine v1 |
| 8 ✅ | Streamlit MVP |
| 9 ✅ | Investment Journal (teses, revisões, snapshots) |
| 10 ✅ | Testes e refinamento / QA final |

**MVP completo.** Evoluções pós-MVP: valuation DCF/DDM, risco agregado (VaR/drawdown/beta), simulação Monte Carlo, IA generativa, multiusuário e integração com corretoras.
