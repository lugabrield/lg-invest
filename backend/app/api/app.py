"""API HTTP da LG INVEST (v1.1, Fase 2 — ver docs/API_CONTRACT.md).

Camada fina sobre `backend/app/services/*`: nenhuma regra de negócio,
cálculo financeiro ou decisão de apresentação vive aqui — só rotas que
chamam os services já validados pela suíte de testes e devolvem os
schemas Pydantic já existentes.

Rodar localmente:
    uvicorn backend.app.api.app:app --reload --port 8000

O frontend Next.js (`frontend-next/`) consome esta API via
`NEXT_PUBLIC_API_URL` — nunca chama o banco diretamente.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import (
    aporte,
    ativos,
    dashboard,
    intelligence,
    journal,
    portfolio,
    radar,
    simulacao,
    system,
)
from backend.app.core.config import settings

app = FastAPI(
    title="LG INVEST API",
    version="1.1.0",
    description="Investment Intelligence Platform — camada HTTP sobre os services existentes.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(aporte.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(intelligence.router, prefix="/api")
app.include_router(ativos.router, prefix="/api")
app.include_router(radar.router, prefix="/api")
app.include_router(simulacao.router, prefix="/api")
app.include_router(journal.router, prefix="/api")
