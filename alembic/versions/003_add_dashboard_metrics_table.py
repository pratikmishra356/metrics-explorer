"""Add dashboard_metrics table.

Revision ID: 003
Revises: 002
Create Date: 2026-02-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create dashboard_metrics table
    op.create_table(
        'dashboard_metrics',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('dashboard_id', sa.String(36), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('widget_id', sa.String(255), nullable=True),
        sa.Column('metric_name', sa.String(512), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['dashboard_id'],
            ['organization_dashboards.id'],
            ondelete='CASCADE',
        ),
    )

    # Create indexes
    op.create_index(
        'ix_dashboard_metrics_dashboard_id',
        'dashboard_metrics',
        ['dashboard_id'],
    )
    op.create_index(
        'ix_dashboard_metric_provider',
        'dashboard_metrics',
        ['dashboard_id', 'provider'],
    )


def downgrade() -> None:
    op.drop_table('dashboard_metrics')
