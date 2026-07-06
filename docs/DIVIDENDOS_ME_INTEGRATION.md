# Integração Dividendos.me (Sprint 23 / 23.1 / 23.2 / 23.3)

## Decisão de produto

Dividendos.me passa a ser a fonte oficial das posições reais da carteira. A
LG INVEST continua sendo a camada de inteligência (valuation, LG Conviction
Score, recomendações de aporte, Decision Engine, Journal) — ela consome as
posições sincronizadas, mas não decide mais quantidade/preço médio por conta
própria quando a sincronização está em uso.

As duas carteiras existentes no Dividendos.me (Brasil e internacional) são
consolidadas em uma única visão na LG INVEST, sempre no `portfolio_id`
escolhido pelo usuário. A origem de cada posição fica registrada em
`Position.source` (`dividendos_me:b3` ou `dividendos_me:international`) só
para auditoria — nenhum engine depende desse campo para calcular nada.

## Por que Playwright, não uma API

Investigação ao vivo (login real + inspeção de rede) encontrou uma API REST
parcial em `api.dividendos.me/Portfolio/chart*`, mas ela só devolve
agregados de alocação (para os gráficos de pizza), nunca a lista de posições
com ticker/quantidade/preço. Essa tabela é montada no cliente por um
mecanismo que nunca aparece como uma requisição HTTP capturável (indício de
Firebase/Firestore com listener em tempo real). Sem um endpoint estável para
replicar, a extração lê a tabela já renderizada na tela "Tabela de Ativos"
via Playwright, mapeando colunas pelo texto do cabeçalho (não por posição
fixa), o que torna a extração resistente a pequenas mudanças de layout.

## Por que só local (não Streamlit Cloud)

Playwright depende de um binário de navegador (Chromium) que é pesado e
instável em ambientes de container limitados como o Streamlit Community
Cloud. Por isso a sincronização é pensada para rodar localmente (via botão
na tela ou via CLI), atualizando o banco (SQLite local ou Supabase/Postgres
remoto); o app publicado no Streamlit Cloud só lê o resultado. A tela detecta
com `is_playwright_available()` se o pacote está instalado e desabilita os
botões automaticamente quando não está — nunca tenta rodar mesmo assim.

## Segurança de credenciais (regras que nunca podem ser violadas)

- Nunca hardcoded no código, nunca commitado.
- Local: `.env` com `DIVIDENDOS_ME_EMAIL` e `DIVIDENDOS_ME_PASSWORD`
  (`.env` já está no `.gitignore`).
- Streamlit Cloud: `st.secrets["dividendos_me"]["email"/"password"]`
  (`.streamlit/secrets.toml`, também no `.gitignore`).
- A UI nunca mostra o valor — só "Credenciais configuradas: Sim/Não"
  (`backend/app/integrations/dividendos_me/secrets.py`).
- Nunca logado, nunca salvo no banco, nunca em traceback: falhas de login
  sempre viram a mensagem genérica `"Falha ao autenticar no Dividendos.me.
  Verifique credenciais ou tente novamente."` (`auth.py`).
- Sessão do Playwright é sempre efêmera: login do zero a cada execução,
  nenhum cookie/token é salvo em disco (`storage_state` nunca é usado).
- A sincronização nunca roda sozinha — só por clique explícito na tela ou
  por comando explícito no terminal (nunca em toda carga do app).

## Arquitetura

```
backend/app/integrations/dividendos_me/
  secrets.py        # leitura/mascaramento de credenciais
  schemas.py         # DTOs (ExtractedPosition, SyncPreview, SyncDiff, SyncRunResult,
                      # IncomeSyncPreview/RunResult, IncomeMonthlySyncPreview/RunResult)
  parser.py          # normalização pura de número/percentual/ticker de posições (sem I/O)
  income_parser.py    # normalização pura de proventos (calendário + histórico mensal, sem I/O)
  auth.py             # login via Playwright, erro genérico
  client.py           # navega + extrai carteira/proventos (Playwright)
  service.py          # orquestra client+parser, calcula diff/seções esperadas, grava no banco
  income_service.py   # orquestra os dois fluxos de proventos (calendário + histórico mensal)
scripts/sync_dividendos_me.py               # CLI local
frontend/streamlit_app/pages_impl/sincronizar_dividendos_me.py  # tela (5A/5B separadas)
frontend/streamlit_app/components/import_preview.py             # preview/diff da carteira
frontend/streamlit_app/components/income_preview.py             # preview do calendário futuro
frontend/streamlit_app/components/monthly_summary_preview.py    # preview do histórico mensal
database/migrations/versions/d4a8f21e9c07_...py  # position.source + external_sync_runs
database/migrations/versions/..._create_income_events.py         # income_events (calendário)
database/migrations/versions/b2f6a1d84c33_...py  # income_monthly_summaries (histórico mensal)
```

