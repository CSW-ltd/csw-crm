"""GPS dispatch PR-A: tashqi GPS akkauntlari, mahallalar, geozonalar, mahalla ↔ geozona, mashina ↔ GPS obyekti

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-20 22:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT


revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gps_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("system", sa.String(20), nullable=False),
        sa.Column("server", sa.String(120), nullable=False),
        sa.Column("account", sa.String(100), nullable=False),
        sa.Column("token_env", sa.String(64), nullable=True),
        sa.Column("district_id", sa.Integer(), sa.ForeignKey("districts.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("server", "account", name="uq_gps_sources_server_account"),
    )
    op.create_table(
        "mahallas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("district_id", sa.Integer(), sa.ForeignKey("districts.id"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("name_key", sa.String(150), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("gps_sources.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("district_id", "name_key", name="uq_mahallas_district_key"),
    )
    op.create_index("ix_mahallas_district_id", "mahallas", ["district_id"])
    op.create_table(
        "geozones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("gps_sources.id"), nullable=False),
        sa.Column("ext_resource_id", sa.Integer(), nullable=False),
        sa.Column("ext_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("width_m", sa.Float(), nullable=True),
        sa.Column("radius_m", sa.Float(), nullable=True),
        sa.Column("coords", sa.Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("min_lat", sa.Float(), nullable=False),
        sa.Column("max_lat", sa.Float(), nullable=False),
        sa.Column("min_lng", sa.Float(), nullable=False),
        sa.Column("max_lng", sa.Float(), nullable=False),
        sa.Column("color", sa.String(9), nullable=True),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_id", "ext_resource_id", "ext_id", name="uq_geozones_ext"),
    )
    op.create_index("ix_geozones_source_id", "geozones", ["source_id"])
    op.create_table(
        "mahalla_geozones",
        sa.Column("mahalla_id", sa.Integer(), sa.ForeignKey("mahallas.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("geozone_id", sa.Integer(), sa.ForeignKey("geozones.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(10), primary_key=True),
    )
    op.create_index("ix_mahalla_geozones_geozone_id", "mahalla_geozones", ["geozone_id"])
    op.create_table(
        "vehicle_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("gps_sources.id"), nullable=False),
        sa.Column("ext_unit_id", sa.Integer(), nullable=False),
        sa.Column("ext_name", sa.String(150), nullable=True),
        sa.Column("has_gps", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("source_id", "ext_unit_id", name="uq_vehicle_links_unit"),
    )
    op.create_index("ix_vehicle_links_vehicle_id", "vehicle_links", ["vehicle_id"])


def downgrade() -> None:
    op.drop_table("vehicle_links")
    op.drop_table("mahalla_geozones")
    op.drop_table("geozones")
    op.drop_table("mahallas")
    op.drop_table("gps_sources")
