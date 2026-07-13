# Release Checklist — LG INVEST v1.0.0

Os 24 critérios de prontidão definidos para fechar a v1.0 (Sprint 31 — Release Candidate), cada um verificado com evidência concreta desta sprint.

## 1. App abre sem erro

✅ `streamlit run frontend/streamlit_app/app.py` carrega a sidebar e as 10 telas sem traceback. Confirmado por smoke test de importação de todas as telas + `app.py` (Sprint 30) e por execução real dos services de cada tela contra o banco de produção nesta sprint (Parte 7 — QA funcional).

## 2. Todas as telas funcionam

✅ Dashboard, Carteira, Aporte, Inteligência, Ativos, Radar, Simulação, Journal, Sincronizar Dividendos.me e Configurações — todas revisadas nesta sprint (Parte 3) e exercitadas via os services reais na Parte 7 (portfolio_summary, recommend_v3, watchlist, simulação, LG Score/Conviction Score/coverage) contra a carteira real (33 ativos).

## 3. Sidebar organizada

✅ Três grupos desde a Sprint 30 (Principal / Análise / Operação), rodapé com versão (`LG INVEST v1.0.0`, `frontend/streamlit_app/version.py`), ambiente e última sincronização.

## 4. Design System aplicado

✅ `components/patterns.py` (page_header, metric_card_row, alert_box, recommendation_card, empty_state) e `components/badges.py` aplicados nas 10 telas desde a Sprint 30 — ver `docs/UX_UI_GUIDE.md`.

## 5. Texto claro, sem jargão técnico cru

✅ Revisão de copywriting desta sprint (Parte 2): jargão de engine (`underweight`, `dimension_type` cru) traduzido para português de produto nos textos exibidos ao usuário (`scoring.py`); confirmado por varredura que o restante do app já usava vocabulário traduzido (labels em `badges.py`, `radar.py`, `aporte.py`, `decision_service.py`).

## 6. Empty states existem

✅ `empty_state()` presente em Dashboard, Carteira, Inteligência, Radar, Journal, Ativos; adicionado nesta sprint (Parte 5) em Aporte para o caso de zero ativos cadastrados.

## 7. Central de Dados funciona

✅ Painel "Atualizar dados e análises" no Dashboard, com botões de preço/fundamentos/watchlist/tudo e confirmação em duas etapas para "Atualizar tudo" — hierarquia de botão reforçada nesta sprint (Parte 4, `type="primary"`).

## 8. Dividendos.me dry-run funciona

✅ Fluxo dry-run/update/replace com preview obrigatório antes de qualquer alteração; `replace` exige confirmação por palavra digitada; bloqueio de segurança se uma seção esperada não for encontrada no scraping (comportamento existente, preservado — nenhuma mudança de lógica nesta sprint).

## 9. Carteira mostra dados corretos

✅ `python -m scripts.portfolio_summary --portfolio-id 1` confirmado nesta sprint contra a carteira real: total, pesos, retorno e concentração calculados corretamente (Parte 7).

## 10. BTC permanece em USD

✅ Corrigido e testado em sprints anteriores (`BTC_CRYPTO_CURRENCY_FIX.md`); nenhuma mudança de lógica de câmbio nesta sprint (fora do escopo de freeze de features).

## 11. Aporte v3 respeita limites pós-alocação

✅ Verificado nesta sprint (Parte 7) com valores reais: R$500/1000/2000 alocam integralmente; R$1.000.000 (aporte extremo) aciona o Post-Allocation Constraints Engine, corta a dimensão moeda USD em 60% (limite configurado) e deixa R$387.350,49 genuinamente não alocado — nunca força 100%, nunca sugere venda. Invariante `allocated_amount ≤ valor solicitado` confirmado nos 4 cenários.

## 12. Watchlist/Radar funciona

✅ `WatchlistService.list_watchlist_assets` confirmado nesta sprint contra 6 candidatos reais (AAPL, COST, EGIE3.SA, GOOGL, SCHD, +1), todos classificados corretamente como `candidate` (Parte 7).

## 13. Ativos mostra dados ausentes sem quebrar

✅ Confirmado nesta sprint (Parte 7) com 3 tickers de classes diferentes (WEGE3.SA ação, HGLG11.SA FII, AAPL ação EUA) — LG Score, Conviction Score e Data Coverage calculados sem erro em todos, incluindo o caso de cobertura parcial (HGLG11.SA: "Análise de Renda: insuficiente (0%)").

