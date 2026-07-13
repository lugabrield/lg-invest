# LG INVEST v1.0.0 — Release Notes

**Data:** 11 de julho de 2026
**Codinome:** "Release Candidate v1.0" (Sprint 31)

## Resumo

A LG INVEST chega à v1.0.0 como um app local estável, bonito, organizado e utilizável no dia a dia. Esta versão não adiciona nenhuma engine nova nem funcionalidade complexa nova — é uma sprint de **finalização**: bugfixes, revisão de texto, hierarquia visual, empty states, documentação completa e um script de backup, fechando o trabalho acumulado desde o MVP inicial até o Design System da Sprint 30.

## Principais funcionalidades (visão consolidada)

- **Carteira centralizada** — ações BR/EUA, FIIs, ETFs, REITs, Bitcoin (sempre em USD), Tesouro Direto (sempre em BRL), com preços automáticos (Yahoo Finance) e câmbio USD/BRL automático (BCB PTAX, com fallback).
- **LG Score e LG Conviction Score v2** — qualidade, valuation, crescimento, risco e reinvestimento de capital, com pesos por classe de ativo, explicação por fator e nível de confiança sempre visível.
- **Decision Engine v3 / Aporte v3** — recomendação de distribuição de aporte multi-fator, com Post-Allocation Constraints Engine (nunca ultrapassa limites configurados *depois* do aporte, nunca sugere venda, nunca força 100% de alocação).
- **Análise Fundamentalista completa** — Valuation Engine 2.0 (DCF, múltiplos, Graham) para ações; análise de renda (P/VP + DY + estabilidade) para FIIs/REITs; adequação de política para ETF/cripto/Tesouro; Trap Detection Engine para armadilhas de valuation.
- **Radar/Watchlist** — funil de candidatos antes de virarem posição.
- **Simulação Monte Carlo** — projeção probabilística de patrimônio futuro.
- **Sincronização com o Dividendos.me** (opcional) — dry-run/update/replace, sempre com preview e confirmação explícita.
- **Investment Journal** — teses, decisões e revisões ao longo do tempo.
- **Design System** — 10 telas com layout consistente (Sprint 30 + refinamentos desta sprint).

## O que mudou nesta sprint (Release Candidate v1.0)

### Corrigido

- **Teste flaky** (`test_dividendos_me_client.py`) — usava um caminho relativo fixo em vez do fixture `tmp_path` do pytest, causando resíduos entre execuções. Corrigido; estável em 5 execuções consecutivas.
- **Bug real no script de backup** — `shutil.copy2` preserva o timestamp do arquivo original em cada cópia, então ordenar backups por `st_mtime` para a lógica de `--keep-last` podia apagar o backup mais recente em vez do mais antigo. Corrigido para ordenar por nome do arquivo (que embute o timestamp de criação). Encontrado e corrigido durante o próprio desenvolvimento do script, com 8 testes cobrindo o comportamento correto.
- **5 mensagens de erro que vazavam texto técnico bruto** (exceções de rede/Yahoo Finance interpoladas diretamente na tela) — substituídas por mensagens amigáveis consistentes com o padrão já usado na sincronização do Dividendos.me.
- **Jargão técnico vazando para o usuário** — a razão de bônus de alocação no Decision Engine v3 mostrava a chave técnica crua (`underweight na dimensão 'currency'`); traduzida para português de produto ("abaixo da meta de alocação em moeda").
- **Versão hardcoded incorreta na sidebar** ("LG INVEST v1.0 RC") — centralizada em `frontend/streamlit_app/version.py`, fonte única da versão.

### Melhorado

- **Hierarquia de botões** — ação principal de cada painel agora usa `type="primary"` (Dashboard: "Atualizar tudo"; Configurações: "Salvar alocação-alvo", "Salvar premissa"); três ações destrutivas que executavam imediatamente ao clique (limpar meta de alocação, remover regra detalhada, resetar premissa de simulação) agora exigem confirmação em duas etapas, no mesmo padrão já usado para presets e sincronização do Dividendos.me.
- **Empty state em Aporte** — carteira sem nenhum ativo cadastrado agora mostra uma orientação clara em vez de um resultado confuso com tudo zerado.

### Adicionado

- **`scripts/backup_database.py`** — backup simples e confiável do banco SQLite (`data/lg_invest.db` → `data/backups/lg_invest_YYYYMMDD_HHMMSS.db`), com `--keep-last N` opcional. Sem agendamento automático, sem compressão — só uma cópia rápida antes de operações arriscadas.
- **`frontend/streamlit_app/version.py`** — `APP_NAME`/`APP_VERSION` como fonte única de versão.
- **Documentação completa de release**: `README.md` reescrito, `docs/USER_GUIDE.md`, `docs/INSTALLATION.md`, `docs/LOCAL_RUNBOOK.md`, `docs/TROUBLESHOOTING.md`, `docs/RELEASE_CHECKLIST.md`, este arquivo.
- **Housekeeping**: removida pasta de debug obsoleta (`debug_dividendos_me_test_tmp/`) e ambiente virtual órfão (`.venv_check/`); `debug_dividendos_me*/` adicionado ao `.gitignore`.

### Deliberadamente fora do escopo (freeze de features)

Nenhuma engine nova, nenhuma mudança de regra de negócio do Decision Engine, do Aporte v3 ou da sincronização do Dividendos.me, nenhuma mudança de banco além do que já existia, nenhuma tela removida. A revisão de copywriting foi pontual (o único jargão técnico cru encontrado numa varredura direcionada), não uma reescrita completa de todos os textos do app.

## Como validar esta versão

```bash
python -m alembic upgrade head
python -m pytest -q
python -m ruff check .
python -m black --check .
```

Resultado nesta sprint: alembic limpo, **1192 testes passando**, ruff limpo, black limpo (427 arquivos).

## Limitações conhecidas

Ver a seção "Limitações conhecidas (v1.0)" no `README.md` — resumo: não é aconselhamento financeiro automatizado, fundamentos via Yahoo Finance como proxy (cobertura variável, com importação manual como fallback), câmbio só para exibição, Dividendos.me depende de scraping e é opcional, uso local single-user, Simulação usa premissas configuráveis, não dados de mercado real.

## Próximas melhorias sugeridas (não fazem parte da v1.0)

- Revisão de copywriting ponta-a-ponta (texto por texto, tela por tela) para além do jargão técnico já identificado.
- Testes automatizados de UI (hoje a cobertura é de services/engines; a camada Streamlit em si depende de smoke tests manuais/inspeção de código).
- Explorar conversão de câmbio também no Decision Engine (hoje é só exibição no Dashboard).
- Se o volume de dados crescer muito, avaliar rotação/retenção automática de backups (hoje `--keep-last` é manual, por decisão explícita do usuário de manter simples).

## Como criar a tag desta versão

```bash
git tag -a v1.0.0 -m "LG INVEST v1.0.0 — Release Candidate estável para uso local diário"
git push origin v1.0.0
```
