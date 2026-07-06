"""create income_monthly_summaries

Revision ID: b2f6a1d84c33
Revises: e7b3f0a915c2
Create Date: 2026-07-04 00:00:00.000000

Sprint 23.3 — separa o histórico mensal agregado de proventos (aba
"Central de Proventos" -> "Análise" do Dividendos.me) de `income_events`.
Migration puramente aditiva (cria uma tabela nova, não altera nenhuma
existente, sem backfill) — segura para rodar contra o banco de
produção/Supabase e não apaga nenhum dado existente.

`income_monthly_summaries` guarda um RESUMO mensal por carteira
(portfolio_id + wallet_name + year + month), nunca um evento por ticker
(isso continua em `income_events`). Dados já gravados em `income_events`
com `source` de agregado mensal (de execuções anteriores à Sprint 23.3)
NÃO são migrados nem apagados por esta migration — decisão explícita do
usuário de tratar isso separadamente depois, sem backfill automático.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2f6a1d84c33'
down_revision: Union[str, Sequence[str], None] = 'e7b3f0a915c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'income_monthly_summaries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('portfolio_id', sa.Integer(), sa.ForeignKey('portfolios.id'), nullable=False),
        sa.Column('wallet_name', sa.String(60), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('amount_total', sa.Numeric(18, 6), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('source', sa.String(60), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('annual_total', sa.Numeric(18, 6), nullable=True),
        sa.Column('annual_average', sa.Numeric(18, 6), nullable=True),
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
    op.create_index(
        'ix_income_monthly_summaries_portfolio_id',
        'income_monthly_summaries',
        ['portfolio_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_income_monthly_summaries_portfolio_id', table_name='income_monthly_summaries')
    op.drop_table('income_monthly_summaries')
