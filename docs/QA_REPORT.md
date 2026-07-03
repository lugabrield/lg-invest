# Relatório de QA — LG INVEST MVP

Documento de qualidade do MVP (Volume 18 / Volume 20 prompt 12), gerado ao final do Sprint 10.

## 1. Estado geral

- **153 testes**, todos passando, determinísticos e sem acesso à rede (mocks/fixtures).
- **Cobertura total: 86%.**
- `ruff` e `black` limpos; nenhuma chave de API no código; `.env` fora do versionamento.

## 2. Cobertura por área vs. metas (Volume 18 §13)

| Área | Cobertura | Meta MVP | Status |
|---|---|---|---|
| Portfolio Engine | 100% | 90% | ✅ |
| Decision Engine | 98% | 90% | ✅ |
| LG Score Engine | 97% | 85% | ✅ |
| ETL | 92% | 70% | ✅ |
| Modelos de banco | 100% | — | ✅ |
| Serviços (orquestração) | 89% | 80% | ✅ |

As lacunas restantes são majoritariamente branches defensivos, o entrypoint `main.py` e schemas exercitados indiretamente — nenhuma regra financeira sem teste.

## 3. Testes por categoria

- **Unitários das engines** — valores conhecidos, limites 0–100, pesos, classificação.
- **Regressão** (`tests/regression/`) — carteiras de exemplo (Brasil e Global) comparadas a um baseline salvo. Qualquer mudança de engine falha o teste; a atualização do baseline passa a ser um ato consciente.
- **Determinismo** — mesma entrada → mesma saída nas três engines.
- **Casos extremos** — carteira de 500 ativos, preços zerados, aporte negativo, ativo único (HHI=1), todos sobreconcentrados.
- **ETL** — parsing com yfinance mockado; nenhum teste toca a rede.
- **Persistência** — FK, unicidade, duplicidade, ciclo de vida da tese.

## 4. Riscos encontrados e tratados

| Risco | Severidade | Tratamento |
|---|---|---|
| Renormalização de pesos violava o teto de 50% no Decision Engine | Alta | Corrigido no Sprint 7; `_apply_min_max` reescrito; coberto por teste. |
| Divisão por zero (rentabilidade com preço médio 0; HHI de carteira vazia) | Média | Retorno `None`/neutro; testado. |
| Preço ausente contaminando totais | Média | Posições sem preço vão para `unpriced_tickers`, fora dos totais. |
| Dependência de API instável (yfinance) | Média | Isolada atrás de `MarketDataProvider`; substituível; testes com mock. |
| Câmbio não convertido em carteira multi-moeda | Conhecida | Somado por moeda + flag `is_multi_currency`; documentado. |

## 5. Limitações conhecidas do MVP

- **LG Score por proxy:** pilares derivam de classe do ativo e histórico de preços, não de fundamentos (ROIC, margens, CAGR de lucro), ainda não coletados. Confiança baixa sinaliza a limitação.
- **Sem conversão cambial:** o Portfolio Engine não converte BRL/USD.
- **Concentração em carteiras pequenas:** o limite de 30% pode barrar a maioria dos ativos e deixar parte do aporte sem alocar (comportamento correto e sinalizado; limite parametrizável).
- **Sem peso-alvo por padrão:** o gap de alocação é 0 sem política definida.
- **Fora do MVP:** valuation por DCF/DDM, risco agregado (VaR/drawdown/beta), Monte Carlo, IA generativa, multiusuário, integração com corretoras.

## 6. Segurança (Volume 18 §11)

- Nenhum `.env` versionado; `.gitignore` cobre `.env`, banco e exports pessoais.
- Nenhuma chave de API no código — tudo via `.env`.
- Logs não expõem dados sensíveis além do necessário.

## 7. Como executar

```bash
pip install -r requirements-dev.txt
cp .env.example .env
pytest                 # 153 testes
pytest --cov=backend/app --cov-report=term-missing   # com cobertura
```
