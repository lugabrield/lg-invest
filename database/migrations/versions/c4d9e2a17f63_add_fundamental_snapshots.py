"""add fundamental snapshots

Revision ID: c4d9e2a17f63
Revises: 8f1c3a9b2d40
Create Date: 2026-07-02 12:00:00.000000

Cria `fundamental_snapshots` (Fase 2, Sprint 13): fundamentos de um
ativo por período (`period_end`), permitindo múltiplos snapshots ao
longo do tempo para o Fundamentals Engine (Sprint 14) calcular CAGR de
receita/lucro/FCF a partir de demonstrativos anuais coletados numa
única chamada ao provider. Todos os campos financeiros são nullable —
ausência de indicador é normal, nunca erro.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d9e2a17f63'
down_revision: Union[str, Sequence[str], None] = '8f1c3a9b2d40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'fundamental_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id'), nullable=False, index=True),
        sa.Column('period_end', sa.Date(), nullable=False, index=True),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='yahoo'),
        sa.Column('roe', sa.Numeric(12, 6), nullable=True),
        sa.Column('roa', sa.Numeric(12, 6), nullable=True),
        sa.Column('net_margin', sa.Numeric(12, 6), nullable=True),
        sa.Column('ebitda_margin', sa.Numeric(12, 6), nullable=True),
        sa.Column('revenue', sa.Numeric(24, 2), nullable=True),
        sa.Column('net_income', sa.Numeric(24, 2), nullable=True),
        sa.Column('ebitda', sa.Numeric(24, 2), nullable=True),
        sa.Column('ebit', sa.Numeric(24, 2), nullable=True),
        sa.Column('free_cash_flow', sa.Numeric(24, 2), nullable=True),
        sa.Column('net_debt', sa.Numeric(24, 2), nullable=True),
        sa.Column('debt_to_ebitda', sa.Numeric(12, 6), nullable=True),
        sa.Column('pe_ratio', sa.Numeric(12, 6), nullable=True),
        sa.Column('pb_ratio', sa.Numeric(12, 6), nullable=True),
        sa.Column('ev_ebitda', sa.Numeric(12, 6), nullable=True),
        sa.Column('dividend_yield', sa.Numeric(12, 6), nullable=True),
        sa.Column('payout_ratio', sa.Numeric(12, 6), nullable=True),
        sa.Column('eps', sa.Numeric(18, 6), nullable=True),
        sa.Column('revenue_per_share', sa.Numeric(18, 6), nullable=True),
        sa.Column('beta', sa.Numeric(12, 6), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint('asset_id', 'period_end', name='uq_fundamental_asset_period'),
    )
    op.create_index(
        'ix_fundamental_snapshots_asset_period',
        'fundamental_snapshots',
        ['asset_id', 'period_end'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_fundamental_snapshots_asset_period', table_name='fundamental_snapshots')
    op.drop_table('fundamental_snapshots')
