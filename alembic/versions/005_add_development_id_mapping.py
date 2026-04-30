"""Add development_id_mappings table.

Revision ID: 005
Revises: 004
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "development_id_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("development_id", sa.String(50), nullable=False,
                  comment="NewDevelopmentId from Avito feed"),
        sa.Column("jk_name", sa.String(255), nullable=False,
                  comment="Resolved JK name"),
        sa.Column("notes", sa.Text(), nullable=True,
                  comment="Admin notes"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("development_id"),
    )
    op.create_index("ix_development_id_mappings_dev_id",
                    "development_id_mappings", ["development_id"])


def downgrade() -> None:
    op.drop_index("ix_development_id_mappings_dev_id",
                  table_name="development_id_mappings")
    op.drop_table("development_id_mappings")
