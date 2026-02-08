"""Add used_dashboards JSON column to organizations.

Stores a list of provider dashboard IDs that are marked as
important / frequently used for this organization.

Revision ID: 006
Revises: 005
Create Date: 2026-02-08

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("used_dashboards", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("organizations", "used_dashboards")
