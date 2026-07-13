# Plano de Migração — LG INVEST v1.0.0 → v1.1 Premium Web App

> Branch: `feature/v1.1-premium-web-app`. Não altera `main`/v1.0.0.
> Ver `docs/WEB_APP_ARCHITECTURE.md` para as decisões de arquitetura e
> `docs/STREAMLIT_TO_NEXTJS_MIGRATION.md` para o mapa tela-a-tela.

## Princípio

Nenhuma engine nova, nenhuma regra de negócio nova, nenhuma mudança de
cálculo. Esta é uma migração de **camada de apresentação e arquitetura
de deploy** — o Decision Engine v3, o LG Score, o Valuation Engine 2.0 e
todo o resto continuam exatamente como estão, só passam a ser
consumidos por HTTP/JSON em vez de import direto do Streamlit.

## Estado no início desta sprint

- v1.0.0 real commitada e taggeada (`eac71d5`) — 1213 testes passando,
  ruff/black limpos, documentação completa.
- Streamlit continua sendo o app de produção até o Next.js cobrir o
  fluxo principal (Dashboard, Carteira, Aporte no mínimo).

## Fases

### Fase 0 — Auditoria de arquitetura atual ✅ (esta entrega)
Mapa das 10 telas, dos 40+ services, das engines, do fluxo de dados do
Dividendos.me, decisão de onde roda cada camada. Ver
`docs/WEB_APP_ARCHITECTURE.md` e `docs/STREAMLIT_TO_NEXTJS_MIGRATION.md`.

### Fase 1 — Protótipo Next.js (esta entrega, parcial)
`frontend-next/` criado com App Router + TypeScript + Tailwind +
shadcn/ui, tema dark, AppShell/Sidebar, Dashboard com **dados
mockados** (sem API ainda). Objetivo: validar o visual antes de
integrar dado real. Não migra nenhuma tela de verdade ainda.

### Fase 2 — API do Dashboard
`backend/app/api/` (FastAPI) criado com o primeiro endpoint real:
`GET /api/dashboard`, reaproveitando `cached_dashboard_bundle`-equivalente
(sem depender de `st.cache_data`, que é Streamlit-only — criar
cache de leitura equivalente ou usar cache HTTP simples). Dashboard
Next.js passa a consumir dado real. Primeiro teste de API.

### Fase 3 — Aporte v3
`POST /api/recommendations/aporte` chamando `DecisionService.recommend_v3`
sem alterar a assinatura nem o comportamento. UI premium do Aporte
(cards por ativo, motivo, badges, "como a carteira ficaria depois").

### Fase 4 — Carteira, Inteligência, Ativos, Radar
Uma tela por vez, cada uma com: endpoint dedicado, loading state, error
state, empty state, teste básico. Ordem sugerida por dependência
crescente de dado (Carteira é a mais simples; Ativos é a mais rica).

### Fase 5 — Simulação, Journal, Configurações
Simulação (`POST /api/simulation/monte-carlo`), Journal (CRUD simples),
Configurações (GET/PATCH de alocação-alvo, política, premissas —
telas com mais formulário que gráfico).

### Fase 6 — Sincronização Dividendos.me (nova UX seguro)
A parte mais sensível: modal de credenciais no frontend, mas login e
scraping sempre no backend. Ver `docs/DIVIDENDOS_ME_FRONT_SYNC.md` e
`docs/SECURITY_NOTES.md` em detalhe. Só começa depois que o backend
FastAPI já está validado com as telas mais simples (Fases 2-4), porque
é a integração de maior risco técnico (Playwright + credenciais).

### Fase 7 — Robustez do Dividendos.me
Mensagens de erro específicas por causa (login inválido, Playwright
indisponível, site mudou, timeout, captcha/2FA), preview mais rico
(contagem por classe/moeda, novos/removidos/atualizados), rate limit
básico, sanitização reforçada.

### Fase 8 — Deploy
Vercel (frontend) + Render/Fly/Railway (backend) + Supabase (banco).
CORS restrito, healthcheck, logs sanitizados, `DATABASE_URL` nunca no
frontend. Documentado em `docs/VERCEL_DEPLOYMENT.md` (a escrever nesta
fase).

### Fase 9 — QA final e release v1.1
Suíte Python completa + suíte de API + suíte de frontend, todas verdes.
Streamlit permanece disponível como fallback até confirmação de que o
Next.js cobre 100% do fluxo diário. Checklist de release equivalente ao
`docs/RELEASE_CHECKLIST.md` da v1.0.0, adaptado para a arquitetura nova.

## O que esta entrega cobre (primeira rodada)

Conforme pedido explicitamente: só Fase 0 (auditoria) + Fase 1
(protótipo visual com mock, sem tocar engines nem Streamlit). Fases 2+
dependem de validação do visual pelo usuário antes de prosseguir.

## Estimativa de esforço por fase (ordem de grandeza, não compromisso)

| Fase | Esforço relativo |
|---|---|
| 0 — Auditoria | Pequeno (concluído nesta entrega) |
| 1 — Protótipo visual | Pequeno-médio (concluído nesta entrega) |
| 2 — API Dashboard | Médio |
| 3 — Aporte v3 | Médio |
| 4 — Carteira/Inteligência/Ativos/Radar | Grande (4 telas, Ativos é rica) |
| 5 — Simulação/Journal/Configurações | Médio |
| 6 — Dividendos.me UX segura | Grande (maior risco técnico) |
| 7 — Robustez Dividendos.me | Pequeno-médio |
| 8 — Deploy | Médio (depende de escolha de provedor backend) |
| 9 — QA final | Pequeno-médio |

## Riscos gerais da migração

Ver `docs/WEB_APP_ARCHITECTURE.md`, seção "Riscos", para os riscos
técnicos de arquitetura. Riscos específicos de processo:

- **Duas UIs em paralelo por várias semanas** — risco de esquecer de
  manter o Streamlit funcional enquanto o Next.js avança. Mitigado por
  regra explícita: nenhuma mudança nas engines/services até que o
  Next.js substitua completamente uma tela (não há "meio-termo" onde
  ambos ficam quebrados).
- **Escopo crescer sem controle** ("já que estou migrando, vou também
  melhorar X") — mitigado pelo princípio do topo deste documento: zero
  regra nova nesta migração. Melhorias de regra de negócio (ex.: nova
  fonte de dados, novo fator de score) ficam para depois da v1.1.
- **Perder o freeze de qualidade da v1.0.0** — mitigado rodando a suíte
  Python completa a cada fase que toca `backend/` (mesmo que só para
  adicionar a camada de API).
