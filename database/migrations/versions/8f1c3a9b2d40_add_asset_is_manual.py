"""add asset is_manual

Revision ID: 8f1c3a9b2d40
Revises: 37287838d417
Create Date: 2026-07-02 00:00:00.000000

Adiciona `assets.is_manual` para marcar ativos sem cotação de mercado
(ex.: Tesouro Direto), permitindo que a atualização automática de preços
(Sprint 12) pule esses ativos de forma confiável, sem depender de
heurística por asset_class. Coluna aditiva com default `false` —
preserva o comportamento atual para todos os ativos já cadastrados.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f1c3a9b2d40'
down_revision: Union[str, Sequence[str], None] = '37287838d417'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'assets',
        sa.Column('is_manual', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('assets', 'is_manual')
