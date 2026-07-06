"""Entidade ExternalSyncRun — auditoria de sincronizações externas (Sprint 23).

Registra cada execução de sincronização com uma fonte externa (hoje só
o Dividendos.me) para rastreabilidade: quando rodou, em que modo, quantas
posições mudaram e um snapshot em JSON do estado anterior. Nunca guarda
senha, cookie ou token — só metadados operacionais.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.database.base import Base

# Provedores externos suportados. Hoje só o Dividendos.me; a lista existe
# para deixar explícito que o campo é validado, não texto livre.
SYNC_PROVIDERS = ("dividendos_me",)

# Modos de sincronização (Sprint 23): "dry-run" só lê e mostra preview,
# nunca grava; "replace" substitui 100% das posições da carteira alvo;
# "update" (opcional, uso futuro) atualiza/cria sem remover as antigas.
SYNC_MODES = ("dry-run", "replace", "update")

SYNC_STATUSES = ("success", "failed")


class ExternalSyncRun(Base):
    """Uma execução de sincronização com uma fonte externa de carteira."""

    __tablename__ = "external_sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id"), index=True, nullable=False
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    assets_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    positions_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    positions_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    positions_removed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Snapshot da carteira antes da substituição + outras notas (JSON serializado
    # como texto — nunca inclui senha/cookie/token, só ticker/quantidade/preço).
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ExternalSyncRun id={self.id} provider={self.provider!r} "
            f"mode={self.mode!r} status={self.status!r}>"
        )
