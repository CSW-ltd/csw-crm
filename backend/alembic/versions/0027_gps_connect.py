"""GPS dispatch PR-B: SmartGPS/Wialon ulanishi (shifrlangan faqat o'qish tokeni), geozona guruhlari, sinxronlash jurnali

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-24 03:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0027'
down_revision = '0026'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("gps_sources") as b:
        b.add_column(sa.Column("token_enc", sa.Text(), nullable=True))
        b.add_column(sa.Column("token_status", sa.String(10), nullable=False, server_default="none"))
        b.add_column(sa.Column("token_user", sa.String(100), nullable=True))
        b.add_column(sa.Column("token_set_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("unit_group", sa.String(150), nullable=True))
        b.add_column(sa.Column("settings", sa.Text(), nullable=True))
        b.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
        b.add_column(sa.Column("sync_requested_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("last_sync_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("last_error", sa.String(500), nullable=True))
    op.create_table(
        "geozone_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("gps_sources.id"), nullable=False),
        sa.Column("ext_resource_id", sa.Integer(), nullable=False),
        sa.Column("ext_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("zone_ids", sa.Text(), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_id", "ext_resource_id", "ext_id", name="uq_geozone_groups_ext"),
    )
    op.create_index("ix_geozone_groups_source_id", "geozone_groups", ["source_id"])
    op.create_table(
        "gps_sync_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("gps_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stats", sa.Text(), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
    )
    op.create_index("ix_gps_sync_log_source_id", "gps_sync_log", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_gps_sync_log_source_id", table_name="gps_sync_log")
    op.drop_table("gps_sync_log")
    op.drop_index("ix_geozone_groups_source_id", table_name="geozone_groups")
    op.drop_table("geozone_groups")
    with op.batch_alter_table("gps_sources") as b:
        for c in ("last_error", "last_sync_at", "sync_requested_at", "is_active", "settings", "unit_group", "token_set_at",
                  "token_user", "token_status", "token_enc"):
            b.drop_column(c)
