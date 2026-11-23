"""GPS token chidamliligi: zaxira token (boshqa akkauntdan ham bo'lishi mumkin), faol slot, har soatlik tekshiruv, ogohlantirish holati

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-24 12:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0028'
down_revision = '0027'
branch_labels = None
depends_on = None

COLS = ("alert_state", "token_checked_at", "active_slot", "backup_token_set_at", "backup_token_user", "backup_token_status",
        "backup_token_enc", "backup_account")


def upgrade() -> None:
    with op.batch_alter_table("gps_sources") as b:
        b.add_column(sa.Column("backup_account", sa.String(100), nullable=True))
        b.add_column(sa.Column("backup_token_enc", sa.Text(), nullable=True))
        b.add_column(sa.Column("backup_token_status", sa.String(10), nullable=False, server_default="none"))
        b.add_column(sa.Column("backup_token_user", sa.String(100), nullable=True))
        b.add_column(sa.Column("backup_token_set_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("active_slot", sa.String(10), nullable=False, server_default="main"))
        b.add_column(sa.Column("token_checked_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("alert_state", sa.String(10), nullable=False, server_default="ok"))


def downgrade() -> None:
    with op.batch_alter_table("gps_sources") as b:
        for c in COLS:
            b.drop_column(c)
