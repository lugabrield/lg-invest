"""add fundamentals roic fields

Revision ID: d8a2f5c7b104
Revises: b7e4d1f8a293
Create Date: 2026-07-08 00:00:00.000000

Sprint 26 — Análise Fundamentalista Avançada / Valuation Engine 2.0,
Fase 1 (dados). Adiciona a `fundamental_snapshots` 3 colunas novas
(total_equity, roic, interest_coverage), todas nullable e sem default —
migration puramente aditiva: não altera nem apaga nenhuma coluna ou
linha existente, não requer backfill, e é segura para rodar contra o
banco de produção (Supabase) sem perda de dado. Linhas já existentes
simplesmente ficam com essas colunas em NULL até a próxima coleta de
fundamentos (`scripts`/tela Configurações -> "Atualizar fundamentos").
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8a2f5c7b104'
down_revision: Union[str, Sequence[str], None] = 'b7e4d1f8a293'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('fundamental_snapshots', sa.Column('total_equity', sa.Numeric(24, 2), nullable=True))
    op.add_column('fundamental_snapshots', sa.Column('roic', sa.Numeric(12, 6), nullable=True))
    op.add_column('fundamental_snapshots', sa.Column('interest_coverage', sa.Numeric(12, 4), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('fundamental_snapshots', 'interest_coverage')
    op.drop_column('fundamental_snapshots', 'roic')
    op.drop_column('fundamental_snapshots', 'total_equity')
