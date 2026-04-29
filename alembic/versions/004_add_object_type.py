"""Add object_type column to objects table.

Revision ID: 004
Revises: 003
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "objects",
        sa.Column(
            "object_type",
            sa.String(50),
            nullable=False,
            server_default="квартира",
            comment="квартира / кладовка / машиноместо / апартаменты",
        ),
    )


def downgrade() -> None:
    op.drop_column("objects", "object_type")
