# Provedores de Dados Fundamentalistas (Sprint 28)

## Objetivo

Documentar a arquitetura plugável de fontes de dados fundamentalistas
já existente desde o Sprint 13 — e deixar explícito como adicionar uma
nova fonte no futuro (ex.: Fundamentus, Status Invest, CVM/B3) sem
reescrever `FundamentalsService`, `DataRefreshService` ou qualquer
engine. Esta sprint não implementou nenhuma fonte nova: o trabalho foi
garantir que a arquitetura já suporta múltiplas fontes com fallback
seguro (nunca inventar dado, nunca quebrar por falha de uma fonte) e
documentar isso claramente.

## O contrato: `FundamentalsProvider`

```python
# backend/app/etl/providers/fundamentals_provider.py
class FundamentalsProvider(ABC):
    name: str = "abstract"

    def get_latest(self, ticker: str) -> FundamentalData | None: ...
    def get_history(self, ticker: str) -> list[FundamentalData]: ...
```

Todo provedor de fundamentos — atual ou futuro — implementa essa
interface. `FundamentalsService` (e, por extensão,
`DataRefreshService`) recebe o provider por injeção de dependência no
construtor:

```python
FundamentalsService(db, YahooFundamentalsProvider())
```

Nunca instancia um provider concreto internamente por conta própria —
isso é o que torna a fonte trocável/combinável sem tocar no serviço.
Mesmo padrão já usado para preços (`MarketDataProvider`) e câmbio
(`FxRateProvider`).

## Fonte atual: Yahoo Finance

`backend/app/etl/providers/yahoo_fundamentals_provider.py` —
`YahooFundamentalsProvider` é hoje a única implementação em produção.
Usa a biblioteca `yfinance` para buscar os ~30 campos fundamentalistas
suportados (ver lista completa em
`backend/app/services/fundamentals_service.py::_SNAPSHOT_FIELDS`).
Toda `FundamentalSnapshot` gravada por essa fonte recebe
`source="yahoo"`.

### Limitações conhecidas da fonte atual

- Cobertura inconsistente para ações brasileiras de segunda linha —
  campos como FCF, patrimônio líquido ou ROIC frequentemente vêm
  `None` (a causa raiz do problema relatado pelo usuário nesta sprint,
  ex.: `ALUP4.SA`).
- Nenhum dado histórico anterior a alguns anos, dependendo do ticker.
- Sujeito a mudanças de schema/rate-limit da API não-oficial do Yahoo
  Finance.

Quando o Yahoo Finance não cobre um campo, a plataforma **nunca
inventa um valor**: o campo fica `available=False` no Data Coverage
Report (`docs/DATA_COVERAGE_REPORT.md`), e o usuário tem dois caminhos
para preencher a lacuna: aguardar uma fonte alternativa ser
implementada, ou usar a Importação Manual de Fundamentos (ver
`docs/MANUAL_FUNDAMENTALS_IMPORT.md`).

## Camada 2 do fallback: importação manual

A importação manual (`source="manual_import"`) já funciona hoje como
uma segunda "fonte" no sentido dos dados — não implementa
`FundamentalsProvider` (é orientada a arquivo, não a chamada de
ticker), mas persiste na mesma tabela `fundamental_snapshots`, com a
mesma prioridade de leitura para todas as engines (nenhuma engine
distingue `"yahoo"` de `"manual_import"` ao consumir um campo — o
valor é o valor). Ver `docs/MANUAL_FUNDAMENTALS_IMPORT.md`.

## Como falha de fonte externa é tratada (nunca derruba o sistema)

`FundamentalsService.collect_for_asset` envolve toda chamada ao
provider em `try/except Exception`:

```python
try:
    latest = self.provider.get_latest(ticker)
except Exception as exc:
    logger.error("Erro coletando fundamentos de %s: %s", ticker, exc)
    return FundamentalsCollectionResult(
        ticker=ticker, collected=False, error=f"falha na coleta: {type(exc).__name__}"
    )
```

Garantias, testadas em `backend/tests/unit/test_fundamentals_service.py`
e `backend/tests/unit/test_data_refresh_service.py`:

- Uma falha de rede/parsing em UM ativo nunca derruba o restante do
  lote (`collect_all`, `DataRefreshService.refresh_portfolio_fundamentals`)
  — cada ativo é processado e persistido individualmente.
- Um snapshot já salvo no banco **nunca é apagado ou zerado** por uma
  falha de coleta subsequente — a falha só impede a atualização; o
  dado antigo permanece exatamente como estava
  (`test_provider_failure_keeps_existing_snapshot_and_logs_warning`).
- Toda falha é registrada em log (`logger.error`/`logger.warning`) —
  nunca engolida silenciosamente.
- Falha ao buscar o histórico (`get_history`) não bloqueia o snapshot
  mais recente já coletado com sucesso (`get_latest`) — são tratados
  como independentes.
- Quando o provider simplesmente não tem o dado (`get_latest` retorna
  `None`, sem exceção), o resultado é `reason="sem dado do provider"`
  — distinto de uma falha real (`error=...`), para que o Data Coverage
  Report e a UI expliquem a diferença corretamente.

## Como adicionar uma nova fonte no futuro

1. Criar uma classe em `backend/app/etl/providers/` que implemente
   `FundamentalsProvider` (`get_latest`/`get_history`), devolvendo
   `FundamentalData` (mesmo contrato usado pelo Yahoo).
2. Decidir a estratégia de combinação com o Yahoo — duas opções já
   suportadas pela arquitetura atual sem mudança estrutural:
   - **Fonte alternativa por ativo** (ex.: só para tickers que o Yahoo
     não cobre): um serviço "roteador" que tenta o Yahoo primeiro e
     cai para a fonte alternativa quando o campo relevante vier
     ausente — nenhuma peça nova precisa ser criada além desse
     roteador, que também implementaria `FundamentalsProvider`.
   - **Fonte complementar por campo**: rodar as duas fontes e mesclar
     campo a campo (a fonte alternativa só preenche o que o Yahoo
     deixou `None`) — usar o mesmo mecanismo de "nunca sobrescrever
     dado bom com `None`" já existente em
     `FundamentalsService._upsert`.
3. Nunca sobrescrever um valor válido de uma fonte com `None` de outra
   — regra já garantida por `_upsert` (só grava quando
   `getattr(data, field, None) is not None`).
4. Registrar a nova fonte em `FUNDAMENTALS_SOURCES`
   (`backend/app/infrastructure/database/models/fundamental_snapshot.py`)
   para que o valor de `source` seja válido.
5. Testar isoladamente com um provider fake (mesmo padrão de
   `FakeFundamentalsProvider` nos testes existentes) — nenhum teste do
   projeto depende de rede real.

## O que ficou fora desta sprint

- Nenhuma fonte nova foi implementada (Fundamentus, Status Invest,
  CVM/B3, Dividendos.me como fonte de fundamentos) — só a arquitetura
  e a documentação de como adicionar uma.
- Nenhum "roteador"/estratégia de combinação automática entre múltiplas
  fontes foi implementado — hoje há só uma fonte automática (Yahoo) e
  uma manual (importação CSV/Excel).
