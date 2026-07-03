"""CLI de migração de dados: SQLite local -> Postgres/Supabase (Sprint 20).

Implementa o passo 5 de `docs/SUPABASE_MIGRATION_PLAN.md`: exporta cada
tabela do SQLite local e reimporta no Postgres de destino, respeitando
a ordem de dependência de chave estrangeira (via
`Base.metadata.sorted_tables`, que o SQLAlchemy já ordena
topologicamente) e usando SQLAlchemy Core para copiar linha a linha sem
reescrever SQL manualmente nem duplicar validação (os dados já foram
validados quando entraram no SQLite).

Este script NUNCA apaga nem modifica o SQLite de origem — é somente
leitura lá. Por padrão roda em modo *dry-run* (só mostra quantas linhas
seriam copiadas por tabela); é preciso passar --execute explicitamente
para gravar no destino, e --wipe-target para limpar tabelas já
populadas no destino antes de copiar (evita duplicar em reexecuções).

Uso:
    # 1) Rode `alembic upgrade head` contra o Postgres vazio ANTES deste
    #    script (cria as tabelas; ver docs/SUPABASE_MIGRATION_PLAN.md).
    # 2) Dry-run (não grava nada, só mostra a contagem por tabela):
    python -m scripts.migrate_sqlite_to_postgres \\
        --target "postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DATABASE"

    # 3) Migração de verdade:
    python -m scripts.migrate_sqlite_to_postgres \\
        --target "postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DATABASE" \\
        --execute

A URL de origem vem de `settings.database_url` (o SQLite local padrão);
pode ser sobrescrita com --source para migrar de um arquivo específico.
"""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine, insert, select
from sqlalchemy.engine import Engine

from backend.app.core.config import settings
from backend.app.infrastructure.database.models import Base  # registra todas as tabelas


def _engine_for(url: str) -> Engine:
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    return create_engine(url, **kwargs)


def _copy_table(source: Engine, target: Engine, table, *, execute: bool, wipe_target: bool) -> int:
    with source.connect() as source_conn:
        rows = [dict(row._mapping) for row in source_conn.execute(select(table))]

    if not execute:
        print(f"[dry-run] {table.name}: {len(rows)} linha(s) seriam copiadas.")
        return len(rows)

    with target.begin() as target_conn:
        if wipe_target:
            target_conn.execute(table.delete())
        if rows:
            target_conn.execute(insert(table), rows)

    print(f"[executado] {table.name}: {len(rows)} linha(s) copiada(s).")
    return len(rows)


def _validate_counts(source: Engine, target: Engine, tables) -> bool:
    """Confere que a contagem de linhas no destino bate com a origem, tabela a tabela."""
    ok = True
    print("\nValidação pós-migração:")
    with source.connect() as source_conn, target.connect() as target_conn:
        for table in tables:
            # rowcount de SELECT não é confiável em todos os drivers; conta via len().
            source_count = len(list(source_conn.execute(select(table))))
            target_count = len(list(target_conn.execute(select(table))))
            status = "OK" if source_count == target_count else "DIVERGENTE"
            if source_count != target_count:
                ok = False
            print(f"  {table.name}: origem={source_count} destino={target_count} [{status}]")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migra dados do SQLite local para um Postgres/Supabase de destino."
    )
    parser.add_argument(
        "--source",
        type=str,
        default=settings.database_url,
        help="DATABASE_URL de origem (padrão: settings.database_url, o SQLite local).",
    )
    parser.add_argument(
        "--target",
        type=str,
        required=True,
        help="DATABASE_URL de destino (Postgres/Supabase). "
        "Ex.: postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DATABASE",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Grava de fato no destino. Sem esta flag, roda em dry-run (só conta as linhas).",
    )
    parser.add_argument(
        "--wipe-target",
        action="store_true",
        help="Apaga as linhas já existentes em cada tabela do destino antes de copiar "
        "(evita duplicar em reexecuções). Só tem efeito com --execute.",
    )
    args = parser.parse_args()

    if args.target.startswith("sqlite"):
        raise SystemExit("--target deve ser um Postgres/Supabase, não SQLite.")

    source = _engine_for(args.source)
    target = _engine_for(args.target)

    tables = list(Base.metadata.sorted_tables)  # já em ordem topológica de FK

    print(f"Origem:  {args.source}")
    print(f"Destino: {args.target}")
    print(f"Modo: {'EXECUÇÃO' if args.execute else 'DRY-RUN (nada será gravado)'}")
    print(f"Tabelas ({len(tables)}): {', '.join(t.name for t in tables)}\n")

    for table in tables:
        _copy_table(source, target, table, execute=args.execute, wipe_target=args.wipe_target)

    if args.execute:
        all_ok = _validate_counts(source, target, tables)
        if not all_ok:
            raise SystemExit(
                "\nDivergência de contagem entre origem e destino — revise antes de "
                "considerar a migração concluída."
            )
        print("\nMigração concluída: todas as tabelas batem entre origem e destino.")
    else:
        print("\nDry-run concluído. Rode novamente com --execute para gravar no destino.")


if __name__ == "__main__":
    main()
