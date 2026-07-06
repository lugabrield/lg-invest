# Watchlist / Radar Engine (Sprint 25, Parte 2)

## Contexto

Até a Sprint 24, a LG INVEST só sabia falar de ativos que já eram posição.
Não havia lugar para registrar "estou de olho nisso" sem já ter comprado —
o usuário tinha que guardar essa informação na cabeça ou fora do sistema.
A Sprint 25 (Parte 2) resolve isso com dois componentes novos, deliberadamente
separados:

- **Watchlist** (`watchlist_assets`, `WatchlistService`): cadastro de ativos
  candidatos. Puro CRUD + coleta de dados, sem opinião.
- **Radar Engine** (`engines/radar`, `RadarService`): compara posições atuais
  com a Watchlist e classifica cada ativo. Engine pura, sem banco/rede.

## Garantias centrais (testadas explicitamente)

- **A Watchlist nunca cria uma `Position`.** Marcar um ativo como "bought"
  só registra que o usuário passou a ter (ou vai ter) posição — normalmente
  depois de detectar isso via sincronização Dividendos.me ou manualmente.
  Nunca mexe em patrimônio, nunca cria linha em `positions`.
- **O Radar nunca cria posição.** É uma classificação de apoio à decisão,
  não uma ação.
- **Nenhuma classificação implica venda.** Mesmo um ativo já na carteira
  com score fraco vira `"monitor"`, nunca `"avoid"` — esse rótulo é
  reservado a candidatos que ainda não são posição.
- **Nenhum dado é inventado.** Sem preço/fundamentos suficientes, o
  resultado vira `insufficient_data` (Radar) ou `low_confidence=True`
  (coleta de dados da Watchlist) — nunca um placeholder fabricado.
- Testes: `test_watchlist_service.py` (17), `test_radar_engine.py` (13),
  `test_radar_service.py` (5), `test_decision_watchlist_integration.py` (7),
  `test_decision_allocation_limits.py` (9 no total, 5 novos para o teto de
  ativo novo).

## Watchlist

### Modelo (`watchlist_assets`, migration `a3f7c9e2d156`)

Campos: `id`, `portfolio_id`, `ticker`, `name`, `asset_class`, `country`,
`currency`, `sector`, `status`, `priority` (0-10, manual), `thesis`, `notes`,
`source` ("manual"/"imported"/"future_api"), `created_at`, `updated_at`.
Índice único em `(portfolio_id, ticker)` — um ticker só pode ter um registro
ativo por carteira.

### Os 5 status (`WATCHLIST_STATUSES`)

- **watching**: só acompanhando, sem convicção formada.
- **candidate**: candidato ativo a receber aporte (via Radar/Aporte v3).
- **blocked**: usuário decidiu bloquear manualmente — nunca vira candidato,
  mesmo com bom score. Decisão explícita do usuário, não um limite de
  carteira (esse é o papel do Target Allocation Rule Engine).
- **discarded**: usuário olhou e descartou. Fica no histórico, mas some das
  telas ativas e do Radar. Pode ser recadastrado (o `add_watchlist_asset`
  faz update em vez de rejeitar por duplicata quando o status atual é
  `discarded`).
- **bought**: usuário comprou (ou detectou que já tinha) o ativo. Não
  remove o registro nem cria `Position` — só sinaliza.

### Serviço (`WatchlistService`)

CRUD: `add_watchlist_asset`, `update_watchlist_asset`, `remove_watchlist_asset`,
`list_watchlist_assets`, `get_watchlist_asset_by_ticker`, `set_status`,
`mark_as_bought`, `block_asset`, `discard_asset`.

Validações (`WatchlistAssetCreate`/`WatchlistAssetUpdate`, Pydantic):
ticker/name obrigatórios, `asset_class` precisa estar em `ASSET_CLASSES`,
`status` precisa estar em `WATCHLIST_STATUSES`, país/moeda normalizados
para maiúsculas. `add_watchlist_asset` rejeita duplicata **ativa** (status
≠ `discarded`) do mesmo ticker na carteira.

