"""Add template_variables table.

Stores resolved template variable definitions per dashboard.
Unique on (organization_id, dashboard_id, variable_name).

Revision ID: 005
Revises: 004
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'template_variables',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('organization_id', sa.String(36), nullable=False),
        sa.Column('dashboard_id', sa.String(36), nullable=False),
        sa.Column('variable_name', sa.String(255), nullable=False),
        sa.Column('tag_key', sa.String(255), nullable=False),
        sa.Column('default_value', sa.String(255), nullable=True),
        sa.Column('values', sa.JSON(), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['organization_id'],
            ['organizations.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['dashboard_id'],
            ['organization_dashboards.id'],
            ondelete='CASCADE',
        ),
        sa.UniqueConstraint(
            'organization_id', 'dashboard_id', 'variable_name',
            name='uq_org_dash_varname',
        ),
    )

    op.create_index(
        'ix_template_variables_organization_id',
        'template_variables',
        ['organization_id'],
    )
    op.create_index(
        'ix_template_variables_dashboard_id',
        'template_variables',
        ['dashboard_id'],
    )
    op.create_index(
        'ix_template_var_org_active',
        'template_variables',
        ['organization_id', 'is_active'],
    )


def downgrade() -> None:
    op.drop_table('template_variables')
