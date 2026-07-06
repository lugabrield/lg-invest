"""add position.source and external_sync_runs

Revision ID: d4a8f21e9c07
Revises: a1f4e6c2b8d9
Create Date: 2026-07-04 00:00:00.000000

Sprint 23 — Sincronização Dividendos.me. Duas mudanças, ambas puramente
aditivas (sem alterar/apagar coluna ou linha existente, sem backfill
obrigatório, seguras para rodar contra o banco de produção/Supabase):

1. `positions.source` (nullable): identifica de onde veio a posição —
   `None` para posições criadas manualmente/importadas por CSV (Sprint 3),
   `"dividendos_me:b3"` ou `"dividendos_me:international"` para posições
   substituídas pela sincronização com o Dividendos.me (Sprint 23). Só
   auditoria/rastreabilidade — nenhum engine/serviço existente depende
   deste campo para calcular nada.

2. `external_sync_runs`: log de auditoria de cada execução de
   sincronização externa (dry-run/replace/update), com contadores e um
   snapshot em JSON do estado anterior à substituição. Nunca guarda
   senha, cookie ou token — só metadados operacionais.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a8f21e9c07'
down_revision: Union[str, Sequence[str], None] = 'a1f4e6c2b8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('positions', sa.Column('source', sa.String(40), nullable=True))

    op.create_table(
        'external_sync_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider', sa.String(40), nullable=False),
        sa.Column('portfolio_id', sa.Integer(), sa.ForeignKey('portfolios.id'), nullable=False),
        sa.Column('mode', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('assets_found', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('positions_created', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('positions_updated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('positions_removed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('errors_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('summary_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        'ix_external_sync_runs_portfolio_id', 'external_sync_runs', ['portfolio_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_external_sync_runs_portfolio_id', table_name='external_sync_runs')
    op.drop_table('external_sync_runs')
    op.drop_column('positions', 'source')
