"""create watchlist_assets

Revision ID: a3f7c9e2d156
Revises: f1993c6433b8
Create Date: 2026-07-05 00:00:00.000000

Sprint 25 (Parte 2.1) — cria uma tabela nova, puramente aditiva (não
altera nenhuma tabela existente, sem backfill): `watchlist_assets`,
o cadastro de ativos candidatos que o usuário quer acompanhar mas ainda
NÃO tem posição na carteira (ou já teve e quer registrar como
descartado/bloqueado). Nunca populada automaticamente por esta
migration — a lista começa vazia até o usuário cadastrar um ativo
(Watchlist/Radar, ver `docs/WATCHLIST_RADAR.md`).

Importante: watchlist_assets NUNCA cria uma `Position` nem altera o
patrimônio calculado pelo Portfolio Engine — é uma tabela lida só pelo
Radar Engine e, opcionalmente, pelo Decision Engine 3.0 quando o usuário
habilitar explicitamente `allow_watchlist_candidates` na tela Aporte.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7c9e2d156'
down_revision: Union[str, Sequence[str], None] = 'f1993c6433b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'watchlist_assets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('portfolio_id', sa.Integer(), sa.ForeignKey('portfolios.id'), nullable=False),
        sa.Column('ticker', sa.String(20), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('asset_class', sa.String(30), nullable=False),
        sa.Column('country', sa.String(2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('sector', sa.String(120), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='watching'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('thesis', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('source', sa.String(30), nullable=False, server_default='manual'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        'ix_watchlist_assets_portfolio_ticker',
        'watchlist_assets',
        ['portfolio_id', 'ticker'],
        unique=True,
    )
    op.create_index(
        'ix_watchlist_assets_status',
        'watchlist_assets',
        ['status'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_watchlist_assets_status', table_name='watchlist_assets')
    op.drop_index('ix_watchlist_assets_portfolio_ticker', table_name='watchlist_assets')
    op.drop_table('watchlist_assets')
