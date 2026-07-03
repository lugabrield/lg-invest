"""CLI de correção pós-migração: realinha as sequências do Postgres (Sprint 20).

Quando `scripts/migrate_sqlite_to_postgres.py` copia linhas com o `id`
original do SQLite, o Postgres não avança automaticamente a sequência
usada para gerar o próximo `id` de cada tabela (ela só avança quando um
INSERT normal deixa o banco escolher o valor via `nextval()`). Sem essa
correção, o primeiro INSERT feito pela aplicação depois da migração
tenta reusar um `id` já ocupado e falha com `IntegrityError` (chave
primária duplicada) — foi exatamente o que aconteceu ao salvar uma
recomendação pela tela Aporte.

Este script roda, para cada tabela com chave primária inteira, o
equivalente a:
    SELECT setval(pg_get_serial_sequence('<tabela>', 'id'),
                   COALESCE((SELECT MAX(id) FROM <tabela>), 1));
Ou seja: avança a sequência para o maior `id` já existente na tabela
(ou a deixa em 1 se a tabela estiver vazia). Idempotente — pode ser
rodado quantas vezes for preciso, inclusive sem ter havido migração.

Uso (depois de rodar a migração de dados):
    python -m scripts.fix_postgres_sequences \\
        --target "postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DATABASE"
"""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine

from backend.app.infrastructure.database.models import Base  # registra todas as tabelas


def _engine_for(url: str) -> Engine:
    return create_engine(url)


def fix_sequences(target: Engine) -> None:
    tables = list(Base.metadata.sorted_tables)
    with target.begin() as conn:
        for table in tables:
            if "id" not in table.c:
                continue
            max_id = conn.execute(select(func.max(table.c.id))).scalar()
            next_val = (max_id or 0) + 1 if max_id is not None else 1
            result = conn.execute(
                text("SELECT setval(pg_get_serial_sequence(:table_name, 'id'), :next_val, false)"),
                {"table_name": table.name, "next_val": next_val},
            )
            # setval retorna None quando a coluna não usa sequência (ex.: sem autoincrement).
            row = result.first()
            if row is not None and row[0] is not None:
                print(f"{table.name}: sequência ajustada para próximo id = {next_val}")
            else:
                print(f"{table.name}: sem sequência associada a 'id' (ignorado).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Realinha as sequências de id do Postgres após uma migração de dados."
    )
    parser.add_argument(
        "--target",
        type=str,
        required=True,
        help="DATABASE_URL do Postgres/Supabase a corrigir. "
        "Ex.: postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DATABASE",
    )
    args = parser.parse_args()

    if args.target.startswith("sqlite"):
        raise SystemExit("--target deve ser um Postgres/Supabase, não SQLite.")

    target = _engine_for(args.target)
    fix_sequences(target)
    print("\nSequências realinhadas. Tente gerar/salvar uma recomendação novamente.")


if __name__ == "__main__":
    main()
