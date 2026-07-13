"""add watchlist_assets.last_collected_at

Revision ID: b7e4d1f8a293
Revises: a3f7c9e2d156
Create Date: 2026-07-06 00:00:00.000000

Sprint 25 (ajuste Watchlist/Radar) — coluna aditiva nullable, sem
backfill: registra quando `collect_data_for_asset` foi executado com
sucesso pela última vez para um candidato da Watchlist. Não inventa
dado para registros existentes (fica `NULL` até a próxima coleta) e não
afeta nenhuma tabela de posição/patrimônio.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e4d1f8a293'
down_revision: Union[str, Sequence[str], None] = 'a3f7c9e2d156'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'watchlist_assets',
        sa.Column('last_collected_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('watchlist_assets', 'last_collected_at')