`WatchlistAssetView.already_in_portfolio`: sinalizado pelo serviço
(`AssetRepository.get_by_ticker` + `PositionRepository.get_by_portfolio_and_asset`),
nunca calculado no schema — permite à UI avisar "você já tem isso" sem
alterar o registro da watchlist.

### Coleta de dados (`collect_data_for_asset`)

Passo a passo, sempre sem inventar dado:

1. Garante o cadastro em `assets` (cria via `AssetService` se ainda não
   existir, usando os dados já preenchidos na watchlist).
2. Calcula LG Score (`LGScoreService`) e Conviction Score
   (`ConvictionScoreService`) com o que **já existir** de preço/fundamentos
   — não dispara coleta de preço/fundamentos externa (isso é
   responsabilidade da tela Ativos ou de um job dedicado, para não
   esconder uma chamada de rede dentro do Radar).
3. Marca `low_confidence=True` quando a confiança calculada fica abaixo de
   `0.5`, ou quando nem LG Score nem Conviction Score puderam ser
   calculados — sempre com o motivo em `notes`.

Retorna `WatchlistDataCollectionResult` (ticker, asset_ensured,
price_collected, fundamentals_collected, lg_score, conviction_score,
confidence, low_confidence, notes).

## Radar Engine

### Entrada (`RadarCandidateInput`, `engines/radar/inputs.py`)

Cada candidato — posição existente ou item da Watchlist — chega já
resolvido: ticker/nome/classe, `watchlist_status` (`None` quando é só
posição sem registro na watchlist), `is_current_holding`, `current_weight`,
scores, `dimension_blocked`/`dimension_blocked_reason` (ver abaixo).

### As 6 classificações (`RADAR_CLASSIFICATIONS`)

| Classificação | Quando |
|---|---|
| `blocked` | `watchlist_status == "blocked"` (decisão do usuário) OU a dimensão (classe/moeda/país) já está `"blocked"` no Target Allocation Rule Engine v2. |
| `insufficient_data` | Sem LG Score/Conviction Score, ou confiança abaixo de `0.5`. |
| `current_holding_candidate` | Já é posição e o score efetivo é bom (≥ 60). |
| `new_candidate` | Não é posição, status `"candidate"` na watchlist, score bom (≥ 60). |
| `avoid` | Não é posição, score fraco (< 40) — reservado a candidatos NOVOS. |
| `monitor` | Todo o resto (já é posição com score mediano/fraco, ou candidato novo com score intermediário). |

Ordem de checagem: bloqueio explícito > dado insuficiente > é posição? >
score. Um ativo já na carteira nunca cai em `avoid` — na pior das
hipóteses vira `monitor`, preservando a regra de nunca sugerir venda.

`_effective_score`: usa Conviction Score quando disponível, cai para LG
Score senão — mesma cadeia de fallback do Decision Engine 3.0.

### Serviço (`RadarService.evaluate(portfolio_id)`)

1. Lê o `PortfolioSummary` (posições atuais + pesos).
2. Lê a Watchlist, excluindo `discarded`.
3. Calcula, para cada posição/candidato, LG Score/Conviction Score (sem
   coletar dado novo).
4. Resolve o bloqueio por dimensão via
   `TargetAllocationService.evaluate_portfolio_rules()` — só marca
   `dimension_blocked=True` quando existe uma regra detalhada (Target
   Allocation Rule Engine v2) com `gap_status == "blocked"` para a
   classe/moeda/país do candidato.
5. Chama `evaluate_radar()` (engine pura).

**Limitação documentada:** o bloqueio por dimensão do Radar reflete só a
regra detalhada de alocação-alvo — não a Investment Policy isolada (que só
tem efeito real no bloqueio do Decision Engine 3.0 durante o aporte, via a
precedência corrigida na Parte 1). Isso é uma escolha deliberada para não
duplicar a lógica de precedência dentro do Radar; ver
`docs/DECISION_ENGINE_3.md`.

## Integração opcional no Aporte v3 (Sprint 25, Parte 2.5)

`DecisionService.recommend_v3(..., allow_watchlist_candidates=False)`:

