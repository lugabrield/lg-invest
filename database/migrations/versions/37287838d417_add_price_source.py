"""add price source

Revision ID: 37287838d417
Revises: 425380c796bb
Create Date: 2026-07-02 00:00:00.000000

Adiciona `prices.source` para distinguir preços coletados automaticamente
(Yahoo Finance) de preços cadastrados manualmente pelo usuário (ex.:
Tesouro Direto). Coluna aditiva com default 'yahoo' — não quebra dados
existentes, nem exige backfill manual.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '37287838d417'
down_revision: Union[str, Sequence[str], None] = '425380c796bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'prices',
        sa.Column('source', sa.String(length=20), nullable=False, server_default='yahoo'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('prices', 'source')
