"""Source improvements: status, cache fields, jk_synonyms table.

Revision ID: 002
Revises: 001
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Add new columns to sources table ──────────────────────────────────
    op.add_column(
        "sources",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="unknown",
            comment="Last pre-flight result: ok/warning/error/unknown",
        ),
    )
    op.add_column(
        "sources",
        sa.Column(
            "cache_last_path",
            sa.Text(),
            nullable=True,
            comment="Filesystem path to latest cached feed file",
        ),
    )
    op.add_column(
        "sources",
        sa.Column(
            "cache_last_success_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the cache was last successfully updated",
        ),
    )

    # ── 2. Create jk_synonyms table ──────────────────────────────────────────
    op.create_table(
        "jk_synonyms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "raw_name",
            sa.String(512),
            nullable=False,
            comment="Raw name as it appears in the feed (stored lowercase)",
        ),
        sa.Column(
            "normalized_name",
            sa.String(512),
            nullable=False,
            comment="Canonical name to use instead",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_name", name="uq_jk_synonyms_raw_name"),
    )
    op.create_index("ix_jk_synonyms_raw_name", "jk_synonyms", ["raw_name"])


def downgrade() -> None:
    op.drop_index("ix_jk_synonyms_raw_name", table_name="jk_synonyms")
    op.drop_table("jk_synonyms")
    op.drop_column("sources", "cache_last_success_at")
    op.drop_column("sources", "cache_last_path")
    op.drop_column("sources", "status")