Scraping/Playwright fica isolado em `integrations/` — nunca importado por
`engines/` nem por `services/` que fazem cálculo financeiro.

## Modos de sincronização

- `dry-run`: busca e mostra o preview. Nunca grava nada. Modo padrão.
- `replace` (principal): substitui 100% das posições do `portfolio_id` pelas
  posições consolidadas do Dividendos.me. Exige confirmação explícita —
  na UI, digitar a palavra `SUBSTITUIR`; na CLI, a flag `--confirm`.
- `update` (opcional, uso futuro): cria/atualiza posições sem remover as que
  não vieram da fonte externa. Também exige confirmação.

Ativos marcados `review_required` (ticker/seção não reconhecidos com
confiança) nunca são criados/atualizados automaticamente em nenhum modo —
ficam só visíveis no preview para revisão manual.

## Fluxo na tela "Sincronizar Dividendos.me"

1. Status: credenciais configuradas (sim/não), Playwright disponível
   (sim/não), última sincronização com sucesso.
2. "Testar login": confirma que a conta funciona, não busca nada.
3. "Buscar carteira": login + extração de todas as seções + preview (total
   de patrimônio, ativos encontrados, diff contra a LG INVEST hoje,
   seções que falharam, ativos para revisão manual). Nada é gravado ainda.
4. Escolha do modo (`replace` recomendado, `update` opcional) + campo de
   confirmação textual. O botão de confirmar só habilita com a palavra
   exata digitada.
5. Após confirmar: aplica a sincronização, grava um registro de auditoria em
   `external_sync_runs`, mostra o resumo final (criadas/atualizadas/
   removidas, avisos) e sugere atualizar preços/fundamentos em seguida.

## CLI local

```bash
python -m scripts.sync_dividendos_me --portfolio-id 1 --mode dry-run
python -m scripts.sync_dividendos_me --portfolio-id 1 --mode replace --confirm
python -m scripts.sync_dividendos_me --portfolio-id 1 --mode update --confirm
```

Lê as credenciais só do `.env` (`os.getenv`), nunca de argumento de linha de
comando. `--headed` roda o navegador visível, útil para depurar localmente.

## Normalização de ticker (resumo)

| Seção Dividendos.me       | Regra                                                    |
|----------------------------|-----------------------------------------------------------|
| Brasil (Ações/FIIs/ETFs/BDRs) | adiciona `.SA` se ausente; classe pelo subgrupo da tabela |
| EUA (Ações/ETFs/REITs)     | remove `.SA` se presente; classe pelo subgrupo da tabela  |
| Criptomoedas               | `BTC` -> `BTC-USD` (validado); outras moedas ficam `review_required` |
| Renda Fixa (Tesouro Direto) | sintetiza `TESOURO-{INDEXADOR}-{ANO}`; ativo manual (`is_manual=True`) |

Qualquer combinação não reconhecida vira `review_required=True` em vez de
classificada silenciosamente errada.

## Limitações conhecidas

- **Proteção por seção esperada (Sprint 23.3):** as seções que a carteira
  atual (no banco) indica que deveriam vir na extração (`brasil`/`eua`/
  `criptomoedas`/`renda_fixa`) são calculadas antes de comparar com o que a
  extração realmente trouxe. Se uma seção esperada vier vazia — mesmo sem o
  client reportar um erro explícito —, ela entra em `sections_failed`
  (efetivo) e o `total_patrimonio` do preview é marcado como
  `total_patrimonio_status="partial"`. O modo `replace` é bloqueado nesse
  caso (mensagem fixa "Extração incompleta: uma ou mais seções da carteira
  não foram carregadas. Substituição bloqueada para evitar perda de
  ativos."); não existe bypass/force para esse bloqueio em nenhuma camada.
  O modo `update` nunca é bloqueado por isso, pois nunca remove posições.
- A causa raiz de por que as seções "EUA"/"Criptomoedas"/"Renda Fixa"
  eventualmente navegam sem lançar exceção do Playwright mas retornam zero
  linhas extraídas **ainda não foi confirmada** contra o site ao vivo (este
  ambiente de desenvolvimento não tem acesso de rede/Playwright real). A
  instrumentação de navegação adicionada nesta sprint
  (`SectionDiagnostics.navigation_detail`, com rótulo do acordeão clicado e
  URL final) e a nova lógica de retry-on-empty devem ajudar a diagnosticar
  isso no próximo dry-run real, mas não garantem sozinhas a correção da
  causa raiz.
- A coluna "DIV" da tabela do Dividendos.me foi interpretada como dividend
  yield percentual (`dividend_yield_pct`), não como valor de dividendos
  recebidos em R$ — não havia confirmação suficiente para tratá-la como
  valor monetário, e o projeto prefere não inventar um dado incerto.
- `Position.opened_at` é preenchido com a data da sincronização (o
  Dividendos.me não expõe data de abertura da posição) — campo informativo,
  não usado em nenhum cálculo de rentabilidade.
