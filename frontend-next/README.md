# LG INVEST — Web App (Next.js)

Frontend novo da LG INVEST (v1.1), em migração a partir do app
Streamlit (`frontend/streamlit_app/`). Ver `docs/V1_1_MIGRATION_PLAN.md`
e `docs/WEB_APP_ARCHITECTURE.md` na raiz do projeto para o plano
completo e as decisões de arquitetura.

## Estado atual (Fase 1)

Só o Dashboard, com **dados mockados** (`lib/mock/dashboard.ts`) — sem
integração com nenhuma API ainda. Objetivo desta fase é validar o
visual antes de conectar dado real (Fase 2).

## Rodar localmente

```bash
npm install
npm run dev
```

Abre em `http://localhost:3000`.

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
│   ├── utils.ts           # cn() — merge de classes Tailwind
│   └── mock/               # dados mockados (só na Fase 1)
```

## Regras (ver docs/API_CONTRACT.md e docs/SECURITY_NOTES.md)

- Este frontend nunca calcula recomendação, score ou valuation — só
  apresenta o que a API devolve pronto.
- Nenhum segredo (senha, `DATABASE_URL`) chega até aqui — só
  `NEXT_PUBLIC_API_URL` (a URL pública da API).
