"""Add address column to objects table.

Revision ID: 003
Revises: 002
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "objects",
        sa.Column("address", sa.Text(), nullable=True, comment="Street address from feed"),
    )


def downgrade() -> None:
    op.drop_column("objects", "address")
