# Performance e Cache (Sprint 24, Fase 10)

## Contexto

A Fase 9 (Dashboard 2.0) expôs as cinco engines das Fases 4-8 na UI,
o que fez o Dashboard passar a compor 6 serviços a cada carregamento de
página (`build_dashboard_view`, `get_portfolio_diagnostics`,
`build_intelligence_dashboard`, `DataQualityService`,
`PortfolioHealthService`, `PortfolioRiskService`) e a Inteligência passar
a compor 2 (`build_intelligence_dashboard`, `IncomeAnalysisService`).
Como o Streamlit reexecuta o script inteiro a cada interação (qualquer
clique, mudança de filtro, etc.), sem cache isso significava recalcular
tudo do zero a cada clique — inclusive cálculos que não mudam entre um
clique e outro na mesma sessão.

## O que foi feito

Novo módulo `frontend/streamlit_app/cache.py`, com dois wrappers
decorados com `st.cache_data(ttl=300)` (5 minutos):

- `cached_dashboard_bundle(portfolio_id, exchange_rate)`: substitui as 6
  chamadas que a tela Dashboard fazia dentro do `session_scope()`.
- `cached_intelligence_bundle(portfolio_id)`: substitui as 2 chamadas que
  a tela Inteligência fazia (inteligência da carteira + análise de
  renda).

Os wrappers abrem sua própria sessão de banco internamente (nunca
recebem `db` como argumento — uma sessão SQLAlchemy não é hasheável
pelo `st.cache_data`) e devolvem só schemas Pydantic/dataclasses
imutáveis, que o Streamlit consegue serializar para guardar em cache.

### Por que TTL curto em vez de cache "para sempre"

Um TTL de 5 minutos funciona como rede de segurança para qualquer
mudança de dado que aconteça fora do conhecimento do Streamlit (ex.: um
processo externo rodando `scripts/import_portfolio.py` ou
`scripts/sync_dividendos_me.py` direto, sem passar pela UI). Mas o TTL
nunca é a única defesa: toda ação dentro da própria UI que muda um dado
lido por esses dois bundles chama `clear_all_caches()` explicitamente,
logo após persistir, para refletir a mudança na hora, sem esperar o TTL
expirar. Os pontos que fazem isso hoje:

- **Configurações**: atualizar preços em lote, salvar/limpar
  alocação-alvo simples, salvar política de investimento,
  salvar/remover regra de alocação-alvo detalhada, salvar/resetar
  premissa do Monte Carlo.
- **Ativos**: atualizar preço automático de um ativo, coletar
  fundamentos (de um ativo ou em lote), marcar/desmarcar ativo como
  manual, salvar preço manual.
- **Carteira**: importar posições (CSV/Excel).

A tela Dashboard também ganhou um botão "🔄 Atualizar dados", que chama
`clear_all_caches()` e força um novo carregamento — útil para o caso
raro de uma mudança externa ao Streamlit dentro da janela de 5 minutos.

### Por que a taxa de câmbio não precisa de invalidação explícita

`exchange_rate` é parte da chave de cache de `cached_dashboard_bundle`
(um `Decimal`, hasheável). Atualizar o câmbio (automático ou manual) já
muda essa chave e produz uma nova entrada de cache automaticamente — sem
precisar de uma chamada extra a `clear_all_caches()`.

## O que não mudou

Nenhuma engine ou serviço foi alterado — isto é puramente uma camada de
apresentação sobre chamadas já existentes e já testadas nas Fases 4-9.
O `MODEL_VERSION`/comportamento de cada engine é idêntico com ou sem
cache; a única diferença observável é que, dentro da janela de 5
minutos e sem nenhuma ação de escrita, a tela não recalcula do zero a
cada clique.

## O que ainda não existe

- Cache não é compartilhado entre usuários/sessões diferentes do
  Streamlit (`st.cache_data` já isola por argumentos de entrada, o que
  cobre o caso de uma única carteira/processo — no MVP local isso é
  suficiente).
- Não há cache para as telas Aporte, Ativos, Carteira ou Simulação —
  são ações sob demanda (o usuário clica em um botão para calcular),
  não leituras repetidas a cada navegação, então o ganho de cachear
  seria marginal.
- Não há invalidação automática por trigger de banco — depende de cada
  ação de escrita da UI chamar `clear_all_caches()` explicitamente (ver
  lista acima). Uma escrita direta no banco fora da UI (ex.: um script
  rodado em paralelo ao Streamlit) só é refletida quando o TTL de 5
  minutos expirar.
