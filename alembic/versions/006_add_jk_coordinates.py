"""Add jk_coordinates table for manual lat/lon overrides per JK name.

Revision ID: 006
Revises: 005
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jk_coordinates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "jk_name", sa.String(512), nullable=False,
            comment="Canonical JK name (case-insensitive lookup key)",
        ),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=True,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jk_name"),
    )
    op.create_index(
        "ix_jk_coordinates_jk_name",
        "jk_coordinates", ["jk_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_jk_coordinates_jk_name", table_name="jk_coordinates")
    op.drop_table("jk_coordinates")
