"""create income_events

Revision ID: e7b3f0a915c2
Revises: d4a8f21e9c07
Create Date: 2026-07-04 00:00:00.000000

Sprint 23.2 — Proventos/Dividendos do Dividendos.me. Migration puramente
aditiva (cria uma tabela nova, não altera nenhuma existente, sem
backfill) — segura para rodar contra o banco de produção/Supabase e não
apaga nenhum dado existente.

`income_events` guarda EVENTOS/HISTÓRICO de proventos, nunca estado
atual de carteira (isso continua em `positions`). `asset_id`/`ticker`
são nullable de propósito: o agregado mensal por carteira do
Dividendos.me (única fonte histórica confiável encontrada na
investigação desta sprint) não é quebrado por ativo.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7b3f0a915c2'
down_revision: Union[str, Sequence[str], None] = 'd4a8f21e9c07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'income_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('portfolio_id', sa.Integer(), sa.ForeignKey('portfolios.id'), nullable=False),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id'), nullable=True),
        sa.Column('ticker', sa.String(20), nullable=True),
        sa.Column('source', sa.String(60), nullable=False),
        sa.Column('event_type', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('ex_date', sa.Date(), nullable=True),
        sa.Column('payment_date', sa.Date(), nullable=True),
        sa.Column('declared_date', sa.Date(), nullable=True),
        sa.Column('quantity', sa.Numeric(24, 8), nullable=True),
        sa.Column('amount_per_share', sa.Numeric(18, 6), nullable=True),
        sa.Column('amount_total', sa.Numeric(18, 6), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('raw_payload_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index('ix_income_events_portfolio_id', 'income_events', ['portfolio_id'])
    op.create_index('ix_income_events_asset_id', 'income_events', ['asset_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_income_events_asset_id', table_name='income_events')
    op.drop_index('ix_income_events_portfolio_id', table_name='income_events')
    op.drop_table('income_events')
