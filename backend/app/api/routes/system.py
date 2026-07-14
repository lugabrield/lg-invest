"""Rota de sistema (v1.1, Fase 2) — healthcheck simples, sem dado sensível."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.core.config import settings

router = APIRouter(tags=["system"])


@router.get("/system/status")
def get_status(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        database_ok = True
    except Exception:  # healthcheck nunca deve derrubar a API por erro de conexão
        database_ok = False

    return {
        "status": "ok" if database_ok else "degraded",
        "environment": settings.environment,
        "database_ok": database_ok,
    }
