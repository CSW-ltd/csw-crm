"""Korxona geofence (circle/polygon) va GPS tasdig'i; xodim bildirishnomalari

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-11 15:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("customers") as b:
        b.add_column(sa.Column("geofence", sa.Text(), nullable=True))
        b.add_column(sa.Column("location_confirmed_by_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("location_confirmed_at", sa.DateTime(), nullable=True))
        b.create_foreign_key("fk_customers_location_confirmed_by", "users", ["location_confirmed_by_id"], ["id"])
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("params", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("ref_type", sa.String(20), nullable=True),
        sa.Column("ref_id", sa.Integer(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])


def downgrade() -> None:
    op.drop_table("notifications")
    with op.batch_alter_table("customers") as b:
        b.drop_constraint("fk_customers_location_confirmed_by", type_="foreignkey")
        b.drop_column("location_confirmed_at")
        b.drop_column("location_confirmed_by_id")
        b.drop_column("geofence")
