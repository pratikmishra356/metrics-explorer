"""Refactor dashboard_metrics to widget-level storage.

Drop and recreate the dashboard_metrics table:
- Replace metric_name with generic `name` and `description` columns
- One row per widget instead of one row per query
- Widget-specific details stored in the `details` JSON column

Revision ID: 004
Revises: 003
Create Date: 2026-02-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing table (data can be re-extracted from providers)
    op.drop_table('dashboard_metrics')

    # Recreate with new schema
    op.create_table(
        'dashboard_metrics',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('dashboard_id', sa.String(36), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('widget_id', sa.String(255), nullable=True),
        sa.Column('name', sa.String(512), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['dashboard_id'],
            ['organization_dashboards.id'],
            ondelete='CASCADE',
        ),
    )

    # Recreate indexes
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
    # Drop the new table
    op.drop_table('dashboard_metrics')

    # Recreate original schema
    op.create_table(
        'dashboard_metrics',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('dashboard_id', sa.String(36), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('widget_id', sa.String(255), nullable=True),
        sa.Column('metric_name', sa.String(512), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['dashboard_id'],
            ['organization_dashboards.id'],
            ondelete='CASCADE',
        ),
    )
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
