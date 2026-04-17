"""Initial schema — all tables.

Revision ID: 001_initial
Create Date: 2026-04-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Sources
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("developer_name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("format", sa.String(50), nullable=True),
        sa.Column("mapping_config", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("phone_override", sa.String(20), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_object_count", sa.Integer(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # Objects
    op.create_table(
        "objects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("source_object_id", sa.String(255), nullable=False),
        sa.Column("developer_name", sa.String(255), nullable=False),
        sa.Column("jk_name", sa.String(255), nullable=False),
        sa.Column("jk_id_cian", sa.Integer(), nullable=True),
        sa.Column("house_name", sa.String(255), nullable=True),
        sa.Column("section_number", sa.String(50), nullable=True),
        sa.Column("flat_number", sa.String(50), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("floors_total", sa.Integer(), nullable=True),
        sa.Column("rooms", sa.Integer(), nullable=False),
        sa.Column("total_area", sa.Numeric(10, 1), nullable=False),
        sa.Column("living_area", sa.Numeric(10, 1), nullable=True),
        sa.Column("kitchen_area", sa.Numeric(10, 1), nullable=True),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("price_per_sqm", sa.Integer(), nullable=True),
        sa.Column("sale_type", sa.String(50), nullable=True),
        sa.Column("decoration", sa.String(50), nullable=True),
        sa.Column("is_euro", sa.Boolean(), nullable=True),
        sa.Column("is_apartments", sa.Boolean(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("photos", ARRAY(sa.Text()), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("hash", sa.String(64), nullable=True),
        sa.Column("missing_count", sa.Integer(), default=0),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_objects_external_id", "objects", ["external_id"], unique=True)
    op.create_index("ix_objects_source_id", "objects", ["source_id"])
    op.create_index("ix_objects_composite_key", "objects",
                    ["source_id", "jk_name", "house_name", "flat_number"])
    op.create_index("ix_objects_source_floor_area", "objects",
                    ["source_id", "jk_name", "floor", "total_area", "rooms"])
    op.create_index("ix_objects_status", "objects", ["status"])

    # Object history
    op.create_table(
        "object_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("object_id", sa.Integer(), sa.ForeignKey("objects.id"), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_object_history_object_id", "object_history", ["object_id"])

    # Sync logs
    op.create_table(
        "sync_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("objects_total", sa.Integer(), default=0),
        sa.Column("objects_new", sa.Integer(), default=0),
        sa.Column("objects_updated", sa.Integer(), default=0),
        sa.Column("objects_removed", sa.Integer(), default=0),
        sa.Column("errors_count", sa.Integer(), default=0),
        sa.Column("status", sa.String(20), default="running"),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Alerts
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("telegram_response", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Mappings
    op.create_table(
        "mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("source_field", sa.String(255), nullable=False),
        sa.Column("target_field", sa.String(100), nullable=False),
        sa.Column("transform_rule", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mappings_source_id", "mappings", ["source_id"])

    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), default="observer"),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )


def downgrade():
    op.drop_table("users")
    op.drop_table("mappings")
    op.drop_table("alerts")
    op.drop_table("sync_logs")
    op.drop_table("object_history")
    op.drop_table("objects")
    op.drop_table("sources")
