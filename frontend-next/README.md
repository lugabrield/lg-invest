# LG INVEST — Web App (Next.js)

Frontend novo da LG INVEST (v1.1), em migração a partir do app
Streamlit (`frontend/streamlit_app/`). Ver `docs/V1_1_MIGRATION_PLAN.md`
e `docs/WEB_APP_ARCHITECTURE.md` na raiz do projeto para o plano
completo e as decisões de arquitetura.

## Estado atual (Fase 2)

O Dashboard consome dado real de `GET /api/dashboard` (`lib/api.ts` +
`lib/adapt-dashboard.ts`) — nenhum cálculo acontece aqui, só
formatação do que a API já devolve pronto. `lib/mock/dashboard.ts`
continua existindo só pelos tipos de apresentação (`StatusKind`,
`KpiMock` etc.) que os componentes usam; os arrays de dado mockado não
são mais importados em `app/page.tsx`.

## Rodar localmente

Precisa do backend rodando também (ver raiz do projeto):

```bash
# terminal 1 — API
uvicorn backend.app.api.app:app --reload --port 8000

# terminal 2 — frontend
cd frontend-next
npm install
npm run dev
```

Abre em `http://localhost:3000`. Se a API não estiver no ar, o
Dashboard mostra um `ErrorState` (nunca quebra a página nem mostra
stack trace).

## Scripts

```bash
npm run dev        # servidor de desenvolvimento
npm run build      # build de produção
npm run start      # roda o build de produção
npm run lint       # ESLint (next/core-web-vitals)
npm run typecheck  # tsc --noEmit
```

## Estrutura

```
frontend-next/
├── app/                  # App Router (páginas, layout, estilos globais)
├── components/           # Design system (AppShell, Sidebar, MetricCard,
│                          #   DonutChartCard, ProgressBar, AssetTable,
│                          #   StatusBadge, AlertCard, EmptyState, etc.)
├── lib/
│   ├── api.ts             # cliente HTTP da API (tipos = schemas Pydantic)
│   ├── adapt-dashboard.ts # formata DashboardBundle para os componentes
│   ├── utils.ts           # cn() — merge de classes Tailwind
│   └── mock/               # só tipos de apresentação + dado de referência
```

## Regras (ver docs/API_CONTRACT.md e docs/SECURITY_NOTES.md)

- Este frontend nunca calcula recomendação, score ou valuation — só
  apresenta o que a API devolve pronto.
- Nenhum segredo (senha, `DATABASE_URL`) chega até aqui — só
  `NEXT_PUBLIC_API_URL` (a URL pública da API).