## 14. Simulação roda

✅ Confirmado nesta sprint (Parte 7) com parâmetros normais (30 anos, R$1.000/mês) e extremos (0 aporte/1 ano; R$50.000/mês por 80 anos) — Monte Carlo completa sem erro em todos os casos.

## 15. Configurações salva

✅ Três camadas de alocação-alvo (simples/regras detalhadas/política geral), câmbio manual, premissas de simulação — fluxos preservados desde a Sprint 25; ações destrutivas (limpar meta, remover regra, resetar premissa) ganharam confirmação em duas etapas nesta sprint (Parte 4).

## 16. Migrations aplicam

✅ `python -m alembic upgrade head` executado várias vezes nesta sprint contra o banco real (14 migrations) — sempre idempotente, sem erro.

## 17. Backup existe e está documentado

✅ `scripts/backup_database.py` (novo nesta sprint) — copia `data/lg_invest.db` para `data/backups/lg_invest_YYYYMMDD_HHMMSS.db`, com `--keep-last` opcional. Um bug real foi encontrado e corrigido durante o desenvolvimento (`shutil.copy2` preserva o mtime do arquivo original, então ordenar por `st_mtime` para o `--keep-last` podia apagar o backup errado — corrigido para ordenar por nome do arquivo). 8 testes unitários. Documentado em `README.md` e `docs/LOCAL_RUNBOOK.md`.

## 18. Testes passam

✅ **1192 testes passando, 0 falhas** (`python -m pytest -q`), incluindo os 8 novos testes do script de backup e o teste flaky corrigido nesta sprint.

## 19. Ruff limpo

✅ `python -m ruff check .` → "All checks passed!" em todo o repositório.

## 20. Black limpo

✅ `python -m black --check --fast .` → "All done! 427 files would be left unchanged."

## 21. README/user guide existem

✅ `README.md` reescrito para v1.0 (o que o app faz, fluxo principal, telas, instalação, backup, limitações, aviso de não-aconselhamento). `docs/USER_GUIDE.md` novo (fluxo detalhado de 10 passos + guia de cada tela + como interpretar os indicadores).

## 22. Release notes existem

✅ `docs/RELEASE_NOTES_v1.0.md` (novo) e entrada `[1.0.0]` no `CHANGELOG.md`.

## 23. Limitações conhecidas documentadas

✅ Seção "Limitações conhecidas (v1.0)" no `README.md`: não é aconselhamento automatizado, fundamentos via Yahoo Finance (proxy), câmbio só para exibição, Dividendos.me depende de scraping, uso local single-user, Monte Carlo com premissas configuráveis.

## 24. Nenhuma feature crítica pela metade

✅ Nenhuma engine nova foi criada nesta sprint (conforme o freeze de features, Parte 1); todas as correções foram bugfixes, texto, hierarquia de botão, empty states e documentação sobre funcionalidade já existente e testada. O único código de produto novo (`scripts/backup_database.py`) tem 8 testes e foi validado com dados reais.

---

## Resumo

| # | Critério | Status |
|---|---|---|
| 1 | App abre sem erro | ✅ |
| 2 | Todas as telas funcionam | ✅ |
| 3 | Sidebar organizada | ✅ |
| 4 | Design System aplicado | ✅ |
| 5 | Texto claro, sem jargão técnico | ✅ |
| 6 | Empty states existem | ✅ |
| 7 | Central de Dados funciona | ✅ |
| 8 | Dividendos.me dry-run funciona | ✅ |
| 9 | Carteira mostra dados corretos | ✅ |
| 10 | BTC permanece em USD | ✅ |
| 11 | Aporte v3 respeita limites pós-alocação | ✅ |
| 12 | Watchlist/Radar funciona | ✅ |
| 13 | Ativos mostra dados ausentes sem quebrar | ✅ |
| 14 | Simulação roda | ✅ |
| 15 | Configurações salva | ✅ |
| 16 | Migrations aplicam | ✅ |
| 17 | Backup existe e está documentado | ✅ |
| 18 | Testes passam | ✅ (1192/1192) |
| 19 | Ruff limpo | ✅ |
| 20 | Black limpo | ✅ |
| 21 | README/user guide existem | ✅ |
| 22 | Release notes existem | ✅ |
| 23 | Limitações conhecidas documentadas | ✅ |
| 24 | Nenhuma feature crítica pela metade | ✅ |

**24/24 critérios atendidos.** A LG INVEST v1.0.0 está pronta para uso local diário.
