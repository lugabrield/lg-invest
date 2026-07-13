"""Backup simples do banco local (Sprint 31 — Release Candidate v1.0, Parte 9).

Copia o arquivo SQLite (`data/lg_invest.db`, ou o caminho configurado em
`DATABASE_URL`) para `data/backups/lg_invest_YYYYMMDD_HHMMSS.db`. Não faz
nada além disso: sem agendamento automático, sem retenção/rotação, sem
compressão — só uma cópia simples e confiável de "antes de eu fazer algo
arriscado" (sincronizar Dividendos.me em modo replace, aplicar uma
migration, etc.).

Só funciona para banco SQLite local (a URL padrão do projeto). Se o
projeto estiver configurado para Postgres (Supabase), este script avisa
e não faz nada — backup de Postgres é responsabilidade do provedor
(Supabase já faz backup automático) e está fora do escopo desta v1.0.

Uso:
    python -m scripts.backup_database
    python -m scripts.backup_database --keep-last 10
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from backend.app.core.config import settings

_SQLITE_PREFIX = "sqlite:///"


def _resolve_sqlite_path(database_url: str) -> Path | None:
    """Extrai o caminho do arquivo de uma `DATABASE_URL` SQLite.

    Devolve `None` quando a URL não é SQLite (ex.: Postgres/Supabase) —
    o chamador decide o que fazer, este helper nunca lança exceção nem
    tenta adivinhar um caminho para outro driver."""
    if not database_url.startswith(_SQLITE_PREFIX):
        return None
    relative = database_url[len(_SQLITE_PREFIX) :]
    return (Path(__file__).resolve().parents[1] / relative).resolve()


def backup_database(keep_last: int | None = None) -> Path:
    """Copia o banco SQLite atual para `data/backups/`.

    `keep_last`, quando informado, apaga os backups mais antigos além
    dos N mais recentes — nunca apaga o backup recém-criado. Sem
    `keep_last`, nenhum backup antigo é removido (comportamento padrão:
    só acumula, nunca decide sozinho o que descartar)."""
    db_path = _resolve_sqlite_path(settings.database_url)
    if db_path is None:
        raise RuntimeError(
            "DATABASE_URL não é SQLite (parece Postgres/Supabase) — este script só faz "
            "backup do banco SQLite local. Bancos gerenciados (Supabase) já têm backup "
            "automático do provedor."
        )
    if not db_path.exists():
        raise FileNotFoundError(
            f"Banco não encontrado em {db_path}. Rode `alembic upgrade head` primeiro."
        )

    backups_dir = db_path.parent / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backups_dir / f"{db_path.stem}_{timestamp}.db"
    shutil.copy2(db_path, backup_path)

    if keep_last is not None and keep_last > 0:
        # Ordena pelo NOME do arquivo (que embute o timestamp
        # `YYYYMMDD_HHMMSS`), não por `st_mtime`: `shutil.copy2` copia os
        # metadados do arquivo de origem, incluindo o mtime — como todos os
        # backups são cópias do mesmo `db_path`, eles acabam com o mesmo
        # mtime (o do banco original), e ordenar por `st_mtime` não reflete
        # a ordem real de criação dos backups. O nome, por ter o timestamp
        # com largura fixa, ordena lexicograficamente na mesma ordem
        # cronológica.
        existing = sorted(backups_dir.glob(f"{db_path.stem}_*.db"), key=lambda p: p.name)
        for old in existing[:-keep_last]:
            old.unlink(missing_ok=True)

    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup simples do banco SQLite local.")
    parser.add_argument(
        "--keep-last",
        type=int,
        default=None,
        help="Mantém só os N backups mais recentes (apaga os mais antigos). "
        "Sem esta flag, nenhum backup antigo é removido.",
    )
    args = parser.parse_args()

    try:
        backup_path = backup_database(keep_last=args.keep_last)
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"Backup não realizado: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    print(f"Backup criado: {backup_path}")


if __name__ == "__main__":
    main()
