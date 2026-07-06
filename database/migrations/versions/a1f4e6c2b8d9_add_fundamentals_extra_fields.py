"""add fundamentals extra fields

Revision ID: a1f4e6c2b8d9
Revises: c4d9e2a17f63
Create Date: 2026-07-03 00:00:00.000000

Sprint 21 — Fundamentals Foundation. Adiciona a `fundamental_snapshots`
9 colunas adicionais (market_cap, enterprise_value, forward_pe,
operating_margin, total_debt, total_cash, operating_cash_flow,
gross_profit, shares_outstanding), todas nullable e sem default —
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
revision: str = 'a1f4e6c2b8d9'
down_revision: Union[str, Sequence[str], None] = 'c4d9e2a17f63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('fundamental_snapshots', sa.Column('market_cap', sa.Numeric(24, 2), nullable=True))
    op.add_column('fundamental_snapshots', sa.Column('enterprise_value', sa.Numeric(24, 2), nullable=True))
    op.add_column('fundamental_snapshots', sa.Column('forward_pe', sa.Numeric(12, 6), nullable=True))
    op.add_column('fundamental_snapshots', sa.Column('operating_margin', sa.Numeric(12, 6), nullable=True))
    op.add_column('fundamental_snapshots', sa.Column('total_debt', sa.Numeric(24, 2), nullable=True))
    op.add_column('fundamental_snapshots', sa.Column('total_cash', sa.Numeric(24, 2), nullable=True))
    op.add_column('fundamental_snapshots', sa.Column('operating_cash_flow', sa.Numeric(24, 2), nullable=True))
    op.add_column('fundamental_snapshots', sa.Column('gross_profit', sa.Numeric(24, 2), nullable=True))
    op.add_column('fundamental_snapshots', sa.Column('shares_outstanding', sa.Numeric(24, 2), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('fundamental_snapshots', 'shares_outstanding')
    op.drop_column('fundamental_snapshots', 'gross_profit')
    op.drop_column('fundamental_snapshots', 'operating_cash_flow')
    op.drop_column('fundamental_snapshots', 'total_cash')
    op.drop_column('fundamental_snapshots', 'total_debt')
    op.drop_column('fundamental_snapshots', 'operating_margin')
    op.drop_column('fundamental_snapshots', 'forward_pe')
    op.drop_column('fundamental_snapshots', 'enterprise_value')
    op.drop_column('fundamental_snapshots', 'market_cap')