- **Default `False`**: comportamento idêntico ao pré-Sprint 25. O Radar
  nunca é chamado.
- **`True`**: além das posições existentes, `build_inputs_v3` chama
  `RadarService.evaluate()` e inclui só os candidatos classificados como
  `"new_candidate"` (nunca `monitor`/`avoid`/`blocked`/`insufficient_data`,
  nunca um ticker que já é posição). Cada um entra como `DecisionInput`
  com `current_weight=0` e `is_new_from_watchlist=True`.
- **Teto de alocação inicial**: `DecisionConfig.max_new_asset_weight`
  (default 25%, dentro da faixa 10%-25% pedida) é aplicado só a tickers
  marcados como `is_new_from_watchlist` — nunca ao restante da carteira.
  Implementado em `engines/decision/allocation.py`
  (`select_and_distribute(..., new_asset_tickers=...)`): o teto por ativo
  vira `min(max_single_weight, max_new_asset_weight)` para esses tickers;
  o excedente fica não alocado, nunca redistribuído para outro ativo à
  força.
- **Linguagem**: a recomendação nunca diz "compre" — os alertas usam
  "considere iniciar uma posição pequena" e deixam explícito que nada é
  registrado automaticamente.
- **UI (`pages_impl/aporte.py`)**: checkbox "Permitir ativos novos da
  watchlist" (só visível com o motor v3). Quando há item novo na
  recomendação, a tela separa visualmente "Já tenho" de "Novo candidato
  (Watchlist)", cada um com sua própria justificativa por ativo.

## Tela Radar (Sprint 25, Parte 2.6)

`pages_impl/radar.py`, registrada em `app.py` na ordem: Dashboard, Carteira,
Ativos, Inteligência, Aporte, Simulação, **Radar**, Journal, Sincronizar
Dividendos.me, Configurações.

Seções: resumo da Watchlist (contagem por status), formulário de cadastro
rápido, tabela da Watchlist com ações (coletar dados de um/de todos,
bloquear, descartar, marcar comprado, remover), e o Radar de oportunidades
propriamente dito — uma seção por classificação, com tabela e explicação
por ativo (`reasons` do `RadarClassificationResult`).

## Como validar localmente

```bash
# Migration (upgrade/downgrade/upgrade contra banco descartável)
DATABASE_URL="sqlite:////tmp/lg_watchlist_test.db" python -m alembic upgrade head
DATABASE_URL="sqlite:////tmp/lg_watchlist_test.db" python -m alembic downgrade -1
DATABASE_URL="sqlite:////tmp/lg_watchlist_test.db" python -m alembic upgrade head

# Testes
python -m pytest backend/tests/unit/test_watchlist_service.py -v
python -m pytest backend/tests/unit/test_radar_engine.py backend/tests/unit/test_radar_service.py -v
python -m pytest backend/tests/unit/test_decision_watchlist_integration.py -v
```

Na UI: abra a tela **Radar**, cadastre um candidato, clique em "Coletar
dados" (o score vai ficar com confiança baixa até fundamentos/preço serem
coletados de verdade pela tela Ativos), depois vá em **Aporte**, escolha o
motor v3 e marque "Permitir ativos novos da watchlist" para ver o candidato
aparecer separado em "Novo candidato (Watchlist)".

## O que ainda não existe

- Nenhuma tela de histórico mostra como a classificação do Radar mudou ao
  longo do tempo para um mesmo ativo.
- O universo de tickers sugerido pelo usuário no pedido original da Sprint
  25 (ações/ETFs/FIIs americanos e brasileiros) não foi pré-cadastrado —
  por design: a Watchlist começa vazia para toda carteira, o usuário
  cadastra manualmente o que quiser acompanhar.
- Importação em lote (CSV) de candidatos não existe ainda — `source` já
  reserva o valor `"imported"` para quando isso for implementado.
- O Radar não repete, hoje, a precedência completa (regra detalhada >
  Investment Policy) do Decision Engine 3.0 para o bloqueio por dimensão —
  ver limitação documentada acima.
