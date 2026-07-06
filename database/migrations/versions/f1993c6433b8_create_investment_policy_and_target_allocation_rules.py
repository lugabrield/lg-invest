"""create investment_policy and target_allocation_rules

Revision ID: f1993c6433b8
Revises: b2f6a1d84c33
Create Date: 2026-07-04 00:00:00.000000

Sprint 24 (Fase 3) — cria duas tabelas novas, puramente aditivas (não
alteram nenhuma tabela existente, sem backfill):

- `investment_policy`: uma linha por carteira, guarda o perfil do
  investidor e os limites/parâmetros usados como guardrails pelo
  Decision Engine e (no futuro) pelo Simulation Engine. Nunca é
  populada automaticamente por uma migration de dados — o serviço
  (`investment_policy_service.py`) cria a linha com defaults sensatos
  na primeira leitura, se ainda não existir.
- `target_allocation_rules`: metas de alocação granulares por classe,
  moeda, país OU ativo individual (uma dimensão por linha, nunca
  misturadas) — substitui o antigo armazenamento em JSON
  (`data/app_settings.json`, chave "target_allocation"), que só
  suportava classe e apenas `target_pct`. Nenhuma linha é pré-cadastrada
  com valor inventado: enquanto o usuário não configurar uma meta para
  uma dimensão, ela simplesmente não existe nesta tabela.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1993c6433b8'
down_revision: Union[str, Sequence[str], None] = 'b2f6a1d84c33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'investment_policy',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('portfolio_id', sa.Integer(), sa.ForeignKey('portfolios.id'), nullable=False),
        sa.Column('investor_profile', sa.String(120), nullable=False),
        sa.Column('horizon_years', sa.Integer(), nullable=False),
        sa.Column('base_currency', sa.String(3), nullable=False),
        sa.Column('risk_tolerance', sa.String(20), nullable=False),
        sa.Column('max_asset_weight', sa.Numeric(6, 4), nullable=False),
        sa.Column('max_crypto_weight', sa.Numeric(6, 4), nullable=False),
        sa.Column('target_international_min', sa.Numeric(6, 4), nullable=False),
        sa.Column('target_international_max', sa.Numeric(6, 4), nullable=False),
        sa.Column('target_fii_max', sa.Numeric(6, 4), nullable=False),
        sa.Column('target_brazil_equity', sa.Numeric(6, 4), nullable=False),
        sa.Column('target_us_equity', sa.Numeric(6, 4), nullable=False),
        sa.Column('target_etf', sa.Numeric(6, 4), nullable=False),
        sa.Column('target_reit', sa.Numeric(6, 4), nullable=False),
        sa.Column('target_fixed_income', sa.Numeric(6, 4), nullable=False),
        sa.Column('rebalance_threshold', sa.Numeric(6, 4), nullable=False),
        sa.Column('monthly_contribution_default', sa.Numeric(18, 2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
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
        'ix_investment_policy_portfolio_id',
        'investment_policy',
        ['portfolio_id'],
        unique=True,
    )

    op.create_table(
        'target_allocation_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('portfolio_id', sa.Integer(), sa.ForeignKey('portfolios.id'), nullable=False),
        sa.Column('dimension_type', sa.String(20), nullable=False),
        sa.Column('dimension_key', sa.String(60), nullable=False),
        sa.Column('min_weight', sa.Numeric(6, 4), nullable=True),
        sa.Column('target_weight', sa.Numeric(6, 4), nullable=True),
        sa.Column('max_weight', sa.Numeric(6, 4), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
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
        'ix_target_allocation_rules_portfolio_dimension',
        'target_allocation_rules',
        ['portfolio_id', 'dimension_type', 'dimension_key'],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'ix_target_allocation_rules_portfolio_dimension', table_name='target_allocation_rules'
    )
    op.drop_table('target_allocation_rules')
    op.drop_index('ix_investment_policy_portfolio_id', table_name='investment_policy')
    op.drop_table('investment_policy')
