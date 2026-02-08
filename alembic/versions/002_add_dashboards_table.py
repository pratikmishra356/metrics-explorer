"""Add organization_dashboards table.

Revision ID: 002
Revises: 001
Create Date: 2026-02-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create organization_dashboards table
    op.create_table(
        'organization_dashboards',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('organization_id', sa.String(36), nullable=False),
        sa.Column('dashboard_id', sa.String(255), nullable=False),
        sa.Column('title', sa.String(512), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('provider_type', sa.String(50), nullable=False),
        sa.Column('provider_source', sa.String(255), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )
    
    # Create indexes and constraints
    op.create_index(
        'ix_organization_dashboards_organization_id',
        'organization_dashboards',
        ['organization_id']
    )
    op.create_index(
        'ix_org_dashboard_active',
        'organization_dashboards',
        ['organization_id', 'is_active']
    )
    op.create_unique_constraint(
        'uq_org_dashboard_provider',
        'organization_dashboards',
        ['organization_id', 'dashboard_id', 'provider_type']
    )


def downgrade() -> None:
    op.drop_table('organization_dashboards')
